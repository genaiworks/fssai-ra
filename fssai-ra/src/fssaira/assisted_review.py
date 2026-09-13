"""When the reviewer also has a model: independence as a declarable property.

``fssaira.oversight`` establishes that human review is a finite resource with a
computable ceiling, and that pushing a queue past it turns oversight into a
signature service while every test stays green. That argument has one assumption
buried in it, and by 2026 it is the wrong one: it models an **unaided** reader.

Institutions deploying capable models will not staff review with unaided
readers. They will give the reviewer an assistant — a model that reads the case,
condenses it, and increasingly recommends a disposition. This is not a
governance failure. It is the obvious and largely correct response to a queue
that exceeds the roster, and it genuinely works: a reviewer handed a good summary
decides faster and decides well.

The problem is what it does to the one control standing behind merit failures.

The mechanism
-------------
The deliberation floor is calibrated to unaided human reading time. An assisted
reviewer legitimately decides in a fraction of it, so an institution that
deploys assistance *must* lower the floor or it throttles reviewers who are
doing their jobs. Lowering it is correct.

But the floor was never really measuring seconds. It was a proxy for *a second
mind independently reaching the same conclusion*. Whether that proxy survives
assistance depends entirely on a property nobody currently declares: **is the
assistant independent of the proposer?**

If the review assistant is the same model family, reading the same evidence
packet, with the same framing, then it is not a second mind. It is the proposer's
reasoning arriving a second time wearing a reviewer's badge. On exactly the cases
where the proposer was wrong — the applicant is ineligible, the evidence does not
support the recommendation, the case needed a conversation — the assistant is
wrong the same way, for the same reason, and it is *confident*. The reviewer
ratifies. Every mechanism in this repository still passes: the digest binds, the
signature verifies, the chain is intact, the reviewer is within quota, the
deliberation interval clears the lowered floor. And the merit failures execute.

This is correlated failure between the proposer and the checker, which is an old
result in dependable systems and a new one here only because the two components
are now the same technology. The control it breaks is the last one the
architecture has.

What this module adds
---------------------
**Independence is declared, not assumed.** Three properties, each separately
answerable by an institution about its own deployment: a different model from the
proposer, a different evidence path, and an adversarial posture — the assistant
tasked with finding grounds to refuse rather than producing a summary.

**The floor an institution may set is a function of what it declared.** Assistance
buys throughput in proportion to demonstrated independence and not otherwise. A
deployment that lowers the deliberation floor while declaring a dependent
assistant is refused at configuration time, with a stable code, in the same
fail-secure way an over-capacity approval is refused at issue time.

**The trial measures the correlation rather than asserting it.** Identical
queues, identical merit failures, identical lowered floor; the arms differ only
in the declared independence of the assistant.

Limits, stated in the same terms as everything else here
--------------------------------------------------------
The correlation coefficient between a proposing model and a dependent review
assistant is a **declared parameter**, exactly like the reviewer degradation
curve in :mod:`fssaira.oversight`. No model was evaluated, no assistant was
measured, and no rate is claimed for any named system. What is demonstrated is
that *given any correlation an institution is willing to declare*, the throughput
it may safely buy is computable, and whether the control binds at that line is a
test. Measuring real proposer/assistant correlation is named open work in
``docs/ASSURANCE.md``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .exact_action import (
    ActionProposal,
    ApprovalAuthority,
    CaseRegister,
    ExecutionDenied,
)
from .oversight import OversightMonitor, ReviewLoadPolicy


class AssistanceMode(Enum):
    """What the assistant actually does to the reviewer's decision."""

    #: No assistance. The reviewer reads the case.
    UNAIDED = "unaided"
    #: The assistant condenses the evidence; the reviewer reads the summary.
    SUMMARISED = "summarised"
    #: The assistant proposes a disposition; the reviewer ratifies or overrides.
    RECOMMENDED = "recommended"


class AssistedReviewCode:
    """Stable denial codes for the assisted-review gate."""

    FLOOR_BELOW_DECLARED_INDEPENDENCE = "FLOOR_BELOW_DECLARED_INDEPENDENCE"
    ASSISTANCE_NOT_DECLARED = "ASSISTANCE_NOT_DECLARED"
    ADMITTED = "ADMITTED"


@dataclass(frozen=True)
class ReviewAssistance:
    """What the institution declares about the model helping its reviewers.

    Each property is a question an institution can answer about its own
    deployment without measuring anything, and all three are things a procurement
    process can require in writing. That is the design goal: independence has to
    be *declarable* before it can be enforced.

    ``independent_model`` — a different model, from a different family or
    provider, than the one that produced the proposal. Two instances of the same
    model with different prompts do not qualify; the correlated error is in the
    weights, not the prompt.

    ``independent_evidence`` — the assistant reads the authoritative record, not
    the packet the proposing agent assembled. An assistant handed the proposer's
    selection of the evidence inherits the proposer's selection errors, which are
    the ones that matter.

    ``adversarial_posture`` — the assistant is tasked with finding grounds to
    refuse and surfacing what is missing, not with summarising. A summariser is
    optimised to agree with its input; the failure mode of a summariser on a
    wrong proposal is a fluent summary of a wrong proposal.
    """

    mode: AssistanceMode = AssistanceMode.UNAIDED
    independent_model: bool = False
    independent_evidence: bool = False
    adversarial_posture: bool = False
    declared_by: str = ""
    assistant_name: str = ""

    @property
    def independence_score(self) -> int:
        """0 to 3. Not a measurement — a count of declarations."""
        if self.mode is AssistanceMode.UNAIDED:
            return 3  # an unaided reader is trivially independent of the proposer
        return sum((self.independent_model, self.independent_evidence, self.adversarial_posture))

    @property
    def is_independent(self) -> bool:
        return self.independence_score == 3

    @property
    def floor_multiplier(self) -> float:
        """How much of the unaided deliberation floor this deployment still owes.

        **Declared parameters.** They encode one judgement, stated plainly so an
        institution can disagree with it in its own configuration: throughput is
        bought with independence, and a deployment that has declared none has
        bought none. A partially independent assistant earns a partial
        reduction; a fully dependent one earns nothing, because it is not a
        second mind and the floor is not really about seconds.
        """
        if self.mode is AssistanceMode.UNAIDED:
            return 1.0
        earned = self.independence_score / 3.0
        # A recommending assistant is worth more throughput when independent and
        # is more dangerous when not, because ratifying is cheaper than reading.
        best = 0.2 if self.mode is AssistanceMode.RECOMMENDED else 0.4
        return round(1.0 - (1.0 - best) * earned, 4)

    @classmethod
    def from_env(cls, env: dict | None = None) -> ReviewAssistance:
        """Read the deployment's assistance declaration from the environment.

        Unlike the other two policies this one always returns a value, because
        *not declaring* assistance is itself a declaration: it says reviewers are
        unaided, and the unaided deliberation floor then applies in full. A
        deployment that quietly gives reviewers an assistant without saying so
        has not escaped the control, it has mis-declared its configuration — and
        ``configuration_warnings`` reports the shape of that risk rather than
        pretending it can detect it.
        """
        import os

        source = os.environ if env is None else env
        raw_mode = (source.get("FSSAI_REVIEW_ASSISTANCE_MODE") or "unaided").strip().lower()
        try:
            mode = AssistanceMode(raw_mode)
        except ValueError as exc:
            valid = ", ".join(item.value for item in AssistanceMode)
            raise ValueError(
                f"FSSAI_REVIEW_ASSISTANCE_MODE must be one of {valid}; got {raw_mode!r}"
            ) from exc

        def flag(name: str) -> bool:
            raw = source.get(name)
            if raw is None or not raw.strip():
                return False
            value = raw.strip().lower()
            if value in ("1", "true", "yes", "on"):
                return True
            if value in ("0", "false", "no", "off"):
                return False
            raise ValueError(
                f"{name} must be a boolean (true/false), got {raw!r}"
            )

        return cls(
            mode=mode,
            independent_model=flag("FSSAI_REVIEW_ASSISTANT_INDEPENDENT_MODEL"),
            independent_evidence=flag("FSSAI_REVIEW_ASSISTANT_INDEPENDENT_EVIDENCE"),
            adversarial_posture=flag("FSSAI_REVIEW_ASSISTANT_ADVERSARIAL"),
            declared_by=(source.get("FSSAI_REVIEW_ASSISTANCE_DECLARED_BY") or "").strip(),
            assistant_name=(source.get("FSSAI_REVIEW_ASSISTANT_NAME") or "").strip(),
        )

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "independent_model": self.independent_model,
            "independent_evidence": self.independent_evidence,
            "adversarial_posture": self.adversarial_posture,
            "independence_score": self.independence_score,
            "is_independent": self.is_independent,
            "floor_multiplier": self.floor_multiplier,
            "assistant_name": self.assistant_name,
            "declared_by": self.declared_by,
            "status": "declared configuration, not a measurement of any model",
        }


@dataclass(frozen=True)
class AssistedReviewPolicy:
    """The deliberation floor an institution may set, given what it declared.

    This is the enforcement point. It refuses a *configuration*, not an action —
    which is the earliest place a control can bind and the only place this
    particular failure is visible. By the time an approval is being issued, a
    dependent assistant and an independent one look identical: same reviewer,
    same interval, same signature. The difference exists only in the declaration.
    """

    #: The floor that applies to an unaided reader. The baseline everything else
    #: is derived from; :class:`~fssaira.oversight.ReviewLoadPolicy` ships 45s.
    unaided_floor_seconds: float = 45.0

    def __post_init__(self) -> None:
        # A negative baseline makes every derived floor negative, so every
        # proposed floor clears it and the gate silently stops being a gate.
        # Zero is permitted and means something real — no deliberation floor is
        # declared at all — which `ReviewLoadPolicy.declared_consistency` already
        # reports. Below zero is not a weaker declaration, it is a broken one.
        if self.unaided_floor_seconds < 0:
            raise ValueError(
                "unaided_floor_seconds must not be negative; a negative baseline "
                "disables the gate rather than relaxing it"
            )

    def permitted_floor(self, assistance: ReviewAssistance) -> float:
        """The lowest deliberation floor this declaration earns."""
        return round(self.unaided_floor_seconds * assistance.floor_multiplier, 4)

    def check(self, assistance: ReviewAssistance, proposed_floor: float) -> None:
        """Refuse a floor the declaration does not support.

        Raises :class:`~fssaira.exact_action.ExecutionDenied` so that a
        misconfigured deployment fails to start rather than running with an
        oversight control that has been quietly converted into a formality.
        """
        if assistance.mode is not AssistanceMode.UNAIDED and not assistance.declared_by:
            raise ExecutionDenied(
                AssistedReviewCode.ASSISTANCE_NOT_DECLARED,
                "review assistance is in use but no accountable owner declared its "
                "independence properties",
            )
        if proposed_floor < 0:
            raise ExecutionDenied(
                AssistedReviewCode.FLOOR_BELOW_DECLARED_INDEPENDENCE,
                f"a deliberation floor of {proposed_floor:.1f}s is not a declaration; "
                "a floor cannot be negative",
            )
        permitted = self.permitted_floor(assistance)
        if proposed_floor < permitted:
            raise ExecutionDenied(
                AssistedReviewCode.FLOOR_BELOW_DECLARED_INDEPENDENCE,
                f"a deliberation floor of {proposed_floor:.1f}s requires an assistant "
                f"more independent of the proposer than this deployment declared "
                f"(independence {assistance.independence_score}/3 earns a floor of "
                f"{permitted:.1f}s). Raise the floor, or establish and declare the "
                "independence that buys the throughput",
            )

    def to_dict(self) -> dict:
        return {
            "unaided_floor_seconds": self.unaided_floor_seconds,
            "note": (
                "throughput is bought with declared independence; a dependent "
                "assistant earns no reduction because it is not a second mind"
            ),
        }


@dataclass
class AssistedReviewerModel:
    """A reviewer with a model assistant, degrading by declared parameters.

    **A fixture, not a finding**, in exactly the sense
    :class:`fssaira.oversight.DeclaredReviewerModel` is one. It extends that
    model with the only behaviour that matters here: what the assistant does on
    the cases where the proposer was wrong.

    An **independent** assistant catches those cases on its own, so it extends
    the reviewer's effective attention: the reviewer is reading a second opinion
    that was actually formed separately.

    A **dependent** assistant reproduces the proposer's error at the declared
    correlation and presents it fluently. The reviewer, reading a confident
    endorsement instead of the case, ratifies — and does so quickly, because
    that is what the assistant was bought for. Note that this reviewer is *not*
    fatigued and *not* over quota. Nothing in the oversight report distinguishes
    them from an attentive one.
    """

    #: Arrivals a reviewer reads carefully before load degrades attention.
    attentive_until: int = 8
    #: Seconds an unaided careful review takes.
    careful_seconds: float = 90.0
    #: Seconds a rubber-stamped review takes.
    fatigued_seconds: float = 3.0
    #: Seconds an assisted review takes. Faster, and legitimately so.
    assisted_seconds: float = 12.0
    #: Multiplier on effective attention when the assistant is independent.
    independent_attention_multiplier: float = 4.0
    #: Probability a dependent assistant reproduces the proposer's error.
    #: **Declared, not measured.** ``1.0`` is the honest default for an
    #: assistant that is the same model reading the same evidence: there is no
    #: mechanism by which it would disagree.
    dependent_error_correlation: float = 1.0

    assistance: ReviewAssistance = field(default_factory=ReviewAssistance)
    reviewed: int = 0

    @property
    def effective_attention(self) -> int:
        if self.assistance.mode is AssistanceMode.UNAIDED:
            return self.attentive_until
        if self.assistance.is_independent:
            return int(self.attentive_until * self.independent_attention_multiplier)
        # A dependent assistant does not extend attention. It replaces reading
        # with ratifying, which is faster and is not the same activity.
        return self.attentive_until

    def review(self, *, should_refuse: bool, index: int = 0) -> tuple[bool, float]:
        """Return ``(approves, seconds_taken)`` for one proposal."""
        self.reviewed += 1
        assisted = self.assistance.mode is not AssistanceMode.UNAIDED
        seconds = self.assisted_seconds if assisted else self.careful_seconds

        if self.reviewed <= self.effective_attention:
            # The assistant inherited the proposer's error. Deterministic here so
            # the trial is reproducible: the correlation is a declared parameter
            # applied as a threshold, not sampled.
            correlated = self.dependent_error_correlation >= 1.0 or (
                (index % 100) / 100.0 < self.dependent_error_correlation
            )
            inherits_the_error = (
                assisted
                and not self.assistance.is_independent
                and should_refuse
                and correlated
            )
            if inherits_the_error:
                return (True, seconds)
            return (not should_refuse, seconds)

        # Past effective attention, the unaided failure mode returns unchanged.
        return (True, self.fatigued_seconds if not assisted else seconds)

    def reset(self) -> None:
        self.reviewed = 0


# ---------------------------------------------------------------------------
# The assisted-review trial
# ---------------------------------------------------------------------------


def run_assisted_review_trial(
    profile,
    *,
    arrivals: int = 40,
    merit_refusals_every: int = 7,
    unaided_floor: float = 45.0,
    lowered_floor: float = 10.0,
    reviewer_name: str = "officer-1",
    start: float = 1_000_000.0,
) -> dict:
    """Four deployments, one queue, one difference that matters.

    * ``unaided_full_floor`` — today's control, as ``fssaira.oversight`` ships it.
    * ``assisted_dependent_lowered_floor`` — the tempting deployment: buy an
      assistant, lower the floor, absorb the queue. Every control passes.
    * ``assisted_independent_lowered_floor`` — the same throughput, bought with
      declared independence.
    * ``assisted_dependent_floor_refused`` — the same tempting deployment with
      this module's configuration gate switched on. It does not start.

    Returns a report; never raises for an expected denial.
    """
    from .evidence import EvidenceLedger

    rule = next((r for r in profile.transitions if r.consequential), profile.transitions[0])
    gate = AssistedReviewPolicy(unaided_floor_seconds=unaided_floor)

    dependent = ReviewAssistance(
        mode=AssistanceMode.RECOMMENDED,
        independent_model=False, independent_evidence=False, adversarial_posture=False,
        declared_by="student_services", assistant_name="same-family-summariser",
    )
    independent = ReviewAssistance(
        mode=AssistanceMode.RECOMMENDED,
        independent_model=True, independent_evidence=True, adversarial_posture=True,
        declared_by="student_services", assistant_name="separate-model-challenger",
    )
    unaided = ReviewAssistance(mode=AssistanceMode.UNAIDED, declared_by="student_services")

    specs = (
        ("unaided_full_floor", unaided, unaided_floor, False),
        ("assisted_dependent_lowered_floor", dependent, lowered_floor, False),
        ("assisted_independent_lowered_floor", independent, lowered_floor, False),
        ("assisted_dependent_floor_refused", dependent, lowered_floor, True),
    )

    arms: dict = {}
    for arm, assistance, floor, enforce_gate in specs:
        if enforce_gate:
            try:
                gate.check(assistance, floor)
            except ExecutionDenied as denial:
                arms[arm] = {
                    "started": False,
                    "refused_at_configuration": True,
                    "code": denial.code,
                    "detail": str(denial),
                    "permitted_floor_seconds": gate.permitted_floor(assistance),
                    "assistance": assistance.to_dict(),
                    "reading": (
                        "the deployment does not start. The control binds before any "
                        "case is reviewed, because after that point a dependent "
                        "assistant and an independent one are indistinguishable"
                    ),
                }
                continue

        policy = ReviewLoadPolicy(
            max_approvals_per_window=ReviewLoadPolicy().max_approvals_per_window,
            min_deliberation_seconds=floor,
            second_reviewer_after=None,
        )
        monitor = OversightMonitor(policy)
        model = AssistedReviewerModel(assistance=assistance)
        token = "assisted-review-evidence-writer"
        register = CaseRegister({
            f"case-{index}": {"status": rule.from_status, "version": 1}
            for index in range(arrivals)
        })
        evidence = EvidenceLedger(token)
        authority = ApprovalAuthority(oversight=monitor)
        executor = profile.make_executor(register, evidence, token)

        counters = {
            "started": True,
            "refused_at_configuration": False,
            "merit_refusals_required": 0,
            "reviewer_refused_on_merit": 0,
            "harmful_executed": 0,
            "benign_executed": 0,
            "deferred_to_manual_fallback": 0,
            "refusals_by_code": {},
            "deliberation_floor_seconds": floor,
            "assistance": assistance.to_dict(),
        }
        now = start

        for index in range(arrivals):
            should_refuse = index % merit_refusals_every == merit_refusals_every - 1
            counters["merit_refusals_required"] += int(should_refuse)

            approves, seconds = model.review(should_refuse=should_refuse, index=index)
            presented_at = now
            now += seconds
            if not approves:
                counters["reviewer_refused_on_merit"] += 1
                continue

            proposal = ActionProposal(
                request_id=f"assisted-{arm}-{index}",
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
                    proposal, approver=reviewer_name, approver_role=rule.approval_role,
                    now=now, presented_at=presented_at,
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
        counters["oversight"] = monitor.report(reviewers=1).to_dict()["observed"]
        counters["wall_clock_seconds"] = round(now - start, 1)
        arms[arm] = counters

    baseline = arms["unaided_full_floor"]
    tempting = arms["assisted_dependent_lowered_floor"]
    principled = arms["assisted_independent_lowered_floor"]

    return {
        "schema_version": "1.0",
        "kind": "assisted-review-trial",
        "profile_id": profile.profile_id,
        "arrivals": arrivals,
        "gate": gate.to_dict(),
        "arms": arms,
        "summary": {
            "merit_failures_unaided": baseline["harmful_executed"],
            "merit_failures_assisted_dependent": tempting["harmful_executed"],
            "merit_failures_assisted_independent": principled["harmful_executed"],
            "benign_completed_unaided": baseline["benign_executed"],
            "benign_completed_assisted_dependent": tempting["benign_executed"],
            "benign_completed_assisted_independent": principled["benign_executed"],
            "deferred_to_manual_unaided": baseline["deferred_to_manual_fallback"],
            "deferred_to_manual_assisted": principled["deferred_to_manual_fallback"],
            "benign_completion_gain_from_assistance": (
                round(principled["benign_executed"] / baseline["benign_executed"], 2)
                if baseline["benign_executed"] else None
            ),
            "wall_clock_gain_from_assistance": (
                round(baseline["wall_clock_seconds"] / tempting["wall_clock_seconds"], 2)
                if tempting.get("wall_clock_seconds") else None
            ),
            "dependent_assistance_reintroduced_harm": (
                tempting["harmful_executed"] > principled["harmful_executed"]
            ),
            "independence_bounds_harm_without_removing_it": (
                0 < principled["harmful_executed"] < tempting["harmful_executed"]
            ),
            "every_mechanism_passed_in_the_harmful_arm": bool(
                tempting["evidence_chain_valid"]
                and tempting["oversight"]["refusals_by_code"] == {}
            ),
            "configuration_gate_refused_the_harmful_arm": arms[
                "assisted_dependent_floor_refused"
            ]["refused_at_configuration"],
        },
        "reading": [
            "assistance genuinely buys throughput, and the benign completion counts "
            "show it is not bought by refusing legitimate work: the unaided arm "
            "contains every merit failure and defers most of the queue to do it",
            "the independent arm does not reach zero harm, and that is the result "
            "rather than a tuning failure. Independence multiplies a reviewer's "
            "effective attention; it does not make attention unbounded. The "
            "oversight ceiling still exists, it has simply moved — an institution "
            "that buys an assistant has bought a larger ceiling to compute, not "
            "permission to stop computing one",
            "with a dependent assistant the merit failures return while the oversight "
            "report shows a reviewer inside quota, above the floor, with no refusals: "
            "there is no runtime signal distinguishing this from attentive review",
            "the only place the difference exists is the declaration, which is why the "
            "control is a configuration gate rather than a runtime check",
            "independence is three things an institution can answer about itself and "
            "a procurement process can require in writing",
        ],
        "limits": [
            "the proposer/assistant error correlation is a declared parameter; no model "
            "was evaluated and no rate is claimed for any named system",
            "the reviewer degradation curve remains declared, not observed",
            "floor multipliers encode a judgement about what independence is worth; an "
            "institution that disagrees should set its own and publish them",
            "measuring real proposer/assistant correlation is open work",
        ],
    }


__all__ = [
    "AssistanceMode",
    "AssistedReviewCode",
    "AssistedReviewPolicy",
    "AssistedReviewerModel",
    "ReviewAssistance",
    "run_assisted_review_trial",
]
