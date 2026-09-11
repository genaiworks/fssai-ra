"""Single-transaction execution, and the failure mode it removes.

Release v0.5.0 could detect one failure it could not prevent: a mutation that
committed while its outcome evidence did not. That is the best any system can do
when the register and the evidence ledger are different databases. When they are
the same database, the window closes — and these tests prove it closes rather
than asserting it in prose.

SQLite is used deliberately: it needs no infrastructure, so the atomicity
property is checked on every commit in CI instead of only in an environment that
happens to have Postgres.
"""
import pytest

from fssaira.atomic_execution import AtomicExecutor
from fssaira.evidence import EvidenceError
from fssaira.exact_action import (
    ActionProposal,
    ApprovalAuthority,
    ExecutionDenied,
    ExecutionUncertain,
)
from fssaira.profiles import ApplicationProfile
from fssaira.sql_backend import open_sqlite

NOW = 3_000_000.0
TOKEN = "atomic-evidence-writer"


@pytest.fixture
def profile():
    return ApplicationProfile.load("profiles/student_support.yaml")


@pytest.fixture
def database():
    return open_sqlite(evidence_token=TOKEN)


@pytest.fixture
def executor(profile, database):
    with database.transaction() as unit:
        unit.register.seed("S-104", status="draft", version=1)
    return AtomicExecutor(
        database, TOKEN,
        allowed_operations=profile.allowed_operations,
        transition_rules=profile.transition_rules,
        required_approval_roles=profile.required_approval_roles,
    )


def make_proposal(request_id="req-1", **overrides):
    fields = {
        "request_id": request_id, "requester": "bounded-agent",
        "operation": "prepare_case_for_review", "case_id": "S-104",
        "expected_version": 1, "from_status": "draft",
        "to_status": "ready_for_officer_review", "evidence_version": "snapshot-1",
    }
    fields.update(overrides)
    return ActionProposal(**fields)


def approve(proposal, role="student_support_officer", authority=None):
    return (authority or ApprovalAuthority()).approve(
        proposal, approver="officer.one", approver_role=role, now=NOW
    )


def test_mutation_and_both_evidence_records_commit_together(executor, database):
    proposal = make_proposal()

    result = executor.execute(proposal, approve(proposal), now=NOW + 1)

    with database.transaction() as unit:
        kinds = [record.kind for record in unit.evidence.records()]
        assert kinds == ["action_intent", "action_outcome"]
        assert unit.evidence.verify() is True
        assert unit.register.get("S-104") == {"status": "ready_for_officer_review", "version": 2}
        assert unit.register.mutation_count == 1
        assert len(unit.outbox) == 0
    assert result.version == 2


def test_this_profile_cannot_produce_a_pending_outcome(executor):
    """The recovery protocol still exists; on this profile it has nothing to do."""
    proposal = make_proposal()
    executor.execute(proposal, approve(proposal), now=NOW + 1)

    assert executor.pending_outcome_count == 0
    assert executor.reconcile_pending() == 0
    assert executor.durability == "single-transaction"


def test_a_failure_inside_the_transaction_leaves_no_trace(profile, database):
    """A denial mid-transaction must roll back the intent record with it."""
    with database.transaction() as unit:
        unit.register.seed("S-200", status="draft", version=1)
    executor = AtomicExecutor(
        database, TOKEN,
        allowed_operations=profile.allowed_operations,
        transition_rules=profile.transition_rules,
        required_approval_roles=profile.required_approval_roles,
    )
    # Authorization passes, then the register refuses: the reviewed version is stale.
    proposal = make_proposal("req-stale", case_id="S-200", expected_version=99)

    with pytest.raises(ExecutionDenied) as denied:
        executor.execute(proposal, approve(proposal), now=NOW + 1)

    assert denied.value.code == "CASE_VERSION_CONFLICT"
    with database.transaction() as unit:
        assert unit.evidence.records() == [], "a rolled-back attempt leaves no intent record"
        assert unit.register.get("S-200") == {"status": "draft", "version": 1}
        assert unit.register.mutation_count == 0


def test_retry_returns_the_stored_receipt_without_a_second_mutation(executor, database):
    proposal = make_proposal()
    approval = approve(proposal)

    first = executor.execute(proposal, approval, now=NOW + 1)
    second = executor.execute(proposal, approval, now=NOW + 2)
    third = executor.execute(proposal, approval, now=NOW + 3)

    assert first.receipt_hash == second.receipt_hash == third.receipt_hash
    assert second.replayed and third.replayed
    with database.transaction() as unit:
        assert unit.register.mutation_count == 1
        assert len([r for r in unit.evidence.records() if r.kind == "action_outcome"]) == 1


def test_an_approval_bound_to_another_request_is_denied(executor):
    first = make_proposal("req-a")
    approval = approve(first)
    executor.execute(first, approval, now=NOW + 1)

    # Same approval, different request. The digest check catches it first; the
    # use-binding is the defence behind that.
    second = make_proposal("req-b")
    with pytest.raises(ExecutionDenied) as denied:
        executor.execute(second, approval, now=NOW + 2)
    assert denied.value.code in ("APPROVAL_PAYLOAD_MISMATCH", "APPROVAL_REUSED")


def test_the_evidence_write_credential_is_enforced_by_the_store(database):
    """An agent that guesses the credential is refused by the store itself."""
    with database.transaction() as unit, pytest.raises(EvidenceError, match="write authority"):
        unit.evidence.append("forged", {"by": "an agent"}, token="guessed")


def test_both_executors_apply_identical_authorization_rules(profile, database):
    """The two durability profiles must never drift on what counts as authorized."""
    from fssaira.evidence import EvidenceLedger
    from fssaira.exact_action import CaseRegister

    with database.transaction() as unit:
        unit.register.seed("S-300", status="draft", version=1)
    atomic = AtomicExecutor(
        database, TOKEN,
        allowed_operations=profile.allowed_operations,
        transition_rules=profile.transition_rules,
        required_approval_roles=profile.required_approval_roles,
    )
    memory = profile.make_executor(
        CaseRegister({"S-300": {"status": "draft", "version": 1}}),
        EvidenceLedger(TOKEN), TOKEN,
    )

    cases = [
        (make_proposal("d1", case_id="S-300", operation="not_in_profile"), "student_support_officer"),
        (make_proposal("d2", case_id="S-300", to_status="nowhere"), "student_support_officer"),
        (make_proposal("d3", case_id="S-300"), "a_role_with_no_authority"),
        (make_proposal("d4", case_id="S-300", expected_version=42), "student_support_officer"),
    ]
    for proposal, role in cases:
        approval = approve(proposal, role=role)
        codes = []
        for executor in (atomic, memory):
            try:
                executor.execute(proposal, approval, now=NOW + 1)
                codes.append("EXECUTED")
            except (ExecutionDenied, ExecutionUncertain) as exc:
                codes.append(exc.code)
        assert codes[0] == codes[1], f"executors disagree on {proposal.request_id}: {codes}"


def test_connection_failure_does_not_leave_sqlite_lock_owned():
    from concurrent.futures import ThreadPoolExecutor

    from fssaira.sql_backend import SQLITE, SqlDatabase

    def unavailable():
        raise OSError("synthetic connection failure")

    database = SqlDatabase(unavailable, SQLITE)
    with pytest.raises(OSError, match="synthetic connection"), database.transaction():
        pytest.fail("connection must fail before entering the transaction")

    def another_thread_can_acquire():
        acquired = database._lock.acquire(timeout=1)
        if acquired:
            database._lock.release()
        return acquired

    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(another_thread_can_acquire).result(timeout=3)


def test_close_reopens_a_durable_database_without_losing_committed_state(tmp_path):
    database = open_sqlite(str(tmp_path / "reopen.sqlite"), evidence_token=TOKEN)
    with database.transaction() as unit:
        unit.register.seed("restart-case", status="draft")
    database.close()
    database.close()
    with database.transaction() as unit:
        assert unit.register.get("restart-case") == {"status": "draft", "version": 1}
    database.close()
