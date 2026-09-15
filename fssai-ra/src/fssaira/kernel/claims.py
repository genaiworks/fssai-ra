"""The claims register: every contracted assertion, classified three ways.

* ``machine_verified``: bound to an executable check that exists.
* ``attested``: declared provable only organizationally, with a named attester.
* ``unverified``: bound to nothing. This is a defect to report, never to ship.

Rows are computed from the contract, its bindings and the capability contracts.
No count is typed. A binding that names a missing check stops the register from
being built at all, because a register that counted it would overstate the
evidence.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from fssaira.coverage import measure_coverage
from fssaira.kernel.contract import ContractError, load_capability_contracts, verify_bindings

CLAIM_CLASSES: tuple[str, ...] = ("machine_verified", "attested", "unverified")
_FROM_COVERAGE = {
    "machine_verified": "machine_verified",
    "organizationally_attested": "attested",
    "unverified": "unverified",
}


@dataclass(frozen=True)
class ClaimRow:
    id: str
    source: str  # "contract" (legacy requirement) or "capability" (seven-field contract)
    domain: str
    status: str
    evidence: tuple[str, ...]


@dataclass
class ClaimsRegister:
    rows: list[ClaimRow] = field(default_factory=list)

    def counts(self, source: str | None = None) -> dict[str, int]:
        selected: Iterable[ClaimRow] = (
            self.rows if source is None else (r for r in self.rows if r.source == source)
        )
        totals = dict.fromkeys(CLAIM_CLASSES, 0)
        for row in selected:
            totals[row.status] += 1
        return totals

    def to_yaml(self) -> str:
        doc = {
            "classes": list(CLAIM_CLASSES),
            "counts": self.counts(),
            "counts_by_source": {
                source: self.counts(source) for source in sorted({r.source for r in self.rows})
            },
            "rows": [
                {"id": r.id, "source": r.source, "domain": r.domain,
                 "status": r.status, "evidence": list(r.evidence)}
                for r in self.rows
            ],
        }
        return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def build_register(root: Path) -> ClaimsRegister:
    """Build the register for the repository rooted at ``root``."""
    root = Path(root)
    contract_dir = root / "contract"
    findings = verify_bindings(contract_dir, root=root)
    if findings:
        raise ContractError("bindings name checks that do not exist:\n  " + "\n  ".join(findings))

    rows: list[ClaimRow] = []
    for requirement in measure_coverage(str(contract_dir)).requirements:
        status = _FROM_COVERAGE[requirement.status]
        if status == "attested":
            evidence: tuple[str, ...] = (f"attested_by: {requirement.attested_by}",)
        else:
            evidence = tuple(sorted({b.locator for b in requirement.bindings if b.mechanism != "attestation"}))
        rows.append(ClaimRow(requirement.requirement_id, "contract", requirement.domain, status, evidence))

    for capability in load_capability_contracts(contract_dir / "capabilities", root=root):
        rows.append(ClaimRow(capability.id, "capability", capability.domain,
                             "machine_verified", (capability.failure_test,)))
    return ClaimsRegister(rows)
