"""Signed approvals still need independent semantic checks at execution."""
from dataclasses import replace

import pytest

from fssaira.atomic_execution import AtomicExecutor
from fssaira.evidence import EvidenceLedger
from fssaira.exact_action import (
    AccountableExecutor,
    ActionProposal,
    ApprovalAuthority,
    AsymmetricApprovalAuthority,
    CaseRegister,
    ExecutionDenied,
)
from fssaira.sql_backend import open_sqlite

TOKEN = "boundary-test"


@pytest.fixture(params=["memory", "sqlite"])
def workflow(request):
    proposal = ActionProposal("req-1", "agent", "prepare_case_for_review", "case-1",
                              1, "draft", "ready", "snapshot-1")
    if request.param == "memory":
        register = CaseRegister({"case-1": {"status": "draft", "version": 1}})
        evidence = EvidenceLedger(TOKEN)
        executor = AccountableExecutor(register, evidence, TOKEN)
    else:
        database = open_sqlite(evidence_token=TOKEN)
        with database.transaction() as unit:
            unit.register.seed("case-1", status="draft", version=1)
        executor = AtomicExecutor(database, TOKEN)
    return executor, proposal


@pytest.fixture(params=["hmac", "ed25519"])
def authority(request):
    if request.param == "ed25519":
        return AsymmetricApprovalAuthority()
    return ApprovalAuthority()


def assert_refused_without_effect(executor, proposal, approval, now, code):
    with pytest.raises(ExecutionDenied) as denial:
        executor.execute(proposal, approval, now=now)
    assert denial.value.code == code
    assert executor._register.get(proposal.case_id) == {"status": "draft", "version": 1}
    assert executor._register.result_for(proposal.request_id) is None
    assert not executor._evidence.find("action_intent", request_id=proposal.request_id)


def signed_change(authority, approval, **changes):
    # Model an issuer defect, not signature forgery: the executor must enforce
    # its own invariants even when a trusted key signed semantically bad fields.
    altered = replace(approval, **changes)
    return replace(altered, signature=authority._sign(altered))


def configure_authority(executor, authority):
    if isinstance(authority, AsymmetricApprovalAuthority):
        executor._approval_keys = authority.verification_keys


def test_executor_independently_refuses_signed_self_approval(workflow, authority):
    executor, proposal = workflow
    configure_authority(executor, authority)
    approval = authority.approve(proposal, approver="reviewer", now=1000)
    invalid = signed_change(authority, approval, approver=proposal.requester)
    assert_refused_without_effect(executor, proposal, invalid, 1001, "SEPARATION_OF_DUTIES")
    # Denial must not consume the approval or poison retries.
    assert executor.execute(proposal, approval, now=1001).version == 2


@pytest.mark.parametrize("expiry", [float("nan"), float("inf"), float("-inf"), True, "1300"])
def test_executor_refuses_signed_invalid_expiry(workflow, authority, expiry):
    executor, proposal = workflow
    configure_authority(executor, authority)
    approval = authority.approve(proposal, approver="reviewer", now=1000)
    invalid = signed_change(authority, approval, expires_at=expiry)
    assert_refused_without_effect(executor, proposal, invalid, 1001, "APPROVAL_EXPIRY_INVALID")


@pytest.mark.parametrize("now", [float("nan"), float("inf"), float("-inf"), True, "1001"])
def test_executor_refuses_invalid_clock(workflow, now):
    executor, proposal = workflow
    approval = ApprovalAuthority().approve(proposal, approver="reviewer", now=1000)
    assert_refused_without_effect(executor, proposal, approval, now, "AUTHORIZATION_TIME_INVALID")


@pytest.mark.parametrize("changes", [
    {"now": float("nan")}, {"now": float("inf")}, {"now": True},
    {"ttl_seconds": float("nan")}, {"ttl_seconds": float("inf")},
    {"ttl_seconds": 0}, {"ttl_seconds": -1}, {"ttl_seconds": True},
    {"now": 1e308, "ttl_seconds": 1e308},
])
def test_authority_refuses_invalid_lifetime_before_oversight(workflow, changes):
    _, proposal = workflow

    class NoAdmission:
        def admit(self, **kwargs):
            pytest.fail("invalid lifetime must not consume oversight capacity")

    authority = ApprovalAuthority(oversight=NoAdmission())
    with pytest.raises(ExecutionDenied):
        authority.approve(proposal, approver="reviewer", **{"now": 1000, **changes})


def test_expiry_boundary_and_valid_replay(workflow):
    executor, proposal = workflow
    approval = ApprovalAuthority().approve(proposal, approver="reviewer", now=1000)
    assert_refused_without_effect(executor, proposal, approval, 1300, "APPROVAL_EXPIRED")
    assert executor.execute(proposal, approval, now=1299).version == 2
    assert executor.execute(proposal, approval, now=1299).replayed
