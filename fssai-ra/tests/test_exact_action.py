from dataclasses import replace

import pytest

from fssaira import (
    AccountableExecutor,
    ActionProposal,
    ApprovalAuthority,
    CaseRegister,
    EvidenceLedger,
    ExecutionDenied,
    ExecutionUncertain,
    PendingOutcomeStore,
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
    register, ledger, authority, executor, proposal = setup_workflow()
    approval = authority.approve(proposal, approver="officer-17", now=1000)
    first = executor.execute(proposal, approval, now=1001)
    replay = executor.execute(proposal, approval, now=1002)
    assert first.receipt_hash == replay.receipt_hash
    assert replay.replayed is True
    assert register.mutation_count == 1
    assert len(ledger.find("action_intent", request_id=proposal.request_id)) == 1
    assert len(ledger.find("action_outcome", request_id=proposal.request_id)) == 1

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


def test_tampered_approval_is_rejected_before_mutation():
    register, _, authority, executor, proposal = setup_workflow()
    approval = authority.approve(proposal, approver="officer-17", now=1000)
    forged = replace(approval, approver="attacker")
    assert_denied(
        "APPROVAL_SIGNATURE_INVALID",
        lambda: executor.execute(proposal, forged, now=1001),
    )
    assert register.mutation_count == 0


def test_untrusted_approval_key_is_rejected_before_mutation():
    register, _, _, executor, proposal = setup_workflow()
    other_authority = ApprovalAuthority(key_id="unknown-key", signing_key="other-secret")
    approval = other_authority.approve(proposal, approver="officer-17", now=1000)
    assert_denied(
        "APPROVAL_KEY_UNTRUSTED",
        lambda: executor.execute(proposal, approval, now=1001),
    )
    assert register.mutation_count == 0


def test_executor_rejects_an_approved_but_unallowlisted_operation():
    register, _, authority, executor, proposal = setup_workflow()
    unallowlisted = replace(proposal, operation="approve_award")
    approval = authority.approve(unallowlisted, approver="officer-17", now=1000)
    assert_denied(
        "OPERATION_NOT_ALLOWED",
        lambda: executor.execute(unallowlisted, approval, now=1001),
    )
    assert register.mutation_count == 0


def test_empty_trusted_key_set_fails_closed():
    register, ledger, authority, _, proposal = setup_workflow()
    executor = AccountableExecutor(register, ledger, TOKEN, approval_keys={})
    approval = authority.approve(proposal, approver="officer-17", now=1000)
    assert_denied(
        "APPROVAL_KEY_UNTRUSTED",
        lambda: executor.execute(proposal, approval, now=1001),
    )
    assert register.mutation_count == 0


def test_approval_authority_rejects_empty_signing_material():
    with pytest.raises(ValueError, match="signing_key"):
        ApprovalAuthority(signing_key="")


def test_domain_transition_rule_denies_an_approved_invalid_transition():
    register, ledger, authority, _, proposal = setup_workflow()
    executor = AccountableExecutor(
        register,
        ledger,
        TOKEN,
        transition_rules={"prepare_case_for_review": {("draft", "ready_for_officer_review")}},
    )
    invalid = replace(proposal, to_status="award_approved")
    approval = authority.approve(invalid, approver="officer-17", now=1000)
    assert_denied(
        "TRANSITION_NOT_ALLOWED",
        lambda: executor.execute(invalid, approval, now=1001),
    )
    assert register.mutation_count == 0


class FailsFirstOutcomeLedger(EvidenceLedger):
    def __init__(self, token):
        super().__init__(token)
        self.failed = False

    def append(self, kind, payload, *, token):
        if kind == "action_outcome" and not self.failed:
            self.failed = True
            raise RuntimeError("simulated outage")
        return super().append(kind, payload, token=token)


def test_completed_mutation_is_marked_uncertain_then_reconciled_once():
    register = CaseRegister({"S-104": {"status": "draft", "version": 7}})
    ledger = FailsFirstOutcomeLedger(TOKEN)
    authority = ApprovalAuthority()
    outcomes = PendingOutcomeStore()
    executor = AccountableExecutor(register, ledger, TOKEN, outcome_store=outcomes)
    proposal = ActionProposal(
        "req-recovery", "agent", "prepare_case_for_review", "S-104", 7,
        "draft", "ready_for_officer_review", "snapshot-1",
    )
    approval = authority.approve(proposal, approver="officer", now=1000)

    with pytest.raises(ExecutionUncertain) as exc:
        executor.execute(proposal, approval, now=1001)
    assert exc.value.code == "OUTCOME_EVIDENCE_PENDING"
    assert register.mutation_count == 1
    assert executor.pending_outcome_count == 1

    with pytest.raises(ExecutionUncertain):
        executor.execute(proposal, approval, now=1002)
    assert register.mutation_count == 1

    assert executor.reconcile_pending() == 1
    assert executor.reconcile_pending() == 0
    assert executor.pending_outcome_count == 0
    assert len(ledger.find("action_outcome", request_id="req-recovery")) == 1
    assert ledger.verify()
