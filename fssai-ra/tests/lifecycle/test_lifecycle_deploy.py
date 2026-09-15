"""Deployment profiles cannot make a consequential deployment quietly weaker."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from fssaira.lifecycle.deploy import (
    CONSEQUENTIAL_GATES,
    GATE_IDS,
    DeployProfileError,
    load_deploy_profile,
    load_deploy_profiles,
)

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "deploy" / "profiles"


def _mutated(tmp_path: Path, name: str, **changes) -> Path:
    doc = yaml.safe_load((PROFILES / f"{name}.yaml").read_text())
    for dotted, value in changes.items():
        target = doc
        *parents, leaf = dotted.split("__")
        for key in parents:
            target = target.setdefault(key, {})
        target[leaf] = value
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(doc))
    return path


def test_the_three_shipped_profiles_load():
    profiles = load_deploy_profiles(PROFILES)
    assert set(profiles) == {"teaching", "institutional", "hardware-isolated"}
    assert profiles["teaching"].consequential is False
    assert profiles["institutional"].consequential is True
    assert profiles["hardware-isolated"].consequential is True


def test_every_profile_states_its_isolation_limit():
    for profile in load_deploy_profiles(PROFILES).values():
        assert profile.isolation_statement
    teaching = load_deploy_profiles(PROFILES)["teaching"]
    assert "same-OS-user" in teaching.isolation_statement


def test_consequential_gates_are_a_subset_of_known_gates():
    assert CONSEQUENTIAL_GATES <= GATE_IDS


@pytest.mark.parametrize("name", ["institutional", "hardware-isolated"])
def test_a_consequential_profile_cannot_enable_ablation(tmp_path, name):
    with pytest.raises(DeployProfileError, match="ablation"):
        load_deploy_profile(_mutated(tmp_path, name, ablation_switches="allowed_in_lab_only"))


@pytest.mark.parametrize("name", ["institutional", "hardware-isolated"])
def test_a_consequential_profile_cannot_drop_isolation_or_conformance(tmp_path, name):
    with pytest.raises(DeployProfileError, match="process isolation"):
        load_deploy_profile(_mutated(tmp_path, name, isolation__process_isolation_required=False))
    with pytest.raises(DeployProfileError, match="conformance"):
        load_deploy_profile(_mutated(tmp_path, name, backends__conformance_required=False))


@pytest.mark.parametrize("gate", sorted(CONSEQUENTIAL_GATES))
def test_a_consequential_profile_cannot_omit_a_mandatory_gate(tmp_path, gate):
    doc = yaml.safe_load((PROFILES / "institutional.yaml").read_text())
    doc["required_gates"] = [g for g in doc["required_gates"] if g != gate]
    path = tmp_path / "institutional.yaml"
    path.write_text(yaml.safe_dump(doc))
    with pytest.raises(DeployProfileError, match=gate):
        load_deploy_profile(path)


def test_unknown_gates_and_missing_fallback_are_refused(tmp_path):
    with pytest.raises(DeployProfileError, match="unknown gate"):
        load_deploy_profile(_mutated(tmp_path, "teaching", required_gates=["trust_me"]))
    with pytest.raises(DeployProfileError, match="fallback"):
        load_deploy_profile(_mutated(tmp_path, "teaching", fallback=""))
