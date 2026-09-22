"""The governed data plane at rest: encrypted records, snapshots, and derived indexes.

:class:`EncryptedRecordSource` implements the record-source protocol the context
gate reads through (``fetch(subject, fields)``), so the gate is unchanged: it still
reads only after every check passes. The difference is what sits underneath. Each
field is a :class:`trustkernel.kernel.key_custody.Ciphertext` bound to its subject, field,
class, and version, and only a custody credential with ``decrypt`` turns it back
into text. The gate holds that credential; nothing in the intelligence plane does.

Snapshots and backups copy ciphertext, never plaintext, which is what lets
destroying a subject's data key reach them. :class:`GovernedVectorIndex` applies
the same rule to embeddings, which are derived personal data and are routinely
the copy an erasure procedure forgets.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass, field

from .disclosure_sources import RecordNotFound
from .key_custody import Ciphertext, CustodyDenied, KeyCustody, KeyDestroyed


@dataclass(frozen=True)
class RecordSnapshot:
    """A backup of the store as it was: ciphertext only."""

    snapshot_id: str
    taken_at: float
    rows: dict = field(default_factory=dict)

    def contains_plaintext(self, needle: str) -> bool:
        return needle.encode("utf-8") in _serialise(self.rows)


def _serialise(rows: dict) -> bytes:
    return json.dumps({f"{s}|{f}": {"nonce": c.nonce.hex(), "body": c.body.hex(),
                                    "class": c.data_class, "version": c.version}
                       for (s, f), c in sorted(rows.items())}, sort_keys=True).encode("utf-8")


class EncryptedRecordSource:
    """Records encrypted field by field under per-subject keys."""

    def __init__(self, field_classes: dict[str, str], custody: KeyCustody, *,
                 writer_credential: str, reader_credential: str) -> None:
        self._classes = dict(field_classes)
        self._custody = custody
        self._writer = writer_credential
        self._reader = reader_credential
        self._rows: dict[tuple[str, str], Ciphertext] = {}
        self._versions: dict[str, int] = {}
        self._snapshots = 0
        self._lock = threading.RLock()

    def load(self, subject: str, fields: dict[str, str]) -> None:
        with self._lock:
            unknown = set(fields) - set(self._classes)
            if unknown:
                raise KeyError(f"fields have no declared class: {sorted(unknown)}")
            version = self._versions.get(subject, 0) + 1
            staged = {
                (subject, name): self._custody.encrypt(
                    self._writer, subject=subject, field=name, data_class=self._classes[name],
                    plaintext=str(value), version=version)
                for name, value in fields.items()
            }
            self._rows.update(staged)
            self._versions[subject] = version

    def fetch(self, subject: str, fields: Iterable[str]) -> dict[str, str]:
        names = list(fields)
        with self._lock:
            if not any(key[0] == subject for key in self._rows):
                raise RecordNotFound(subject)
            if self._custody.is_destroyed(subject):
                raise RecordNotFound(f"{subject} (erased)")
            out = {}
            for name in names:
                ciphertext = self._rows.get((subject, name))
                if ciphertext is None:
                    out[name] = ""
                    continue
                try:
                    out[name] = self._custody.decrypt(self._reader, ciphertext, subject=subject,
                                                      field=name)
                except KeyDestroyed as exc:
                    raise RecordNotFound(f"{subject} (erased)") from exc
            return out

    def subjects(self) -> tuple[str, ...]:
        return tuple(sorted({subject for subject, _ in self._rows}))

    # -- backups ---------------------------------------------------------------
    def snapshot(self) -> RecordSnapshot:
        with self._lock:
            self._snapshots += 1
            return RecordSnapshot(f"snapshot-{self._snapshots}", time.time(), dict(self._rows))

    def restore_snapshot(self, snapshot: RecordSnapshot) -> None:
        with self._lock:
            self._rows = dict(snapshot.rows)
            # Preserve the live high-water mark and recover it on a fresh instance.
            for (subject, _name), ciphertext in self._rows.items():
                self._versions[subject] = max(self._versions.get(subject, 0), ciphertext.version)

    def raw_bytes(self) -> bytes:
        with self._lock:
            return _serialise(self._rows)

    # -- attack hooks: model an attacker with write access to the storage medium --
    def _move_ciphertext(self, *, source: str, target: str, field_name: str) -> None:
        with self._lock:
            self._rows[(target, field_name)] = self._rows[(source, field_name)]

    def _row(self, subject: str, field_name: str) -> Ciphertext | None:
        return self._rows.get((subject, field_name))


def hashed_embedding(text: str, dimensions: int = 32) -> list[float]:
    """A deterministic bag-of-words embedding. Enough to exercise the storage rule."""
    vector = [0.0] * dimensions
    for word in text.lower().split():
        digest = hashlib.sha256(word.encode("utf-8")).digest()
        vector[digest[0] % dimensions] += 1.0 if digest[1] % 2 else -1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [round(v / norm, 6) for v in vector]


class GovernedVectorIndex:
    """Embeddings stored encrypted under the subject's key, searchable only by the gate."""

    DATA_CLASS = "derived-embedding"

    def __init__(self, custody: KeyCustody, *, writer_credential: str,
                 reader_credential: str) -> None:
        self._custody = custody
        self._writer = writer_credential
        self._reader = reader_credential
        self._entries: list[tuple[str, str, Ciphertext]] = []

    def add(self, subject: str, entry_id: str, text: str) -> None:
        self._entries.append((subject, entry_id, self._custody.encrypt(
            self._writer, subject=subject, field=f"embedding:{entry_id}",
            data_class=self.DATA_CLASS, plaintext=json.dumps(hashed_embedding(text)))))

    def search(self, query: str, *, subjects: Iterable[str], limit: int = 3) -> list[tuple[str, str, float]]:
        """Nearest entries among ``subjects`` the caller is entitled to; erased entries are skipped."""
        allowed = set(subjects)
        probe = hashed_embedding(query)
        scored = []
        for subject, entry_id, ciphertext in self._entries:
            if subject not in allowed:
                continue
            try:
                vector = json.loads(self._custody.decrypt(
                    self._reader, ciphertext, subject=subject, field=f"embedding:{entry_id}"))
            except CustodyDenied:
                continue
            scored.append((subject, entry_id, sum(a * b for a, b in zip(probe, vector, strict=True))))
        return sorted(scored, key=lambda item: -item[2])[:limit]

    def readable_entries(self, subject: str) -> int:
        count = 0
        for owner, entry_id, ciphertext in self._entries:
            if owner != subject:
                continue
            try:
                self._custody.decrypt(self._reader, ciphertext, subject=owner,
                                      field=f"embedding:{entry_id}")
                count += 1
            except CustodyDenied:
                continue
        return count

    def entries_for(self, subject: str) -> int:
        return sum(1 for owner, _id, _c in self._entries if owner == subject)


__all__ = ["EncryptedRecordSource", "GovernedVectorIndex", "RecordSnapshot", "hashed_embedding"]
