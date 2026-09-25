"""The small-data tier keeps the big-data tier's guarantees without Kafka, Spark or Iceberg."""
import hashlib
import hmac
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from fssaira.atomic_execution import sql_evidence
from fssaira.cli import main
from fssaira.evidence_notary import EvidenceNotary
from fssaira.import_api import create_import_app
from fssaira.runtime_factory import configuration_warnings
from fssaira.scale import Workload, recommend
from fssaira.small_data import (
    SqliteArchiveStore,
    SqliteImportLog,
    archive_ledger,
    ingest_imports,
    verify_archive,
)
from fssaira.sql_backend import open_sqlite

ENVELOPE_KEY = "k" * 40
SOURCE_KEY = "test-source-key"
TOKEN = "small-tier-evidence-writer"


def signed_import(data: str) -> dict:
    return {
        "source": "research-partner", "content_type": "text/plain", "data": data,
        "signature": hmac.new(SOURCE_KEY.encode(), data.encode(), hashlib.sha256).hexdigest(),
    }


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    for name in ("FSSAI_KAFKA_BOOTSTRAP", "FSSAI_IMPORT_AUDIT_PATH"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FSSAI_IMPORT_LOG_PATH", str(tmp_path / "import-log.sqlite3"))
    monkeypatch.setenv("FSSAI_IMPORT_ENVELOPE_KEY", ENVELOPE_KEY)
    monkeypatch.setenv("FSSAI_IMPORT_SOURCE_KEYS_JSON", json.dumps({"research-partner": SOURCE_KEY}))
    return TestClient(create_import_app())


def ledger_with(path, count: int):
    database = open_sqlite(str(path), evidence_token=TOKEN)
    ledger = sql_evidence(database)
    for index in range(count):
        ledger.append("decision", {"request_id": f"r-{index}"}, token=TOKEN)
    return database, ledger


# ---------------------------------------------------------------- gateway → log


def test_gateway_uses_the_sqlite_log_without_kafka(gateway, tmp_path):
    assert gateway.get("/health").json()["inward_log"] == "sqlite-import-log"
    first = gateway.post("/v1/imports", json=signed_import("first observation"))
    second = gateway.post("/v1/imports", json=signed_import("second observation"))
    assert [first.json()["broker_offset"], second.json()["broker_offset"]] == [0, 1]
    log = SqliteImportLog(tmp_path / "import-log.sqlite3")
    envelope = json.loads(log.read()[0]["envelope"])
    assert envelope["value"]["text"] == "first observation"
    assert "mac" in envelope  # the same signed shape the Kafka publisher writes


def test_gateway_without_any_inward_log_refuses_to_start(monkeypatch):
    for name in ("FSSAI_KAFKA_BOOTSTRAP", "FSSAI_IMPORT_LOG_PATH"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="FSSAI_IMPORT_LOG_PATH"):
        create_import_app(trusted_keys={"s": "k"})


# ---------------------------------------------------------------- log → archive


def test_ingest_moves_signed_imports_and_is_idempotent(gateway, tmp_path):
    gateway.post("/v1/imports", json=signed_import("alpha"))
    gateway.post("/v1/imports", json=signed_import("beta"))
    log = SqliteImportLog(tmp_path / "import-log.sqlite3")
    archive = SqliteArchiveStore(tmp_path / "archive.sqlite3")

    report = ingest_imports(log, archive, mac_key=ENVELOPE_KEY.encode())
    assert (report["imported"], report["quarantined"]) == (2, 0)
    assert [row["text"] for row in archive.imports()] == ["alpha", "beta"]
    again = ingest_imports(log, archive, mac_key=ENVELOPE_KEY.encode())
    assert again["imported"] == 0 and len(archive.imports()) == 2


def test_forged_record_is_quarantined_by_position_not_content(gateway, tmp_path):
    gateway.post("/v1/imports", json=signed_import("genuine"))
    log = SqliteImportLog(tmp_path / "import-log.sqlite3")  # no key: a forger
    text = "forged instruction"
    log.append({"source": "research-partner", "text": text, "stripped": [],
                "content_hash": hashlib.sha256(text.encode()).hexdigest()})
    gateway.post("/v1/imports", json=signed_import("after the forgery"))
    archive = SqliteArchiveStore(tmp_path / "archive.sqlite3")

    report = ingest_imports(log, archive, mac_key=ENVELOPE_KEY.encode())
    assert (report["imported"], report["quarantined"]) == (2, 1)
    quarantined = archive.quarantined()[0]
    assert quarantined["log_offset"] == 1 and "text" not in quarantined
    assert "forged" not in json.dumps(quarantined)


def test_content_hash_mismatch_commits_nothing(tmp_path):
    log = SqliteImportLog(tmp_path / "log.sqlite3", mac_key=ENVELOPE_KEY.encode())
    log.append({"source": "s", "text": "good", "stripped": [],
                "content_hash": hashlib.sha256(b"good").hexdigest()})
    log.append({"source": "s", "text": "altered", "stripped": [], "content_hash": "0" * 64})
    archive = SqliteArchiveStore(tmp_path / "archive.sqlite3")
    with pytest.raises(ValueError, match="content hash"):
        ingest_imports(log, archive, mac_key=ENVELOPE_KEY.encode())
    assert archive.imports() == [] and archive.history() == []


def test_unsigned_sink_needs_an_explicit_opt_in(tmp_path):
    log = SqliteImportLog(tmp_path / "log.sqlite3")
    archive = SqliteArchiveStore(tmp_path / "archive.sqlite3")
    with pytest.raises(RuntimeError, match="FSSAI_IMPORT_ENVELOPE_KEY"):
        ingest_imports(log, archive, mac_key=None)
    assert ingest_imports(log, archive, mac_key=None, allow_unsigned=True)["imported"] == 0


def test_truncated_log_is_refused_and_a_recreated_log_is_a_new_generation(tmp_path):
    path = tmp_path / "log.sqlite3"
    log = SqliteImportLog(path, mac_key=ENVELOPE_KEY.encode())
    for text in ("a", "b"):
        log.append({"source": "s", "text": text, "stripped": [],
                    "content_hash": hashlib.sha256(text.encode()).hexdigest()})
    archive = SqliteArchiveStore(tmp_path / "archive.sqlite3")
    ingest_imports(log, archive, mac_key=ENVELOPE_KEY.encode())
    first_generation = log.generation

    with sqlite3.connect(path) as raw:
        raw.execute("DELETE FROM import_log WHERE log_offset = 1")
    with pytest.raises(RuntimeError, match="truncated"):
        ingest_imports(log, archive, mac_key=ENVELOPE_KEY.encode())

    log.close()
    for suffix in ("", "-wal", "-shm"):
        (tmp_path / f"log.sqlite3{suffix}").unlink(missing_ok=True)
    fresh = SqliteImportLog(path, mac_key=ENVELOPE_KEY.encode())
    fresh.append({"source": "s", "text": "c", "stripped": [],
                  "content_hash": hashlib.sha256(b"c").hexdigest()})
    assert fresh.generation != first_generation
    assert ingest_imports(fresh, archive, mac_key=ENVELOPE_KEY.encode())["imported"] == 1


# ---------------------------------------------------------- ledger → archive → verify


def test_archive_and_verify_the_control_ledger(tmp_path):
    database, ledger = ledger_with(tmp_path / "control.sqlite3", 5)
    url = f"sqlite:///{tmp_path / 'control.sqlite3'}"
    archive = SqliteArchiveStore(tmp_path / "archive.sqlite3")

    assert archive_ledger(url, archive, evidence_token=TOKEN)["records"] == 5
    assert archive_ledger(url, archive, evidence_token=TOKEN)["records"] == 0
    ledger.append("decision", {"request_id": "r-5"}, token=TOKEN)
    assert archive_ledger(url, archive, evidence_token=TOKEN)["first_seq"] == 5

    notary = EvidenceNotary()
    checkpoint = notary.checkpoint(list(ledger)).to_dict()
    keys = {key_id: key.hex() for key_id, key in notary.public_keys.items()}
    verdict = verify_archive(archive, checkpoint=checkpoint, public_keys=keys)
    assert verdict["verdict"] == "INTACT" and verdict["records"] == 6
    database.close()


def test_verifier_detects_an_altered_archived_record(tmp_path):
    database, _ledger = ledger_with(tmp_path / "control.sqlite3", 3)
    archive = SqliteArchiveStore(tmp_path / "archive.sqlite3")
    archive_ledger(f"sqlite:///{tmp_path / 'control.sqlite3'}", archive, evidence_token=TOKEN)
    with sqlite3.connect(tmp_path / "archive.sqlite3") as raw:
        raw.execute("UPDATE decision_evidence SET payload_json = '{\"request_id\": \"x\"}' "
                    "WHERE seq = 1")
    verdict = verify_archive(archive)
    assert verdict["verdict"] == "COMPROMISED" and verdict["altered_records"] == [1]
    database.close()


def test_archiver_refuses_a_ledger_truncated_after_archiving(tmp_path):
    database, _ledger = ledger_with(tmp_path / "control.sqlite3", 3)
    url = f"sqlite:///{tmp_path / 'control.sqlite3'}"
    archive = SqliteArchiveStore(tmp_path / "archive.sqlite3")
    archive_ledger(url, archive, evidence_token=TOKEN)
    with sqlite3.connect(tmp_path / "control.sqlite3") as raw:
        raw.execute("DELETE FROM evidence WHERE seq = 2")
    with pytest.raises(ValueError, match="ARCHIVE_AHEAD_OF_LEDGER"):
        archive_ledger(url, archive, evidence_token=TOKEN)
    database.close()


def test_cli_run_does_one_full_pass(gateway, tmp_path, monkeypatch, capsys):
    gateway.post("/v1/imports", json=signed_import("via cli"))
    database, _ledger = ledger_with(tmp_path / "control.sqlite3", 2)
    monkeypatch.setenv("FSSAI_EVIDENCE_TOKEN", TOKEN)
    report_path = tmp_path / "run.json"
    code = main(["small", "run", "--archive", str(tmp_path / "archive.sqlite3"),
                 "--log", str(tmp_path / "import-log.sqlite3"),
                 "--database", f"sqlite:///{tmp_path / 'control.sqlite3'}",
                 "--output", str(report_path)])
    report = json.loads(report_path.read_text())
    assert code == 0
    assert report["ingest"]["imported"] == 1
    assert report["archive"]["records"] == 2
    assert report["verify"]["verdict"] == "INTACT"
    database.close()


# ---------------------------------------------------------------- choosing a tier


def test_small_workloads_get_the_small_tier_and_each_big_need_is_named():
    assert recommend(Workload(records_per_day=5_000))["tier"] == "small"
    shared = recommend(Workload(independent_consumers=3))
    assert shared["tier"] == "big" and shared["exceeded"] == ["independent_consumers"]
    assert recommend(Workload(high_availability=True))["exceeded"] == ["high_availability"]


@pytest.fixture
def clean_env(monkeypatch):
    for name in ("FSSAI_DATABASE_URL", "FSSAI_REDIS_URL", "FSSAI_KAFKA_BOOTSTRAP", "FSSAI_SCALE"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def codes(severity: str | None = None) -> set[str]:
    return {w.code for w in configuration_warnings() if severity in (None, w.severity)}


def test_sqlite_without_kafka_reports_local_durable_events(clean_env):
    clean_env.setenv("FSSAI_DATABASE_URL", "sqlite:///control.sqlite3")
    found = codes()
    assert "LOCAL_EVENTS" in found and "IN_MEMORY_EVENTS" not in found


def test_declared_tier_contradictions_are_reported(clean_env):
    clean_env.setenv("FSSAI_SCALE", "small")
    clean_env.setenv("FSSAI_KAFKA_BOOTSTRAP", "kafka:29092")
    assert "BROKER_IN_SMALL_TIER" in codes()
    clean_env.setenv("FSSAI_SCALE", "big")
    clean_env.delenv("FSSAI_KAFKA_BOOTSTRAP")
    clean_env.setenv("FSSAI_DATABASE_URL", "sqlite:///control.sqlite3")
    assert {"BIG_TIER_WITHOUT_BROKER", "BIG_TIER_ON_SQLITE"} <= codes()
    clean_env.setenv("FSSAI_SCALE", "medium")
    assert "UNKNOWN_SCALE_TIER" in codes("blocking")
