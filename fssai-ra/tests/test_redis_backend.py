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
