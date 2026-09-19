"""The instrument for the study this repository has not run.

Synthetic fixtures cannot tell an institution whether mediated agents help
students, cost reviewers time they do not have, or distribute outcomes
differently across groups. That question needs real data, real reviewers, and
approval from the people whose records are involved. This repository has none of
those, and every honest reading of its results has to say so.

What it can supply -- and what was missing -- is the instrument: a
preregistration that fixes the hypotheses and the analysis *before* the data
arrives, and an analysis that computes the agreed quantities and then refuses to
present them as findings when the preconditions are not met. Three refusals are
enforced in code rather than in prose:

1. **Synthetic provenance.** A dataset marked synthetic yields measurements with
   ``conclusions_permitted`` false. The numbers are still computed, because a
   dry run on fixtures is how you find out the instrument works.
2. **Underpowered samples.** Below the preregistered minimum, or below the
   minimum cell size for a subgroup, the quantity is withheld rather than
   reported with a wide interval that a reader will quote anyway.
3. **Analysis drift.** The analysis plan is hashed into the preregistration. An
   analysis run under a different plan is reported as exploratory, and cannot
   be relabelled afterwards.

The fairness measures are deliberately plural and are reported together:
selection rate, equal-opportunity gap and reviewer-overturn rate answer
different questions and can point in different directions. Reporting whichever
one looks best is the failure mode this structure exists to prevent.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

SYNTHETIC = "synthetic"
INSTITUTIONAL = "institutional"
PROVENANCE = (SYNTHETIC, INSTITUTIONAL)

WITHHELD = "withheld: below the preregistered minimum"


class StudyRefusal(RuntimeError):
    """The instrument refuses to produce a finding it cannot support."""


@dataclass(frozen=True)
class Preregistration:
    """Fixed before data arrives; hashed so drift is visible afterwards."""

    title: str
    hypotheses: tuple[str, ...]
    primary_outcome: str
    secondary_outcomes: tuple[str, ...]
    subgroup_attributes: tuple[str, ...]
    minimum_sample: int
    #: A subgroup smaller than this is neither reported nor used in a gap, both
    #: because the estimate is noise and because small cells re-identify people.
    minimum_cell: int
    analysis_plan: str
    approval_reference: str = ""

    def __post_init__(self) -> None:
        if not self.hypotheses:
            raise ValueError("a preregistration states at least one hypothesis")
        if not self.primary_outcome or not self.analysis_plan.strip():
            raise ValueError("a preregistration names a primary outcome and a plan")
        if self.minimum_sample < 1 or self.minimum_cell < 1:
            raise ValueError("minimum sample and cell size must be positive")
        if self.minimum_cell > self.minimum_sample:
            raise ValueError("cell minimum cannot exceed the sample minimum")

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps({
            "title": self.title, "hypotheses": list(self.hypotheses),
            "primary_outcome": self.primary_outcome,
            "secondary_outcomes": list(self.secondary_outcomes),
            "subgroup_attributes": list(self.subgroup_attributes),
            "minimum_sample": self.minimum_sample, "minimum_cell": self.minimum_cell,
            "analysis_plan": self.analysis_plan,
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "title": self.title, "digest": self.digest,
            "hypotheses": list(self.hypotheses),
            "primary_outcome": self.primary_outcome,
            "secondary_outcomes": list(self.secondary_outcomes),
            "subgroup_attributes": list(self.subgroup_attributes),
            "minimum_sample": self.minimum_sample,
            "minimum_cell": self.minimum_cell,
            "approval_reference": self.approval_reference,
        }


@dataclass(frozen=True)
class DecisionRecord:
    """One task that an agent handled and a human reviewed."""

    case_id: str
    #: Did the mediated system complete the task it was asked to do?
    completed: bool
    #: Did the reviewer accept the agent's proposal?
    approved: bool
    #: Did a reviewer reverse an earlier approval? A cost that completion hides.
    overturned: bool
    #: Ground truth where it exists: should this case have been approved?
    eligible: bool | None
    seconds_to_decision: float
    attributes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id:
            raise ValueError("every record needs a case identifier")
        if self.seconds_to_decision < 0:
            raise ValueError("negative decision time")


@dataclass(frozen=True)
class Dataset:
    provenance: str
    records: tuple[DecisionRecord, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if self.provenance not in PROVENANCE:
            raise ValueError(f"provenance must be one of {PROVENANCE}")


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (0.0, 1.0)
    phat = successes / total
    denominator = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denominator
    spread = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total)) / denominator
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def _rate(successes: int, total: int) -> dict[str, Any]:
    return {
        "value": round(successes / total, 4) if total else None,
        "n": total,
        "interval": [round(v, 4) for v in wilson_interval(successes, total)],
    }


class InstitutionalStudy:
    """Compute the preregistered quantities, and gate the conclusions."""

    def __init__(self, preregistration: Preregistration) -> None:
        self.preregistration = preregistration

    def analyse(self, dataset: Dataset, *, analysis_plan: str | None = None) -> dict:
        prereg = self.preregistration
        records = dataset.records
        plan_followed = analysis_plan is None or analysis_plan == prereg.analysis_plan

        refusals: list[str] = []
        if dataset.provenance == SYNTHETIC:
            refusals.append(
                "the dataset is synthetic: these numbers exercise the instrument "
                "and say nothing about students, reviewers or institutional outcomes")
        if len(records) < prereg.minimum_sample:
            refusals.append(
                f"sample is {len(records)}, below the preregistered minimum of "
                f"{prereg.minimum_sample}")
        if not plan_followed:
            refusals.append(
                "the analysis plan differs from the preregistered plan: this run "
                "is exploratory and cannot be relabelled confirmatory afterwards")
        if not prereg.approval_reference and dataset.provenance == INSTITUTIONAL:
            refusals.append(
                "institutional data was supplied without an approval reference")

        completed = sum(r.completed for r in records)
        approved = sum(r.approved for r in records)
        overturned = sum(r.overturned for r in records)
        times = sorted(r.seconds_to_decision for r in records)

        utility = {
            "task_completion": _rate(completed, len(records)),
            "approval_rate": _rate(approved, len(records)),
            "reviewer_overturn": _rate(overturned, len(records)),
            "seconds_to_decision": {
                "median": round(_median(times), 3) if times else None,
                "p90": round(times[max(0, math.ceil(0.9 * len(times)) - 1)], 3) if times else None,
                "n": len(times),
            },
        }

        fairness = {attribute: self._fairness(records, attribute)
                    for attribute in prereg.subgroup_attributes}

        return {
            "schema_version": "1.0",
            "kind": "institutional_evaluation",
            "preregistration": prereg.to_dict(),
            "analysis_plan_followed": plan_followed,
            "dataset": {
                "provenance": dataset.provenance,
                "description": dataset.description,
                "records": len(records),
            },
            "utility": utility,
            "fairness": fairness,
            "conclusions_permitted": not refusals,
            "refusals": refusals,
            "reporting_rules": [
                "selection rate, equal-opportunity gap and overturn rate are "
                "reported together; a single favourable measure is not a result",
                "subgroups below the preregistered cell minimum are withheld, for "
                "statistical and re-identification reasons alike",
                "a gap is an observation about outcomes, not an explanation of them",
            ],
        }

    def _fairness(self, records: Sequence[DecisionRecord], attribute: str) -> dict:
        prereg = self.preregistration
        groups: dict[str, list[DecisionRecord]] = {}
        for record in records:
            value = record.attributes.get(attribute)
            if value is not None:
                groups.setdefault(value, []).append(record)

        reported: dict[str, Any] = {}
        withheld: list[str] = []
        opportunity: dict[str, Any] = {}
        for value, members in sorted(groups.items()):
            if len(members) < prereg.minimum_cell:
                withheld.append(value)
                continue
            reported[value] = {
                "selection_rate": _rate(sum(r.approved for r in members), len(members)),
                "overturn_rate": _rate(sum(r.overturned for r in members), len(members)),
            }
            eligible = [r for r in members if r.eligible]
            if len(eligible) >= prereg.minimum_cell:
                opportunity[value] = _rate(
                    sum(r.approved for r in eligible), len(eligible))

        rates = [entry["selection_rate"]["value"] for entry in reported.values()]
        gaps = {
            "selection_rate_gap": (round(max(rates) - min(rates), 4)
                                   if len(rates) > 1 else None),
        }
        opportunity_values = [v["value"] for v in opportunity.values()]
        gaps["equal_opportunity_gap"] = (
            round(max(opportunity_values) - min(opportunity_values), 4)
            if len(opportunity_values) > 1 else None)

        return {
            "groups": reported,
            "true_positive_rate": opportunity,
            "gaps": gaps,
            "withheld_groups": withheld,
            "withheld_reason": (WITHHELD if withheld else ""),
        }


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def reference_preregistration() -> Preregistration:
    """The study this architecture would need, written out in full.

    It is published as a concrete artefact so that a reviewer can argue with the
    design, and so that an institution that wants to run it has something to
    start from rather than an invitation to future work.
    """
    return Preregistration(
        title="Mediated agent assistance in transcript correction: utility, "
              "review cost and outcome distribution",
        hypotheses=(
            "H1: mediated agent assistance completes at least as many correction "
            "tasks as the existing manual process",
            "H2: mediated agent assistance reduces median time to decision",
            "H3: mediated agent assistance does not increase the reviewer overturn "
            "rate, which would indicate reviewers rubber-stamping proposals",
            "H4: approval rates among eligible cases do not differ across declared "
            "subgroups by more than the preregistered equivalence margin",
        ),
        primary_outcome="task_completion",
        secondary_outcomes=("seconds_to_decision", "reviewer_overturn",
                            "equal_opportunity_gap"),
        subgroup_attributes=("enrolment_status", "campus"),
        minimum_sample=400,
        minimum_cell=30,
        analysis_plan=(
            "Two-arm comparison against the existing manual process over one "
            "term. Primary outcome analysed with a two-proportion test at alpha "
            "0.05. Secondary outcomes reported with 95% Wilson intervals and no "
            "multiplicity correction claim. Subgroup analyses are preregistered "
            "and reported in full, including null results. No outcome is "
            "substituted after data collection begins."
        ),
        approval_reference="",
    )


__all__ = [
    "INSTITUTIONAL", "PROVENANCE", "SYNTHETIC", "WITHHELD", "Dataset",
    "DecisionRecord", "InstitutionalStudy", "Preregistration", "StudyRefusal",
    "reference_preregistration", "wilson_interval",
]
