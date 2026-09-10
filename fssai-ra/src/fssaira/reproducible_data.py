"""Reproducible-data domain: lineage-logged transforms (Spark-like) and
versioned, rollback-able snapshots with signed manifests (Iceberg-like).

Together these give the contract's "reproducible data states" property: any
past decision's exact inputs can be reconstructed, and a poisoned or mistaken
state can be rolled back to the last approved snapshot. Signed manifests (a
content hash of the rows) let the evidence ledger bind a decision to the exact
data version it used.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass


def _manifest(rows) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    ts: float
    rows: tuple
    manifest: str
    parent: str | None
    note: str = ""


class SnapshotStore:
    """Iceberg-like: atomic snapshots, history, signed manifests, rollback."""

    def __init__(self) -> None:
        self._snaps: dict[str, Snapshot] = {}
        self._current: str | None = None

    def commit(self, rows, parent: str | None = None, note: str = "") -> str:
        sid = f"snap-{len(self._snaps):04d}"
        rows_t = tuple(rows)
        snap = Snapshot(sid, time.time(), rows_t, _manifest(list(rows_t)), parent, note)
        self._snaps[sid] = snap
        self._current = sid
        return sid

    def read(self, snapshot_id: str) -> list:
        return list(self._snaps[snapshot_id].rows)

    def manifest(self, snapshot_id: str) -> str:
        return self._snaps[snapshot_id].manifest

    @property
    def current_id(self) -> str | None:
        return self._current

    def current_rows(self) -> list:
        return self.read(self._current) if self._current else []

    def rollback(self, snapshot_id: str) -> str:
        """Restore an earlier approved snapshot as a new current snapshot."""
        rows = self.read(snapshot_id)
        return self.commit(rows, parent=snapshot_id, note=f"rollback->{snapshot_id}")

    def history(self) -> list[Snapshot]:
        return list(self._snaps.values())


class Transformer:
    """Spark-like transform that logs lineage for every job."""

    CODE_VERSION = "1.0.0"

    def run(self, records, fn, job: str = "transform", rules: str = ""):
        inputs = list(records)
        rows = [fn(r) for r in inputs]
        lineage = {
            "job": job,
            "code_version": self.CODE_VERSION,
            "input_hash": _manifest(inputs),
            "output_hash": _manifest(rows),
            "rules": rules,
            "n_in": len(inputs),
            "n_out": len(rows),
        }
        return rows, lineage
