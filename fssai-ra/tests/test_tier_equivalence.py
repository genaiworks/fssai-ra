"""The small and big tiers give the same evidence-plane verdicts on the same attacks.

Each scenario runs twice: once against the SQLite archive (small tier) and once
against a real Iceberg table (big tier), created in a local SQL catalog with the
schema ``jobs/bootstrap_iceberg.py`` applies. Both go through the same archiver
(``archive_evidence``) and the same verifier (``verify_rows``); the test checks
that the storage underneath does not change what either of them concludes.

The Iceberg half needs the ``iceberg`` extra plus ``pyiceberg[sql-sqlite]`` and
is skipped without it.
"""
import json

import pytest

from fssaira.chain_verification import verify_rows
from fssaira.evidence import EvidenceLedger
from fssaira.evidence_notary import EvidenceNotary
from fssaira.iceberg_backend import EVIDENCE_TABLE, IcebergSnapshotStore, archive_evidence
from fssaira.small_data import SqliteArchiveStore

TOKEN = "tier-equivalence"


def iceberg_store(tmp_path):
    pytest.importorskip("pyarrow")
    pytest.importorskip("sqlalchemy")
    sql = pytest.importorskip("pyiceberg.catalog.sql")
    from pyiceberg.schema import Schema
    from pyiceberg.types import DoubleType, LongType, NestedField, StringType, TimestamptzType

    tmp_path.mkdir(parents=True, exist_ok=True)
    catalog = sql.SqlCatalog("tier", uri=f"sqlite:///{tmp_path / 'catalog.db'}",
                             warehouse=f"file://{tmp_path / 'warehouse'}")
    catalog.create_namespace("fssaira")
    # Mirrors TABLE_DDL[EVIDENCE_TABLE]; Spark's TIMESTAMP is Iceberg's timestamptz.
    catalog.create_table(f"fssaira.{EVIDENCE_TABLE}", schema=Schema(
        NestedField(1, "ledger_id", StringType(), required=False),
        NestedField(2, "seq", LongType(), required=True),
        NestedField(3, "ts", DoubleType(), required=True),
        NestedField(4, "kind", StringType(), required=True),
        NestedField(5, "request_id", StringType(), required=False),
        NestedField(6, "payload_json", StringType(), required=True),
        NestedField(7, "prev_hash", StringType(), required=True),
        NestedField(8, "hash", StringType(), required=True),
        NestedField(9, "archived_at", TimestamptzType(), required=True),
    ))
    return IcebergSnapshotStore(table=f"fssaira.{EVIDENCE_TABLE}", _catalog=catalog)


def sqlite_store(tmp_path):
    return SqliteArchiveStore(tmp_path / "archive.sqlite3")


def archived_rows(store, ledger_id="primary"):
    """What each tier's verifier reads: the archived rows for one ledger, by seq."""
    if isinstance(store, SqliteArchiveStore):
        return store.evidence_rows(ledger_id)
    rows = [r for r in store.current_rows() if r["ledger_id"] == ledger_id]
    return sorted(({k: r[k] for k in ("seq", "ts", "kind", "payload_json", "prev_hash", "hash")}
                   for r in rows), key=lambda r: r["seq"])


@pytest.fixture(params=["small", "big"])
def store(request, tmp_path):
    return sqlite_store(tmp_path) if request.param == "small" else iceberg_store(tmp_path)


def ledger(count, prefix="r"):
    built = EvidenceLedger(TOKEN)
    for index in range(count):
        built.append("decision", {"request_id": f"{prefix}-{index}"}, token=TOKEN)
    return built


def test_archive_is_incremental_and_verifies_intact(store):
    primary = ledger(4)
    first = archive_evidence(primary, store)
    assert (first["records"], first["first_seq"], first["last_seq"]) == (4, 0, 3)
    assert archive_evidence(primary, store)["records"] == 0
    primary.append("decision", {"request_id": "r-4"}, token=TOKEN)
    assert archive_evidence(primary, store)["first_seq"] == 4
    verdict = verify_rows(archived_rows(store))
    assert verdict["verdict"] == "INTACT" and verdict["records"] == 5


def test_rewritten_ledger_is_refused(store):
    archive_evidence(ledger(3), store)
    with pytest.raises(ValueError, match="ARCHIVE_DIVERGED"):
        archive_evidence(ledger(4, prefix="rewritten"), store)


def test_truncated_ledger_is_refused(store):
    archive_evidence(ledger(3), store)
    with pytest.raises(ValueError, match="ARCHIVE_AHEAD_OF_LEDGER"):
        archive_evidence(ledger(2), store)


def test_missing_tail_is_caught_only_by_the_signed_checkpoint(store):
    primary = ledger(4)
    notary = EvidenceNotary()
    checkpoint = notary.checkpoint(list(primary)).to_dict()
    keys = {key_id: key.hex() for key_id, key in notary.public_keys.items()}
    # The primary lost its newest two records before they were archived.
    archive_evidence(_Prefix(primary, 2), store)
    rows = archived_rows(store)
    assert verify_rows(rows)["verdict"] == "INTACT"  # why a checkpoint is needed
    verdict = verify_rows(rows, checkpoint=checkpoint, public_keys=keys)
    assert verdict["verdict"] == "COMPROMISED"
    assert verdict["checkpoint"]["code"] == "LEDGER_TRUNCATED"


def test_altered_archived_payload_is_detected(store):
    archive_evidence(ledger(3), store)
    rows = archived_rows(store)
    rows[1] = {**rows[1], "payload_json": json.dumps({"request_id": "forged"})}
    verdict = verify_rows(rows)
    assert verdict["verdict"] == "COMPROMISED" and verdict["altered_records"] == [1]


def test_ledgers_sharing_one_archive_stay_separate(store):
    archive_evidence(ledger(2, "a"), store, ledger_id="alpha")
    archive_evidence(ledger(3, "b"), store, ledger_id="beta")
    assert verify_rows(archived_rows(store, "alpha"))["records"] == 2
    assert verify_rows(archived_rows(store, "beta"))["records"] == 3
    assert verify_rows(archived_rows(store, "beta"))["verdict"] == "INTACT"


def test_racing_archivers_differ_only_in_where_the_duplicate_is_stopped(tmp_path):
    """The one documented difference between tiers.

    Iceberg appends do not conflict, so two archivers that read the same head can
    both append; the verifier reports the duplicate. SQLite's primary key refuses
    the second copy at write time. Either way no duplicate passes as INTACT.
    """
    import sqlite3

    primary = ledger(2)
    small = sqlite_store(tmp_path)
    archive_evidence(primary, small)
    rows = [{"ledger_id": "primary", "seq": r.seq, "ts": r.ts, "kind": r.kind,
             "request_id": "", "payload_json": json.dumps(r.payload, sort_keys=True),
             "prev_hash": r.prev_hash, "hash": r.hash, "archived_at": "now"} for r in primary]
    with pytest.raises(sqlite3.IntegrityError):
        small.commit(rows)

    big = iceberg_store(tmp_path / "big")
    archive_evidence(primary, big)
    from datetime import datetime, timezone

    big.commit([{**row, "archived_at": datetime.now(timezone.utc)} for row in rows])
    verdict = verify_rows(archived_rows(big))
    assert verdict["verdict"] == "COMPROMISED" and verdict["duplicate_seqs"] == [0, 1]


class _Prefix:
    """The first ``count`` records of a real ledger: a primary whose tail was deleted."""

    def __init__(self, source, count):
        self._records = list(source)[:count]

    def __iter__(self):
        return iter(self._records)

    def __len__(self):
        return len(self._records)

    def verify(self):
        return True
