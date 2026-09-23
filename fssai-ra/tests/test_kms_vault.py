"""Custody with key-encryption keys held by Vault Transit.

Runs against a real Vault when ``FSSAI_TEST_VAULT_ADDR`` and
``FSSAI_TEST_VAULT_TOKEN`` are set (dev server: ``vault server -dev`` plus
``vault secrets enable transit``); otherwise skipped.
"""
import os
import secrets
import uuid

import pytest

from fssaira.custody_store import SqlCustodyStore
from fssaira.encrypted_records import EncryptedRecordSource, RecordNotFound
from fssaira.key_custody import CustodyDenied, KeyCustody
from fssaira.kms_vault import VaultTransitKeyWrapper

ADDR, TOKEN = os.getenv("FSSAI_TEST_VAULT_ADDR"), os.getenv("FSSAI_TEST_VAULT_TOKEN")
pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(not (ADDR and TOKEN), reason="set FSSAI_TEST_VAULT_ADDR/TOKEN")]
FIELDS = {"patient_name": "synthetic-health-record", "diagnosis": "highly-restricted"}


def wrapper(prefix):
    return VaultTransitKeyWrapper(ADDR, TOKEN, key_prefix=prefix)


def open_all(store, prefix):
    custody = KeyCustody(key_wrapper=wrapper(prefix), store=store)
    w = custody.register_principal("ingest", {"encrypt"})
    r = custody.register_principal("gate", {"decrypt"})
    a = custody.register_principal("admin", {"erase", "rotate", "backup"})
    return custody, EncryptedRecordSource(FIELDS, custody, writer_credential=w,
                                          reader_credential=r, store=store), a


def test_data_keys_are_wrapped_by_vault_and_survive_restart(tmp_path):
    prefix = "t" + uuid.uuid4().hex[:8]
    store = SqlCustodyStore.open(f"sqlite:///{tmp_path / 'c.sqlite'}")
    custody, records, _ = open_all(store, prefix)
    records.load("patient-1", {"patient_name": "Alice Example", "diagnosis": "SYNTHETIC-A"})
    wrapped = custody._wrapped[("patient-1", "synthetic-health-record")]
    assert wrapped.body.startswith(b"vault:v1:") and wrapped.nonce == b""
    assert custody._master is None  # this process never held a key-encryption key

    _c2, restarted, _ = open_all(SqlCustodyStore.open(f"sqlite:///{tmp_path / 'c.sqlite'}"), prefix)
    assert restarted.fetch("patient-1", ["patient_name"]) == {"patient_name": "Alice Example"}


def test_rotation_rewraps_inside_vault(tmp_path):
    prefix = "t" + uuid.uuid4().hex[:8]
    store = SqlCustodyStore.open(f"sqlite:///{tmp_path / 'c.sqlite'}")
    custody, records, admin = open_all(store, prefix)
    records.load("patient-1", {"patient_name": "Alice Example"})
    records.load("patient-2", {"patient_name": "Bob Example"})
    assert custody.rotate_kek(admin, "synthetic-health-record") == 2
    for subject in ("patient-1", "patient-2"):
        assert custody._wrapped[(subject, "synthetic-health-record")].body.startswith(b"vault:v2:")
    _c2, restarted, _ = open_all(SqlCustodyStore.open(f"sqlite:///{tmp_path / 'c.sqlite'}"), prefix)
    assert restarted.fetch("patient-2", ["patient_name"]) == {"patient_name": "Bob Example"}


def test_a_wrapped_key_moved_to_another_subject_does_not_open(tmp_path):
    prefix = "t" + uuid.uuid4().hex[:8]
    custody, records, _ = open_all(SqlCustodyStore.open(f"sqlite:///{tmp_path / 'c.sqlite'}"), prefix)
    records.load("patient-1", {"patient_name": "Alice Example"})
    records.load("patient-2", {"patient_name": "Bob Example"})
    key = ("patient-2", "synthetic-health-record")
    custody._wrapped[key] = custody._wrapped[("patient-1", "synthetic-health-record")]
    with pytest.raises(CustodyDenied) as exc:
        records.fetch("patient-2", ["patient_name"])
    assert exc.value.code == "CUSTODY_KEY_UNWRAP_FAILED"


def test_erasure_still_destroys_the_subject(tmp_path):
    prefix = "t" + uuid.uuid4().hex[:8]
    custody, records, admin = open_all(SqlCustodyStore.open(f"sqlite:///{tmp_path / 'c.sqlite'}"), prefix)
    records.load("patient-1", {"patient_name": "Alice Example"})
    custody.destroy_subject(admin, "patient-1", erased_by="dpo", reason="request")
    with pytest.raises(RecordNotFound):
        records.fetch("patient-1", ["patient_name"])


def test_a_revoked_token_cannot_unwrap(tmp_path):
    prefix = "t" + uuid.uuid4().hex[:8]
    store = SqlCustodyStore.open(f"sqlite:///{tmp_path / 'c.sqlite'}")
    _c, records, _ = open_all(store, prefix)
    records.load("patient-1", {"patient_name": "Alice Example"})
    bad = KeyCustody(key_wrapper=VaultTransitKeyWrapper(ADDR, "not-a-valid-token",
                                                        key_prefix=prefix), store=store)
    reader = bad.register_principal("gate", {"decrypt"})
    source = EncryptedRecordSource(FIELDS, bad, writer_credential="", reader_credential=reader,
                                   store=store)
    with pytest.raises(CustodyDenied):
        source.fetch("patient-1", ["patient_name"])


def test_custody_refuses_both_a_master_key_and_a_key_service():
    with pytest.raises(ValueError):
        KeyCustody(master_seed=secrets.token_bytes(32), key_wrapper=wrapper("x"))
