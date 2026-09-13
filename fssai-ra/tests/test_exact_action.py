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


def test_second_reviewer_identity_and_role_are_covered_by_the_signature():
    register, _, authority, executor, proposal = setup_workflow()
    approval = authority.approve(
        proposal,
        approver="officer-17",
        second_approver="officer-18",
        second_approver_role="student_support_officer",
        now=1000,
    )
    forged = replace(approval, second_approver="attacker")

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


# ---------------------------------------------------------------------------
# The escalation endorsement, re-checked by the executor
# ---------------------------------------------------------------------------
#
# The oversight monitor refuses to *issue* an approval whose second reviewer is
# missing or is the primary. In a real deployment that check is made by a
# different process with different owners, so the executor re-derives it — the
# same reason it rechecks the digest, audience, role, expiry and version that
# were all correct when the approval was signed.
#
# Until these tests existed, escalation was the one field the executor carried
# into evidence without ever checking it.


def _escalation_fixture():
    from fssaira.profiles import ApplicationProfile

    profile = ApplicationProfile.load("profiles/student_support.yaml")
    rule = next(r for r in profile.transitions if r.consequential)
    register = CaseRegister({"c1": {"status": rule.from_status, "version": 1}})
    ledger = EvidenceLedger("escalation-token")
    executor = profile.make_executor(register, ledger, "escalation-token")
    proposal = ActionProposal(
        "req-esc", "agent-1", rule.operation, "c1", 1,
        rule.from_status, rule.to_status, "snap-1",
    )
    return ApprovalAuthority(), executor, proposal, rule


def _approve(authority, proposal, rule, **kwargs):
    return authority.approve(
        proposal, approver="officer-1", approver_role=rule.approval_role,
        now=1_000.0, **kwargs
    )


def test_an_escalation_naming_the_primary_as_the_second_reviewer_is_refused():
    """Two signatures from one person are not a second judgement."""
    authority, executor, proposal, rule = _escalation_fixture()
    approval = _approve(
        authority, proposal, rule,
        second_approver="officer-1", second_approver_role=rule.approval_role,
    )
    with pytest.raises(ExecutionDenied) as denial:
        executor.validate_authorization(proposal, approval, now=1_001.0)
    assert denial.value.code == "SECOND_APPROVER_NOT_DISTINCT"


def test_the_requester_cannot_be_the_escalation_reviewer():
    """Separation of duties applies to the second signature as much as the first."""
    authority, executor, proposal, rule = _escalation_fixture()
    approval = _approve(
        authority, proposal, rule,
        second_approver="agent-1", second_approver_role=rule.approval_role,
    )
    with pytest.raises(ExecutionDenied) as denial:
        executor.validate_authorization(proposal, approval, now=1_001.0)
    assert denial.value.code == "SECOND_APPROVER_IS_REQUESTER"


def test_an_escalation_reviewer_must_carry_the_role_they_hold():
    """An unattributed signature is not an endorsement."""
    authority, executor, proposal, rule = _escalation_fixture()
    approval = _approve(authority, proposal, rule, second_approver="officer-2")
    with pytest.raises(ExecutionDenied) as denial:
        executor.validate_authorization(proposal, approval, now=1_001.0)
    assert denial.value.code == "SECOND_APPROVER_ROLE_MISSING"


def test_escalating_to_a_role_that_could_not_have_approved_it_alone_is_refused():
    """Otherwise escalation adds a name rather than a control."""
    authority, executor, proposal, rule = _escalation_fixture()
    approval = _approve(
        authority, proposal, rule,
        second_approver="officer-2", second_approver_role="facilities_contractor",
    )
    with pytest.raises(ExecutionDenied) as denial:
        executor.validate_authorization(proposal, approval, now=1_001.0)
    assert denial.value.code == "SECOND_APPROVER_ROLE_NOT_ALLOWED"


def test_a_role_recorded_for_a_reviewer_who_was_never_named_is_refused():
    authority, executor, proposal, rule = _escalation_fixture()
    approval = _approve(authority, proposal, rule, second_approver_role=rule.approval_role)
    with pytest.raises(ExecutionDenied) as denial:
        executor.validate_authorization(proposal, approval, now=1_001.0)
    assert denial.value.code == "SECOND_APPROVER_ROLE_WITHOUT_REVIEWER"


def test_a_well_formed_escalation_executes_and_records_both_reviewers():
    """The control must not refuse the thing it exists to permit."""
    authority, executor, proposal, rule = _escalation_fixture()
    approval = _approve(
        authority, proposal, rule,
        second_approver="officer-2", second_approver_role=rule.approval_role,
    )
    result = executor.execute(proposal, approval, now=1_001.0)
    assert result.status == rule.to_status

    intent = executor._evidence.find("action_intent", request_id=proposal.request_id)
    assert intent, "an escalated action must leave an intent record"
    payload = intent[0].payload
    assert payload["approver"] == "officer-1"
    assert payload["second_approver"] == "officer-2"
    assert payload["second_approver_role"] == rule.approval_role, (
        "the evidence must name the role the escalation reviewer held, not just their name"
    )


def test_the_escalation_fields_are_authenticated_not_merely_carried():
    """Tampering with either must invalidate the signature."""
    authority, executor, proposal, rule = _escalation_fixture()
    approval = _approve(
        authority, proposal, rule,
        second_approver="officer-2", second_approver_role=rule.approval_role,
    )
    for field, value in (("second_approver", "officer-9"), ("second_approver_role", "registrar")):
        tampered = replace(approval, **{field: value})
        with pytest.raises(ExecutionDenied) as denial:
            executor.validate_authorization(proposal, tampered, now=1_001.0)
        assert denial.value.code == "APPROVAL_SIGNATURE_INVALID", field
