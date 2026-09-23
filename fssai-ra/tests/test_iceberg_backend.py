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

        def archived_head(self, ledger_id):
            return None

    store = RecordingStore()
    report = archive_evidence(ledger, store)

    assert report["snapshot_id"] == "42"
    assert isinstance(store.rows[0]["archived_at"], datetime)


class ArchiveStore:
    """In-memory stand-in with the two calls archive_evidence relies on."""

    table = f"fssaira.{EVIDENCE_TABLE}"

    def __init__(self):
        self.rows = []
        self.commits = 0

    def commit(self, rows, parent=None, note=""):
        self.rows.extend(rows)
        self.commits += 1
        return str(100 + self.commits)

    def archived_head(self, ledger_id):
        mine = [r for r in self.rows if r["ledger_id"] == ledger_id]
        if not mine:
            return None
        last = max(mine, key=lambda r: r["seq"])
        return last["seq"], last["hash"]

    @property
    def current_id(self):
        return str(100 + self.commits) if self.commits else None


def ledger_with(count):
    ledger = EvidenceLedger("token")
    for index in range(count):
        ledger.append("decision", {"request_id": f"r-{index}"}, token="token")
    return ledger


def test_repeated_archive_appends_only_new_records():
    ledger, store = ledger_with(3), ArchiveStore()
    first = archive_evidence(ledger, store, ledger_id="primary")
    assert first["records"] == 3 and first["first_seq"] == 0 and first["last_seq"] == 2

    again = archive_evidence(ledger, store, ledger_id="primary")
    assert again["records"] == 0 and again["snapshot_id"] == first["snapshot_id"]
    assert store.commits == 1

    ledger.append("decision", {"request_id": "r-3"}, token="token")
    more = archive_evidence(ledger, store, ledger_id="primary")
    assert more["records"] == 1 and more["first_seq"] == 3
    assert sorted(r["seq"] for r in store.rows) == [0, 1, 2, 3]


def test_two_ledgers_share_one_table_without_colliding():
    store = ArchiveStore()
    archive_evidence(ledger_with(2), store, ledger_id="site-a")
    report = archive_evidence(ledger_with(2), store, ledger_id="site-b")
    assert report["records"] == 2
    assert {(r["ledger_id"], r["seq"]) for r in store.rows} == {
        ("site-a", 0), ("site-a", 1), ("site-b", 0), ("site-b", 1)}


def test_archive_refuses_a_ledger_that_diverged_from_its_archive():
    store = ArchiveStore()
    archive_evidence(ledger_with(2), store, ledger_id="primary")
    rewritten = EvidenceLedger("token")  # same seqs, different content and hashes
    for index in range(3):
        rewritten.append("decision", {"request_id": f"forged-{index}"}, token="token")
    with pytest.raises(ValueError, match="ARCHIVE_DIVERGED"):
        archive_evidence(rewritten, store, ledger_id="primary")


def test_archive_refuses_a_ledger_shorter_than_its_archive():
    store = ArchiveStore()
    ledger = ledger_with(3)
    archive_evidence(ledger, store, ledger_id="primary")
    truncated = EvidenceLedger("token")
    for record in list(ledger)[:1]:
        truncated._records.append(record)
    with pytest.raises(ValueError, match="ARCHIVE_AHEAD_OF_LEDGER"):
        archive_evidence(truncated, store, ledger_id="primary")
