"""Key custody: envelope encryption, per-subject keys, and cryptographic erasure.

The paper says the governed data plane is "encrypted at rest under per-subject
keys" and that "erasure is implemented by destroying a subject's data key". Until
this module existed that sentence described nothing in the code. This is the
mechanism, and it is written so that each part of the sentence is a check.

Envelope
--------
* Every ``(subject, data class)`` pair has its own **data encryption key** (DEK),
  256-bit AES-GCM.
* A DEK is stored only **wrapped** by the **key-encryption key** (KEK) of its data
  class. KEKs never leave custody; wrapped DEKs are what custody backs up.
* Every ciphertext carries **associated data** naming its subject, field, class,
  and record version. A ciphertext copied into another subject's row, or another
  field, fails authentication instead of decrypting under the wrong identity.

Credentials
-----------
Custody holds keys and performs operations; it never returns a key. Each caller
presents a credential that names the operations it may perform (``encrypt``,
``decrypt``, ``erase``, ``rotate``, ``backup``). The context gate holds decrypt;
the ingest path holds encrypt; the erasure officer holds erase. A model runtime is
given no credential at all, and the tests check that nothing it can reach holds
one. In a deployment the process boundary, an HSM, or a cloud KMS enforces what a
credential string enforces here.

Erasure
-------
:meth:`KeyCustody.destroy_subject` deletes every wrapped DEK for a subject and
appends the subject's surrogate identifier to an **erasure journal**. Destroying
the key makes every ciphertext of that subject unreadable wherever the ciphertext
lives: primary store, replica, snapshot, backup, or encrypted vector index.

The classic hole in cryptographic erasure is the key backup: restore last week's
custody backup and the destroyed key comes back. :meth:`KeyCustody.restore`
therefore replays the journal over every restore, and refuses a restore that is
not given the journal. The journal holds surrogate identifiers and timestamps,
never keys, but identifiers and reasons can still be personal data; protect it
and apply a justified retention policy.

What erasure here does not reach, and must not be claimed to reach: plaintext that
already left the governed boundary (an output released to a person, a screen, a
provider log in an external zone). The architecture narrows that set by keeping
restricted classes on local, stateless model endpoints and by tokenizing identity
before inference; :mod:`fssaira.privacy_pipeline` verifies every copy it governs.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

OPERATIONS = frozenset({"encrypt", "decrypt", "erase", "rotate", "backup"})


class CustodyCode:
    CREDENTIAL_UNKNOWN = "CUSTODY_CREDENTIAL_UNKNOWN"
    OPERATION_NOT_PERMITTED = "CUSTODY_OPERATION_NOT_PERMITTED"
    KEY_DESTROYED = "CUSTODY_KEY_DESTROYED"
    KEY_ABSENT = "CUSTODY_KEY_ABSENT"
    CIPHERTEXT_BINDING = "CUSTODY_CIPHERTEXT_BINDING_INVALID"
    RESTORE_WITHOUT_JOURNAL = "CUSTODY_RESTORE_WITHOUT_JOURNAL"
    #: The wrapped key did not open: a different master key, or a tampered key row.
    KEY_UNWRAP_FAILED = "CUSTODY_KEY_UNWRAP_FAILED"


class CustodyDenied(PermissionError):
    """Custody refused an operation; no key was used or disclosed."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class KeyDestroyed(CustodyDenied):
    """The subject key was destroyed in this custody instance."""


def _aesgcm():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError("key custody needs the 'cryptography' package") from exc
    return AESGCM


def _hkdf(material: bytes, info: str) -> bytes:
    return hmac.new(material, info.encode("utf-8"), hashlib.sha256).digest()


@dataclass(frozen=True)
class Ciphertext:
    """One encrypted field value and the identity it is bound to."""

    subject: str
    field: str
    data_class: str
    version: int
    key_generation: int
    nonce: bytes
    body: bytes

    def associated_data(self) -> bytes:
        return _binding(self.subject, self.field, self.data_class, self.version)

    def rebound(self, **changes: Any) -> Ciphertext:
        """A copy claiming another identity. Used by tests that move ciphertext."""
        values = {**self.__dict__, **changes}
        return Ciphertext(**values)


def _binding(subject: str, field_name: str, data_class: str, version: int) -> bytes:
    return json.dumps({"subject": subject, "field": field_name, "class": data_class,
                       "version": version}, sort_keys=True).encode("utf-8")


@dataclass(frozen=True)
class WrappedKey:
    data_class: str
    kek_generation: int
    key_generation: int
    nonce: bytes
    body: bytes


@dataclass(frozen=True)
class ErasureEntry:
    seq: int
    subject: str
    erased_at: float
    erased_by: str
    reason: str


@dataclass(frozen=True)
class ErasureCertificate:
    """What custody destroyed. Metadata may be sensitive; no key material is included."""

    subject: str
    classes: tuple[str, ...]
    journal_seq: int
    erased_at: float
    erased_by: str
    reason: str

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()

    def to_dict(self) -> dict:
        return {"subject": self.subject, "classes": list(self.classes),
                "journal_seq": self.journal_seq, "erased_at": self.erased_at,
                "erased_by": self.erased_by, "reason": self.reason}


@dataclass(frozen=True)
class CustodyBackup:
    """Wrapped DEKs as of one moment. KEKs are not in it; they never leave custody."""

    taken_at: float
    wrapped: dict = field(default_factory=dict)
    journal_length: int = 0


@dataclass
class _Principal:
    name: str
    operations: frozenset[str]


class KeyCustody:
    """Holds KEKs, wraps DEKs, performs cryptographic operations for credentialed callers.

    ``master_seed`` makes KEKs reproducible for fixtures. DEKs and nonces are always
    random, so no two runs produce the same ciphertext and no published figure may
    depend on ciphertext bytes.
    """

    def __init__(self, *, master_seed: bytes | None = None, clock=None,
                 evidence: Any = None, evidence_token: str | None = None,
                 store: Any = None) -> None:
        if store is not None and master_seed is None:
            raise ValueError("durable custody needs the master key it was created with "
                             "(see fssaira.custody_store.load_master_key)")
        self._master = master_seed if master_seed is not None else secrets.token_bytes(32)
        self._clock = clock or time.time
        self._lock = threading.RLock()
        self._kek_generation: dict[str, int] = {}
        self._wrapped: dict[tuple[str, str], WrappedKey] = {}
        self._principals: dict[str, _Principal] = {}
        self._journal: list[ErasureEntry] = []
        self._destroyed: set[str] = set()
        self._evidence = evidence
        self._evidence_token = evidence_token
        self.operations_log: list[dict] = []
        #: Optional :class:`fssaira.custody_store.SqlCustodyStore`. When set, keys,
        #: generations and the erasure journal survive a restart.
        self._store = store
        if store is not None:
            state = store.load()
            self._kek_generation = dict(state["generations"])
            self._wrapped = dict(state["wrapped"])
            self._journal = list(state["journal"])
            self._destroyed = set(state["destroyed"])

    # -- credentials ---------------------------------------------------------
    def register_principal(self, name: str, operations: Iterable[str]) -> str:
        """Issue a credential for ``name`` limited to ``operations``. Returns the secret."""
        ops = frozenset(operations)
        unknown = sorted(ops - OPERATIONS)
        if unknown:
            raise ValueError(f"unknown custody operations: {', '.join(unknown)}")
        credential = f"custody-{secrets.token_hex(24)}"
        with self._lock:
            self._principals[self._fingerprint(credential)] = _Principal(name, ops)
        return credential

    @staticmethod
    def _fingerprint(credential: str) -> str:
        return hashlib.sha256(str(credential).encode("utf-8")).hexdigest()

    def _authorize(self, credential: str | None, operation: str) -> _Principal:
        principal = self._principals.get(self._fingerprint(credential or ""))
        if principal is None:
            raise CustodyDenied(CustodyCode.CREDENTIAL_UNKNOWN,
                                "custody does not recognise this credential")
        if operation not in principal.operations:
            raise CustodyDenied(CustodyCode.OPERATION_NOT_PERMITTED,
                                f"{principal.name} may not {operation}")
        return principal

    def holds_credential_material(self, text: str) -> bool:
        """True when ``text`` contains any issued credential. Used by leak scanners."""
        return any(self._fingerprint(token) in self._principals
                   for token in _credential_candidates(text))

    # -- keys ----------------------------------------------------------------
    def _kek(self, data_class: str, generation: int) -> bytes:
        return _hkdf(self._master, f"kek:{data_class}:{generation}")

    def _current_kek_generation(self, data_class: str) -> int:
        return self._kek_generation.setdefault(data_class, 1)

    def _unwrap(self, subject: str, data_class: str) -> tuple[bytes, int]:
        if subject in self._destroyed:
            raise KeyDestroyed(CustodyCode.KEY_DESTROYED,
                               f"the data key for {subject} was destroyed")
        wrapped = self._wrapped.get((subject, data_class))
        if wrapped is None:
            raise CustodyDenied(CustodyCode.KEY_ABSENT,
                                f"no data key for {subject} in class {data_class}")
        try:
            dek = _aesgcm()(self._kek(data_class, wrapped.kek_generation)).decrypt(
                wrapped.nonce, wrapped.body, _wrap_binding(subject, data_class))
        except Exception as exc:  # cryptography.exceptions.InvalidTag
            raise CustodyDenied(CustodyCode.KEY_UNWRAP_FAILED,
                                "the wrapped data key did not open under this master key") from exc
        return dek, wrapped.key_generation

    def _dek(self, subject: str, data_class: str) -> tuple[bytes, int]:
        with self._lock:
            if (subject, data_class) not in self._wrapped and subject not in self._destroyed:
                dek = secrets.token_bytes(32)
                generation = self._current_kek_generation(data_class)
                nonce = secrets.token_bytes(12)
                body = _aesgcm()(self._kek(data_class, generation)).encrypt(
                    nonce, dek, _wrap_binding(subject, data_class))
                wrapped = WrappedKey(data_class, generation, 1, nonce, body)
                if self._store is not None:
                    self._store.save_new_key(subject, wrapped)
                self._wrapped[(subject, data_class)] = wrapped
            return self._unwrap(subject, data_class)

    # -- operations ----------------------------------------------------------
    def encrypt(self, credential: str, *, subject: str, field: str, data_class: str,
                plaintext: str, version: int = 1) -> Ciphertext:
        self._authorize(credential, "encrypt")
        dek, generation = self._dek(subject, data_class)
        nonce = secrets.token_bytes(12)
        body = _aesgcm()(dek).encrypt(nonce, plaintext.encode("utf-8"),
                                      _binding(subject, field, data_class, version))
        return Ciphertext(subject, field, data_class, version, generation, nonce, body)

    def decrypt(self, credential: str, ciphertext: Ciphertext, *, subject: str,
                field: str) -> str:
        """Decrypt only if ``ciphertext`` is bound to the ``subject`` and ``field`` asked for."""
        self._authorize(credential, "decrypt")
        if ciphertext.subject != subject or ciphertext.field != field:
            raise CustodyDenied(CustodyCode.CIPHERTEXT_BINDING,
                                "ciphertext is bound to a different subject or field")
        with self._lock:
            dek, _generation = self._unwrap(subject, ciphertext.data_class)
            try:
                plain = _aesgcm()(dek).decrypt(
                    ciphertext.nonce, ciphertext.body,
                    _binding(subject, field, ciphertext.data_class, ciphertext.version))
            except Exception as exc:  # cryptography.exceptions.InvalidTag
                raise CustodyDenied(CustodyCode.CIPHERTEXT_BINDING,
                                    "ciphertext failed authentication under its claimed binding") from exc
            return plain.decode("utf-8")

    def destroy_subject(self, credential: str, subject: str, *, erased_by: str,
                        reason: str) -> ErasureCertificate:
        """Destroy every data key for ``subject`` and journal the erasure."""
        self._authorize(credential, "erase")
        with self._lock:
            classes = tuple(sorted(cls for (subj, cls) in self._wrapped if subj == subject))
            entry = ErasureEntry(len(self._journal) + 1, subject, self._clock(), erased_by, reason)
            if self._store is not None:  # durable first: a failed write erases nothing
                self._store.save_erasure(subject, entry)
            for cls in classes:
                del self._wrapped[(subject, cls)]
            self._destroyed.add(subject)
            self._journal.append(entry)
        certificate = ErasureCertificate(subject, classes, entry.seq, entry.erased_at,
                                         erased_by, reason)
        self._log("subject_keys_destroyed", {"subject": subject, "classes": list(classes),
                                             "journal_seq": entry.seq,
                                             "certificate_digest": certificate.digest})
        return certificate

    def is_destroyed(self, subject: str) -> bool:
        return subject in self._destroyed

    def has_key(self, subject: str, data_class: str) -> bool:
        return (subject, data_class) in self._wrapped

    def rotate_kek(self, credential: str, data_class: str) -> int:
        """Re-wrap every DEK of ``data_class`` under a new KEK generation.

        Ciphertexts are untouched: rotation changes what protects the keys, not the
        data, which is why it is cheap enough to do on a schedule.
        """
        self._authorize(credential, "rotate")
        with self._lock:
            new_generation = self._current_kek_generation(data_class) + 1
            updated: dict[tuple[str, str], WrappedKey] = {}
            for (subject, cls), wrapped in list(self._wrapped.items()):
                if cls != data_class:
                    continue
                dek = _aesgcm()(self._kek(cls, wrapped.kek_generation)).decrypt(
                    wrapped.nonce, wrapped.body, _wrap_binding(subject, cls))
                nonce = secrets.token_bytes(12)
                body = _aesgcm()(self._kek(cls, new_generation)).encrypt(
                    nonce, dek, _wrap_binding(subject, cls))
                updated[(subject, cls)] = WrappedKey(cls, new_generation,
                                                     wrapped.key_generation, nonce, body)
            if self._store is not None:  # all rewrapped keys commit together
                self._store.save_rotation(data_class, new_generation, updated)
            self._wrapped.update(updated)
            rewrapped = len(updated)
            self._kek_generation[data_class] = new_generation
        self._log("kek_rotated", {"data_class": data_class, "generation": new_generation,
                                  "rewrapped": rewrapped})
        return rewrapped

    # -- backup and restore --------------------------------------------------
    @property
    def journal(self) -> tuple[ErasureEntry, ...]:
        return tuple(self._journal)

    def backup(self, credential: str) -> CustodyBackup:
        self._authorize(credential, "backup")
        with self._lock:
            return CustodyBackup(self._clock(), dict(self._wrapped), len(self._journal))

    def restore(self, credential: str, backup: CustodyBackup,
                journal: Iterable[ErasureEntry] | None, *, replay_journal: bool = True) -> int:
        """Restore wrapped keys, then re-destroy everything the journal says was erased.

        ``replay_journal=False`` exists only so the ablation can show what restoring a
        key backup without the journal does: it resurrects erased subjects.
        Returns the number of keys the journal re-destroyed.
        """
        self._authorize(credential, "backup")
        if replay_journal and journal is None:
            raise CustodyDenied(CustodyCode.RESTORE_WITHOUT_JOURNAL,
                                "a key backup may be restored only together with the erasure journal")
        entries = tuple(journal or ())
        if replay_journal:
            expected = list(range(1, len(entries) + 1))
            if [entry.seq for entry in entries] != expected or len(entries) < backup.journal_length:
                raise CustodyDenied(CustodyCode.RESTORE_WITHOUT_JOURNAL,
                                    "erasure journal is incomplete or out of sequence")
        with self._lock:
            if replay_journal and (len(entries) < len(self._journal) or
                    any(a != b for a, b in zip(self._journal, entries, strict=False))):
                raise CustodyDenied(CustodyCode.RESTORE_WITHOUT_JOURNAL,
                                    "restore cannot roll back or replace known erasure history")
            self._wrapped = dict(backup.wrapped)
            removed = 0
            if replay_journal:
                erased = {entry.subject for entry in entries}
                for key in [k for k in self._wrapped if k[0] in erased]:
                    del self._wrapped[key]
                    removed += 1
                self._destroyed = set(self._destroyed) | erased
                known = {entry.seq for entry in self._journal}
                self._journal.extend(e for e in entries if e.seq not in known)
            else:
                self._destroyed = {s for s in self._destroyed
                                   if not any(k[0] == s for k in self._wrapped)}
            if self._store is not None:
                self._store.save_restore(self._wrapped, self._destroyed, self._journal)
        self._log("custody_restored", {"keys": len(backup.wrapped), "journal_replayed": replay_journal,
                                       "re_destroyed": removed})
        return removed

    # -- evidence ------------------------------------------------------------
    def _log(self, kind: str, payload: dict) -> None:
        self.operations_log.append({"kind": kind, **payload})
        if self._evidence is not None and self._evidence_token is not None:
            self._evidence.append(kind, payload, token=self._evidence_token)


def _wrap_binding(subject: str, data_class: str) -> bytes:
    return json.dumps({"wrap": True, "subject": subject, "class": data_class},
                      sort_keys=True).encode("utf-8")


def _credential_candidates(text: str) -> list[str]:
    import re

    return re.findall(r"custody-[0-9a-f]{48}", str(text))


def random_master_seed() -> bytes:
    return os.urandom(32)


__all__ = [
    "Ciphertext", "CustodyBackup", "CustodyCode", "CustodyDenied", "ErasureCertificate",
    "ErasureEntry", "KeyCustody", "KeyDestroyed", "OPERATIONS", "WrappedKey",
    "random_master_seed",
]
