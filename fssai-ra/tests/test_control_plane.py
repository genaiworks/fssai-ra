
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
