"""Key-encryption keys held by HashiCorp Vault's Transit engine.

With :class:`VaultTransitKeyWrapper`, custody never holds a key-encryption key.
Vault wraps each data key and unwraps it on request; rotation and re-wrapping
happen inside Vault, so re-wrapping never exposes a data key to this process.
Each data class has its own Transit key (``<prefix>-<class>``), created with
``derived: true`` so every wrap is bound to its subject and class through Vault's
key-derivation context -- the same binding the local wrapper puts in AES-GCM's
associated data.

Configure with ``FSSAI_VAULT_ADDR``, ``FSSAI_VAULT_TOKEN_FILE`` (or
``FSSAI_VAULT_TOKEN``), optional ``FSSAI_VAULT_CA_FILE`` for HTTPS, and
``FSSAI_VAULT_TRANSIT_MOUNT`` (default ``transit``). The token needs only
``create``/``update`` on the transit ``encrypt``, ``decrypt``, ``rewrap`` and
``keys/<prefix>-*/rotate`` paths and ``read`` on ``keys/<prefix>-*``; with
``FSSAI_VAULT_RETIRE_ON_ROTATE=true`` also ``update`` on ``keys/<prefix>-*/config``.

What this changes: someone who copies the custody database *and* this host's
memory still cannot unwrap data keys without Vault answering. What it does not:
data keys are still unwrapped into this process to encrypt fields, and a Vault in
development mode is not an HSM. Use Vault with an HSM seal, or a cloud KMS, for
hardware-backed keys.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import ssl
import urllib.error
import urllib.request

from .key_custody import CustodyCode, CustodyDenied, WrappedKey


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _context(subject: str, data_class: str) -> str:
    return _b64(json.dumps({"wrap": True, "subject": subject, "class": data_class},
                           sort_keys=True).encode("utf-8"))


class VaultTransitKeyWrapper:
    """Wrap and unwrap data keys through Vault Transit; KEKs stay in Vault."""

    name = "vault-transit"

    def __init__(self, addr: str, token: str, *, mount: str = "transit",
                 key_prefix: str = "fssaira", ca_file: str | None = None,
                 timeout: float = 10.0, retire_on_rotate: bool = False) -> None:
        if not token:
            raise ValueError("a Vault token is required")
        self.addr = addr.rstrip("/")
        self._token = token
        self.mount = mount.strip("/")
        self.key_prefix = key_prefix
        self.timeout = timeout
        self._context = ssl.create_default_context(cafile=ca_file) if ca_file else None
        self._ready: set[str] = set()
        #: After custody has re-wrapped every key, refuse older versions for
        #: decryption. A wrapped key leaked before the rotation then no longer
        #: opens -- and neither does a custody backup taken before it.
        self.retire_on_rotate = retire_on_rotate

    @classmethod
    def from_env(cls) -> VaultTransitKeyWrapper | None:
        addr = os.getenv("FSSAI_VAULT_ADDR")
        if not addr:
            return None
        token = os.getenv("FSSAI_VAULT_TOKEN", "")
        token_file = os.getenv("FSSAI_VAULT_TOKEN_FILE")
        if token_file:
            with open(token_file, encoding="utf-8") as handle:
                token = handle.read().strip()
        return cls(addr, token, mount=os.getenv("FSSAI_VAULT_TRANSIT_MOUNT", "transit"),
                   key_prefix=os.getenv("FSSAI_VAULT_KEY_PREFIX", "fssaira"),
                   ca_file=os.getenv("FSSAI_VAULT_CA_FILE"),
                   retire_on_rotate=os.getenv("FSSAI_VAULT_RETIRE_ON_ROTATE", "").lower()
                   == "true")

    # -- HTTP --------------------------------------------------------------
    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        request = urllib.request.Request(
            f"{self.addr}/v1/{self.mount}/{path}", method=method,
            data=None if body is None else json.dumps(body).encode("utf-8"),
            headers={"X-Vault-Token": self._token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout,
                                        context=self._context) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200]
            if exc.code == 404:
                raise LookupError(path) from exc
            raise CustodyDenied(CustodyCode.KEY_UNWRAP_FAILED,
                                f"key service refused {path.split('/')[0]}: {exc.code} {detail}"
                                ) from exc
        return json.loads(raw) if raw else {}

    def key_name(self, data_class: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_-]", "-", data_class)[:40]
        digest = hashlib.sha256(data_class.encode("utf-8")).hexdigest()[:8]
        return f"{self.key_prefix}-{safe}-{digest}"

    def _ensure(self, data_class: str) -> str:
        name = self.key_name(data_class)
        if name not in self._ready:
            try:
                self._call("GET", f"keys/{name}")
            except LookupError:
                self._call("POST", f"keys/{name}", {"type": "aes256-gcm96", "derived": True})
            self._ready.add(name)
        return name

    @staticmethod
    def _version(ciphertext: str) -> int:
        match = re.match(r"^vault:v(\d+):", ciphertext)
        if not match:
            raise CustodyDenied(CustodyCode.KEY_UNWRAP_FAILED, "not a Vault Transit ciphertext")
        return int(match.group(1))

    # -- wrapper interface ------------------------------------------------
    def initial_generation(self, data_class: str) -> int:
        name = self._ensure(data_class)
        return int(self._call("GET", f"keys/{name}")["data"]["latest_version"])

    def wrap(self, subject: str, data_class: str, generation: int,
             dek: bytes) -> tuple[bytes, bytes, int]:
        name = self._ensure(data_class)
        ciphertext = self._call("POST", f"encrypt/{name}", {
            "plaintext": _b64(dek), "context": _context(subject, data_class),
        })["data"]["ciphertext"]
        return b"", ciphertext.encode("ascii"), self._version(ciphertext)

    def unwrap(self, subject: str, data_class: str, wrapped: WrappedKey) -> bytes:
        name = self._ensure(data_class)
        plaintext = self._call("POST", f"decrypt/{name}", {
            "ciphertext": wrapped.body.decode("ascii"), "context": _context(subject, data_class),
        })["data"]["plaintext"]
        return base64.b64decode(plaintext)

    def rotate(self, data_class: str, current: int) -> int:
        name = self._ensure(data_class)
        self._call("POST", f"keys/{name}/rotate", {})
        return int(self._call("GET", f"keys/{name}")["data"]["latest_version"])

    def rewrap(self, subject: str, data_class: str, wrapped: WrappedKey,
               generation: int) -> tuple[bytes, bytes, int]:
        name = self._ensure(data_class)
        ciphertext = self._call("POST", f"rewrap/{name}", {
            "ciphertext": wrapped.body.decode("ascii"), "context": _context(subject, data_class),
        })["data"]["ciphertext"]
        return b"", ciphertext.encode("ascii"), self._version(ciphertext)

    def retire(self, data_class: str, generation: int) -> bool:
        """Refuse decryption with versions older than ``generation``, if configured."""
        if not self.retire_on_rotate:
            return False
        name = self._ensure(data_class)
        self._call("POST", f"keys/{name}/config", {"min_decryption_version": int(generation)})
        return True


__all__ = ["VaultTransitKeyWrapper"]
