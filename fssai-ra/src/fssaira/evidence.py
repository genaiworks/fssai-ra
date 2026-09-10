"""Append-only, hash-chained, tamper-evident evidence ledger.

This is the durable-evidence property of the control contract. Every
consequential step in the pipeline writes a record here. Records are linked
into a hash chain (each record's hash covers the previous hash), so any later
edit or deletion of a past record is *detectable* by :meth:`EvidenceLedger.verify`.

Two design choices matter for fail-secure behaviour:

* **Separate write path.** Appends require an ``append_token``. Agents never
  receive this token, so a compromised agent cannot write, rewrite, or delete
  its own record. In production the token is a credential held only by the
  execution/evidence service; here it is a simple opaque string so the property
  is demonstrable and testable.
* **Tamper-evidence, not tamper-proofing.** The chain makes silent edits
  detectable. It does not make a sufficiently privileged insider unable to try;
  that residual risk is handled by separation of duties and independent
  monitoring (see ``docs/SECURITY.md``).
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Iterator

GENESIS_HASH = "0" * 64


def _digest(seq: int, ts: float, kind: str, payload: dict, prev_hash: str) -> str:
    body = json.dumps(
        {"seq": seq, "ts": ts, "kind": kind, "payload": payload, "prev": prev_hash},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceRecord:
    seq: int
    ts: float
    kind: str
    payload: dict
    prev_hash: str
    hash: str


class EvidenceError(RuntimeError):
    """Raised when the ledger detects a write-authority or integrity violation."""


class EvidenceLedger:
    """A minimal append-only, hash-chained ledger with a guarded write path."""

    def __init__(self, append_token: str) -> None:
        if not append_token:
            raise ValueError("append_token must be a non-empty secret")
        self._append_token = append_token
        self._records: list[EvidenceRecord] = []
        self._lock = threading.Lock()

    def append(self, kind: str, payload: dict, *, token: str) -> EvidenceRecord:
        """Append a record. Requires the append token (separate write path)."""
        if token != self._append_token:
            raise EvidenceError("no evidence write authority")
        with self._lock:
            seq = len(self._records)
            ts = time.time()
            prev = self._records[-1].hash if self._records else GENESIS_HASH
            h = _digest(seq, ts, kind, payload, prev)
            rec = EvidenceRecord(seq, ts, kind, payload, prev, h)
            self._records.append(rec)
            return rec

    def verify(self) -> bool:
        """Recompute the chain; return False if any record was altered/removed."""
        prev = GENESIS_HASH
        for i, rec in enumerate(self._records):
            if rec.seq != i or rec.prev_hash != prev:
                return False
            if _digest(rec.seq, rec.ts, rec.kind, rec.payload, rec.prev_hash) != rec.hash:
                return False
            prev = rec.hash
        return True

    def find(self, kind: str | None = None, **match: Any) -> list[EvidenceRecord]:
        out = []
        for rec in self._records:
            if kind is not None and rec.kind != kind:
                continue
            if all(rec.payload.get(k) == v for k, v in match.items()):
                out.append(rec)
        return out

    def __iter__(self) -> Iterator[EvidenceRecord]:
        return iter(list(self._records))

    def __len__(self) -> int:
        return len(self._records)
