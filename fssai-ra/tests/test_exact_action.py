from dataclasses import replace

import pytest

from fssaira import (
    AccountableExecutor,
    ActionProposal,
    ApprovalAuthority,
    CaseRegister,
    EvidenceLedger,
    ExecutionDenied,
)

TOKEN = "evidence-writer"


def setup_workflow():
    register = CaseRegister({"S-104": {"status": "draft", "version": 7}})
    ledger = EvidenceLedger(TOKEN)
    authority = ApprovalAuthority()
    executor = AccountableExecutor(register, ledger, TOKEN)
    proposal = ActionProposal(
        request_id="req-104-a",
        requester="agent-student-support",
        operation="prepare_case_for_review",
        case_id="S-104",
        expected_version=7,
        from_status="draft",
        to_status="ready_for_officer_review",
        evidence_version="snapshot-2026-09-10-a",
    )
    return register, ledger, authority, executor, proposal


def assert_denied(code, fn):
    with pytest.raises(ExecutionDenied) as exc:
        fn()
    assert exc.value.code == code


def test_exact_approved_action_executes_once_with_reconstructable_receipt():
    register, ledger, authority, executor, proposal = setup_workflow()
    approval = authority.approve(proposal, approver="officer-17", now=1000)
    result = executor.execute(proposal, approval, now=1001)
    assert result.status == "ready_for_officer_review"
    assert register.mutation_count == 1
    assert ledger.find("action_intent", request_id=proposal.request_id)
    assert ledger.find("action_outcome", request_id=proposal.request_id)
    assert ledger.verify()


@pytest.mark.parametrize(
    "changed",
    [
        {"case_id": "S-999"},
        {"to_status": "award_approved"},
    ],
)
def test_target_or_arguments_changed_after_approval_are_denied(changed):
    register, _, authority, executor, proposal = setup_workflow()
    approval = authority.approve(proposal, approver="officer-17", now=1000)
    altered = replace(proposal, **changed)
    assert_denied("APPROVAL_PAYLOAD_MISMATCH", lambda: executor.execute(altered, approval, now=1001))
    assert register.mutation_count == 0


def test_expired_approval_is_denied():
    register, _, authority, executor, proposal = setup_workflow()
    approval = authority.approve(proposal, approver="officer-17", ttl_seconds=5, now=1000)
    assert_denied("APPROVAL_EXPIRED", lambda: executor.execute(proposal, approval, now=1006))
    assert register.mutation_count == 0


def test_retry_is_idempotent_and_cross_request_reuse_is_denied():
    register, _, authority, executor, proposal = setup_workflow()
    approval = authority.approve(proposal, approver="officer-17", now=1000)
    first = executor.execute(proposal, approval, now=1001)
    replay = executor.execute(proposal, approval, now=1002)
    assert first.receipt_hash == replay.receipt_hash
    assert replay.replayed is True
    assert register.mutation_count == 1

    reused = replace(proposal, request_id="req-104-b")
    assert_denied("APPROVAL_PAYLOAD_MISMATCH", lambda: executor.execute(reused, approval, now=1003))
    assert register.mutation_count == 1


def test_changed_authoritative_case_requires_renewed_review():
    register, _, authority, executor, proposal = setup_workflow()
    approval = authority.approve(proposal, approver="officer-17", now=1000)
    concurrent = replace(proposal, request_id="system-update", to_status="under_manual_review")
    register.transition(concurrent)
    assert_denied("CASE_VERSION_CONFLICT", lambda: executor.execute(proposal, approval, now=1001))
    assert register.mutation_count == 1


def test_requester_cannot_approve_own_proposal():
    _, _, authority, _, proposal = setup_workflow()
    assert_denied(
        "SEPARATION_OF_DUTIES",
        lambda: authority.approve(proposal, approver=proposal.requester, now=1000),
    )
