"""Load and validate the property-based control contract from ``contract/*.yaml``.

Each requirement records the seven fields from the paper: protected asset,
permitted operation, enforcement point, owner, test, evidence artifact, and
failure response. The contract is machine-readable so it can double as a
conformance checklist: adopt a property, choose tools that pass its test.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field

import yaml

REQUIRED_FIELDS = (
    "id", "domain", "protected_asset", "permitted_operation",
    "enforcement_point", "owner", "test", "evidence_artifact", "failure_response",
)


@dataclass
class Requirement:
    id: str
    domain: str
    protected_asset: str
    permitted_operation: str
    enforcement_point: str
    owner: str
    test: str
    evidence_artifact: str
    failure_response: str


@dataclass
class ControlContract:
    requirements: list = field(default_factory=list)

    @classmethod
    def load(cls, directory: str) -> "ControlContract":
        reqs = []
        for path in sorted(glob.glob(os.path.join(directory, "*.yaml"))):
            with open(path) as fh:
                doc = yaml.safe_load(fh) or {}
            domain = doc.get("domain", os.path.splitext(os.path.basename(path))[0])
            for item in doc.get("requirements", []):
                item = dict(item)
                item.setdefault("domain", domain)
                reqs.append(Requirement(**{k: item.get(k, "") for k in
                                           (f for f in REQUIRED_FIELDS)}))
        return cls(reqs)

    def validate(self) -> None:
        seen = set()
        for r in self.requirements:
            for fname in REQUIRED_FIELDS:
                if not getattr(r, fname):
                    raise ValueError(f"requirement {r.id!r} missing field {fname!r}")
            if r.id in seen:
                raise ValueError(f"duplicate requirement id {r.id!r}")
            seen.add(r.id)

    def by_domain(self, domain: str) -> list:
        return [r for r in self.requirements if r.domain == domain]

    def __iter__(self):
        return iter(self.requirements)

    def __len__(self) -> int:
        return len(self.requirements)
