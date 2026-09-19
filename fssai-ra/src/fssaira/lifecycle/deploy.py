"""Deployment profiles: which gates a promotion must pass, and what is forbidden.

A profile is declarative (``deploy/profiles/*.yaml``). The loader enforces the
rules that make "consequential" mean something:

* a consequential profile forbids ablation switches;
* it requires process isolation and backend conformance;
* it requires every consequential gate in :data:`CONSEQUENTIAL_GATES`.

Types are strict. A YAML null is not a fallback, and the string ``"false"`` is
not a boolean. A profile cannot quietly drop a gate that the paper makes
mandatory.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

#: Every gate a profile may name. Implementations live in :mod:`fssaira.lifecycle.stages`.
GATE_IDS: frozenset[str] = frozenset({
    "contract_complete",
    "failure_tests_exist",
    "claims_register_no_unverified",
    "pack_floor_passes",
    "no_model_holds_a_key",
    "falsifiers_zero_counterexamples",
    "ablations_restore_harm",
    "backend_conformance_current",
    "evidence_matches_fresh_run",
    "table4_obligations_signed",
    "interface_inventory_owned",
})

#: Gates no consequential profile may omit.
CONSEQUENTIAL_GATES: frozenset[str] = frozenset({
    "contract_complete",
    "failure_tests_exist",
    "claims_register_no_unverified",
    "pack_floor_passes",
    "no_model_holds_a_key",
    "falsifiers_zero_counterexamples",
    "ablations_restore_harm",
    "backend_conformance_current",
    "evidence_matches_fresh_run",
    "table4_obligations_signed",
})

#: Paper §9.3: teaching sandbox, shadow pilot, bounded operational pilot.
STAGES: frozenset[str] = frozenset({"sandbox", "shadow_pilot", "bounded_operational_pilot"})
_ABLATION_VALUES = frozenset({"forbidden", "allowed_in_lab_only"})


class DeployProfileError(ValueError):
    """The deployment profile would permit something the architecture forbids."""


@dataclass(frozen=True)
class DeployProfile:
    name: str
    stage: str
    consequential: bool
    ablation_switches: str
    process_isolation_required: bool
    conformance_required: bool
    allowed_backends: tuple[str, ...]
    required_gates: tuple[str, ...]
    fallback: str
    isolation_statement: str


def _text(mapping: dict, key: str, where: str, message: str | None = None) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DeployProfileError(f"{where}: {message or f'{key!r} must be a non-empty string'}")
    return value.strip()


def _flag(mapping: dict, key: str, where: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise DeployProfileError(f"{where}: {key!r} must be true or false, not {value!r}")
    return value


def _section(doc: dict, key: str, where: str) -> dict[str, Any]:
    value = doc.get(key)
    if not isinstance(value, dict):
        raise DeployProfileError(f"{where}: {key!r} must be a mapping")
    return value


def _strings(value: Any, where: str, key: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise DeployProfileError(f"{where}: {key!r} must be a list of non-empty strings")
    return tuple(v.strip() for v in value)


def load_deploy_profile(path: Path) -> DeployProfile:
    """Load and validate one deployment profile."""
    path = Path(path)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise DeployProfileError(f"{path.name}: a deployment profile must be a mapping")
    name = _text(doc, "profile", path.name, "profile has no name")
    consequential = _flag(doc, "consequential", name)
    stage = _text(doc, "stage", name)
    if stage not in STAGES:
        raise DeployProfileError(f"{name}: stage must be one of {sorted(STAGES)}, not {stage!r}")
    ablation = _text(doc, "ablation_switches", name)
    if ablation not in _ABLATION_VALUES:
        raise DeployProfileError(f"{name}: ablation_switches must be one of {sorted(_ABLATION_VALUES)}")
    isolation = _section(doc, "isolation", name)
    backends = _section(doc, "backends", name)
    gates = _strings(doc.get("required_gates"), name, "required_gates")
    unknown = sorted(set(gates) - GATE_IDS)
    if unknown:
        raise DeployProfileError(f"{name}: unknown gate(s) {unknown}")
    fallback = _text(doc, "fallback", name, "a profile without a manual fallback cannot fail secure")
    statement = _text(isolation, "statement", name,
                      "the isolation statement is required, even when isolation is not")

    profile = DeployProfile(
        name=name,
        stage=stage,
        consequential=consequential,
        ablation_switches=ablation,
        process_isolation_required=_flag(isolation, "process_isolation_required", name),
        conformance_required=_flag(backends, "conformance_required", name),
        allowed_backends=_strings(backends.get("allowed"), name, "backends.allowed"),
        required_gates=gates,
        fallback=fallback,
        isolation_statement=statement,
    )
    if profile.consequential:
        if profile.ablation_switches != "forbidden":
            raise DeployProfileError(f"{name}: a consequential profile must forbid ablation switches")
        if not profile.process_isolation_required:
            raise DeployProfileError(f"{name}: a consequential profile must require process isolation")
        if not profile.conformance_required:
            raise DeployProfileError(f"{name}: a consequential profile must require backend conformance")
        missing = sorted(CONSEQUENTIAL_GATES - set(profile.required_gates))
        if missing:
            raise DeployProfileError(f"{name}: a consequential profile cannot omit gate(s) {missing}")
    return profile


def load_deploy_profiles(directory: Path) -> dict[str, DeployProfile]:
    """Load every profile in ``directory``, keyed by name; duplicate names are refused."""
    profiles: dict[str, DeployProfile] = {}
    for path in sorted(Path(directory).glob("*.yaml")):
        profile = load_deploy_profile(path)
        if profile.name in profiles:
            raise DeployProfileError(f"{path.name}: duplicate profile name {profile.name!r}")
        profiles[profile.name] = profile
    return profiles
