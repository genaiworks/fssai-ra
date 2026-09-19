"""Regression tests for the code-review findings on the lifecycle gates (C1, H1, H2, H6, M2, M6)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from fssaira.lifecycle import stages
from fssaira.pipeline import EVIDENCE_TOKEN

ROOT = Path(__file__).resolve().parents[2]


# -- C1: the digest covers the code that enforces, not only the facades -------

def _governed_copy(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    skip = shutil.ignore_patterns("__pycache__")
    for relative in ("src", "tests", "contract", "profiles", "packs", "deploy", "threats"):
        shutil.copytree(ROOT / relative, root / relative, ignore=skip)
    return root


def test_c1_deleting_a_real_check_in_the_executor_changes_the_digest(tmp_path):
    root = _governed_copy(tmp_path)
    before = stages.governed_digest(root)["sha256"]
    target = root / "src" / "fssaira" / "exact_action.py"
    target.write_text(target.read_text().replace("def validate_authorization(", "def validate_authorization_(", 1))
    assert stages.governed_digest(root)["sha256"] != before


@pytest.mark.parametrize("relative", ["tests/test_exact_action.py", "deploy/profiles/institutional.yaml",
                                      "threats/catalogue.yaml", "src/fssaira/lifecycle/stages.py"])
def test_c1_tests_gates_profiles_and_threats_are_governed(tmp_path, relative):
    root = _governed_copy(tmp_path)
    before = stages.governed_digest(root)["sha256"]
    path = root / relative
    path.write_text(path.read_text() + "\n# edited\n")
    assert stages.governed_digest(root)["sha256"] != before


def test_c1_a_pack_source_outside_the_repository_is_governed(tmp_path):
    root = _governed_copy(tmp_path)
    outside = tmp_path / "elsewhere" / "corporate.yaml"
    outside.parent.mkdir()
    shutil.copy(ROOT / "profiles" / "corporate_confidential_data.yaml", outside)
    manifest = root / "packs" / "corporate.pack.yaml"
    manifest.write_text(manifest.read_text().replace(
        "../profiles/corporate_confidential_data.yaml", str(outside)))
    before = stages.governed_digest(root)["sha256"]
    outside.write_text(outside.read_text() + "\n# edited outside the repository\n")
    assert stages.governed_digest(root)["sha256"] != before


# -- H1: partial or forged artifacts cannot authorize -------------------------

@pytest.fixture(scope="module")
def complete_artifact(tmp_path_factory):
    path = tmp_path_factory.mktemp("h1") / "falsify.json"
    path.write_text(json.dumps(stages.falsify(ROOT).to_dict()))
    return path


def test_h1_the_reviewers_minimal_forged_artifact_is_refused(tmp_path):
    forged = tmp_path / "forged.json"
    forged.write_text(json.dumps({"passed": True, "artifact": {
        "governed_digest": {"sha256": stages.governed_digest(ROOT)["sha256"]}}}))
    result = stages.operate(ROOT, falsify_artifact=forged, allow_not_run=True)
    assert not result.passed
    assert "partial falsification scope" in result.gate("change_returns_to_falsify").detail


@pytest.mark.parametrize("scope", [
    {"conference_only": ["F01"], "ablation": True},
    {"conference_only": None, "ablation": False},
])
def test_h1_a_partial_scope_cannot_authorize_operation_or_promotion(tmp_path, complete_artifact, scope):
    recorded = json.loads(complete_artifact.read_text())
    recorded["artifact"]["scope"] = scope
    partial = tmp_path / "partial.json"
    partial.write_text(json.dumps(recorded))
    assert not stages.operate(ROOT, falsify_artifact=partial, allow_not_run=True).passed
    promoted = stages.promote(ROOT, profile_path=ROOT / "deploy/profiles/teaching.yaml", falsify_artifact=partial)
    assert not promoted.gate("falsifiers_zero_counterexamples").passed


def test_h1_a_complete_current_artifact_authorizes_teaching(complete_artifact):
    promoted = stages.promote(ROOT, profile_path=ROOT / "deploy/profiles/teaching.yaml",
                              falsify_artifact=complete_artifact)
    assert promoted.passed, promoted.to_dict()


def test_h1_consequential_promotion_ignores_the_artifact_and_re_runs(complete_artifact):
    result = stages.promote(ROOT, profile_path=ROOT / "deploy/profiles/institutional.yaml",
                            falsify_artifact=complete_artifact, falsify_only=["F01"],
                            evidence_commands=[], rerun_conformance=False)
    gate = result.gate("falsifiers_zero_counterexamples")
    assert not gate.passed and "partial falsification scope" in gate.detail


# -- H2: nulls are not filled fields ------------------------------------------

def test_h2_a_frame_of_nulls_fails(tmp_path):
    path = tmp_path / "frame.yaml"
    path.write_text("".join(f"{name}:\n" for name in stages.FRAME_FIELDS))
    result = stages.frame(path)
    assert not result.passed
    assert set(result.gate("frame_complete").observed["missing"]) == set(stages.FRAME_FIELDS)


@pytest.mark.parametrize("body", ["- a\n- list\n", "just a string\n", ": : not yaml : :\n  - ["])
def test_h2_a_malformed_frame_fails_as_a_gate(tmp_path, body):
    path = tmp_path / "frame.yaml"
    path.write_text(body)
    assert not stages.frame(path).passed


# -- H6: credentials reachable from the model at any depth ---------------------

class _Holder:
    def __init__(self, value: object) -> None:
        self.value = value

    def method(self) -> object:
        return self.value


def _nested_model():
    class Model:
        def __init__(self) -> None:
            self.config = {"retries": 2, "auth": [_Holder(EVIDENCE_TOKEN)]}
    return Model()


def _closure_model():
    secret = EVIDENCE_TOKEN

    class Model:
        def __init__(self) -> None:
            self.callback = lambda: secret
    return Model()


def _bound_method_model():
    class Model:
        def __init__(self) -> None:
            self.fetch = _Holder(EVIDENCE_TOKEN).method
    return Model()


@pytest.mark.parametrize("factory", [_nested_model, _closure_model, _bound_method_model])
def test_h6_positive_controls_a_credential_planted_deep_in_the_model_fails_bind(factory):
    outcome = stages.check_no_model_holds_a_key(model=factory())
    assert not outcome.passed
    assert outcome.observed["leaks"]


def test_h6_the_real_model_passes_and_the_mediator_reference_is_reported():
    outcome = stages.check_no_model_holds_a_key()
    assert outcome.passed, outcome.detail
    assert outcome.observed["mediator_references"] == ["pep"]
    assert "not isolation" in outcome.detail


def test_h6_the_walker_does_not_enter_stop_objects():
    holder = _Holder(EVIDENCE_TOKEN)
    assert stages.find_reachable_secret(_Holder(holder), EVIDENCE_TOKEN)
    assert not stages.find_reachable_secret(_Holder(holder), EVIDENCE_TOKEN, stop=[holder])


# -- M6 and crashes ------------------------------------------------------------

def test_m6_zero_of_zero_is_not_complete():
    from fssaira.kernel.packs import Ratio

    assert not stages._full(Ratio(0, 0, "scenario"))
    assert stages._full(Ratio(3, 3, "scenario"))
    assert not stages._full(Ratio(2, 3, "scenario"))


def test_a_wrong_root_fails_falsify_as_a_gate(tmp_path):
    result = stages.falsify(tmp_path)
    assert not result.passed
    assert "could not run" in result.gate("falsifiers_zero_counterexamples").detail


def test_the_template_manifest_pointing_at_a_missing_source_is_a_failed_gate(tmp_path):
    manifest = tmp_path / "broken.pack.yaml"
    doc = yaml.safe_load((ROOT / "packs" / "corporate.pack.yaml").read_text())
    doc["sources"]["profiles"] = [str(tmp_path / "missing.yaml")]
    manifest.write_text(yaml.safe_dump(doc))
    result = stages.pack(ROOT, paths=[manifest])
    assert not result.passed and result.gate("pack_floor_passes").observed["failures"]
