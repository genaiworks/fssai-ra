"""A request ID is an idempotency key, never permission to substitute a receipt."""
from dataclasses import replace

import fakeredis
import pytest

from fssaira.atomic_execution import AtomicExecutor, sql_evidence, sql_register
from fssaira.evidence import EvidenceLedger
from fssaira.exact_action import (
    ActionProposal,
    ApprovalAuthority,
    CaseRegister,
    ExecutionDenied,
    ExecutionResult,
    validate_replay,
)
from fssaira.profiles import ApplicationProfile
from fssaira.redis_backend import RedisCaseRegister
from fssaira.sql_backend import open_sqlite

NOW = 3_000_000.0
TOKEN = "identity-fixture"


@pytest.fixture(params=["memory", "sqlite", "redis-fixture"])
def backend(request):
    profile = ApplicationProfile.load("profiles/student_support.yaml")
    database = None
    if request.param == "sqlite":
        database = open_sqlite(evidence_token=TOKEN)
        register, evidence = sql_register(database), sql_evidence(database)
        executor = AtomicExecutor(
            database, TOKEN, allowed_operations=profile.allowed_operations,
            transition_rules=profile.transition_rules,
            required_approval_roles=profile.required_approval_roles,
        )
    else:
        register = CaseRegister({}) if request.param == "memory" else RedisCaseRegister(
            fakeredis.FakeRedis(decode_responses=True), "request-identity"
        )
        evidence = EvidenceLedger(TOKEN)
        executor = profile.make_executor(register, evidence, TOKEN)
    register.seed("one", status="draft")
    register.seed("two", status="draft")
    yield register, evidence, executor
    if database is not None:
        database.close()


def proposal():
    return ActionProposal("request-1", "agent", "prepare_case_for_review", "one", 1,
                          "draft", "ready_for_officer_review", "snapshot-1")


def approve(item):
    return ApprovalAuthority().approve(item, approver="officer",
                                       approver_role="student_support_officer", now=NOW)


@pytest.mark.parametrize("change", [
    {"case_id": "two"}, {"evidence_version": "different-snapshot"},
    {"requester": "different-agent"}, {"expected_version": 2},
])
def test_valid_new_approval_cannot_reuse_another_proposals_request_id(backend, change):
    register, evidence, executor = backend
    original = proposal()
    executor.execute(original, approve(original), now=NOW + 1)
    changed = replace(original, **change)
    # Both approvals are valid. Digest mismatch with the stored receipt must
    # still prevent returning the previous action as this action's outcome.
    with pytest.raises(ExecutionDenied) as error:
        executor.execute(changed, approve(changed), now=NOW + 2)
    assert error.value.code == "REQUEST_ID_CONFLICT"
    assert register.mutation_count == 1
    assert register.get("two") == {"status": "draft", "version": 1}
    assert len(evidence) == 2


def test_renewed_approval_for_identical_proposal_does_not_duplicate_evidence(backend):
    register, evidence, executor = backend
    item = proposal()
    first = executor.execute(item, approve(item), now=NOW + 1)
    second = executor.execute(item, approve(item), now=NOW + 2)
    assert first.proposal_digest == second.proposal_digest == item.digest
    assert first.receipt_hash == second.receipt_hash
    assert second.replayed
    assert len(evidence) == 2
    assert register.mutation_count == 1


def test_register_itself_rejects_a_conflicting_request_identity(backend):
    register, _, _ = backend
    item = proposal()
    register.transition(item)
    with pytest.raises(ExecutionDenied, match="REQUEST_ID_CONFLICT"):
        register.transition(replace(item, evidence_version="changed"))
    assert register.mutation_count == 1


def test_legacy_receipt_without_digest_requires_reconciliation():
    item = proposal()
    legacy = ExecutionResult(item.request_id, item.case_id, 2, item.to_status, "legacy-hash")
    with pytest.raises(ExecutionDenied, match="REPLAY_IDENTITY_UNVERIFIABLE"):
        validate_replay(item, legacy)


def test_sql_request_identity_survives_a_new_executor_and_connection(tmp_path):
    path = str(tmp_path / "identity.sqlite")
    profile = ApplicationProfile.load("profiles/student_support.yaml")
    database = open_sqlite(path, evidence_token=TOKEN)
    sql_register(database).seed("one", status="draft")

    def executor(db):
        return AtomicExecutor(db, TOKEN, allowed_operations=profile.allowed_operations,
                              transition_rules=profile.transition_rules,
                              required_approval_roles=profile.required_approval_roles)

    item = proposal()
    executor(database).execute(item, approve(item), now=NOW + 1)
    database.close()
    reopened = open_sqlite(path, evidence_token=TOKEN)
    try:
        changed = replace(item, evidence_version="changed")
        with pytest.raises(ExecutionDenied, match="REQUEST_ID_CONFLICT"):
            executor(reopened).execute(changed, approve(changed), now=NOW + 2)
        assert executor(reopened).execute(item, approve(item), now=NOW + 2).replayed
    finally:
        reopened.close()
