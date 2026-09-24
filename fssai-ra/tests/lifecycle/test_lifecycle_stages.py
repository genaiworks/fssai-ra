"""Lifecycle gates run real checks and fail when their precondition is broken."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from fssaira.lifecycle import stages
from fssaira.planes import Plane

ROOT = Path(__file__).resolve().parents[2]


# -- frame -----------------------------------------------------------------

def _frame(tmp_path: Path, **fields) -> Path:
    body = {
        "capability": "transcript correction",
        "protected_asset": "a student's academic record",
        "harm": "a wrong grade on a transcript",
        "accountable_owner": "registrar",
        "manual_fallback": "paper correction form reviewed by the registrar",
        **fields,
    }
    path = tmp_path / "frame.yaml"
    path.write_text(yaml.safe_dump(body))
    return path


def test_a_complete_frame_passes_and_is_digested(tmp_path):
    result = stages.frame(_frame(tmp_path))
    assert result.passed
    assert len(result.artifact["digest"]) == 64


@pytest.mark.parametrize("name", stages.FRAME_FIELDS)
def test_an_empty_framing_field_fails(tmp_path, name):
    result = stages.frame(_frame(tmp_path, **{name: ""}))
    assert not result.passed
    assert name in result.gate("frame_complete").detail


def test_framing_several_capabilities_at_once_fails(tmp_path):
    path = tmp_path / "frame.yaml"
    path.write_text(yaml.safe_dump({"capabilities": [{"capability": "a"}, {"capability": "b"}]}))
    assert not stages.frame(path).passed


# -- contract --------------------------------------------------------------

def test_the_repository_contract_stage_passes_and_writes_the_register(tmp_path):
    out = tmp_path / "claims_register.yaml"
    result = stages.contract(ROOT, register_out=out)
    assert result.passed, result.to_dict()
    doc = yaml.safe_load(out.read_text())
    assert doc["counts"] == result.artifact["counts"]
    assert doc["counts"]["unverified"] == 0


def _copy_contract_repo(tmp_path: Path) -> Path:
    """A throwaway copy holding what the contract stage reads: contract, tests, sources."""
    root = tmp_path / "repo"
    skip = shutil.ignore_patterns("__pycache__")
    shutil.copytree(ROOT / "contract", root / "contract")
    shutil.copytree(ROOT / "tests", root / "tests", ignore=skip)
    shutil.copytree(ROOT / "src", root / "src", ignore=skip)
    return root


def test_a_deleted_failure_test_fails_the_contract_stage(tmp_path):
    root = _copy_contract_repo(tmp_path)
    target = root / "tests" / "test_exact_action.py"
    target.write_text(target.read_text().replace(
        "def test_requester_cannot_approve_own_proposal", "def test_renamed_away"))
    result = stages.contract(root)
    assert not result.passed
    assert "test_requester_cannot_approve_own_proposal" in result.gate("contract_complete").detail


def test_an_emptied_contract_field_fails_the_contract_stage(tmp_path):
    root = _copy_contract_repo(tmp_path)
    path = root / "contract" / "capabilities" / "action.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["capabilities"][0]["accountable_owner"] = ""
    path.write_text(yaml.safe_dump(doc))
    result = stages.contract(root)
    assert not result.passed
    assert "open governance decision" in result.gate("contract_complete").detail


# -- pack ------------------------------------------------------------------

def test_the_repository_pack_stage_passes_with_every_profile_on_the_full_floor():
    result = stages.pack(ROOT)
    gate = result.gate("pack_floor_passes")
    assert result.passed, gate.detail
    assert gate.observed["denominator"] == gate.observed["loaded"] == 5
    # Every shipped profile declares controls and review capacity, so none is exempted.
    exemptions = [e for items in gate.observed["floor_exemptions"].values() for e in items]
    assert exemptions == []
    assert all(p["limits"] for p in result.artifact["packs"])


def test_the_template_pack_is_refused_until_it_is_filled():
    result = stages.pack(ROOT, paths=[ROOT / "packs" / stages.TEMPLATE_PACK])
    assert not result.passed
    assert result.gate("pack_floor_passes").observed["failures"]


def test_a_pack_that_drifts_from_its_profile_is_refused(tmp_path):
    source = ROOT / "packs" / "corporate.pack.yaml"
    doc = yaml.safe_load(source.read_text())
    doc["purposes"] = [*doc["purposes"], "purpose_the_runtime_never_enforces"]
    drifted = tmp_path / "corporate.pack.yaml"
    text = yaml.safe_dump(doc)
    drifted.write_text(text.replace("../profiles/", str(ROOT / "profiles") + "/"))
    result = stages.pack(ROOT, paths=[drifted])
    assert not result.passed


def test_pack_evidence_regenerates_for_one_pack():
    result = stages.pack(ROOT, paths=[ROOT / "packs" / "corporate.pack.yaml"], evaluate=True)
    gate = result.gate("pack_evidence_regenerates")
    assert gate.passed, gate.detail
    assert gate.observed["incomplete"] == []


# -- bind ------------------------------------------------------------------

def test_the_repository_bind_stage_passes():
    result = stages.bind(ROOT)
    assert result.passed, result.to_dict()
    assert result.gate("no_model_holds_a_key").observed["checked"] >= 3


def test_positive_control_a_model_component_taking_a_key_fails_bind():
    class LeakyModel:
        def __init__(self, prompt: str, signing_key: bytes) -> None:
            self.prompt, self.signing_key = prompt, signing_key

    import sys
    import types

    module = types.ModuleType("leaky_model_fixture")
    module.LeakyModel = LeakyModel  # type: ignore[attr-defined]
    sys.modules["leaky_model_fixture"] = module
    try:
        plane = Plane("intelligence", "untrusted", (), ("leaky_model_fixture:LeakyModel",), untrusted=True)
        outcome = stages.check_no_model_holds_a_key([plane])
    finally:
        del sys.modules["leaky_model_fixture"]
    assert not outcome.passed
    assert "signing_key" in outcome.detail


# -- governed digest -------------------------------------------------------

def test_the_governed_digest_is_stable_and_detects_edits_renames_and_deletions(tmp_path):
    root = tmp_path / "repo"
    for relative in ("src/fssaira/kernel", "src/fssaira/mediators", "src/fssaira/planes",
                     "contract", "profiles"):
        shutil.copytree(ROOT / relative, root / relative, ignore=shutil.ignore_patterns("__pycache__"))
    first = stages.governed_digest(root)
    assert first == stages.governed_digest(root)
    assert first["files"] > 10

    contract = root / "contract" / "capabilities" / "action.yaml"
    original = contract.read_text()
    contract.write_text(original.replace("Program registrar", "Program registrar (acting)"))
    edited = stages.governed_digest(root)
    assert edited["sha256"] != first["sha256"]

    contract.write_text(original)
    assert stages.governed_digest(root) == first
    contract.rename(contract.with_name("action-renamed.yaml"))
    assert stages.governed_digest(root)["sha256"] != first["sha256"]


def test_pycache_does_not_change_the_governed_digest(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(ROOT / "src/fssaira/kernel", root / "src/fssaira/kernel",
                    ignore=shutil.ignore_patterns("__pycache__"))
    before = stages.governed_digest(root)
    cache = root / "src/fssaira/kernel/__pycache__"
    cache.mkdir(exist_ok=True)
    (cache / "contract.cpython-314.pyc").write_bytes(b"\x00junk")
    assert stages.governed_digest(root) == before


# -- falsify ---------------------------------------------------------------

def test_the_falsify_stage_holds_with_a_live_positive_control():
    from fssaira import falsification

    first = falsification.FALSIFIERS[0].id
    result = stages.falsify(ROOT, include_ablation=True, conference_only=[first])
    gate = result.gate("falsifiers_zero_counterexamples")
    assert gate.passed, gate.detail
    assert gate.observed["thesis_counterexamples"] == 0
    assert gate.observed["positive_control_violations"] > 0
    assert result.gate("ablations_restore_harm").passed
    assert result.artifact["governed_digest"] == stages.governed_digest(ROOT)


# -- operate ---------------------------------------------------------------

@pytest.fixture(scope="module")
def falsify_artifact(tmp_path_factory):

    result = stages.falsify(ROOT)
    path = tmp_path_factory.mktemp("falsify") / "falsify.json"
    path.write_text(json.dumps(result.to_dict()))
    return path


def test_operate_fails_when_live_gates_did_not_run_unless_explicitly_allowed(falsify_artifact):
    result = stages.operate(ROOT, falsify_artifact=falsify_artifact)
    assert not result.passed
    assert result.gate("live_gates_run").observed["not_run"] == [
        "reconciliation_clear", "review_capacity_not_breached"]


def test_operate_without_a_falsification_artifact_fails():
    result = stages.operate(ROOT)
    assert not result.passed
    assert "fssaira falsify" in result.gate("change_returns_to_falsify").detail


def test_operate_passes_when_nothing_changed_and_names_what_it_did_not_run(falsify_artifact):
    result = stages.operate(ROOT, allow_not_run=True, falsify_artifact=falsify_artifact)
    assert result.passed, result.to_dict()
    assert {item["gate"] for item in result.artifact["not_run"]} == {
        "reconciliation_clear", "review_capacity_not_breached"}


def test_a_changed_configuration_returns_to_falsify(tmp_path, falsify_artifact):
    recorded = json.loads(falsify_artifact.read_text())
    recorded["artifact"]["governed_digest"]["sha256"] = "0" * 64
    stale = tmp_path / "stale.json"
    stale.write_text(json.dumps(recorded))
    result = stages.operate(ROOT, falsify_artifact=stale)
    assert not result.passed
    assert "return to stage 5" in result.gate("change_returns_to_falsify").detail


def test_a_failed_falsification_run_cannot_authorize_operation(tmp_path, falsify_artifact):
    recorded = json.loads(falsify_artifact.read_text())
    recorded["passed"] = False
    failed = tmp_path / "failed.json"
    failed.write_text(json.dumps(recorded))
    assert not stages.operate(ROOT, falsify_artifact=failed).passed


def test_pending_reconciliation_blocks_operation(falsify_artifact):
    class Executor:
        def __init__(self, pending: int) -> None:
            self._pending = pending

        def pending_outcome_count(self) -> int:
            return self._pending

    assert stages.operate(ROOT, allow_not_run=True, falsify_artifact=falsify_artifact, executor=Executor(0)).passed
    blocked = stages.operate(ROOT, allow_not_run=True, falsify_artifact=falsify_artifact, executor=Executor(2))
    assert not blocked.passed
    assert blocked.gate("reconciliation_clear").observed["pending_outcomes"] == 2


def test_a_real_fresh_executor_has_nothing_to_reconcile(falsify_artifact):
    from fssaira import AccountableExecutor, CaseRegister, EvidenceLedger

    executor = AccountableExecutor(CaseRegister({}), EvidenceLedger("t"), "t")
    assert stages.operate(ROOT, allow_not_run=True, falsify_artifact=falsify_artifact, executor=executor).passed


def test_a_saturated_reviewer_blocks_operation(falsify_artifact):
    from fssaira.oversight import OversightMonitor, ReviewLoadPolicy

    idle = OversightMonitor(ReviewLoadPolicy(max_approvals_per_window=2, second_reviewer_after=None))
    assert stages.operate(ROOT, allow_not_run=True, falsify_artifact=falsify_artifact, monitor=idle).passed

    busy = OversightMonitor(ReviewLoadPolicy(max_approvals_per_window=2, second_reviewer_after=None))
    for n in range(2):
        busy.admit(reviewer="officer-1", request_id=f"r-{n}", now=1_000.0 + n, presented_at=0.0)
    result = stages.operate(ROOT, allow_not_run=True, falsify_artifact=falsify_artifact, monitor=busy)
    assert not result.passed
    assert result.gate("review_capacity_not_breached").observed["headroom"] == 0.0
