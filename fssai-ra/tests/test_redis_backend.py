import fakeredis

from fssaira import (
    ActionProposal,
    ApplicationProfile,
)
from fssaira.control_plane import ControlPlane
from fssaira.redis_backend import (
    RedisApprovalUseStore,
    RedisCaseRegister,
    RedisEvidenceLedger,
    RedisObjectStore,
    RedisPendingOutcomeStore,
)


def make_redis_plane():
    client = fakeredis.FakeRedis(decode_responses=True)
    token = "redis-evidence-token"
    return ControlPlane(
        ApplicationProfile.load("profiles/student_support.yaml"),
        register=RedisCaseRegister(client, "test"),
        evidence=RedisEvidenceLedger(client, token, "test"),
        evidence_token=token,
        objects=RedisObjectStore(client, "test"),
        outcome_store=RedisPendingOutcomeStore(client, "test"),
        approval_use_store=RedisApprovalUseStore(client, "test"),
    )


def test_redis_backed_control_plane_is_idempotent_and_persistent():
    plane = make_redis_plane()
    plane.register_resource("R-1", status="draft", version=4)
    plane.propose(
        request_id="redis-request", requester="agent", operation="prepare_case_for_review",
        resource_id="R-1", from_status="draft", to_status="ready_for_officer_review",
        evidence_version="snapshot-redis",
    )
    plane.approve(
        "redis-request", approver="officer", approver_role="student_support_officer"
    )
    first = plane.execute("redis-request")
    replay = plane.execute("redis-request")
    assert first.receipt_hash == replay.receipt_hash
    assert replay.replayed
    assert plane.register.mutation_count == 1
    assert plane.evidence.verify()
    assert len(plane.evidence_for("redis-request")) == 2


def test_redis_register_detects_stale_version_atomically():
    plane = make_redis_plane()
    plane.register_resource("R-2", status="draft", version=1)
    proposal = ActionProposal(
        "one", "agent", "prepare_case_for_review", "R-2", 1,
        "draft", "ready_for_officer_review", "snapshot",
    )
    first = plane.register.transition(proposal)
    assert first.version == 2
    stale = ActionProposal(
        "two", "agent", "prepare_case_for_review", "R-2", 1,
        "draft", "ready_for_officer_review", "snapshot",
    )
    try:
        plane.register.transition(stale)
    except Exception as exc:
        assert getattr(exc, "code", None) == "CASE_VERSION_CONFLICT"
    else:
        raise AssertionError("stale transition was accepted")


def test_sustained_contention_fails_closed_instead_of_spinning(monkeypatch):
    import pytest
    import redis

    from fssaira import ExecutionDenied

    client = fakeredis.FakeRedis(decode_responses=True)
    register = RedisCaseRegister(client, "contended", max_attempts=3)
    register.seed("R-9", status="draft", version=1)
    attempts = []

    def always_conflict(self, *args, **kwargs):
        attempts.append(1)
        raise redis.WatchError("another writer changed a watched key")

    monkeypatch.setattr(redis.client.Pipeline, "execute", always_conflict)
    proposal = ActionProposal(
        request_id="r-9", requester="agent", operation="prepare_case_for_review",
        case_id="R-9", expected_version=1, from_status="draft",
        to_status="ready_for_officer_review", evidence_version="snapshot",
    )
    with pytest.raises(ExecutionDenied) as exc:
        register.transition(proposal)
    assert exc.value.code == "STATE_CONTENTION" and len(attempts) == 3
    monkeypatch.undo()
    assert register.get("R-9") == {"status": "draft", "version": 1}


def test_evidence_append_contention_is_bounded(monkeypatch):
    import pytest
    import redis

    client = fakeredis.FakeRedis(decode_responses=True)
    ledger = RedisEvidenceLedger(client, "token", "contended", max_attempts=2)

    def always_conflict(self, *args, **kwargs):
        raise redis.WatchError("conflict")

    monkeypatch.setattr(redis.client.Pipeline, "execute", always_conflict)
    with pytest.raises(RuntimeError, match="EVIDENCE_CONTENTION"):
        ledger.append("decision", {"request_id": "r"}, token="token")
