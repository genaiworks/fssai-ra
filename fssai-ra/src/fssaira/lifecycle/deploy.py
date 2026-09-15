"""Deployment profiles: which gates a promotion must pass, and what is forbidden.

A profile is declarative (``deploy/profiles/*.yaml``). The loader enforces the
rules that make "consequential" mean something:

* a consequential profile forbids ablation switches;
* it requires process isolation and backend conformance;
* it requires every consequential gate in :data:`CONSEQUENTIAL_GATES`.

A profile cannot quietly drop a gate that the paper makes mandatory.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


def load_deploy_profile(path: Path) -> DeployProfile:
    """Load and validate one deployment profile."""
    path = Path(path)
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    name = str(doc.get("profile", "")).strip()
    if not name:
        raise DeployProfileError(f"{path.name}: profile has no name")
    consequential = doc.get("consequential")
    if not isinstance(consequential, bool):
        raise DeployProfileError(f"{name}: 'consequential' must be true or false")
    ablation = str(doc.get("ablation_switches", "")).strip()
    if ablation not in _ABLATION_VALUES:
        raise DeployProfileError(f"{name}: ablation_switches must be one of {sorted(_ABLATION_VALUES)}")
    isolation = doc.get("isolation") or {}
    backends = doc.get("backends") or {}
    gates = tuple(str(g) for g in (doc.get("required_gates") or ()))
    unknown = sorted(set(gates) - GATE_IDS)
    if unknown:
        raise DeployProfileError(f"{name}: unknown gate(s) {unknown}")
    fallback = str(doc.get("fallback", "")).strip()
    if not fallback:
        raise DeployProfileError(f"{name}: a profile without a manual fallback cannot fail secure")
    statement = str(isolation.get("statement", "")).strip()
    if not statement:
        raise DeployProfileError(f"{name}: the isolation statement is required, even when isolation is not")

    profile = DeployProfile(
        name=name,
        stage=str(doc.get("stage", "")).strip(),
        consequential=consequential,
        ablation_switches=ablation,
        process_isolation_required=bool(isolation.get("process_isolation_required")),
        conformance_required=bool(backends.get("conformance_required")),
        allowed_backends=tuple(str(b) for b in (backends.get("allowed") or ())),
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
    """Load every profile in ``directory``, keyed by name."""
    profiles = [load_deploy_profile(p) for p in sorted(Path(directory).glob("*.yaml"))]
    return {p.name: p for p in profiles}
