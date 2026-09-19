"""Promotion runs exactly the gates a deployment profile requires, and refuses on any gap."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

from fssaira.conformance import memory_bundle
from fssaira.kernel.assurance import run_and_record
from fssaira.lifecycle import stages

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "deploy" / "profiles"
PASS = [[sys.executable, "-c", "pass"]]
FAIL = [[sys.executable, "-c", "import sys; sys.exit(3)"]]


@pytest.fixture(scope="module")
def falsify_artifact(tmp_path_factory):
    result = stages.falsify(ROOT)
    path = tmp_path_factory.mktemp("promote") / "falsify.json"
    path.write_text(json.dumps(result.to_dict()))
    return path


@pytest.fixture(scope="module")
def memory_record(tmp_path_factory):
    record = run_and_record("memory", memory_bundle())
    path = tmp_path_factory.mktemp("records") / "records.json"
    path.write_text(json.dumps([record.to_dict()]))
    return path


def test_teaching_promotes_with_a_passing_falsification(falsify_artifact):
    result = stages.promote(ROOT, profile_path=PROFILES / "teaching.yaml", falsify_artifact=falsify_artifact)
    assert result.passed, result.to_dict()
    assert [g.gate for g in result.gates] == [
        "deploy_profile_valid", "contract_complete", "failure_tests_exist", "falsifiers_zero_counterexamples"]


def test_teaching_without_falsification_is_refused():
    result = stages.promote(ROOT, profile_path=PROFILES / "teaching.yaml")
    assert not result.passed
    assert "fssaira falsify" in result.gate("falsifiers_zero_counterexamples").detail


def test_institutional_is_refused_for_every_missing_institutional_record(falsify_artifact):
    result = stages.promote(ROOT, profile_path=PROFILES / "institutional.yaml",
                            falsify_artifact=falsify_artifact, evidence_commands=PASS)
    assert not result.passed
    failed = {g.gate for g in result.gates if not g.passed}
    assert {"backend_conformance_current", "table4_obligations_signed"} <= failed
    assert result.gate("evidence_matches_fresh_run").passed
    assert result.gate("no_model_holds_a_key").passed
    assert result.gate("pack_floor_passes").passed


def test_a_real_conformance_record_passes_with_a_fresh_rerun(memory_record):
    outcome = stages.check_backend_conformance(["memory"], memory_record, allowed=["memory", "sqlite"])
    assert outcome.passed, outcome.detail
    assert outcome.observed["backends"]["memory"]["fresh_run_executed"] > 0


def test_a_record_for_another_backend_or_a_disallowed_backend_is_refused(tmp_path, memory_record):
    body = json.loads(memory_record.read_text())
    body[0]["backend"] = "sqlite"
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps(body))
    assert not stages.check_backend_conformance(["memory"], wrong).passed
    assert not stages.check_backend_conformance(["memory"], memory_record, allowed=["postgres"]).passed
    assert not stages.check_backend_conformance([], memory_record).passed


def test_a_tampered_implementation_digest_is_refused(tmp_path, memory_record):
    body = json.loads(memory_record.read_text())
    for key, value in list(body[0].items()):
        if "digest" in key and isinstance(value, str):
            body[0][key] = "0" * len(value)
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(body))
    assert not stages.check_backend_conformance(["memory"], tampered).passed


def test_a_failing_or_missing_regenerator_blocks_promotion(tmp_path):
    assert stages.check_evidence_matches_fresh_run(ROOT, PASS).passed
    assert not stages.check_evidence_matches_fresh_run(ROOT, FAIL).passed
    assert not stages.check_evidence_matches_fresh_run(ROOT, [["scripts/does_not_exist.py", "--check"]]).passed
    assert not stages.check_evidence_matches_fresh_run(ROOT, []).passed


def test_the_interface_inventory_must_name_a_control_and_owner_for_every_interface(tmp_path):
    assert not stages.check_interface_inventory(None).passed
    path = tmp_path / "interfaces.yaml"
    path.write_text(yaml.safe_dump({"interfaces": [
        {"name": "import-diode", "direction": "inward", "control": "certified one-way device",
         "owner": "Security owner"},
        {"name": "model-egress", "direction": "outward", "control": "", "owner": "Platform owner"},
    ]}))
    outcome = stages.check_interface_inventory(path)
    assert not outcome.passed and outcome.observed["uncontrolled"] == ["model-egress"]
    doc = yaml.safe_load(path.read_text())
    doc["interfaces"][1]["control"] = "egress proxy allowlist"
    path.write_text(yaml.safe_dump(doc))
    assert stages.check_interface_inventory(path).passed


def test_a_stale_falsification_blocks_promotion(tmp_path, falsify_artifact):
    recorded = json.loads(falsify_artifact.read_text())
    recorded["artifact"]["governed_digest"]["sha256"] = "f" * 64
    stale = tmp_path / "stale.json"
    stale.write_text(json.dumps(recorded))
    result = stages.promote(ROOT, profile_path=PROFILES / "teaching.yaml", falsify_artifact=stale)
    assert not result.passed
    assert "re-run stage 5" in result.gate("falsifiers_zero_counterexamples").detail


def test_an_invalid_profile_is_refused_before_any_gate(tmp_path):
    doc = yaml.safe_load((PROFILES / "institutional.yaml").read_text())
    doc["ablation_switches"] = "allowed_in_lab_only"
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(doc))
    result = stages.promote(ROOT, profile_path=bad)
    assert not result.passed
    assert [g.gate for g in result.gates] == ["deploy_profile_valid"]
