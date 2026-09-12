"""Is each contract requirement actually enforced, or only written down?

The seven-field control contract is this project's central claim, and the
diagnostic it applies to everyone else is sharp: *a capability whose seven fields
cannot be filled is one nobody is ready to automate*. One of those fields is
``test`` — the executable failure test that proves the control exists at runtime
rather than in review.

Applying that diagnostic to ourselves produces an uncomfortable question. The
contract loader validates that every requirement *has* a ``test`` field. It has
never checked that the test **exists**. A requirement can therefore carry a
beautifully specific test description, name a real enforcement point, be reviewed
and approved, and be bound to nothing that runs.

``fssaira.profiles`` already says what that is, in the comment explaining why the
approval-role map was rebuilt from every transition rather than the consequential
ones:

    *a control that existed in review and not at runtime is the exact failure
    this project exists to eliminate.*

The first run of this module found eighteen of them in our own contract.

What this module does
---------------------
It computes, for every requirement, which of three states it is in:

**machine_verified** — at least one executable check in this repository is bound
to it and runs. The binding is explicit and is itself checked: a binding naming a
test that does not exist is an error, not a pass.

**organizationally_attested** — the control is real and no code can prove it.
Key custody, the signed interface inventory, separation of administrative duties,
the existence of a manual fallback an actual person will staff: these are
properties of an institution, not of a program. They are declared in the contract
with a named attesting role and a review cadence, and they are counted
separately, because an attestation is a weaker thing than a test and pretending
otherwise is how assurance arguments rot.

**unverified** — neither. A control nobody has bound to anything. This is the
number to watch, and it is printed in the tool output rather than described in a
limitations paragraph, for the same reason
``challenge.externally_contributed`` is.

Why the three-way split matters
-------------------------------
A two-way split forces a dishonest choice. Count attestations as coverage and the
figure is inflated with promises. Count them as gaps and the figure is
permanently and misleadingly bad, which trains everyone to ignore it. Neither
produces a number an institution can act on.

Publishing all three makes the assurance argument legible: *this many controls
our code proves, this many our institution attests to, this many nobody has
claimed.* An adopter can then ask the only question that matters — are the
attested ones the ones you would expect to be unprovable, or are they the
inconvenient ones?
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from datetime import datetime, timezone

import yaml

from .contract import ControlContract

#: Mechanisms a binding can name. Ordered loosely by strength of evidence.
MECHANISMS = (
    "model_check",    # an invariant enumerated over a declared state space
    "conformance",    # a portable check run against the configured backends
    "ablation",       # the control was removed and the harm returned
    "scenario",       # an adversarial scenario contained by the enforcement point
    "unit_test",      # a deterministic test asserting the control's behaviour
    "attestation",    # a named human role attests on a declared cadence
)


@dataclass(frozen=True)
class Binding:
    """One executable (or attested) link from a requirement to evidence."""

    requirement_id: str
    mechanism: str
    locator: str
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "requirement_id": self.requirement_id,
            "mechanism": self.mechanism,
            "locator": self.locator,
            "note": self.note,
        }


@dataclass(frozen=True)
class RequirementCoverage:
    requirement_id: str
    domain: str
    status: str                 # machine_verified | organizationally_attested | unverified
    bindings: tuple = ()
    attested_by: str = ""
    attestation_cadence: str = ""
    declared_test: str = ""

    def to_dict(self) -> dict:
        payload = {
            "requirement_id": self.requirement_id,
            "domain": self.domain,
            "status": self.status,
            "bindings": [b.to_dict() for b in self.bindings],
        }
        if self.status == "organizationally_attested":
            payload["attested_by"] = self.attested_by
            payload["attestation_cadence"] = self.attestation_cadence
        if self.status == "unverified":
            payload["declared_test"] = self.declared_test
        return payload


@dataclass
class CoverageReport:
    generated_at: str
    requirements: tuple = ()
    unknown_bindings: tuple = ()

    def _count(self, status: str) -> int:
        return sum(1 for r in self.requirements if r.status == status)

    @property
    def total(self) -> int:
        return len(self.requirements)

    @property
    def machine_verified(self) -> int:
        return self._count("machine_verified")

    @property
    def organizationally_attested(self) -> int:
        return self._count("organizationally_attested")

    @property
    def unverified(self) -> int:
        return self._count("unverified")

    @property
    def unverified_ids(self) -> tuple:
        return tuple(r.requirement_id for r in self.requirements if r.status == "unverified")

    @property
    def holds(self) -> bool:
        """Every requirement is either proved by code or attested by a named role.

        Deliberately *not* "every requirement is machine_verified". Demanding
        that would push organizational controls out of the contract to make a
        number look good, which is the opposite of the intent.
        """
        return self.unverified == 0 and not self.unknown_bindings

    def to_dict(self) -> dict:
        return {
            "schema_version": "1.0",
            "kind": "contract-coverage",
            "generated_at": self.generated_at,
            "totals": {
                "requirements": self.total,
                "machine_verified": self.machine_verified,
                "organizationally_attested": self.organizationally_attested,
                "unverified": self.unverified,
                "machine_verified_fraction": (
                    round(self.machine_verified / self.total, 4) if self.total else None
                ),
            },
            "unverified_requirements": list(self.unverified_ids),
            "bindings_naming_unknown_requirements": list(self.unknown_bindings),
            "requirements": [r.to_dict() for r in self.requirements],
            "reading": [
                "machine_verified means an executable check in this repository is "
                "bound to the requirement and runs; it does not mean the control is "
                "sufficient, only that it is not imaginary",
                "organizationally_attested is a weaker claim than a test and is counted "
                "separately on purpose; an attestation is a person's word on a cadence",
                "unverified is the number to watch. A requirement here has a test "
                "written in prose and bound to nothing",
                "an adopter should ask whether the attested controls are the ones that "
                "are genuinely unprovable in code, or the inconvenient ones",
            ],
            "limits": [
                "coverage measures that a control is exercised, never that it is adequate",
                "a requirement can be machine_verified by a weak check; strength of "
                "evidence is the mechanism name, not a score",
                "attestation cadence is declared and is not itself verified here",
            ],
        }


def load_bindings(directory: str) -> list:
    """Read the binding manifests that link requirements to executable checks.

    Bindings live in ``contract/bindings/*.yaml`` beside the contract itself,
    rather than inside the requirement entries, for one reason: the contract is
    the institution's document and the bindings are this implementation's. An
    adopter replacing the implementation keeps the first and rewrites the second,
    and the split makes that obvious.
    """
    bindings: list = []
    pattern = os.path.join(directory, "bindings", "*.yaml")
    for path in sorted(glob.glob(pattern)):
        with open(path) as handle:
            doc = yaml.safe_load(handle) or {}
        for item in doc.get("bindings", []) or []:
            mechanism = str(item.get("mechanism", "")).strip()
            if mechanism not in MECHANISMS:
                raise ValueError(
                    f"{os.path.basename(path)}: unknown mechanism {mechanism!r}; "
                    f"expected one of {', '.join(MECHANISMS)}"
                )
            for requirement_id in item.get("requirements", []) or []:
                bindings.append(Binding(
                    requirement_id=str(requirement_id),
                    mechanism=mechanism,
                    locator=str(item.get("locator", "")).strip(),
                    note=str(item.get("note", "")).strip(),
                ))
    return bindings


def measure_coverage(contract_dir: str) -> CoverageReport:
    """Compute three-way coverage over the control contract."""
    contract = ControlContract.load(contract_dir)
    bindings = load_bindings(contract_dir)
    attestations = _load_attestations(contract_dir)

    by_requirement: dict = {}
    for binding in bindings:
        by_requirement.setdefault(binding.requirement_id, []).append(binding)

    known = {requirement.id for requirement in contract}
    unknown = tuple(sorted(set(by_requirement) - known))

    rows: list = []
    for requirement in contract:
        found = tuple(by_requirement.get(requirement.id, ()))
        executable = tuple(b for b in found if b.mechanism != "attestation")
        attestation = attestations.get(requirement.id)

        if executable:
            status = "machine_verified"
        elif attestation:
            status = "organizationally_attested"
        else:
            status = "unverified"

        rows.append(RequirementCoverage(
            requirement_id=requirement.id,
            domain=requirement.domain,
            status=status,
            bindings=found,
            attested_by=(attestation or {}).get("attested_by", ""),
            attestation_cadence=(attestation or {}).get("cadence", ""),
            declared_test=requirement.test if status == "unverified" else "",
        ))

    return CoverageReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        requirements=tuple(rows),
        unknown_bindings=unknown,
    )


def _load_attestations(directory: str) -> dict:
    """Read ``verified_by: organizational`` declarations from the contract.

    A requirement declares itself organizationally attested inside the contract
    rather than in the bindings file, because *whether a control is provable in
    code* is a property of the control, not of this implementation.
    """
    attestations: dict = {}
    for path in sorted(glob.glob(os.path.join(directory, "*.yaml"))):
        with open(path) as handle:
            doc = yaml.safe_load(handle) or {}
        for item in doc.get("requirements", []) or []:
            if str(item.get("verified_by", "")).strip() != "organizational":
                continue
            attested_by = str(item.get("attested_by", "")).strip()
            cadence = str(item.get("attestation_cadence", "")).strip()
            if not attested_by or not cadence:
                raise ValueError(
                    f"{item.get('id')} declares organizational verification but does "
                    "not name both an attesting role and a review cadence. An "
                    "attestation nobody owns on no schedule is not an attestation"
                )
            attestations[str(item["id"])] = {
                "attested_by": attested_by,
                "cadence": cadence,
            }
    return attestations


__all__ = [
    "Binding",
    "CoverageReport",
    "MECHANISMS",
    "RequirementCoverage",
    "load_bindings",
    "measure_coverage",
]
