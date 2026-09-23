"""Custody keys, erasures and encrypted rows survive a restart; plaintext never persists."""
import os
import secrets

import pytest

from fssaira.custody_store import SqlCustodyStore, load_master_key
from fssaira.encrypted_records import EncryptedRecordSource, RecordNotFound
from fssaira.evidence_notary import EvidenceNotary
from fssaira.key_custody import CustodyDenied, KeyCustody

FIELDS = {"patient_name": "synthetic-health-record", "diagnosis": "highly-restricted"}


def open_all(path, master):
    store = SqlCustodyStore.open(f"sqlite:///{path}")
    custody = KeyCustody(master_seed=master, store=store)
    writer = custody.register_principal("ingest", {"encrypt"})
    reader = custody.register_principal("gate", {"decrypt"})
    admin = custody.register_principal("admin", {"erase", "rotate", "backup"})
    records = EncryptedRecordSource(FIELDS, custody, writer_credential=writer,
                                    reader_credential=reader, store=store)
    return custody, records, admin


def test_records_are_readable_after_a_restart(tmp_path):
    master = secrets.token_bytes(32)
    _custody, records, _admin = open_all(tmp_path / "c.sqlite", master)
    records.load("patient-1", {"patient_name": "Alice Example", "diagnosis": "SYNTHETIC-A"})

    _custody2, restarted, _ = open_all(tmp_path / "c.sqlite", master)
    assert restarted.fetch("patient-1", ["patient_name", "diagnosis"]) == {
        "patient_name": "Alice Example", "diagnosis": "SYNTHETIC-A"}
    database_bytes = b"".join(p.read_bytes() for p in tmp_path.iterdir())
    assert b"Alice Example" not in database_bytes


def test_a_new_version_continues_after_restart(tmp_path):
    master = secrets.token_bytes(32)
    _c, records, _a = open_all(tmp_path / "c.sqlite", master)
    records.load("patient-1", {"patient_name": "Alice Example"})
    _c2, restarted, _a2 = open_all(tmp_path / "c.sqlite", master)
    restarted.load("patient-1", {"patient_name": "Alice Renamed"})
    _c3, again, _a3 = open_all(tmp_path / "c.sqlite", master)
    assert again.fetch("patient-1", ["patient_name"]) == {"patient_name": "Alice Renamed"}


def test_erasure_is_permanent_across_restarts(tmp_path):
    master = secrets.token_bytes(32)
    custody, records, admin = open_all(tmp_path / "c.sqlite", master)
    records.load("patient-1", {"patient_name": "Alice Example"})
    records.load("patient-2", {"patient_name": "Bob Example"})
    custody.destroy_subject(admin, "patient-1", erased_by="dpo", reason="request")

    custody2, restarted, _ = open_all(tmp_path / "c.sqlite", master)
    assert custody2.is_destroyed("patient-1")
    assert [e.subject for e in custody2.journal] == ["patient-1"]
    with pytest.raises(RecordNotFound):
        restarted.fetch("patient-1", ["patient_name"])
    assert restarted.fetch("patient-2", ["patient_name"]) == {"patient_name": "Bob Example"}


def test_key_rotation_persists(tmp_path):
    master = secrets.token_bytes(32)
    custody, records, admin = open_all(tmp_path / "c.sqlite", master)
    records.load("patient-1", {"patient_name": "Alice Example"})
    assert custody.rotate_kek(admin, "synthetic-health-record") == 1
    custody2, restarted, _ = open_all(tmp_path / "c.sqlite", master)
    assert custody2._current_kek_generation("synthetic-health-record") == 2
    assert restarted.fetch("patient-1", ["patient_name"]) == {"patient_name": "Alice Example"}


def test_the_database_alone_cannot_decrypt(tmp_path):
    _c, records, _a = open_all(tmp_path / "c.sqlite", secrets.token_bytes(32))
    records.load("patient-1", {"patient_name": "Alice Example"})
    _c2, stolen, _ = open_all(tmp_path / "c.sqlite", secrets.token_bytes(32))
    # The wrapped key does not open under any other master key.
    with pytest.raises(CustodyDenied) as exc:
        stolen.fetch("patient-1", ["patient_name"])
    assert exc.value.code == "CUSTODY_KEY_UNWRAP_FAILED"


def test_durable_custody_refuses_to_invent_a_master_key(tmp_path):
    store = SqlCustodyStore.open(f"sqlite:///{tmp_path / 'c.sqlite'}")
    with pytest.raises(ValueError, match="master key"):
        KeyCustody(store=store)


def test_restore_is_persisted_with_the_journal(tmp_path):
    master = secrets.token_bytes(32)
    custody, records, admin = open_all(tmp_path / "c.sqlite", master)
    records.load("patient-1", {"patient_name": "Alice Example"})
    backup = custody.backup(admin)
    custody.destroy_subject(admin, "patient-1", erased_by="dpo", reason="request")
    custody.restore(admin, backup, custody.journal)  # replaying the journal re-erases
    custody2, restarted, _ = open_all(tmp_path / "c.sqlite", master)
    assert custody2.is_destroyed("patient-1")
    assert not custody2.has_key("patient-1", "synthetic-health-record")


def test_master_key_file_must_be_private(tmp_path):
    key = tmp_path / "master.key"
    key.write_text(secrets.token_hex(32))
    os.chmod(key, 0o644)
    with pytest.raises(PermissionError):
        load_master_key(key)
    os.chmod(key, 0o600)
    assert len(load_master_key(key)) == 32
    key.write_text("too-short")
    with pytest.raises(ValueError):
        load_master_key(key)


def test_notary_key_survives_restart(tmp_path):
    key = tmp_path / "notary.key"
    key.write_text(secrets.token_hex(32))
    os.chmod(key, 0o600)
    assert EvidenceNotary.from_key_file(key).public_keys == \
        EvidenceNotary.from_key_file(key).public_keys


def test_ingest_credential_still_cannot_decrypt_after_restart(tmp_path):
    master = secrets.token_bytes(32)
    custody, records, _ = open_all(tmp_path / "c.sqlite", master)
    records.load("patient-1", {"patient_name": "Alice Example"})
    custody2, restarted, _ = open_all(tmp_path / "c.sqlite", master)
    writer = custody2.register_principal("ingest-2", {"encrypt"})
    row = restarted._rows[("patient-1", "patient_name")]
    with pytest.raises(CustodyDenied):
        custody2.decrypt(writer, row, subject="patient-1", field="patient_name")
