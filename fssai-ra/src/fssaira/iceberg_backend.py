"""Apache Iceberg as the reproducible-data and evidence-archive layer.

Iceberg supplies exactly what the reproducible-data contract asks for: atomic
snapshots, a snapshot history, time travel to any past state, and manifests that
identify content rather than commit order. A decision made on 10 September can
therefore be re-examined against the table as it was on 10 September, not as it
is now.

Two caveats are load-bearing and belong next to the code, not only in a footnote:

* **Retention is a governance setting.** ``expire_snapshots`` and orphan-file
  cleanup will happily delete the snapshot a decision was bound to. A retention
  policy that outlives the appeal window is part of the control, not an
  operational detail.
* **A manifest identifies data; it does not preserve it.** The evidence ledger
  records a snapshot id and a content hash. If the files are gone, the hash
  proves only that they are gone.

The store degrades gracefully: without ``pyiceberg`` installed it raises a clear
ImportError naming the extra, and every other part of the system keeps working.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

DEFAULT_NAMESPACE = "fssaira"
EVIDENCE_TABLE = "decision_evidence"
IMPORT_TABLE = "imported_evidence"


def _manifest(rows) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


def load_catalog(name: str = "sovereign", **options):
    """Load a REST, Glue, Hive, or SQL catalog through pyiceberg."""
    try:
        from pyiceberg.catalog import load_catalog as _load
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Iceberg support requires the 'iceberg' extra: pip install 'fssaira[iceberg]'"
        ) from exc
    settings = {
        "uri": os.getenv("ICEBERG_CATALOG_URI", "http://iceberg-rest:8181"),
        "warehouse": os.getenv("ICEBERG_WAREHOUSE", "s3://warehouse/"),
        "s3.endpoint": os.getenv("S3_ENDPOINT", "http://minio:9000"),
        "s3.access-key-id": os.getenv("AWS_ACCESS_KEY_ID", ""),
        "s3.secret-access-key": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
    }
    settings.update(options)
    return _load(name, **{k: v for k, v in settings.items() if v})


@dataclass
class IcebergSnapshotStore:
    """Snapshot port backed by real Iceberg table versioning.

    ``commit`` appends and returns the new snapshot id; ``read`` time-travels to
    a given snapshot; ``rollback`` sets the table back to an approved one, which
    is the concrete recovery step behind "roll back a poisoned state".
    """

    table: str = f"{DEFAULT_NAMESPACE}.{IMPORT_TABLE}"
    catalog_name: str = "sovereign"
    _catalog: Any = None

    def __post_init__(self) -> None:
        if self._catalog is None:
            self._catalog = load_catalog(self.catalog_name)

    def _table(self):
        return self._catalog.load_table(self.table)

    def commit(self, rows, parent: str | None = None, note: str = "") -> str:  # pragma: no cover
        import pyarrow as pa

        table = self._table()
        properties = {
            key: value for key, value in {
                "fssaira.note": note,
                "fssaira.requested-parent": parent or "",
            }.items() if value
        }
        table.append(
            pa.Table.from_pylist(list(rows), schema=table.schema().as_arrow()),
            snapshot_properties=properties,
        )
        snapshot = table.refresh().current_snapshot()
        if snapshot is None:
            raise RuntimeError("Iceberg append completed without creating a snapshot")
        return str(snapshot.snapshot_id)

    def read(self, snapshot_id: str) -> list:  # pragma: no cover
        table = self._table()
        scan = table.scan(snapshot_id=int(snapshot_id))
        return scan.to_arrow().to_pylist()

    def manifest(self, snapshot_id: str) -> str:  # pragma: no cover
        return _manifest(self.read(snapshot_id))

    def rollback(self, snapshot_id: str) -> str:  # pragma: no cover
        table = self._table()
        table.manage_snapshots().rollback_to_snapshot(int(snapshot_id)).commit()
        return str(table.refresh().current_snapshot().snapshot_id)

    def history(self) -> list[dict]:  # pragma: no cover
        table = self._table().refresh()
        history = []
        for entry in table.history():
            snapshot = table.snapshot_by_id(entry.snapshot_id)
            history.append({
                "snapshot_id": str(entry.snapshot_id),
                "timestamp_ms": entry.timestamp_ms,
                # ``history()`` returns SnapshotLogEntry, which has no parent
                # field. Parentage lives on the referenced Snapshot object.
                "parent_id": (
                    "" if snapshot is None or snapshot.parent_snapshot_id is None
                    else str(snapshot.parent_snapshot_id)
                ),
            })
        return history

    @property
    def current_id(self) -> str | None:  # pragma: no cover
        snapshot = self._table().refresh().current_snapshot()
        return None if snapshot is None else str(snapshot.snapshot_id)

    def current_rows(self) -> list:  # pragma: no cover
        return self._table().scan().to_arrow().to_pylist()

    def archived_head(self, ledger_id: str) -> tuple[int, str] | None:  # pragma: no cover
        """Highest archived ``(seq, hash)`` for one ledger, or ``None``."""
        from pyiceberg.expressions import EqualTo

        rows = (
            self._table().scan(row_filter=EqualTo("ledger_id", ledger_id),
                               selected_fields=("seq", "hash"))
            .to_arrow().to_pylist()
        )
        if not rows:
            return None
        last = max(rows, key=lambda row: row["seq"])
        return int(last["seq"]), last["hash"]


#: DDL for the archive tables, kept beside the code that reads them so a schema
#: change cannot drift from the reader. Applied by ``jobs/bootstrap_iceberg.py``.
TABLE_DDL = {
    IMPORT_TABLE: """
        CREATE TABLE IF NOT EXISTS {catalog}.{namespace}.imported_evidence (
            source STRING NOT NULL,
            text STRING NOT NULL,
            stripped ARRAY<STRING>,
            content_hash STRING,
            trace_id STRING NOT NULL,
            kafka_topic STRING,
            topic_generation STRING,
            kafka_partition INT NOT NULL,
            kafka_offset BIGINT NOT NULL,
            imported_at TIMESTAMP NOT NULL
        ) USING iceberg
        PARTITIONED BY (days(imported_at))
        TBLPROPERTIES ('format-version'='2')
    """,
    EVIDENCE_TABLE: """
        CREATE TABLE IF NOT EXISTS {catalog}.{namespace}.decision_evidence (
            ledger_id STRING,
            seq BIGINT NOT NULL,
            ts DOUBLE NOT NULL,
            kind STRING NOT NULL,
            request_id STRING,
            payload_json STRING NOT NULL,
            prev_hash STRING NOT NULL,
            hash STRING NOT NULL,
            archived_at TIMESTAMP NOT NULL
        ) USING iceberg
        PARTITIONED BY (days(archived_at))
        TBLPROPERTIES ('format-version'='2')
    """,
    # Import records refused because they carried no valid gateway MAC. Positions
    # and a hash of the raw bytes only: the content is untrusted by definition.
    # Columns are nullable: a rejected record may be malformed and lack any field.
    "quarantined_imports": """
        CREATE TABLE IF NOT EXISTS {catalog}.{namespace}.quarantined_imports (
            kafka_topic STRING,
            topic_generation STRING,
            kafka_partition INT,
            kafka_offset BIGINT,
            trace_id STRING,
            reason STRING,
            raw_sha256 STRING,
            quarantined_at TIMESTAMP
        ) USING iceberg
        TBLPROPERTIES ('format-version'='2')
    """,
    "control_events": """
        CREATE TABLE IF NOT EXISTS {catalog}.{namespace}.control_events (
            event_kind STRING NOT NULL,
            resource_id STRING,
            payload_json STRING NOT NULL,
            trace_id STRING NOT NULL,
            observed_at TIMESTAMP NOT NULL
        ) USING iceberg
        PARTITIONED BY (days(observed_at))
        TBLPROPERTIES ('format-version'='2')
    """,
}


#: Columns added after the first release, with the value that existing rows are
#: backfilled with. ``jobs/bootstrap_iceberg.py`` applies them to tables created
#: by an earlier version, so a MERGE on the new key still matches old rows.
#: ``{topic}`` and ``{generation}`` are filled from the import job's settings.
TABLE_MIGRATIONS = {
    IMPORT_TABLE: {"kafka_topic": "{topic}", "topic_generation": "{generation}"},
    EVIDENCE_TABLE: {"ledger_id": "primary"},
}


def _segment_valid(records, previous_hash: str, first_seq: int) -> bool:
    """New records are contiguous, chain from ``previous_hash``, and recompute."""
    from .evidence import _digest

    expected = first_seq
    for record in records:
        if record.seq != expected or record.prev_hash != previous_hash:
            return False
        if _digest(record.seq, record.ts, record.kind, record.payload,
                   record.prev_hash) != record.hash:
            return False
        previous_hash, expected = record.hash, expected + 1
    return True


def archive_evidence(ledger, store: IcebergSnapshotStore, *, ledger_id: str = "primary",
                     batch: int | None = None) -> dict:
    """Append the ledger records the archive does not hold yet. Safe to re-run.

    The archive is a second copy under different retention and different
    administration. It does not make the chain stronger; it makes silent
    truncation of the primary detectable by comparison.

    Each row carries ``ledger_id`` so several ledgers can share one table, and
    ``(ledger_id, seq)`` identifies a record. Before appending, the archive's
    highest ``seq`` for this ledger is compared with the live ledger:

    * same ``seq`` and hash: append only the newer records (none, on a re-run);
    * the archive is *longer* than the ledger: ``ARCHIVE_AHEAD_OF_LEDGER``;
    * same ``seq`` but a different hash: ``ARCHIVE_DIVERGED``.

    Both refusals mean the primary ledger was truncated or rewritten after it was
    archived, which is exactly what the archive exists to reveal.

    A ledger that offers ``records_from(seq, limit)`` (the SQL ledger does) is
    read incrementally: only the archived head and the records after it, at most
    ``batch`` of them per call. ``chain_valid_at_archive`` then covers what this
    call archives -- contiguous, chained from the archived head, and recomputed --
    since everything before the head is already in the archive for the
    independent verifier. ``verified_scope`` names which of the two was checked.
    A ledger without it (the in-memory one) is read and verified in full.

    Run one archiver per ``ledger_id``. Iceberg appends do not conflict with each
    other, so two concurrent archivers can still append the same records;
    ``jobs/verify_evidence_chain.py`` reports such duplicates.
    """
    if store.table.rsplit(".", 1)[-1] != EVIDENCE_TABLE:
        raise ValueError(
            f"evidence archives require an {EVIDENCE_TABLE!r} table, got {store.table!r}"
        )

    from .evidence import GENESIS_HASH

    head = store.archived_head(ledger_id)
    incremental = hasattr(ledger, "records_from")
    if incremental:
        count = len(ledger)
        read_from = 0 if head is None else head[0]
        extra = 0 if head is None else 1
        window = ledger.records_from(read_from, None if batch is None else batch + extra)
        anchor = window[0] if head is not None and window and window[0].seq == head[0] else None
        new_records = window[extra:] if head is not None else window
    else:
        records = list(ledger)
        count = len(records)
        anchor = records[head[0]] if head is not None and head[0] < count else None
        new_records = records[head[0] + 1:] if head is not None else records
        if batch is not None:
            new_records = new_records[:batch]

    start, previous_hash = 0, GENESIS_HASH
    if head is not None:
        archived_seq, archived_hash = head
        if archived_seq >= count:
            raise ValueError(
                f"ARCHIVE_AHEAD_OF_LEDGER: archive holds seq {archived_seq} for {ledger_id!r} "
                f"but the ledger has {count} record(s)"
            )
        if anchor is None or anchor.hash != archived_hash:
            raise ValueError(
                f"ARCHIVE_DIVERGED: ledger record {archived_seq} for {ledger_id!r} no longer "
                "matches the archived hash"
            )
        start, previous_hash = archived_seq + 1, archived_hash

    if incremental:
        chain_valid = _segment_valid(new_records, previous_hash, start)
        scope = "records archived by this call, chained from the archived head"
    else:
        chain_valid = ledger.verify()
        scope = "full ledger"

    archived_at = datetime.now(timezone.utc)
    rows = [
        {
            "ledger_id": ledger_id,
            "seq": record.seq, "ts": record.ts, "kind": record.kind,
            "request_id": str(record.payload.get("request_id", "")),
            "payload_json": json.dumps(record.payload, sort_keys=True, default=str),
            "prev_hash": record.prev_hash, "hash": record.hash,
            "archived_at": archived_at,
        }
        for record in new_records
    ]
    report = {
        "ledger_id": ledger_id,
        "records": len(rows),
        "first_seq": rows[0]["seq"] if rows else None,
        "last_seq": rows[-1]["seq"] if rows else (start - 1 if start else None),
        "chain_valid_at_archive": chain_valid,
        "verified_scope": scope,
        "more": rows[-1]["seq"] + 1 < count if rows else False,
        "manifest": _manifest(rows),
    }
    # Nothing new: do not create an empty snapshot.
    report["snapshot_id"] = (
        store.commit(rows, note=f"evidence archive {ledger_id} seq {start}+")
        if rows else store.current_id
    )
    return report


__all__ = [
    "DEFAULT_NAMESPACE", "EVIDENCE_TABLE", "IMPORT_TABLE", "IcebergSnapshotStore",
    "TABLE_DDL", "TABLE_MIGRATIONS", "archive_evidence", "load_catalog",
]
