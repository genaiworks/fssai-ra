"""Iceberg adapter for the reproducible-data seam.

Enable with:  pip install pyiceberg
Map SnapshotStore.commit/read/rollback onto Iceberg table snapshots so that
"reproducible data states" is backed by real table versioning, time travel, and
signed manifests. Sketch only - wire to your catalog (REST, Glue, Nessie).
"""
from __future__ import annotations


class IcebergSnapshotStore:
    def __init__(self, catalog_uri: str, table: str) -> None:
        try:
            from pyiceberg.catalog import load_catalog  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise ImportError("IcebergSnapshotStore requires 'pyiceberg' (pip install pyiceberg)") from exc
        self._catalog = load_catalog("default", uri=catalog_uri)
        self._table_name = table

    def commit(self, rows, parent=None, note=""):  # pragma: no cover - needs a catalog
        tbl = self._catalog.load_table(self._table_name)
        tbl.append(rows)  # each append creates a new snapshot
        return str(tbl.current_snapshot().snapshot_id)

    def rollback(self, snapshot_id):  # pragma: no cover
        tbl = self._catalog.load_table(self._table_name)
        tbl.manage_snapshots().rollback_to_snapshot(int(snapshot_id)).commit()
        return str(tbl.current_snapshot().snapshot_id)
