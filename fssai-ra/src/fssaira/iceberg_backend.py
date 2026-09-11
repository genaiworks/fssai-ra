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
        table.append(pa.Table.from_pylist(list(rows), schema=table.schema().as_arrow()))
        return str(table.refresh().current_snapshot().snapshot_id)

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
        return [
            {"snapshot_id": str(entry.snapshot_id), "timestamp_ms": entry.timestamp_ms,
             "parent_id": str(entry.parent_snapshot_id or "")}
            for entry in self._table().history()
        ]

    @property
    def current_id(self) -> str | None:  # pragma: no cover
        snapshot = self._table().current_snapshot()
        return None if snapshot is None else str(snapshot.snapshot_id)

    def current_rows(self) -> list:  # pragma: no cover
        return self._table().scan().to_arrow().to_pylist()


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
            kafka_partition INT NOT NULL,
            kafka_offset BIGINT NOT NULL,
            imported_at TIMESTAMP NOT NULL
        ) USING iceberg
        PARTITIONED BY (days(imported_at))
        TBLPROPERTIES ('format-version'='2')
    """,
    EVIDENCE_TABLE: """
        CREATE TABLE IF NOT EXISTS {catalog}.{namespace}.decision_evidence (
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


def archive_evidence(ledger, store: IcebergSnapshotStore) -> dict:  # pragma: no cover
    """Copy a ledger into the Iceberg archive and pin the resulting snapshot.

    The archive is a second copy under different retention and different
    administration. It does not make the chain stronger; it makes silent
    truncation of the primary detectable by comparison.
    """
    import time as _time

    rows = [
        {
            "seq": record.seq, "ts": record.ts, "kind": record.kind,
            "request_id": str(record.payload.get("request_id", "")),
            "payload_json": json.dumps(record.payload, sort_keys=True, default=str),
            "prev_hash": record.prev_hash, "hash": record.hash,
            "archived_at": _time.time(),
        }
        for record in ledger
    ]
    snapshot_id = store.commit(rows, note="evidence archive")
    return {
        "records": len(rows),
        "snapshot_id": snapshot_id,
        "chain_valid_at_archive": ledger.verify(),
        "manifest": _manifest(rows),
    }


__all__ = [
    "DEFAULT_NAMESPACE", "EVIDENCE_TABLE", "IMPORT_TABLE", "IcebergSnapshotStore",
    "TABLE_DDL", "archive_evidence", "load_catalog",
]
