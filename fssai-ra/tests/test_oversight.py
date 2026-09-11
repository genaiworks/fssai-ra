"""Human review capacity as a control: it must bind, and it must be ablatable.

These tests do two separate jobs and it is worth keeping them apart. Most of
them check that the gate refuses exactly what it claims to refuse, with the
stable code it claims to use. The last group checks the thing the paper actually
claims: that removing the load control restores a harm no other control in this
architecture can see.
"""
import pytest

from fssaira.exact_action import ActionProposal, ApprovalAuthority, ExecutionDenied
from fssaira.oversight import (
    DeclaredReviewerModel,
    OversightCode,
    OversightMonitor,
    ReviewLoadPolicy,
    run_queue_pressure_trial,
)
from fssaira.profiles import ApplicationProfile

NOW = 1_000_000.0
PROFILE = "profiles/student_support.yaml"


def proposal(request_id: str = "req-1", requester: str = "bounded-agent") -> ActionProposal:
    return ActionProposal(
        request_id=request_id,
        requester=requester,
        operation="prepare_case_for_review",
        case_id="case-1",
        expected_version=1,
        from_status="draft",
        to_status="ready_for_officer_review",
        evidence_version="snapshot-1",
    )


def admit(monitor: OversightMonitor, index: int, *, now: float, **kwargs):
    return monitor.admit(
        reviewer=kwargs.pop("reviewer", "officer-1"),
        request_id=f"req-{index}",
        now=now,
        presented_at=kwargs.pop("presented_at", now - 60.0),
        **kwargs,
    )


# -- the declared policy ----------------------------------------------------

@pytest.mark.parametrize("kwargs", [
    {"max_approvals_per_window": 0},
    {"window_seconds": 0},
    {"min_deliberation_seconds": -1},
    {"second_reviewer_after": 0},
    {"reviewing_seconds_per_day": 0},
    {"second_reviewer_after": 50, "max_approvals_per_window": 20},
])
def test_an_incoherent_capacity_declaration_is_refused(kwargs):
    with pytest.raises(ValueError):
        ReviewLoadPolicy(**kwargs)


def test_capacity_arithmetic_names_which_constraint_binds():
    # A generous quota with a long deliberation floor: attention binds.
    attention_bound = ReviewLoadPolicy(
        max_approvals_per_window=100, min_deliberation_seconds=600.0,
        second_reviewer_after=None,
    ).sustainable_actions_per_day(4)
    assert attention_bound["binding_constraint"] == "deliberation_floor"
    assert attention_bound["sustainable_per_day"] == 4 * 14_400 / 600

    # A tight quota with a short floor: the declared quota binds.
    quota_bound = ReviewLoadPolicy(
        max_approvals_per_window=2, min_deliberation_seconds=1.0, second_reviewer_after=None,
    ).sustainable_actions_per_day(4)
    assert quota_bound["binding_constraint"] == "policy_quota"
    assert quota_bound["sustainable_per_day"] == 4 * 2 * 24


def test_capacity_is_reported_as_arithmetic_not_as_a_measurement():
    capacity = ReviewLoadPolicy().sustainable_actions_per_day(11)
    assert "not a measurement" in capacity["note"]


# -- the gate ---------------------------------------------------------------

def test_reviews_inside_the_declared_capacity_are_admitted():
    monitor = OversightMonitor(ReviewLoadPolicy(max_approvals_per_window=3,
                                                second_reviewer_after=None))
    for index in range(3):
        record = admit(monitor, index, now=NOW + index)
        assert not record.escalated
    assert monitor.report().approvals == 3


def test_the_ceiling_refuses_the_next_approval_rather_than_flagging_it():
    monitor = OversightMonitor(ReviewLoadPolicy(max_approvals_per_window=2,
                                                second_reviewer_after=None))
    admit(monitor, 0, now=NOW)
    admit(monitor, 1, now=NOW + 1)

    with pytest.raises(ExecutionDenied) as denial:
        admit(monitor, 2, now=NOW + 2)

    assert denial.value.code == OversightCode.REVIEW_CAPACITY_EXCEEDED
    assert monitor.report().approvals == 2  # the refused review was never recorded as one


def test_capacity_is_per_reviewer_and_recovers_when_the_window_passes():
    policy = ReviewLoadPolicy(max_approvals_per_window=1, window_seconds=100.0,
                              second_reviewer_after=None)
    monitor = OversightMonitor(policy)
    admit(monitor, 0, now=NOW, reviewer="officer-1")

    # A different reviewer has their own budget.
    admit(monitor, 1, now=NOW, reviewer="officer-2")
    with pytest.raises(ExecutionDenied):
        admit(monitor, 2, now=NOW + 10, reviewer="officer-1")

    # Past the window, the first reviewer's budget is restored.
    admit(monitor, 3, now=NOW + 101, reviewer="officer-1")
    assert monitor.report().approvals == 3


def test_an_approval_faster_than_the_deliberation_floor_is_refused():
    monitor = OversightMonitor(ReviewLoadPolicy(min_deliberation_seconds=45.0))

    with pytest.raises(ExecutionDenied) as denial:
        admit(monitor, 0, now=NOW, presented_at=NOW - 3.0)

    assert denial.value.code == OversightCode.DELIBERATION_TOO_SHORT
    assert "3.0s" in str(denial.value)


def test_an_unmeasurable_deliberation_interval_fails_closed():
    """A floor you cannot measure is not a floor. It must refuse, not assume."""
    monitor = OversightMonitor(ReviewLoadPolicy(min_deliberation_seconds=45.0))

    with pytest.raises(ExecutionDenied) as denial:
        monitor.admit(reviewer="officer-1", request_id="req-1", now=NOW, presented_at=None)

    assert denial.value.code == OversightCode.DELIBERATION_UNVERIFIABLE


def test_no_floor_configured_means_a_missing_presentation_time_is_permitted():
    monitor = OversightMonitor(ReviewLoadPolicy(min_deliberation_seconds=0.0,
                                                second_reviewer_after=None))
    record = monitor.admit(reviewer="officer-1", request_id="req-1", now=NOW, presented_at=None)
    assert record.deliberation_seconds == 0.0


def test_sustained_load_escalates_to_a_second_distinct_reviewer():
    policy = ReviewLoadPolicy(max_approvals_per_window=10, second_reviewer_after=2)
    monitor = OversightMonitor(policy)
    admit(monitor, 0, now=NOW)
    admit(monitor, 1, now=NOW + 1)

    with pytest.raises(ExecutionDenied) as missing:
        admit(monitor, 2, now=NOW + 2)
    assert missing.value.code == OversightCode.SECOND_REVIEWER_REQUIRED

    with pytest.raises(ExecutionDenied) as same_person:
        admit(monitor, 3, now=NOW + 3, second_reviewer="officer-1")
    assert same_person.value.code == OversightCode.SECOND_REVIEWER_NOT_DISTINCT

    record = admit(monitor, 4, now=NOW + 4, second_reviewer="officer-2")
    assert record.escalated and record.second_reviewer == "officer-2"


# -- the approval authority -------------------------------------------------

def test_an_exhausted_reviewer_cannot_produce_a_signed_approval_at_all():
    """The gate refuses issuance. There is no valid approval left to verify."""
    monitor = OversightMonitor(ReviewLoadPolicy(max_approvals_per_window=1,
                                                min_deliberation_seconds=0.0,
                                                second_reviewer_after=None))
    authority = ApprovalAuthority(oversight=monitor)
    first = authority.approve(proposal("req-1"), approver="officer-1",
                              approver_role="student_support_officer", now=NOW)
    assert first.signature

    with pytest.raises(ExecutionDenied) as denial:
        authority.approve(proposal("req-2"), approver="officer-1",
                          approver_role="student_support_officer", now=NOW + 1)
    assert denial.value.code == OversightCode.REVIEW_CAPACITY_EXCEEDED


def test_separation_of_duties_is_still_checked_before_capacity():
    monitor = OversightMonitor(ReviewLoadPolicy(max_approvals_per_window=1,
                                                second_reviewer_after=None))
    authority = ApprovalAuthority(oversight=monitor)

    with pytest.raises(ExecutionDenied) as denial:
        authority.approve(proposal(requester="officer-1"), approver="officer-1",
                          approver_role="student_support_officer", now=NOW)

    assert denial.value.code == "SEPARATION_OF_DUTIES"
    assert monitor.report().approvals == 0


def test_an_authority_with_no_oversight_configured_behaves_exactly_as_before():
    """Backwards compatibility is a property, not an accident: assert it."""
    authority = ApprovalAuthority()
    for index in range(50):
        approval = authority.approve(proposal(f"req-{index}"), approver="officer-1",
                                     approver_role="student_support_officer", now=NOW)
        assert approval.signature


# -- what a deployment can publish -----------------------------------------

def test_the_report_publishes_load_without_publishing_any_case():
    monitor = OversightMonitor(ReviewLoadPolicy(max_approvals_per_window=4,
                                                second_reviewer_after=None))
    for index in range(3):
        admit(monitor, index, now=NOW + index, presented_at=NOW + index - 90.0)
    with pytest.raises(ExecutionDenied):
        admit(monitor, 9, now=NOW + 9, presented_at=NOW + 9 - 1.0)

    published = monitor.report(reviewers=11).to_dict()
    observed = published["observed"]

    assert observed["approvals_admitted"] == 3
    assert observed["approvals_per_reviewer"] == {"officer-1": 3}
    assert observed["median_deliberation_seconds"] == 90.0
    assert observed["refusals_by_code"] == {OversightCode.DELIBERATION_TOO_SHORT: 1}
    assert observed["capacity_headroom"] == 0.25
    assert published["capacity"]["reviewers"] == 11
    assert any("declared parameter" in limit for limit in published["limits"])


def test_headroom_reaches_zero_when_a_reviewer_is_saturated():
    monitor = OversightMonitor(ReviewLoadPolicy(max_approvals_per_window=2,
                                                second_reviewer_after=None))
    admit(monitor, 0, now=NOW)
    admit(monitor, 1, now=NOW + 1)
    assert monitor.report().headroom == 0.0


# -- the claim the paper makes ---------------------------------------------

def test_load_control_contains_a_harm_no_other_control_can_see():
    """The merit failures here are structurally perfect proposals.

    Every digest binds, every signature verifies, every transition is declared.
    The executor has nothing to object to, and that is the point: the only
    control standing behind this class of harm is a reviewer who is reading.
    """
    report = run_queue_pressure_trial(ApplicationProfile.load(PROFILE), arrivals=40)
    summary = report["summary"]

    assert summary["harmful_executed_without_load_control"] > 0
    assert summary["harmful_executed_with_load_control"] == 0
    assert summary["load_control_is_load_bearing"]

    # Both arms remain fully accountable. That is exactly the problem: an
    # unreviewed decision is as well-evidenced as a reviewed one.
    for arm in report["arms"].values():
        assert arm["evidence_chain_valid"]


def test_the_cost_of_the_control_is_reported_rather_than_hidden():
    report = run_queue_pressure_trial(ApplicationProfile.load(PROFILE), arrivals=40)
    summary = report["summary"]
    controlled = report["arms"]["declared_load_control"]

    assert summary["deferred_to_manual_fallback"] > 0
    assert controlled["benign_executed"] < report["arms"]["no_load_control"]["benign_executed"]
    assert summary["demand_to_declared_capacity"]["ratio"] == 5.0


def test_a_queue_inside_capacity_defers_nothing():
    """The control must be quiet when the institution is staffed for the work."""
    report = run_queue_pressure_trial(
        ApplicationProfile.load(PROFILE),
        arrivals=6,
        reviewer=DeclaredReviewerModel(attentive_until=6, careful_seconds=90.0),
        policy=ReviewLoadPolicy(max_approvals_per_window=20, min_deliberation_seconds=45.0,
                                second_reviewer_after=None),
    )
    controlled = report["arms"]["declared_load_control"]

    assert controlled["deferred_to_manual_fallback"] == 0
    assert controlled["harmful_executed"] == 0
    assert controlled["benign_executed"] == report["arms"]["no_load_control"]["benign_executed"]


def test_the_trial_states_that_its_reviewer_curve_is_declared_not_observed():
    report = run_queue_pressure_trial(ApplicationProfile.load(PROFILE), arrivals=10)
    assert "not a measurement" in report["reviewer_model"]["status"]
    assert any("declared, not observed" in limit for limit in report["limits"])


# -- the control plane, and therefore the HTTP API and the console ----------

def test_the_control_plane_can_enforce_review_capacity():
    """A control the reference deployment cannot switch on is not a feature."""
    from fssaira.control_plane import ControlPlane

    monitor = OversightMonitor(ReviewLoadPolicy(
        max_approvals_per_window=1, min_deliberation_seconds=0.0, second_reviewer_after=None,
    ))
    plane = ControlPlane(ApplicationProfile.load(PROFILE), oversight=monitor)
    for index in (1, 2):
        plane.register_resource(f"case-{index}", status="draft")

    first = plane.propose(
        requester="bounded-agent", operation="prepare_case_for_review",
        resource_id="case-1", from_status="draft",
        to_status="ready_for_officer_review", evidence_version="snapshot-1",
    )
    plane.approve(first.request_id, approver="officer-1",
                  approver_role="student_support_officer")

    second = plane.propose(
        requester="bounded-agent", operation="prepare_case_for_review",
        resource_id="case-2", from_status="draft",
        to_status="ready_for_officer_review", evidence_version="snapshot-2",
    )
    with pytest.raises(ExecutionDenied) as denial:
        plane.approve(second.request_id, approver="officer-1",
                      approver_role="student_support_officer")

    assert denial.value.code == OversightCode.REVIEW_CAPACITY_EXCEEDED
    assert plane.register.mutation_count == 0


def test_the_plane_refuses_two_sources_of_review_policy():
    """Silently merging two oversight configurations would be worse than failing."""
    from fssaira.control_plane import ControlPlane

    with pytest.raises(ValueError):
        ControlPlane(
            ApplicationProfile.load(PROFILE),
            authority=ApprovalAuthority(),
            oversight=OversightMonitor(),
        )


def test_queue_time_is_never_mistaken_for_deliberation_time():
    """A proposal that waited an hour and was approved in two seconds.

    The plane must not infer ``presented_at`` from the proposal's creation time:
    that would score queue time as reading time and pass exactly the behaviour
    the deliberation floor exists to catch. With a floor configured and no
    presentation time supplied, it fails closed instead.
    """
    from fssaira.control_plane import ControlPlane

    plane = ControlPlane(
        ApplicationProfile.load(PROFILE),
        oversight=OversightMonitor(ReviewLoadPolicy(min_deliberation_seconds=45.0)),
    )
    plane.register_resource("case-1", status="draft")
    proposal = plane.propose(
        requester="bounded-agent", operation="prepare_case_for_review",
        resource_id="case-1", from_status="draft",
        to_status="ready_for_officer_review", evidence_version="snapshot-1",
    )

    with pytest.raises(ExecutionDenied) as denial:
        plane.approve(proposal.request_id, approver="officer-1",
                      approver_role="student_support_officer")

    assert denial.value.code == OversightCode.DELIBERATION_UNVERIFIABLE
