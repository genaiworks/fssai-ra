"""The review queue a pack declares is enforced on the approval path."""
import pytest

from fssaira import ApplicationProfile, ControlPlane, ExecutionDenied
from fssaira.control_plane import ReviewQueuePolicy


class Clock:
    def __init__(self):
        self.now = 1_000.0

    def __call__(self):
        return self.now


def plane(limit=2, timeout=60.0, clock=None):
    return ControlPlane(ApplicationProfile.load("profiles/student_support.yaml"),
                        review_queue=ReviewQueuePolicy(limit, timeout, "defer_to_manual",
                                                       "student_services"),
                        clock=clock or Clock())


def propose(p, n):
    p.register_resource(f"S-{n}", status="draft")
    return p.propose(request_id=f"r-{n}", requester="agent", operation="prepare_case_for_review",
                     resource_id=f"S-{n}", from_status="draft",
                     to_status="ready_for_officer_review", evidence_version="v1")


def test_a_full_queue_refuses_new_consequential_proposals():
    p = plane(limit=2)
    propose(p, 1)
    propose(p, 2)
    with pytest.raises(ExecutionDenied) as exc:
        propose(p, 3)
    assert exc.value.code == "REVIEW_QUEUE_FULL"
    assert "student_services" in str(exc.value) and p.objects.get("proposal", "r-3") is None


def test_a_decision_frees_a_place_and_a_retry_is_not_counted_twice():
    p = plane(limit=2)
    propose(p, 1)
    p.propose(request_id="r-1", requester="agent", operation="prepare_case_for_review",
              resource_id="S-1", from_status="draft", to_status="ready_for_officer_review",
              evidence_version="v1")  # idempotent retry
    propose(p, 2)
    p.approve("r-1", approver="officer", approver_role="student_support_officer")
    assert p.review_queue_depth == 1
    propose(p, 3)


def test_an_approval_after_the_timeout_is_refused_and_deferred():
    clock = Clock()
    p = plane(timeout=60, clock=clock)
    propose(p, 1)
    clock.now += 61
    with pytest.raises(ExecutionDenied) as exc:
        p.approve("r-1", approver="officer", approver_role="student_support_officer")
    assert exc.value.code == "REVIEW_TIMED_OUT"
    assert p.objects.get("approval", "r-1") is None


def test_timed_out_entries_leave_the_queue():
    clock = Clock()
    p = plane(limit=1, timeout=60, clock=clock)
    propose(p, 1)
    clock.now += 61
    propose(p, 2)  # the stale entry no longer blocks the queue
    assert p.review_queue_depth == 1


def test_routine_transitions_do_not_queue():
    p = plane(limit=1)
    propose(p, 1)
    p.approve("r-1", approver="officer", approver_role="student_support_officer")
    p.execute("r-1")
    # return_case_for_correction is consequential in this profile; still one slot free.
    assert p.review_queue_depth == 0


@pytest.mark.parametrize("backend", ["sql", "redis"])
def test_the_queue_works_on_durable_object_stores(tmp_path, backend):
    if backend == "sql":
        from fssaira.atomic_execution import sql_object_store
        from fssaira.sql_backend import open_sqlite
        objects = sql_object_store(open_sqlite(str(tmp_path / "q.sqlite")))
    else:
        import fakeredis

        from fssaira.redis_backend import RedisObjectStore
        objects = RedisObjectStore(fakeredis.FakeRedis(decode_responses=True), "q")
    clock = Clock()
    p = ControlPlane(ApplicationProfile.load("profiles/student_support.yaml"), objects=objects,
                     review_queue=ReviewQueuePolicy(1, 60, "defer_to_manual", "owner"), clock=clock)
    propose(p, 1)
    with pytest.raises(ExecutionDenied):
        propose(p, 2)
    clock.now += 61
    p.propose(request_id="r-2", requester="agent", operation="prepare_case_for_review",
              resource_id="S-2", from_status="draft", to_status="ready_for_officer_review",
              evidence_version="v1")  # the resource already exists from the refused attempt
    assert p.review_queue_depth == 1


def test_health_reports_the_review_queue():
    from fastapi.testclient import TestClient

    from fssaira.api import create_app
    from fssaira.security import Authenticator

    p = plane(limit=5)
    propose(p, 1)
    health = TestClient(create_app(p, authenticator=Authenticator())).get("/health").json()
    assert health["review_queue"] == {"depth": 1, "limit": 5, "timeout_seconds": 60.0,
                                      "overload_policy": "defer_to_manual"}


def test_concurrent_proposals_cannot_overfill_the_queue():
    import threading

    p = plane(limit=3)
    for n in range(20):
        p.register_resource(f"S-{n}", status="draft")
    results = []

    def attempt(n):
        try:
            p.propose(request_id=f"r-{n}", requester="agent", operation="prepare_case_for_review",
                      resource_id=f"S-{n}", from_status="draft",
                      to_status="ready_for_officer_review", evidence_version="v1")
            results.append("ok")
        except ExecutionDenied:
            results.append("full")

    threads = [threading.Thread(target=attempt, args=(n,)) for n in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("ok") == 3 and p.review_queue_depth == 3
