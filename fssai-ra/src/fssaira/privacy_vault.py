"""Tokenization reduces exposure of declared identifiers; it does not establish anonymity.

Redaction deletes the thing a model needs to reason about ("the same student
appears in both records"). Pseudonyms that are stable across sessions let any
two contexts be joined back into a profile. This vault does neither.

* A **token** stands for one identifier of one subject **within one session**.
  The same student is the same token throughout a session and a different token
  in the next, so contexts cannot be linked across sessions by their tokens.
* A token is a keyed HMAC, so it is not derivable from the identifier without the
  vault key, and it is checked never to reproduce any four-character run of the
  identifier it replaces (a digit string such as ``1001`` in ``S-1001`` must not
  reappear inside the token by chance).
* The **token map** holds each identifier encrypted under the subject's own data
  key in :class:`fssaira.key_custody.KeyCustody`. Destroying that key makes every
  token mapping unreadable through live custody; independently retained keys and
  runtime memory remain outside that claim.
* **Restoration** needs a custody credential with ``decrypt``. The vault never
  decides who may see identity; :class:`fssaira.privacy_pipeline.PrivacyGate`
  decides that at release, against the recipient's entitlement, and only then
  asks the vault to restore.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
from collections.abc import Iterable
from dataclasses import dataclass

from .key_custody import Ciphertext, CustodyCode, CustodyDenied, KeyCustody, KeyDestroyed

#: Class under which identity values are encrypted in the token map.
IDENTITY_CLASS = "identity-token-map"

TOKEN_PATTERN = re.compile(r"\[\[([A-Z][A-Z_]{0,24})_([0-9A-F]{10})\]\]")

_DETECTORS = (
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")),
    ("PHONE", re.compile(r"\+?\d[\d\s().-]{7,}\d")),
)


class VaultCode:
    TOKEN_UNKNOWN = "VAULT_TOKEN_UNKNOWN"
    TOKEN_IRREVERSIBLE = "VAULT_TOKEN_IRREVERSIBLE"
    RESTORE_NOT_AUTHORIZED = "VAULT_RESTORE_NOT_AUTHORIZED"


class VaultDenied(PermissionError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class TokenEntry:
    session_id: str
    token: str
    subject: str
    kind: str
    ciphertext: Ciphertext


def _shares_run(token: str, identifier: str, run: int = 4) -> bool:
    ident = re.sub(r"[^0-9A-Za-z]", "", identifier).upper()
    body = token.upper()
    return any(ident[i:i + run] in body for i in range(0, max(0, len(ident) - run + 1)))


class TokenVault:
    """Session-scoped keyed tokens, with the reverse map encrypted per subject."""

    def __init__(self, custody: KeyCustody, credential: str, *, key: bytes | None = None) -> None:
        self._custody = custody
        self._credential = credential
        self._key = key if key is not None else secrets.token_bytes(32)
        self._entries: dict[tuple[str, str], TokenEntry] = {}
        self._forward: dict[tuple[str, str, str], str] = {}
        self._lock = threading.RLock()

    # -- tokenize ------------------------------------------------------------
    def token_for(self, *, session_id: str, subject: str, kind: str, value: str) -> str:
        """The session's token for one identifier of one subject."""
        label = re.sub(r"[^A-Z_]", "_", kind.upper())[:24] or "ID"
        if not label[0].isalpha():
            label = "ID" + label[:22]
        encoded = json.dumps([session_id, subject, kind, value], ensure_ascii=False).encode()
        fingerprint = hmac.new(self._key, b"lookup:" + encoded, hashlib.sha256).hexdigest()
        lookup = (session_id, subject, fingerprint)
        with self._lock:
            if self._custody.is_destroyed(subject):
                raise KeyDestroyed(CustodyCode.KEY_DESTROYED, "subject was erased")
            known = self._forward.get(lookup)
            if known is not None:
                return known
            counter = 0
            for counter in range(1024):
                mac = hmac.new(self._key, b"token:" + encoded + str(counter).encode(),
                               hashlib.sha256).hexdigest().upper()[:10]
                token = f"[[{label}_{mac}]]"
                if not _shares_run(mac, value) and not _shares_run(mac, subject) \
                        and (session_id, token) not in self._entries:
                    break
            else:
                raise VaultDenied(VaultCode.TOKEN_UNKNOWN, "token allocation exhausted")
            ciphertext = self._custody.encrypt(self._credential, subject=subject,
                                               field=f"token:{token}", data_class=IDENTITY_CLASS,
                                               plaintext=value)
            self._entries[(session_id, token)] = TokenEntry(session_id, token, subject, kind,
                                                            ciphertext)
            self._forward[lookup] = token
            return token

    def tokenize_text(self, text: str, *, session_id: str,
                      identifiers: Iterable[tuple[str, str, str]]) -> tuple[str, int]:
        """Replace every known identifier ``(subject, kind, value)`` and detected contact detail.

        Longest values are replaced first so that a name containing another name is
        tokenized whole. Matching is case-insensitive. Returns the text and the number
        of replacements made.
        """
        replacements = 0
        items = sorted({(s, k, v) for s, k, v in identifiers if v and v.strip()},
                       key=lambda item: (-len(item[2]), item))
        if not items:
            return text, 0
        by_value = {}
        for subject, kind, value in items:
            by_value.setdefault(value.casefold(), (subject, kind, value))
        pattern = re.compile("|".join(re.escape(v) for _, _, v in items), re.IGNORECASE)

        def replace(match):
            nonlocal replacements
            item = by_value.get(match.group(0).casefold())
            if item is None:
                # Unicode case-insensitive matching can be broader than casefold.
                item = next(item for item in items
                            if re.fullmatch(re.escape(item[2]), match.group(0), re.IGNORECASE))
            subject, kind, value = item
            replacements += 1
            return self.token_for(session_id=session_id, subject=subject, kind=kind, value=value)

        # Do not match a later identifier against token text created earlier, or
        # reinterpret an existing token's label as someone's identifier.
        parts, offset = [], 0
        for token in TOKEN_PATTERN.finditer(text):
            parts.append(pattern.sub(replace, text[offset:token.start()]))
            parts.append(token.group(0))
            offset = token.end()
        parts.append(pattern.sub(replace, text[offset:]))
        return "".join(parts), replacements

    def forget_subject(self, subject: str) -> None:
        """Remove live indexes; this does not promise Python heap zeroization."""
        with self._lock:
            self._forward = {k: v for k, v in self._forward.items() if k[1] != subject}
            self._entries = {k: v for k, v in self._entries.items() if v.subject != subject}

    @staticmethod
    def detect_contact_details(text: str) -> list[tuple[str, str]]:
        """Contact details that no declared field named. Reported, never trusted as complete."""
        found = []
        for kind, pattern in _DETECTORS:
            found.extend((kind, match.group(0)) for match in pattern.finditer(text)
                         if not TOKEN_PATTERN.fullmatch(match.group(0)))
        return found

    # -- restore -------------------------------------------------------------
    def entry(self, session_id: str, token: str) -> TokenEntry | None:
        return self._entries.get((session_id, token))

    def restore(self, credential: str, *, session_id: str, token: str) -> str:
        entry = self._entries.get((session_id, token))
        if entry is None:
            raise VaultDenied(VaultCode.TOKEN_UNKNOWN,
                              "no such token in this session; tokens do not travel between sessions")
        try:
            return self._custody.decrypt(credential, entry.ciphertext, subject=entry.subject,
                                         field=f"token:{token}")
        except CustodyDenied as exc:
            code = VaultCode.TOKEN_IRREVERSIBLE if exc.code.endswith("KEY_DESTROYED") \
                else VaultCode.RESTORE_NOT_AUTHORIZED
            raise VaultDenied(code, exc.detail) from exc

    def restore_text(self, credential: str, *, session_id: str, text: str,
                     subjects: Iterable[str]) -> tuple[str, int]:
        """Restore tokens in ``text`` that belong to ``subjects`` and to this session only."""
        allowed = set(subjects)
        restored = 0

        def replace(match: re.Match) -> str:
            nonlocal restored
            entry = self._entries.get((session_id, match.group(0)))
            if entry is None or entry.subject not in allowed:
                return match.group(0)
            restored += 1
            return self.restore(credential, session_id=session_id, token=match.group(0))

        return TOKEN_PATTERN.sub(replace, text), restored

    # -- inspection for erasure verification ------------------------------------
    def entries_for(self, subject: str) -> list[TokenEntry]:
        return [entry for entry in self._entries.values() if entry.subject == subject]

    def __len__(self) -> int:
        return len(self._entries)


__all__ = ["IDENTITY_CLASS", "TOKEN_PATTERN", "TokenEntry", "TokenVault", "VaultCode",
           "VaultDenied"]
