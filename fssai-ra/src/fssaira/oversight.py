"""Human review as a finite resource, with a declared capacity and a bound.

Every other control in this architecture treats the named human as the place
authority stops. That is correct and incomplete. An approval requirement is only
a control while the person supplying it is actually deciding, and attention is
the one input in the whole pipeline that does not scale with the hardware.

The failure this module addresses is not exotic. It is the ordinary arithmetic of
an institution that automates a queue: four thousand cases arrive, eleven
officers are rostered, each consequential action needs a named approval, and the
median time a reviewer spends on one falls until an approval is a keystroke. At
that point every mechanism in this repository still passes its tests. The
digests bind, the signatures verify, the chain is intact, the evidence is
complete — and the oversight it all funnels into has quietly become a signature
service. A system can be perfectly accountable and completely unreviewed.

So oversight is modelled here the way any other scarce, safety-relevant resource
would be: with a **declared capacity**, an **enforcement point that refuses work
beyond it**, and a **published measurement** of how close the deployment runs to
its own ceiling.

Three controls
--------------
**A capacity ceiling.** A reviewer may issue at most ``max_approvals_per_window``
consequential approvals per window. Beyond it the approval is refused and the
action takes the profile's manual fallback. Refusing to *issue* the approval,
rather than flagging it afterwards, is what makes this a control instead of a
dashboard.

**A deliberation floor.** An approval returned faster than
``min_deliberation_seconds`` after the proposal was presented is refused. The
floor does not detect a careless reviewer — a fast approval can be a correct one,
and a slow one can be inattentive. What it bounds is the *regime*: sustained
approval below any plausible reading time is a measurable property of a queue,
and it is the signature of a control that has stopped functioning.

**Mandatory escalation.** Past ``second_reviewer_after`` approvals in a window,
the next consequential action requires a second, distinct reviewer. Load is
therefore visible in the process rather than absorbed silently by one person.

What is measured, and what is merely declared
---------------------------------------------
This module measures whether the controls bind, exactly and deterministically.
It does **not** measure human reviewers. The degradation curve in
:class:`DeclaredReviewerModel` is a *parameter an institution supplies*, not a
finding of this work: no reviewer was observed, no error rate was estimated, and
no claim is made here about how real officers behave under load. That study is
named as open work in ``docs/ASSURANCE.md``.

The distinction matters, because the useful result survives it. Given *any*
degradation curve an institution is willing to declare, the ceiling implied by
its own staffing is arithmetic, and whether the control binds at that ceiling is
a test. Both are reproducible without watching a single person work.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .exact_action import (
    ActionProposal,
    ApprovalAuthority,
    CaseRegister,
    ExecutionDenied,
)

#: One working day, used only for the published capacity arithmetic below.
SECONDS_PER_DAY = 86_400.0


class OversightCode:
    """Stable denial codes for the oversight gate.

    Part of the public contract, like :class:`fssaira.accountable_action.DenyCode`:
    tests, metrics, and the results tables key on these strings.
    """

    REVIEW_CAPACITY_EXCEEDED = "REVIEW_CAPACITY_EXCEEDED"
    DELIBERATION_TOO_SHORT = "DELIBERATION_TOO_SHORT"
    DELIBERATION_UNVERIFIABLE = "DELIBERATION_UNVERIFIABLE"
    SECOND_REVIEWER_REQUIRED = "SECOND_REVIEWER_REQUIRED"
    SECOND_REVIEWER_NOT_DISTINCT = "SECOND_REVIEWER_NOT_DISTINCT"
    ADMITTED = "ADMITTED"


@dataclass(frozen=True)
class ReviewLoadPolicy:
    """The capacity an institution declares it can actually supply.

    These are deployment configuration, not constants of nature. An institution
    that cannot state them has not established that it can oversee the capability
    it is about to automate — which is the same diagnostic the seven-field
    control contract applies to everything else.
    """

    #: Consequential approvals one reviewer may issue per window.
    max_approvals_per_window: int = 20
    #: Length of the window, in seconds.
    window_seconds: float = 3_600.0
    #: Floor on the interval between presenting a proposal and approving it.
    min_deliberation_seconds: float = 45.0
    #: Approvals in a window after which a second, distinct reviewer is required.
    #: ``None`` disables escalation.
    second_reviewer_after: int | None = 12
    #: Seconds per day a reviewer is actually available for this queue. Used only
    #: for the published capacity figure, never for enforcement.
    reviewing_seconds_per_day: float = 4 * 3_600.0

    def __post_init__(self) -> None:
        if self.max_approvals_per_window < 1:
            raise ValueError("max_approvals_per_window must be at least 1")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if self.min_deliberation_seconds < 0:
            raise ValueError("min_deliberation_seconds must not be negative")
        if self.second_reviewer_after is not None and self.second_reviewer_after < 1:
            raise ValueError("second_reviewer_after must be at least 1 when set")
        if self.reviewing_seconds_per_day <= 0:
            raise ValueError("reviewing_seconds_per_day must be positive")
        if (
            self.second_reviewer_after is not None
            and self.second_reviewer_after > self.max_approvals_per_window
        ):
            raise ValueError("escalation threshold is unreachable below the capacity ceiling")

    # -- the published arithmetic -----------------------------------------
    def sustainable_actions_per_day(self, reviewers: int) -> dict:
        """How many consequential actions this roster can genuinely review daily.

        Two independent ceilings apply and the smaller one binds:

        * the **policy ceiling**, from the declared per-window quota, and
        * the **attention ceiling**, from the deliberation floor and the hours a
          reviewer is actually available.

        Publishing both, and naming which one binds, is the point. An institution
        whose demand exceeds this figure is not choosing between fast and slow
        review; it is choosing between review and the appearance of it.
        """
        if reviewers < 1:
            raise ValueError("reviewers must be at least 1")
        windows_per_day = SECONDS_PER_DAY / self.window_seconds
        policy_ceiling = reviewers * self.max_approvals_per_window * windows_per_day
        attention_ceiling = (
            reviewers * self.reviewing_seconds_per_day / self.min_deliberation_seconds
            if self.min_deliberation_seconds > 0
            else float("inf")
        )
        binding = "policy_quota" if policy_ceiling <= attention_ceiling else "deliberation_floor"
        return {
            "reviewers": reviewers,
            "policy_ceiling_per_day": round(policy_ceiling, 2),
            "attention_ceiling_per_day": (
                round(attention_ceiling, 2) if attention_ceiling != float("inf") else None
            ),
            "sustainable_per_day": round(min(policy_ceiling, attention_ceiling), 2),
            "binding_constraint": binding,
            "note": (
                "arithmetic over declared capacity, not a measurement of reviewers; "
                "substitute your own roster and deliberation floor"
            ),
        }

    def to_dict(self) -> dict:
        return {
            "max_approvals_per_window": self.max_approvals_per_window,
            "window_seconds": self.window_seconds,
            "min_deliberation_seconds": self.min_deliberation_seconds,
            "second_reviewer_after": self.second_reviewer_after,
            "reviewing_seconds_per_day": self.reviewing_seconds_per_day,
        }


@dataclass(frozen=True)
class ReviewRecord:
    """One admitted review, retained for measurement."""

    reviewer: str
    request_id: str
    presented_at: float
    approved_at: float
    escalated: bool
    second_reviewer: str | None

    @property
    def deliberation_seconds(self) -> float:
        return self.approved_at - self.presented_at


class OversightMonitor:
    """Enforcement point for the review-load policy, and its measurement.

    Deliberately separate from :class:`fssaira.exact_action.ApprovalAuthority`:
    the authority proves *who* approved, this proves the approval was issued
    under conditions in which review was still possible. Combining them would
    make it impossible to ablate one without the other, and an ablation that
    cannot isolate a control cannot attribute anything to it.
    """

    def __init__(self, policy: ReviewLoadPolicy | None = None) -> None:
        self.policy = policy or ReviewLoadPolicy()
        self._records: list[ReviewRecord] = []
        self.refusals: dict[str, int] = defaultdict(int)

    # -- enforcement -------------------------------------------------------
    def admit(
        self,
        *,
        reviewer: str,
        request_id: str,
        now: float,
        presented_at: float | None,
        second_reviewer: str | None = None,
    ) -> ReviewRecord:
        """Admit one review, or refuse it with a stable code.

        Refusal raises :class:`~fssaira.exact_action.ExecutionDenied`, so an
        exhausted reviewer cannot produce a signed approval at all. The action
        then takes the profile's declared manual fallback, which is the
        fail-secure behaviour the rest of the architecture already assumes.
        """
        policy = self.policy

        if policy.min_deliberation_seconds > 0 and presented_at is None:
            self._refuse(OversightCode.DELIBERATION_UNVERIFIABLE)
            raise ExecutionDenied(
                OversightCode.DELIBERATION_UNVERIFIABLE,
                "a deliberation floor is configured but the presentation time is unknown",
            )

        prior = self._in_window(reviewer, now)
        if len(prior) >= policy.max_approvals_per_window:
            self._refuse(OversightCode.REVIEW_CAPACITY_EXCEEDED)
            raise ExecutionDenied(
                OversightCode.REVIEW_CAPACITY_EXCEEDED,
                f"reviewer '{reviewer}' is at the declared ceiling of "
                f"{policy.max_approvals_per_window} approvals per window",
            )

        if presented_at is not None:
            elapsed = now - presented_at
            if elapsed < policy.min_deliberation_seconds:
                self._refuse(OversightCode.DELIBERATION_TOO_SHORT)
                raise ExecutionDenied(
                    OversightCode.DELIBERATION_TOO_SHORT,
                    f"approval returned in {elapsed:.1f}s, below the declared "
                    f"deliberation floor of {policy.min_deliberation_seconds:.1f}s",
                )

        escalated = (
            policy.second_reviewer_after is not None
            and len(prior) >= policy.second_reviewer_after
        )
        if escalated:
            if second_reviewer is None:
                self._refuse(OversightCode.SECOND_REVIEWER_REQUIRED)
                raise ExecutionDenied(
                    OversightCode.SECOND_REVIEWER_REQUIRED,
                    f"reviewer '{reviewer}' has issued {len(prior)} approvals this "
                    "window; a second, distinct reviewer is required",
                )
            if second_reviewer == reviewer:
                self._refuse(OversightCode.SECOND_REVIEWER_NOT_DISTINCT)
                raise ExecutionDenied(
                    OversightCode.SECOND_REVIEWER_NOT_DISTINCT,
                    "the escalation reviewer must not be the primary reviewer",
                )

        record = ReviewRecord(
            reviewer=reviewer,
            request_id=request_id,
            presented_at=now if presented_at is None else presented_at,
            approved_at=now,
            escalated=escalated,
            second_reviewer=second_reviewer if escalated else None,
        )
        self._records.append(record)
        return record

    def _refuse(self, code: str) -> None:
        self.refusals[code] += 1

    def _in_window(self, reviewer: str, now: float) -> list[ReviewRecord]:
        floor = now - self.policy.window_seconds
        return [
            record for record in self._records
            if record.reviewer == reviewer and record.approved_at > floor
        ]

    # -- measurement -------------------------------------------------------
    @property
    def records(self) -> tuple[ReviewRecord, ...]:
        return tuple(self._records)

    def report(self, *, reviewers: int | None = None) -> OversightReport:
        distinct = sorted({record.reviewer for record in self._records})
        return OversightReport(
            policy=self.policy,
            records=tuple(self._records),
            refusals=dict(self.refusals),
            roster=reviewers if reviewers is not None else max(len(distinct), 1),
        )


@dataclass(frozen=True)
class OversightReport:
    """What a deployment can publish about the state of its own oversight.

    None of these figures require access to a case, a student record, or the
    content of a decision. An institution can therefore publish them — which is
    what makes reviewer load an accountable quantity rather than an internal one.
    """

    policy: ReviewLoadPolicy
    records: tuple[ReviewRecord, ...]
    refusals: dict = field(default_factory=dict)
    roster: int = 1

    @property
    def approvals(self) -> int:
        return len(self.records)

    @property
    def per_reviewer(self) -> dict:
        counts: dict[str, int] = defaultdict(int)
        for record in self.records:
            counts[record.reviewer] += 1
        return dict(sorted(counts.items()))

    @property
    def median_deliberation_seconds(self) -> float:
        if not self.records:
            return 0.0
        values = sorted(record.deliberation_seconds for record in self.records)
        middle = len(values) // 2
        if len(values) % 2:
            return round(values[middle], 3)
        return round((values[middle - 1] + values[middle]) / 2, 3)

    @property
    def escalations(self) -> int:
        return sum(record.escalated for record in self.records)

    @property
    def refusals_total(self) -> int:
        return sum(self.refusals.values())

    @property
    def headroom(self) -> float:
        """Fraction of the declared per-window ceiling left unused, worst reviewer.

        ``0.0`` means at least one reviewer is saturated: the deployment is
        running at the edge of the capacity it declared, and the next arrival
        takes the manual fallback rather than the automated path.
        """
        counts = self.per_reviewer
        if not counts:
            return 1.0
        busiest = max(counts.values())
        ceiling = self.policy.max_approvals_per_window
        return round(max(0.0, (ceiling - busiest) / ceiling), 4)

    def to_dict(self) -> dict:
        return {
            "schema_version": "1.0",
            "kind": "oversight-load",
            "policy": self.policy.to_dict(),
            "observed": {
                "approvals_admitted": self.approvals,
                "approvals_per_reviewer": self.per_reviewer,
                "median_deliberation_seconds": self.median_deliberation_seconds,
                "escalations_required": self.escalations,
                "refusals_total": self.refusals_total,
                "refusals_by_code": dict(sorted(self.refusals.items())),
                "capacity_headroom": self.headroom,
            },
            "capacity": self.policy.sustainable_actions_per_day(self.roster),
            "limits": [
                "the deliberation floor bounds a regime, not the quality of any one decision",
                "no reviewer was observed; the degradation model is a declared parameter",
                "capacity arithmetic assumes the declared roster is actually available",
                "refusing an approval preserves the boundary; it does not serve the student",
            ],
        }


@dataclass
class DeclaredReviewerModel:
    """A reviewer whose attention degrades with load, by declared parameters.

    **This is a fixture, not a finding.** It exists so that the fatigue scenario
    is deterministic and reproducible, and so an institution can substitute its
    own curve. It asserts nothing about how real officers behave.

    The model: the reviewer reads carefully — and so catches a proposal they
    should refuse — while their load this window is below ``attentive_until``.
    Past it, they approve whatever is in front of them, and they do it in
    ``fatigued_seconds``, which is the observable the deliberation floor keys on.
    """

    attentive_until: int = 8
    careful_seconds: float = 90.0
    fatigued_seconds: float = 3.0
    reviewed: int = 0

    def review(self, *, should_refuse: bool) -> tuple[bool, float]:
        """Return ``(approves, seconds_taken)`` for one proposal."""
        self.reviewed += 1
        if self.reviewed <= self.attentive_until:
            return (not should_refuse, self.careful_seconds)
        return (True, self.fatigued_seconds)  # the rubber stamp

    def reset(self) -> None:
        self.reviewed = 0


__all__ = [
    "DeclaredReviewerModel",
    "OversightCode",
    "OversightMonitor",
    "OversightReport",
    "ReviewLoadPolicy",
    "ReviewRecord",
    "SECONDS_PER_DAY",
    "run_queue_pressure_trial",
]


# ---------------------------------------------------------------------------
# The queue-pressure trial
# ---------------------------------------------------------------------------
#
# Every other adversarial scenario in this repository attacks a *mechanism*: a
# digest that should not match, a signature that should not verify, a role that
# should not apply. The executor catches all of them without a human present,
# which is the point of having an independent enforcement point.
#
# This trial attacks the one thing no mechanism can check. A proposal that is
# structurally perfect — right operation, right transition, current version,
# authentic approval — can still be substantively wrong: the applicant is not
# eligible, the evidence does not support the recommendation, the case needed a
# conversation rather than a status change. No digest detects that. No invariant
# rules it out. The *only* control the architecture has against it is a person
# who is actually reading.
#
# Which is why reviewer load is a security property and not an HR one. Fatigue
# does not break a single control; it silently deletes the last control standing
# behind an entire class of harm, and leaves every test in this repository green
# while it does so.

def _demand_ratio(arrivals: int, reviewer: DeclaredReviewerModel) -> dict:
    """How far past its own declared attention budget this queue ran.

    The deferral count in the controlled arm is not a defect to be tuned away.
    It is the measurement: a queue that sends 40 arrivals to a reviewer who
    declared attention for 8 is not choosing between automation and delay, it is
    choosing between review and the appearance of it. The control converts that
    choice from invisible to arithmetic.
    """
    budget = max(reviewer.attentive_until, 1)
    return {
        "arrivals": arrivals,
        "declared_attentive_capacity": reviewer.attentive_until,
        "ratio": round(arrivals / budget, 2),
        "reading": (
            "deferrals in the controlled arm measure the gap between demand and "
            "declared capacity; they are a finding, not a failure of the control"
        ),
    }


def run_queue_pressure_trial(
    profile,
    *,
    arrivals: int = 40,
    merit_refusals_every: int = 7,
    policy: ReviewLoadPolicy | None = None,
    reviewer: DeclaredReviewerModel | None = None,
    reviewer_name: str = "officer-1",
    start: float = 1_000_000.0,
) -> dict:
    """Run one queue of arrivals past one reviewer, with and without load control.

    Both arms face the identical queue, the identical reviewer, and the identical
    declared degradation curve. The only difference is whether the deployment
    declared a review-load policy and let it refuse work beyond capacity.

    Returns a report, never raises for an expected denial.
    """
    from .evidence import EvidenceLedger  # local: keeps the module's imports minimal

    rule = next((r for r in profile.transitions if r.consequential), profile.transitions[0])
    template = reviewer or DeclaredReviewerModel()
    arms: dict[str, dict] = {}

    for arm, load_control in (("no_load_control", False), ("declared_load_control", True)):
        monitor = OversightMonitor(policy or ReviewLoadPolicy()) if load_control else None
        model = DeclaredReviewerModel(
            attentive_until=template.attentive_until,
            careful_seconds=template.careful_seconds,
            fatigued_seconds=template.fatigued_seconds,
        )
        token = "oversight-evidence-writer"
        cases = {
            f"case-{index}": {"status": rule.from_status, "version": 1}
            for index in range(arrivals)
        }
        register = CaseRegister(cases)
        evidence = EvidenceLedger(token)
        authority = ApprovalAuthority(oversight=monitor)
        executor = profile.make_executor(register, evidence, token)

        counters = {
            "merit_refusals_required": 0,
            "reviewer_refused_on_merit": 0,
            "harmful_executed": 0,
            "benign_executed": 0,
            "deferred_to_manual_fallback": 0,
            "refusals_by_code": {},
        }
        now = start

        for index in range(arrivals):
            should_refuse = index % merit_refusals_every == merit_refusals_every - 1
            counters["merit_refusals_required"] += int(should_refuse)

            approves, seconds = model.review(should_refuse=should_refuse)
            presented_at = now
            now += seconds
            if not approves:
                counters["reviewer_refused_on_merit"] += 1
                continue

            proposal = ActionProposal(
                request_id=f"queue-{arm}-{index}",
                requester="bounded-agent",
                operation=rule.operation,
                case_id=f"case-{index}",
                expected_version=1,
                from_status=rule.from_status,
                to_status=rule.to_status,
                evidence_version=f"snapshot-{index}",
            )
            try:
                approval = authority.approve(
                    proposal,
                    approver=reviewer_name,
                    approver_role=rule.approval_role,
                    now=now,
                    presented_at=presented_at,
                )
                executor.execute(proposal, approval, now=now)
            except ExecutionDenied as denial:
                counters["deferred_to_manual_fallback"] += 1
                counters["refusals_by_code"][denial.code] = (
                    counters["refusals_by_code"].get(denial.code, 0) + 1
                )
                continue
            if should_refuse:
                counters["harmful_executed"] += 1
            else:
                counters["benign_executed"] += 1

        counters["mutations"] = register.mutation_count
        counters["evidence_chain_valid"] = evidence.verify()
        if monitor is not None:
            counters["oversight"] = monitor.report(reviewers=1).to_dict()["observed"]
        arms[arm] = counters

    contained = arms["declared_load_control"]["harmful_executed"]
    uncontrolled = arms["no_load_control"]["harmful_executed"]
    return {
        "schema_version": "1.0",
        "kind": "queue-pressure-trial",
        "profile_id": profile.profile_id,
        "arrivals": arrivals,
        "reviewer_model": {
            "attentive_until": template.attentive_until,
            "careful_seconds": template.careful_seconds,
            "fatigued_seconds": template.fatigued_seconds,
            "status": "declared parameter, not a measurement of any reviewer",
        },
        "policy": (policy or ReviewLoadPolicy()).to_dict(),
        "arms": arms,
        "summary": {
            "harmful_executed_without_load_control": uncontrolled,
            "harmful_executed_with_load_control": contained,
            "load_control_is_load_bearing": contained < uncontrolled,
            "deferred_to_manual_fallback": arms["declared_load_control"][
                "deferred_to_manual_fallback"
            ],
            "demand_to_declared_capacity": _demand_ratio(arrivals, template),
        },
        "limits": [
            "the degradation curve is declared, not observed; substitute your own",
            "refusing an approval preserves the boundary and delays the student",
            "deferral to manual review is a cost, and it is reported as one",
            "this trial models one reviewer and one queue, not an institution",
        ],
    }
