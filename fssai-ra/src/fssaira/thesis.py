"""Try to refute the Mediation Thesis, and report honestly how hard we tried.

    **Intelligence is untrusted. Power and data are mediated.**

A foundation is worth building on only if it can be wrong in a way anyone can
check. This module turns the thesis in ``docs/THESIS.md`` into six falsifiers and
runs every one of them against every declared domain pack. Each falsifier reports
how many bounded attempts it made, how many counterexamples it found, and the
scope inside which the answer holds. Zero counterexamples means *not refuted
within the stated bounds*. It never means proven.

A suite that cannot fail proves nothing, so each falsifier accepts a weakened
configuration and ``tests/test_thesis.py`` shows that removing one mediator check
produces counterexamples.

F1 unmediated effect      a model output alone causes a governed state change
F2 unentitled read        protected data reaches a model without a current entitlement
F3 laundered release      an output reaches an uncleared recipient, or after entitlement ended
F4 amplified delegation   a delegation chain confers more authority than its root
F5 decorative control     a control can be removed without any harm returning
F6 phantom evidence       a requirement, binding, threat, or spec entry cites evidence that is absent
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

THESIS = "Intelligence is untrusted. Power and data are mediated."
COMMITMENTS = (
    "Untrusted intelligence: treat every model as capable, persuasive, and possibly "
    "mistaken, manipulated, or misaligned; its output is a proposal or a request",
    "Mediated power: every effect and every flow of protected information passes a "
    "mediator the model cannot bypass, influence, or impersonate",
    "Evidenced trust: every mediation is contracted, tested, and evidenced in the "
    "deployment that relies on it",
)
RULES = (
    "A model may propose an action. It cannot manufacture the authority to execute it.",
    "A model may request information. It cannot manufacture the entitlement to see it, "
    "and it cannot launder what it saw.",
)
#: The components whose compromise defeats the thesis. Declared, not verified.
TRUSTED_BASE = (
    "authority executor and its write credential",
    "disclosure gate and its record-store credential",
    "approval, grant, and declassification signing keys",
    "evidence store and its append credential",
    "identity provider and role assignment",
    "interface inventory and the administrators of all of the above",
)

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Falsifier:
    id: str
    name: str
    refuted_by: str
    attempts: int = 0
    counterexamples: int = 0
    scope: list = field(default_factory=list)
    detail: dict = field(default_factory=dict)

    @property
    def refuted(self) -> bool:
        return self.counterexamples > 0

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "refuted_by": self.refuted_by,
                "attempts": self.attempts, "counterexamples": self.counterexamples,
                "refuted": self.refuted, "scope": self.scope, "detail": self.detail}


@dataclass
class ThesisReport:
    falsifiers: list
    residuals: list
    generated_at: str

    @property
    def attempts(self) -> int:
        return sum(f.attempts for f in self.falsifiers)

    @property
    def counterexamples(self) -> int:
        return sum(f.counterexamples for f in self.falsifiers)

    @property
    def holds(self) -> bool:
        return self.counterexamples == 0

    def to_dict(self) -> dict:
        return {
            "schema_version": "1.0",
            "kind": "mediation-thesis-falsification",
            "generated_at": self.generated_at,
            "thesis": THESIS,
            "commitments": list(COMMITMENTS),
            "rules": list(RULES),
            "summary": {
                "falsifiers": len(self.falsifiers),
                "attempts": self.attempts,
                "counterexamples": self.counterexamples,
                "verdict": ("not refuted within the stated bounds" if self.holds
                            else "REFUTED: see counterexamples"),
                "holds": self.holds,
            },
            "falsifiers": [f.to_dict() for f in self.falsifiers],
            "trusted_base": list(TRUSTED_BASE),
            "residuals": self.residuals,
            "reading": [
                "an attempt is one bounded configuration, scenario, operation, ablation, or "
                "evidence reference that could have produced a counterexample",
                "zero counterexamples means not refuted inside the declared scope; it is not a "
                "proof and not a security probability",
                "the thesis assumes the trusted base holds; its compromise is outside every "
                "falsifier and is listed so that nobody mistakes silence for coverage",
            ],
        }


def _packs(root: Path) -> list:
    from .profiles import ApplicationProfile, discover_profiles

    return [ApplicationProfile.load(item["path"])
            for item in discover_profiles(root / "profiles")]


def falsify_unmediated_effect(packs: Iterable, evaluations: dict) -> Falsifier:
    from .verification import verify_profile

    result = Falsifier("F1", "Unmediated effect",
                       "a model output alone causes a governed state change")
    for profile in packs:
        report = verify_profile(profile)
        evaluation = evaluations[profile.profile_id]
        result.attempts += report.states_explored + evaluation.total
        found = len(report.violations) + evaluation.unauthorized_mutations
        result.counterexamples += found
        result.detail[profile.profile_id] = {
            "configurations": report.states_explored, "hostile_scenarios": evaluation.total,
            "counterexamples": found,
        }
    result.scope = ["declared statuses, operations, approval variants, versions, and presence",
                    "single-process execution; distributed interleavings out of scope"]
    return result


def falsify_disclosure(packs: Iterable, *, enforce=None) -> tuple:
    from .disclosure import ALL_CHECKS
    from .disclosure_eval import verify_disclosure_space
    from .disclosure_stateful import run_stateful

    checks = frozenset(ALL_CHECKS if enforce is None else enforce)
    read = Falsifier("F2", "Unentitled read",
                     "protected data reaches a model context without a current, holder-bound, "
                     "purpose-bound grant and consent")
    release = Falsifier("F3", "Laundered release",
                        "an output reaches a recipient that does not dominate its label, or is "
                        "released after consent, revocation, or expiry should have stopped it")
    for profile in packs:
        if profile.disclosure is None:
            continue
        space = verify_disclosure_space(profile.disclosure, profile_id=profile.profile_id)
        release_invariants = ("DX-4", "DX-7")
        release_violations = sum(1 for v in space.violations
                                 if v.invariant.startswith(release_invariants))
        read.attempts += space.read_states
        read.counterexamples += len(space.violations) - release_violations
        stateful = run_stateful(profile.disclosure, sequences=150, steps=40, enforce=checks)
        release.attempts += space.release_states + stateful.steps
        release.counterexamples += release_violations + len(stateful.disagreements)
        read.detail[profile.profile_id] = {"read_configurations": space.read_states}
        release.detail[profile.profile_id] = {
            "release_configurations": space.release_states,
            "stateful_operations": stateful.steps,
            "stateful_disagreements": len(stateful.disagreements),
        }
    read.scope = ["grant defects, purpose, subject, field, clearance, consent, endpoint, "
                  "break-glass, and evidence availability for one read"]
    release.scope = ["claimed label, recipient, purpose, declassification, and live state at "
                     "release", "random sequences of grant, revoke, consent, time, read, "
                     "derive, declassify, and release"]
    if enforce is not None:
        release.scope.append(f"weakened configuration: {sorted(set(ALL_CHECKS) - checks)} removed")
    return read, release


def falsify_amplified_delegation() -> Falsifier:
    from .delegation import verify_delegation_space

    space = verify_delegation_space()
    result = Falsifier("F4", "Amplified delegation",
                       "a delegation chain confers more authority than its root")
    result.attempts = space.states_explored
    result.counterexamples = len(space.violations)
    result.scope = ["declared chain shapes, depths, expiries, signers, and principals"]
    return result


def falsify_decorative_controls(packs: Iterable, evaluations: dict) -> Falsifier:
    from .delegation_eval import ablate_delegation
    from .disclosure_eval import run_disclosure_suite

    result = Falsifier("F5", "Decorative control",
                       "removing a control lets no harm through")
    for profile in packs:
        coverage = evaluations[profile.profile_id].coverage
        result.attempts += coverage.controls_declared
        result.counterexamples += coverage.controls_declared - coverage.controls_load_bearing
        if profile.disclosure is not None:
            suite = run_disclosure_suite(profile.disclosure, profile_id=profile.profile_id,
                                         verify=False)
            result.attempts += len(suite.ablations)
            result.counterexamples += sum(1 for row in suite.ablations if not row["load_bearing"])
    rows = ablate_delegation()
    result.attempts += len(rows)
    result.counterexamples += sum(1 for row in rows if not row["load_bearing"])
    result.scope = ["each authority, disclosure, and delegation control removed in turn "
                    "against its declared hostile scenarios"]
    return result


_SPEC_ROW = re.compile(r"^\|\s*([A-Z]-\d+)\s*\|\s*(?:MUST NOT|MUST|SHOULD|MAY)\s*\|.+\|(.+)\|\s*$",
                       re.M)


def falsify_phantom_evidence(root: Path) -> Falsifier:
    from .coverage import load_bindings, measure_coverage
    from .threats import check_catalogue, locator_exists

    result = Falsifier("F6", "Phantom evidence",
                       "a requirement, binding, threat, or specification entry cites evidence "
                       "that does not exist or runs nothing")
    missing: list = []

    coverage = measure_coverage(str(root / "contract"))
    result.attempts += coverage.total
    unverified = list(coverage.unverified_ids) + list(coverage.unknown_bindings)
    missing += [f"contract requirement unbound: {item}" for item in unverified]

    for binding in load_bindings(str(root / "contract")):
        for locator in (part.strip() for part in binding.locator.split(",")):
            if not locator.startswith(("tests/", "src/")):
                continue
            result.attempts += 1
            if not locator_exists(root, locator):
                missing.append(f"contract binding {binding.requirement_id}: {locator}")

    threats = check_catalogue(root / "threats" / "catalogue.yaml", root)
    result.attempts += sum(len(t.evidence) for t in threats.threats)
    missing += [f"threat evidence: {item}" for item in threats.missing_locators]

    spec = (root / "docs" / "SPECIFICATION.md").read_text(encoding="utf-8")
    for requirement_id, evidence in _SPEC_ROW.findall(spec):
        for locator in re.findall(r"`(tests/[^`]+)`", evidence):
            result.attempts += 1
            if not locator_exists(root, locator):
                missing.append(f"specification {requirement_id}: {locator}")

    result.counterexamples = len(missing)
    result.detail = {"missing": missing}
    result.scope = ["every contract requirement, binding locator under tests/ or src/, threat "
                    "evidence locator, and specification test citation"]
    return result


def run_thesis(root: Path | None = None) -> ThesisReport:
    from .evaluation import EvaluationRunner
    from .threats import check_catalogue

    base = Path(root) if root is not None else ROOT
    packs = _packs(base)
    evaluations = {p.profile_id: EvaluationRunner(p).run(include_utility=False) for p in packs}
    read, release = falsify_disclosure(packs)
    falsifiers = [
        falsify_unmediated_effect(packs, evaluations),
        read,
        release,
        falsify_amplified_delegation(),
        falsify_decorative_controls(packs, evaluations),
        falsify_phantom_evidence(base),
    ]
    catalogue = check_catalogue(base / "threats" / "catalogue.yaml", base)
    residuals = [{"id": t.id, "title": t.title, "remains": t.residual}
                 for t in catalogue.threats if t.status == "residual"]
    return ThesisReport(falsifiers, residuals, datetime.now(timezone.utc).isoformat())


__all__ = [
    "COMMITMENTS", "Falsifier", "RULES", "THESIS", "TRUSTED_BASE", "ThesisReport",
    "falsify_amplified_delegation", "falsify_decorative_controls", "falsify_disclosure",
    "falsify_phantom_evidence", "falsify_unmediated_effect", "run_thesis",
]
