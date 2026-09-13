"""Validated application profiles for adapting exact-action controls by domain."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .evidence import EvidenceLedger
from .exact_action import AccountableExecutor, CaseRegister, PendingOutcomeStore


class ProfileError(ValueError):
    """Raised when a profile is incomplete or internally inconsistent."""


@dataclass(frozen=True)
class TransitionRule:
    operation: str
    from_status: str
    to_status: str
    consequential: bool
    approval_role: str


@dataclass(frozen=True)
class GovernanceContext:
    """Domain facts that must travel with a reusable authority profile.

    These fields are descriptive and deliberately do not claim compliance.
    They force an adopter to name purpose, sensitive-data classes, prohibited
    uses, external obligations, and the people who own data/privacy/security.
    Enforcement remains in transitions and the control contract.
    """

    domain: str
    purpose: str
    deployment_profile: str
    data_classes: tuple[str, ...]
    applicable_frameworks: tuple[str, ...]
    prohibited_uses: tuple[str, ...]
    processing_basis: str
    data_minimization_rule: str
    retention_rule: str
    deletion_rule: str
    residency_rule: str
    incident_response: str
    data_owner: str
    privacy_owner: str
    security_owner: str


@dataclass(frozen=True)
class ApplicationProfile:
    profile_id: str
    version: str
    title: str
    resource_name: str
    owner: str
    manual_fallback: str
    transitions: tuple[TransitionRule, ...]
    governance: GovernanceContext | None = None

    @property
    def allowed_operations(self) -> set[str]:
        return {rule.operation for rule in self.transitions}

    @property
    def transition_rules(self) -> dict[str, set[tuple[str, str]]]:
        grouped: dict[str, set[tuple[str, str]]] = {}
        for rule in self.transitions:
            grouped.setdefault(rule.operation, set()).add(
                (rule.from_status, rule.to_status)
            )
        return grouped

    @property
    def required_approval_roles(self) -> dict[tuple[str, str, str], set[str]]:
        """The approver role the executor enforces for each declared transition.

        Every transition, not only the consequential ones. Earlier releases built
        this map from consequential rules alone, which was unreachable while the
        only reference profile declared every transition consequential. Adding a
        second domain with an ordinary routine step exposed it immediately: the
        schema *requires* ``approval_role`` on every transition, so a rule that
        declared one and had it ignored was a control that existed in review and
        not at runtime — the exact failure this project exists to eliminate.

        ``consequential`` answers a different question, and keeps answering it:
        whether a *named human* must supply the approval at all. Whether the role
        they hold is the declared one is not a question any transition gets to
        opt out of.
        """
        return {
            (rule.operation, rule.from_status, rule.to_status): {rule.approval_role}
            for rule in self.transitions
        }

    def make_executor(
        self,
        register: CaseRegister,
        evidence: EvidenceLedger,
        evidence_token: str,
        *,
        approval_keys: dict[str, str] | None = None,
        outcome_store: PendingOutcomeStore | None = None,
        approval_use_store=None,
    ) -> AccountableExecutor:
        return AccountableExecutor(
            register,
            evidence,
            evidence_token,
            approval_keys=approval_keys,
            allowed_operations=self.allowed_operations,
            transition_rules=self.transition_rules,
            required_approval_roles=self.required_approval_roles,
            outcome_store=outcome_store,
            approval_use_store=approval_use_store,
        )

    @classmethod
    def load(cls, path: str | Path) -> ApplicationProfile:
        source = Path(path)
        try:
            raw = yaml.safe_load(source.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ProfileError(f"cannot load profile {source}: {exc}") from exc
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: Any) -> ApplicationProfile:
        if not isinstance(raw, dict):
            raise ProfileError("profile must be a mapping")
        required = (
            "profile_id", "version", "title", "resource_name", "owner",
            "manual_fallback", "transitions",
        )
        missing = [key for key in required if not raw.get(key)]
        if missing:
            raise ProfileError("missing required fields: " + ", ".join(missing))
        for key in required[:-1]:
            if not isinstance(raw[key], str) or not raw[key].strip():
                raise ProfileError(f"{key} must be a non-empty string")
        if not isinstance(raw["transitions"], list):
            raise ProfileError("transitions must be a list")

        rules = []
        seen = set()
        for index, item in enumerate(raw["transitions"]):
            if not isinstance(item, dict):
                raise ProfileError(f"transition {index} must be a mapping")
            fields = ("operation", "from_status", "to_status", "approval_role")
            absent = [key for key in fields if not item.get(key)]
            if absent or "consequential" not in item:
                raise ProfileError(
                    f"transition {index} missing fields: "
                    + ", ".join(absent + ([] if "consequential" in item else ["consequential"]))
                )
            if not isinstance(item["consequential"], bool):
                raise ProfileError(f"transition {index} consequential must be boolean")
            for key in fields:
                if not isinstance(item[key], str) or not item[key].strip():
                    raise ProfileError(f"transition {index} {key} must be a non-empty string")
            identity = (item["operation"], item["from_status"], item["to_status"])
            if identity in seen:
                raise ProfileError(f"duplicate transition at index {index}")
            seen.add(identity)
            rules.append(TransitionRule(**{key: item[key] for key in (*fields, "consequential")}))

        governance = _governance_context(raw.get("governance"))

        return cls(
            profile_id=str(raw["profile_id"]),
            version=str(raw["version"]),
            title=str(raw["title"]),
            resource_name=str(raw["resource_name"]),
            owner=str(raw["owner"]),
            manual_fallback=str(raw["manual_fallback"]),
            transitions=tuple(rules),
            governance=governance,
        )


def _governance_context(raw: Any) -> GovernanceContext | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ProfileError("governance must be a mapping")
    required = (
        "domain", "purpose", "deployment_profile", "data_classes",
        "applicable_frameworks", "prohibited_uses", "processing_basis",
        "data_minimization_rule", "retention_rule", "deletion_rule",
        "residency_rule", "incident_response", "owners",
    )
    missing = [key for key in required if key not in raw]
    if missing:
        raise ProfileError("governance missing required fields: " + ", ".join(missing))
    for key in (
        "domain", "purpose", "deployment_profile", "processing_basis",
        "data_minimization_rule", "retention_rule", "deletion_rule",
        "residency_rule", "incident_response",
    ):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise ProfileError(f"governance {key} must be a non-empty string")
    if raw["deployment_profile"] not in {
        "teaching", "institutional-pilot", "hardware-isolated",
    }:
        raise ProfileError(
            "governance deployment_profile must be teaching, institutional-pilot, "
            "or hardware-isolated"
        )

    def string_list(key: str) -> tuple[str, ...]:
        value = raw[key]
        if (
            not isinstance(value, list)
            or not value
            or not all(isinstance(item, str) and item.strip() for item in value)
        ):
            raise ProfileError(f"governance {key} must be a non-empty list of strings")
        normalized = tuple(item.strip() for item in value)
        if len(set(normalized)) != len(normalized):
            raise ProfileError(f"governance {key} contains duplicates")
        return normalized

    owners = raw["owners"]
    if not isinstance(owners, dict):
        raise ProfileError("governance owners must be a mapping")
    owner_values = {}
    for key in ("data", "privacy", "security"):
        value = owners.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ProfileError(f"governance owners.{key} must be a non-empty string")
        owner_values[key] = value.strip()
    return GovernanceContext(
        domain=raw["domain"].strip(),
        purpose=raw["purpose"].strip(),
        deployment_profile=raw["deployment_profile"],
        data_classes=string_list("data_classes"),
        applicable_frameworks=string_list("applicable_frameworks"),
        prohibited_uses=string_list("prohibited_uses"),
        processing_basis=raw["processing_basis"].strip(),
        data_minimization_rule=raw["data_minimization_rule"].strip(),
        retention_rule=raw["retention_rule"].strip(),
        deletion_rule=raw["deletion_rule"].strip(),
        residency_rule=raw["residency_rule"].strip(),
        incident_response=raw["incident_response"].strip(),
        data_owner=owner_values["data"],
        privacy_owner=owner_values["privacy"],
        security_owner=owner_values["security"],
    )


def discover_profiles(directory: str | Path) -> list[dict]:
    """Validate and summarize every YAML domain pack in a directory."""
    root = Path(directory)
    if not root.is_dir():
        raise ProfileError(f"profile directory does not exist: {root}")
    summaries = []
    profile_ids: set[str] = set()
    for path in sorted(root.glob("*.yaml")):
        if path.name == "template.yaml":
            continue
        profile = ApplicationProfile.load(path)
        if profile.profile_id in profile_ids:
            raise ProfileError(f"duplicate profile_id in {root}: {profile.profile_id}")
        profile_ids.add(profile.profile_id)
        governance = profile.governance
        if governance is None:
            raise ProfileError(
                f"domain pack {path} must declare a governance context"
            )
        summaries.append({
            "profile_id": profile.profile_id,
            "title": profile.title,
            "resource_name": profile.resource_name,
            "owner": profile.owner,
            "domain": governance.domain if governance else "undeclared",
            "purpose": governance.purpose if governance else "undeclared",
            "deployment_profile": (
                governance.deployment_profile if governance else "undeclared"
            ),
            "data_classes": list(governance.data_classes) if governance else [],
            "applicable_frameworks": (
                list(governance.applicable_frameworks) if governance else []
            ),
            "prohibited_uses": list(governance.prohibited_uses) if governance else [],
            "processing_basis": governance.processing_basis if governance else "undeclared",
            "data_minimization_rule": (
                governance.data_minimization_rule if governance else "undeclared"
            ),
            "retention_rule": governance.retention_rule if governance else "undeclared",
            "deletion_rule": governance.deletion_rule if governance else "undeclared",
            "residency_rule": governance.residency_rule if governance else "undeclared",
            "incident_response": (
                governance.incident_response if governance else "undeclared"
            ),
            "transitions": len(profile.transitions),
            "consequential_transitions": sum(rule.consequential for rule in profile.transitions),
            "approval_roles": sorted({rule.approval_role for rule in profile.transitions}),
            "path": str(path),
        })
    if not summaries:
        raise ProfileError(f"profile directory contains no domain packs: {root}")
    return summaries


__all__ = [
    "ApplicationProfile", "GovernanceContext", "ProfileError", "TransitionRule",
    "discover_profiles",
]
