"""Mandate linting: refuse a task contract that is broader than its purpose needs.

Every other control in the runtime enforces the task contract faithfully. That is
the point, and also the gap: a contract that grants a correction task a public
destination, open-ended expiry and the right to spawn workers is enforced just as
faithfully as a minimal one. A permissive but valid policy is the failure that
runtime enforcement cannot see.

This module moves that failure earlier. An institution declares, per purpose, what
the purpose needs -- operations, destinations, tools, duration and a budget
ceiling -- in a purpose profile (``profiles/tbc/purposes.json``). A contract is
linted against its purpose before it may start. Every grant beyond the purpose is
a finding with a stable code, so a reviewer argues with a named excess rather than
a feeling, and a corpus of known-bad mandates (``profiles/tbc/mandate-corpus``) is
checked on every run.

What it cannot do: judge whether the purpose profile itself is right. It narrows
"is the policy wrong?" to "is this one declared profile wrong?", which is a small,
reviewable document instead of every contract anyone ever writes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .contracts import TaskContract

CODES = (
    "MANDATE_UNKNOWN_PURPOSE",
    "MANDATE_RESOURCE_BEYOND_SUBJECT",
    "MANDATE_UNNEEDED_OPERATION",
    "MANDATE_UNNEEDED_DESTINATION",
    "MANDATE_UNNEEDED_TOOL",
    "MANDATE_OPEN_ENDED",
    "MANDATE_BUDGET_EXCEEDS_PURPOSE",
)


@dataclass(frozen=True)
class Finding:
    code: str
    detail: str

    def to_dict(self) -> dict:
        return {"code": self.code, "detail": self.detail}


def load_purposes(path: str | Path) -> dict:
    purposes = json.loads(Path(path).read_text(encoding="utf-8"))
    for name, profile in purposes.items():
        missing = {"operations", "destinations", "tools", "max_duration_seconds",
                   "budget_ceiling"} - set(profile)
        if missing:
            raise ValueError(f"purpose {name!r} is missing {sorted(missing)}")
    return purposes


def lint_mandate(contract: TaskContract, purposes: dict, *, now: int) -> list[Finding]:
    """Every grant in ``contract`` that its declared purpose does not need."""
    profile = purposes.get(contract.purpose)
    if profile is None:
        return [Finding("MANDATE_UNKNOWN_PURPOSE",
                        f"no purpose profile declares {contract.purpose!r}; it cannot be checked")]
    scope = contract.scope
    findings = []
    subject = f"{contract.tenant}/{contract.subject}"
    for resource in sorted(set(scope.resources) - {subject}):
        findings.append(Finding("MANDATE_RESOURCE_BEYOND_SUBJECT",
                                f"{resource} is not the contract's subject {subject}"))
    for operation in sorted(set(scope.operations) - set(profile["operations"])):
        findings.append(Finding("MANDATE_UNNEEDED_OPERATION",
                                f"{operation} is not needed for {contract.purpose}"))
    for destination in sorted(set(scope.destinations) - set(profile["destinations"])):
        findings.append(Finding("MANDATE_UNNEEDED_DESTINATION",
                                f"{destination} is not a destination {contract.purpose} needs"))
    for tool in sorted(set(scope.tools) - set(profile["tools"])):
        findings.append(Finding("MANDATE_UNNEEDED_TOOL", f"{tool} is not needed for {contract.purpose}"))
    if contract.expires - now > profile["max_duration_seconds"]:
        findings.append(Finding("MANDATE_OPEN_ENDED",
                                f"expires {contract.expires - now} s from now; {contract.purpose} "
                                f"needs at most {profile['max_duration_seconds']} s"))
    for dimension, amount in sorted(contract.budget.to_dict().items()):
        ceiling = profile["budget_ceiling"].get(dimension)
        if ceiling is None or amount > ceiling:
            findings.append(Finding("MANDATE_BUDGET_EXCEEDS_PURPOSE",
                                    f"{dimension} {amount} exceeds the purpose ceiling {ceiling}"))
    return findings


__all__ = ["CODES", "Finding", "lint_mandate", "load_purposes"]
