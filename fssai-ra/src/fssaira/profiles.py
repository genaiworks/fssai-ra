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
class ApplicationProfile:
    profile_id: str
    version: str
    title: str
    resource_name: str
    owner: str
    manual_fallback: str
    transitions: tuple[TransitionRule, ...]

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

        return cls(
            profile_id=str(raw["profile_id"]),
            version=str(raw["version"]),
            title=str(raw["title"]),
            resource_name=str(raw["resource_name"]),
            owner=str(raw["owner"]),
            manual_fallback=str(raw["manual_fallback"]),
            transitions=tuple(rules),
        )
