"""A backend inherits no assurance until the same suites pass on it."""
from __future__ import annotations

import json
import shutil
from dataclasses import replace

import pytest

from fssaira.conformance import memory_bundle, sql_bundle
from fssaira.kernel.assurance import (
    AssuranceCode,
    AssuranceRefused,
    CheckOutcome,
    ConformanceRecord,
    assurance_status,
    implementation_digest,
    load_records,
    module_files,
    require_assurance,
    run_and_record,
)


@pytest.fixture(scope="module")
def memory_record():
    return run_and_record("memory", memory_bundle())


@pytest.fixture(scope="module")
def sqlite_record():
    return run_and_record("sqlite", sql_bundle())


def test_real_memory_and_sqlite_runs_confer_assurance(memory_record, sqlite_record):
    for backend, record in (("memory", memory_record), ("sqlite", sqlite_record)):
        assert record.executed and not record.failures, record.failures
        status = require_assurance(backend, record)
        assert status.assured and status.checks_executed == len(record.executed)
    assert memory_record.implementation_digest != sqlite_record.implementation_digest


def test_assurance_does_not_transfer_between_backends(memory_record):
    with pytest.raises(AssuranceRefused) as refused:
        require_assurance("sqlite", memory_record)
    assert refused.value.code == AssuranceCode.BACKEND_MISMATCH
    with pytest.raises(AssuranceRefused) as refused:
        require_assurance("sqlite", replace(memory_record, backend="sqlite"))
    assert refused.value.code == AssuranceCode.DIGEST_MISMATCH


def test_no_record_refuses():
    with pytest.raises(AssuranceRefused) as refused:
        require_assurance("memory", None)
    assert refused.value.code == AssuranceCode.NO_RECORD
    assert not assurance_status("redis", None).assured


def test_tampered_digest_refuses(sqlite_record):
    tampered = replace(sqlite_record, implementation_digest="sha256:" + "0" * 64)
    with pytest.raises(AssuranceRefused) as refused:
        require_assurance("sqlite", tampered)
    assert refused.value.code == AssuranceCode.DIGEST_MISMATCH


def test_code_changed_after_the_run_refuses(tmp_path, sqlite_record):
    copies = []
    for path in module_files(["fssaira.sql_backend", "fssaira.atomic_execution"]):
        target = tmp_path / path.name
        shutil.copy(path, target)
        copies.append(target)
    record = replace(sqlite_record, implementation_digest=implementation_digest(
        "sqlite", files=copies))
    assert require_assurance("sqlite", record, files=copies).assured
    copies[0].write_text(copies[0].read_text() + "\n# a one-line change\n")
    with pytest.raises(AssuranceRefused) as refused:
        require_assurance("sqlite", record, files=copies)
    assert refused.value.code == AssuranceCode.DIGEST_MISMATCH


def test_a_failing_check_refuses(memory_record):
    checks = list(memory_record.checks)
    index = next(i for i, c in enumerate(checks) if not c.skipped)
    checks[index] = CheckOutcome(checks[index].id, passed=False)
    with pytest.raises(AssuranceRefused) as refused:
        require_assurance("memory", replace(memory_record, checks=tuple(checks)))
    assert refused.value.code == AssuranceCode.CHECK_FAILED
    assert checks[index].id in refused.value.detail


def test_all_skipped_or_stale_suite_refuses(memory_record):
    skipped = tuple(CheckOutcome(c.id, True, True) for c in memory_record.checks)
    with pytest.raises(AssuranceRefused) as refused:
        require_assurance("memory", replace(memory_record, checks=skipped))
    assert refused.value.code == AssuranceCode.NO_EXECUTED_CHECKS
    with pytest.raises(AssuranceRefused) as refused:
        require_assurance("memory", replace(memory_record, suite_id="fssaira.conformance@old"))
    assert refused.value.code == AssuranceCode.SUITE_MISMATCH


def test_records_round_trip_through_json(tmp_path, memory_record, sqlite_record):
    path = tmp_path / "records.json"
    path.write_text(json.dumps([memory_record.to_dict(), sqlite_record.to_dict()]))
    loaded = load_records(path)
    assert loaded["memory"] == memory_record and loaded["sqlite"] == sqlite_record
    with pytest.raises(AssuranceRefused) as refused:
        ConformanceRecord.from_dict({"backend": "memory"})
    assert refused.value.code == AssuranceCode.MALFORMED


# -- wiring into runtime construction ------------------------------------------


@pytest.fixture
def factory_env(monkeypatch):
    import os

    from fssaira import runtime_factory

    for name in list(os.environ):
        if name.startswith("FSSAI_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FSSAI_MODEL_PROBE", "0")
    return monkeypatch, runtime_factory


def _production(monkeypatch, runtime_factory):
    # Isolate the assurance gate from the teaching-defaults gate, which has its own tests.
    monkeypatch.setenv("FSSAI_DEPLOYMENT_PROFILE", "production")
    monkeypatch.setattr(runtime_factory, "configuration_warnings", lambda: [])


def _write(tmp_path, *records):
    path = tmp_path / "conformance-records.json"
    path.write_text(json.dumps([r.to_dict() for r in records]))
    return str(path)


def test_teaching_profile_records_status_without_enforcing(factory_env):
    _monkeypatch, runtime_factory = factory_env
    plane = runtime_factory.build_control_plane(profile_path="profiles/student_support.yaml")
    assert plane.backend_assurance["memory"]["code"] == "NOT_REQUIRED_TEACHING"
    assert plane.backend_assurance["memory"]["assured"] is False


def test_production_refuses_a_backend_without_a_record(factory_env):
    monkeypatch, runtime_factory = factory_env
    _production(monkeypatch, runtime_factory)
    with pytest.raises(RuntimeError, match=AssuranceCode.NO_RECORD):
        runtime_factory.build_control_plane(profile_path="profiles/student_support.yaml")


def test_production_starts_with_a_current_record_and_refuses_a_tampered_one(
        factory_env, tmp_path, memory_record):
    monkeypatch, runtime_factory = factory_env
    _production(monkeypatch, runtime_factory)
    monkeypatch.setenv("FSSAI_CONFORMANCE_RECORDS", _write(tmp_path, memory_record))
    plane = runtime_factory.build_control_plane(profile_path="profiles/student_support.yaml")
    assert plane.backend_assurance["memory"]["assured"] is True

    tampered = replace(memory_record, implementation_digest="sha256:" + "f" * 64)
    monkeypatch.setenv("FSSAI_CONFORMANCE_RECORDS", _write(tmp_path, tampered))
    with pytest.raises(RuntimeError, match=AssuranceCode.DIGEST_MISMATCH):
        runtime_factory.build_control_plane(profile_path="profiles/student_support.yaml")


def test_production_sqlite_needs_its_own_record(factory_env, tmp_path, memory_record,
                                                sqlite_record):
    monkeypatch, runtime_factory = factory_env
    _production(monkeypatch, runtime_factory)
    monkeypatch.setenv("FSSAI_DATABASE_URL", f"sqlite:///{tmp_path / 'state.db'}")
    monkeypatch.setenv("FSSAI_CONFORMANCE_RECORDS", _write(tmp_path, memory_record))
    with pytest.raises(RuntimeError, match=AssuranceCode.NO_RECORD):
        runtime_factory.build_control_plane(profile_path="profiles/student_support.yaml")
    monkeypatch.setenv("FSSAI_CONFORMANCE_RECORDS",
                       _write(tmp_path, memory_record, sqlite_record))
    plane = runtime_factory.build_control_plane(profile_path="profiles/student_support.yaml")
    assert plane.backend_assurance["sqlite"]["assured"] is True
