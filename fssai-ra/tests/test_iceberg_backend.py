"""Unit-level contract checks for Iceberg code without a running catalog."""
import sys
import types
from dataclasses import dataclass
from datetime import datetime

import pytest

from fssaira.evidence import EvidenceLedger
from fssaira.iceberg_backend import EVIDENCE_TABLE, IcebergSnapshotStore, archive_evidence


@dataclass
class Snapshot:
    snapshot_id: int
    parent_snapshot_id: int | None = None


class Table:
    def __init__(self):
        self.appended = None
        self.properties = None
        self.current = Snapshot(12, 11)

    def schema(self):
        return types.SimpleNamespace(as_arrow=lambda: "schema")

    def append(self, rows, snapshot_properties=None):
        self.appended = rows
        self.properties = snapshot_properties

    def refresh(self):
        return self

    def current_snapshot(self):
        return self.current

    def history(self):
        return [types.SimpleNamespace(snapshot_id=12, timestamp_ms=1234)]

    def snapshot_by_id(self, snapshot_id):
        return self.current if snapshot_id == 12 else None


class Catalog:
    def __init__(self, table):
        self.table = table

    def load_table(self, _name):
        return self.table


def store_for(table, name="fssaira.imported_evidence"):
    return IcebergSnapshotStore(table=name, _catalog=Catalog(table))


def test_commit_preserves_framework_lineage_in_snapshot_properties(monkeypatch):
    table = Table()
    arrow = types.SimpleNamespace(
        Table=types.SimpleNamespace(from_pylist=lambda rows, schema: (rows, schema))
    )
    monkeypatch.setitem(sys.modules, "pyarrow", arrow)
    store = store_for(table)

    snapshot_id = store.commit([{"id": 1}], parent="11", note="validated import")

    assert snapshot_id == "12"
    assert table.properties == {
        "fssaira.note": "validated import",
        "fssaira.requested-parent": "11",
    }


def test_history_reads_parent_from_snapshot_not_log_entry():
    assert store_for(Table()).history() == [{
        "snapshot_id": "12", "timestamp_ms": 1234, "parent_id": "11",
    }]


def test_evidence_archive_refuses_the_import_table_before_writing():
    ledger = EvidenceLedger("token")
    ledger.append("decision", {"request_id": "r-1"}, token="token")

    with pytest.raises(ValueError, match=EVIDENCE_TABLE):
        archive_evidence(ledger, store_for(Table()))


def test_evidence_archive_uses_timestamp_values_the_iceberg_schema_accepts():
    ledger = EvidenceLedger("token")
    ledger.append("decision", {"request_id": "r-1"}, token="token")

    class RecordingStore:
        table = f"fssaira.{EVIDENCE_TABLE}"

        def commit(self, rows, parent=None, note=""):
            self.rows = rows
            return "42"

    store = RecordingStore()
    report = archive_evidence(ledger, store)

    assert report["snapshot_id"] == "42"
    assert isinstance(store.rows[0]["archived_at"], datetime)
