"""Review finding H3: nulls and string booleans cannot weaken a deployment profile."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from fssaira.lifecycle.deploy import DeployProfileError, load_deploy_profile, load_deploy_profiles

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "deploy" / "profiles"


def _write(tmp_path: Path, doc: dict, name: str = "profile.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(doc))
    return path


def _institutional() -> dict:
    return yaml.safe_load((PROFILES / "institutional.yaml").read_text())


@pytest.mark.parametrize("mutate,message", [
    (lambda d: d.__setitem__("fallback", None), "fallback"),
    (lambda d: d["isolation"].__setitem__("statement", None), "isolation statement"),
    (lambda d: d["isolation"].__setitem__("process_isolation_required", "false"), "true or false"),
    (lambda d: d["backends"].__setitem__("conformance_required", "no"), "true or false"),
    (lambda d: d.__setitem__("consequential", "yes"), "true or false"),
    (lambda d: d.__setitem__("stage", "production-ish"), "stage must be one of"),
    (lambda d: d.__setitem__("isolation", "strict"), "must be a mapping"),
    (lambda d: d.__setitem__("required_gates", "contract_complete"), "list of non-empty strings"),
])
def test_loose_types_are_refused(tmp_path, mutate, message):
    doc = _institutional()
    mutate(doc)
    with pytest.raises(DeployProfileError, match=message):
        load_deploy_profile(_write(tmp_path, doc))


def test_the_reviewers_exact_weakened_profile_is_refused(tmp_path):
    doc = _institutional()
    doc["fallback"] = None
    doc["isolation"]["statement"] = None
    doc["isolation"]["process_isolation_required"] = "false"
    doc["backends"]["conformance_required"] = "no"
    with pytest.raises(DeployProfileError):
        load_deploy_profile(_write(tmp_path, doc))


def test_duplicate_profile_names_are_refused(tmp_path):
    shutil.copy(PROFILES / "teaching.yaml", tmp_path / "a.yaml")
    shutil.copy(PROFILES / "teaching.yaml", tmp_path / "b.yaml")
    with pytest.raises(DeployProfileError, match="duplicate"):
        load_deploy_profiles(tmp_path)


def test_a_non_mapping_document_is_refused(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- not\n- a\n- profile\n")
    with pytest.raises(DeployProfileError, match="mapping"):
        load_deploy_profile(path)
