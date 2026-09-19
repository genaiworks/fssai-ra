"""Table 4 gap-closure obligations as signed institutional records.

Code cannot establish that an institution isolated its mediators, reviewed its
quasi-identifiers or staffed its manual fallback. It *can* refuse to promote a
consequential capability until a record exists for every Table 4 hurdle that:

* names an accountable owner and a signer;
* points at versioned evidence whose digest is verified when the evidence is a local file;
* is inside its validity window;
* states the residual risk the institution accepted.

The gate is therefore "the record exists and is well-formed". It is never "the
obligation was met", and its detail says so.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

#: One id per Table 4 row, in the paper's order.
HURDLES: tuple[str, ...] = (
    "bypass_and_common_mode",
    "policy_and_pack_escalation",
    "tenant_beneficiary_delegation_scope",
    "label_and_action_composition",
    "memory_retrieval_modality",
    "declassification_and_inference",
    "erasure_and_evidence_retention",
    "model_and_tool_supply_chain",
    "distributed_and_external_effects",
    "evidence_integrity_and_privacy",
    "review_overload_correlated_errors",
    "correctness_fairness_redress",
    "availability_cost_sustainability",
    "transfer_and_external_assurance",
)
_FIELDS = ("hurdle", "owner", "signed_by", "evidence", "evidence_sha256", "date", "expires",
           "accepted_residual_risk")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ObligationReport:
    complete: bool
    present: int
    denominator: int
    problems: tuple[str, ...]

    @property
    def detail(self) -> str:
        if self.complete:
            return (f"{self.present} of {self.denominator} Table 4 obligations have a current, signed, "
                    "owned record with verified evidence digests; code cannot confirm the obligations were met")
        return f"{self.present} of {self.denominator} obligations recorded; problems: {'; '.join(self.problems)}"


def _as_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def check_obligations(path: Path | None, *, today: date | None = None) -> ObligationReport:
    """Check one obligations record file against Table 4."""
    today = today or date.today()
    if path is None or not Path(path).is_file():
        return ObligationReport(False, 0, len(HURDLES), (f"no obligations record at {path}",))
    path = Path(path)
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = doc.get("obligations") or []
    problems: list[str] = []
    seen: dict[str, dict] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            problems.append(f"entry {index} is not a mapping")
            continue
        hurdle = str(entry.get("hurdle", "")).strip()
        where = hurdle or f"entry {index}"
        if hurdle not in HURDLES:
            problems.append(f"{where}: not a Table 4 hurdle")
            continue
        if hurdle in seen:
            problems.append(f"{hurdle}: recorded twice")
            continue
        empty = [name for name in _FIELDS if not str(entry.get(name, "")).strip()]
        if empty:
            problems.append(f"{hurdle}: empty {', '.join(empty)}")
            continue
        digest = str(entry["evidence_sha256"]).strip().lower()
        if not _HEX64.match(digest):
            problems.append(f"{hurdle}: evidence_sha256 is not a sha256 digest")
            continue
        evidence = str(entry["evidence"]).strip()
        if "://" not in evidence:
            local = (path.parent / evidence).resolve()
            if not local.is_file():
                problems.append(f"{hurdle}: evidence file {evidence} does not exist")
                continue
            if hashlib.sha256(local.read_bytes()).hexdigest() != digest:
                problems.append(f"{hurdle}: evidence digest does not match {evidence}")
                continue
        signed, expires = _as_date(entry["date"]), _as_date(entry["expires"])
        if signed is None or expires is None:
            problems.append(f"{hurdle}: date and expires must be ISO dates")
            continue
        if signed > today:
            problems.append(f"{hurdle}: signed in the future ({signed})")
            continue
        if expires <= today:
            problems.append(f"{hurdle}: expired on {expires}")
            continue
        if str(entry["owner"]).strip() == str(entry["signed_by"]).strip():
            problems.append(f"{hurdle}: owner and signer are the same identity")
            continue
        seen[hurdle] = entry
    missing = [h for h in HURDLES if h not in seen]
    if missing:
        problems.append(f"missing: {', '.join(missing)}")
    return ObligationReport(not problems, len(seen), len(HURDLES), tuple(problems))
