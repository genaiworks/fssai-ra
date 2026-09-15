"""Lifecycle gates run real checks and fail when their precondition is broken."""
from __future__ import annotations

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
