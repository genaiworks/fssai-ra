
import pytest

from fssaira import ApplicationProfile, ControlPlane, ExecutionDenied


@pytest.fixture
def plane():
    return ControlPlane(ApplicationProfile.load("profiles/student_support.yaml"))


def test_control_plane_runs_profiled_workflow_and_records_events(plane):
    plane.register_resource("S-200", status="draft", version=3)
    proposal = plane.propose(
        request_id="req-200", requester="agent-1",
        operation="prepare_case_for_review", resource_id="S-200",
        from_status="draft", to_status="ready_for_officer_review",
        evidence_version="snapshot-200",
    )
    plane.approve(
        proposal.request_id, approver="officer-1",
        approver_role="student_support_officer",
    )
    result = plane.execute(proposal.request_id)
    assert result.status == "ready_for_officer_review"
    assert plane.register.mutation_count == 1
    assert len(plane.evidence_for(proposal.request_id)) == 2
    assert len(plane.events) == 4


def test_control_plane_rejects_transition_before_proposal_is_saved(plane):
    plane.register_resource("S-201", status="draft")
    with pytest.raises(ExecutionDenied) as exc:
        plane.propose(
            request_id="bad", requester="agent-1", operation="prepare_case_for_review",
            resource_id="S-201", from_status="draft", to_status="award_approved",
            evidence_version="snapshot",
        )
    assert exc.value.code == "TRANSITION_NOT_ALLOWED"
    assert plane.objects.get("proposal", "bad") is None


def test_control_plane_requires_existing_proposal_and_approval(plane):
    with pytest.raises(ExecutionDenied) as exc:
        plane.execute("missing")
    assert exc.value.code == "PROPOSAL_NOT_FOUND"


def test_repeating_the_identical_request_id_is_idempotent(plane):
    plane.register_resource("S-idempotent", status="draft")
    arguments = {
        "request_id": "stable-request",
        "requester": "agent-1",
        "operation": "prepare_case_for_review",
        "resource_id": "S-idempotent",
        "from_status": "draft",
        "to_status": "ready_for_officer_review",
        "evidence_version": "snapshot",
    }

    first = plane.propose(**arguments)
    second = plane.propose(**arguments)

    assert first == second
    assert len(plane.events) == 2  # resource registration + one proposal


def test_reusing_a_request_id_for_another_proposal_is_refused(plane):
    plane.register_resource("S-one", status="draft")
    plane.register_resource("S-two", status="draft")
    plane.propose(
        request_id="collision", requester="agent-1",
        operation="prepare_case_for_review", resource_id="S-one",
        from_status="draft", to_status="ready_for_officer_review",
        evidence_version="snapshot",
    )

    with pytest.raises(ExecutionDenied) as exc:
        plane.propose(
            request_id="collision", requester="agent-1",
            operation="prepare_case_for_review", resource_id="S-two",
            from_status="draft", to_status="ready_for_officer_review",
            evidence_version="snapshot",
        )

    assert exc.value.code == "REQUEST_ID_CONFLICT"


def test_proposal_starting_state_must_match_the_authoritative_record(plane):
    plane.register_resource("S-state", status="draft")

    with pytest.raises(ExecutionDenied) as exc:
        plane.propose(
            requester="agent-1", operation="return_case_for_correction",
            resource_id="S-state", from_status="ready_for_officer_review",
            to_status="draft", evidence_version="snapshot",
        )

    assert exc.value.code == "CASE_STATE_CONFLICT"


def test_second_review_endorsement_is_idempotent_and_cannot_be_overwritten(plane):
    plane.register_resource("S-review", status="draft")
    proposal = plane.propose(
        requester="agent-1", operation="prepare_case_for_review",
        resource_id="S-review", from_status="draft",
        to_status="ready_for_officer_review", evidence_version="snapshot",
    )
    plane.begin_review(proposal.request_id, reviewer="officer-2")

    first = plane.endorse_review(
        proposal.request_id, reviewer="officer-2",
        reviewer_role="student_support_officer",
    )
    repeated = plane.endorse_review(
        proposal.request_id, reviewer="officer-2",
        reviewer_role="student_support_officer",
    )
    assert repeated == first

    plane.begin_review(proposal.request_id, reviewer="officer-3")
    with pytest.raises(ExecutionDenied) as exc:
        plane.endorse_review(
            proposal.request_id, reviewer="officer-3",
            reviewer_role="student_support_officer",
        )
    assert exc.value.code == "REVIEW_ENDORSEMENT_CONFLICT"
