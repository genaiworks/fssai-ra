"""Transactional event outbox: a committed change always has a durable event."""
import pytest

from fssaira import ApplicationProfile, ControlPlane
from fssaira.atomic_execution import AtomicExecutor, sql_evidence, sql_object_store, sql_register
from fssaira.event_outbox import OutboxRelay, SqlEventOutbox
from fssaira.kafka_backend import ConsumedEvent, EvidenceProjector
from fssaira.sql_backend import open_sqlite

TOKEN = "outbox-test-evidence-writer"


class RecordingPublisher:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    def append(self, value, key="", trace_id=""):
        if self.fail:
            raise RuntimeError("broker unavailable")
        self.sent.append((key, value, trace_id))
        return len(self.sent) - 1


def build(tmp_path, publisher=None):
    database = open_sqlite(str(tmp_path / "outbox.sqlite"), evidence_token=TOKEN)
    profile = ApplicationProfile.load("profiles/student_support.yaml")
    plane = ControlPlane(
        profile,
        register=sql_register(database),
        evidence=sql_evidence(database),
        evidence_token=TOKEN,
        objects=sql_object_store(database),
        events=SqlEventOutbox(database, publisher=publisher),
        executor=AtomicExecutor(
            database, TOKEN,
            allowed_operations=profile.allowed_operations,
            transition_rules=profile.transition_rules,
            required_approval_roles=profile.required_approval_roles,
        ),
    )
    return database, plane


def run_workflow(plane, request_id="req-1", resource_id="S-1"):
    plane.register_resource(resource_id, status="draft")
    plane.propose(
        request_id=request_id, requester="agent-1", operation="prepare_case_for_review",
        resource_id=resource_id, from_status="draft", to_status="ready_for_officer_review",
        evidence_version="snapshot-1",
    )
    plane.approve(request_id, approver="officer-1", approver_role="student_support_officer")
    return plane.execute(request_id)


def test_every_event_has_a_stable_id_and_is_stored(tmp_path):
    database, plane = build(tmp_path)
    run_workflow(plane)
    ids = [row["event_id"] for row in plane.events.read_all()]
    assert ids[0] == "resource.registered:S-1"
    assert ids[1] == "action.proposed:req-1"
    assert ids[2].startswith("action.approved:")
    assert ids[3] == "action.executed:req-1"
    assert len(plane.events) == 4


def test_executed_event_is_written_in_the_state_transaction(tmp_path):
    database, plane = build(tmp_path)
    plane.register_resource("S-1", status="draft")
    plane.propose(
        request_id="req-1", requester="agent-1", operation="prepare_case_for_review",
        resource_id="S-1", from_status="draft", to_status="ready_for_officer_review",
        evidence_version="snapshot-1",
    )
    plane.approve("req-1", approver="officer-1", approver_role="student_support_officer")
    # Call the executor directly: the control plane's own emit never runs, so the
    # event can only exist if the executor wrote it inside its transaction.
    plane.executor.execute(plane.get_proposal("req-1"), plane.get_approval("req-1"))
    with database.transaction() as unit:
        row = unit.events.get("action.executed:req-1")
    assert row is not None and row["value"]["payload"]["version"] == 2


def test_rolled_back_execution_leaves_no_event(tmp_path, monkeypatch):
    database, plane = build(tmp_path)
    plane.register_resource("S-1", status="draft")
    plane.propose(
        request_id="req-1", requester="agent-1", operation="prepare_case_for_review",
        resource_id="S-1", from_status="draft", to_status="ready_for_officer_review",
        evidence_version="snapshot-1",
    )
    plane.approve("req-1", approver="officer-1", approver_role="student_support_officer")
    from fssaira import sql_backend

    original = sql_backend._TxEventOutbox.enqueue

    def crash_after_enqueue(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("crash before commit")

    monkeypatch.setattr(sql_backend._TxEventOutbox, "enqueue", crash_after_enqueue)
    with pytest.raises(RuntimeError):
        plane.executor.execute(plane.get_proposal("req-1"), plane.get_approval("req-1"))
    monkeypatch.undo()
    assert plane.get_resource("S-1")["version"] == 1
    with database.transaction() as unit:
        assert unit.events.get("action.executed:req-1") is None


def test_broker_outage_does_not_fail_the_request_and_relay_catches_up(tmp_path):
    down = RecordingPublisher(fail=True)
    database, plane = build(tmp_path, publisher=down)
    result = run_workflow(plane)
    assert result.version == 2 and not result.replayed
    assert plane.events.unpublished_count() == 4

    up = RecordingPublisher()
    relay = OutboxRelay(database, up)
    assert relay.relay_once() == 4
    assert [value["event_id"] for _key, value, _trace in up.sent] == [
        row["event_id"] for row in plane.events.read_all()
    ]
    assert all(trace == value["event_id"] for _key, value, trace in up.sent)
    assert plane.events.unpublished_count() == 0
    assert relay.relay_once() == 0


def test_healthy_broker_publishes_immediately(tmp_path):
    publisher = RecordingPublisher()
    _database, plane = build(tmp_path, publisher=publisher)
    run_workflow(plane)
    assert len(publisher.sent) == 4
    assert plane.events.unpublished_count() == 0


def test_replayed_execution_does_not_duplicate_the_event(tmp_path):
    publisher = RecordingPublisher()
    _database, plane = build(tmp_path, publisher=publisher)
    run_workflow(plane)
    replay = plane.execute("req-1")
    assert replay.replayed
    kinds = [value["kind"] for _key, value, _trace in publisher.sent]
    assert kinds.count("action.executed") == 1
    assert len(plane.events) == 4


def test_relay_stops_at_first_failure_and_keeps_order(tmp_path):
    database, plane = build(tmp_path, publisher=RecordingPublisher(fail=True))
    run_workflow(plane)

    class FlakyPublisher(RecordingPublisher):
        def append(self, value, key="", trace_id=""):
            if len(self.sent) == 2:
                raise RuntimeError("broker dropped")
            return super().append(value, key, trace_id)

    flaky = FlakyPublisher()
    with pytest.raises(RuntimeError):
        OutboxRelay(database, flaky).relay_once()
    assert plane.events.unpublished_count() == 2
    second = RecordingPublisher()
    assert OutboxRelay(database, second).relay_once() == 2
    assert [v["kind"] for _k, v, _t in second.sent] == ["action.approved", "action.executed"]


def test_projector_ignores_a_republished_event_id():
    projector = EvidenceProjector()
    value = {"event_id": "action.executed:req-1", "kind": "action.executed",
             "payload": {"case_id": "S-1"}}
    projector.apply(ConsumedEvent("fssaira.events", 0, 5, "S-1", value, "t", 0.0))
    # At-least-once relay: the same event arrives again at a later offset.
    projector.apply(ConsumedEvent("fssaira.events", 0, 9, "S-1", value, "t", 0.0))
    assert projector.counts == {"action.executed": 1}


def test_control_plane_reports_and_relays_backlog(tmp_path):
    database, plane = build(tmp_path, publisher=RecordingPublisher(fail=True))
    run_workflow(plane)
    assert plane.unpublished_events == 4
    plane.events.publisher.fail = False
    assert plane.relay_events() == 4
    assert plane.unpublished_events == 0


def test_runtime_factory_uses_the_outbox_for_sql(tmp_path, monkeypatch):
    from fssaira.runtime_factory import build_control_plane

    monkeypatch.setenv("FSSAI_DATABASE_URL", f"sqlite:///{tmp_path / 'factory.sqlite'}")
    monkeypatch.delenv("FSSAI_KAFKA_BOOTSTRAP", raising=False)
    monkeypatch.setenv("FSSAI_MODEL", "deterministic")
    plane = build_control_plane()
    assert isinstance(plane.events, SqlEventOutbox)


def test_relay_backs_off_after_a_failure_so_requests_stay_fast(tmp_path):
    class CountingDown(RecordingPublisher):
        calls = 0

        def append(self, value, key="", trace_id=""):
            CountingDown.calls += 1
            raise RuntimeError("broker unavailable")

    database = open_sqlite(str(tmp_path / "backoff.sqlite"), evidence_token=TOKEN)
    clock = [1000.0]
    outbox = SqlEventOutbox(database, publisher=CountingDown(), retry_after=30.0,
                            clock=lambda: clock[0])
    for index in range(5):
        outbox.append({"event_id": f"e-{index}", "kind": "k", "payload": {}}, key="r")
    # One failed attempt, then no inline retries during the back-off window.
    assert CountingDown.calls == 1 and outbox.unpublished_count() == 5
    clock[0] += 31
    outbox.append({"event_id": "e-5", "kind": "k", "payload": {}}, key="r")
    assert CountingDown.calls == 2


def test_forced_relay_ignores_the_back_off(tmp_path):
    database = open_sqlite(str(tmp_path / "force.sqlite"), evidence_token=TOKEN)
    publisher = RecordingPublisher(fail=True)
    outbox = SqlEventOutbox(database, publisher=publisher, retry_after=3600.0)
    outbox.append({"event_id": "e-0", "kind": "k", "payload": {}}, key="r")
    publisher.fail = False
    assert outbox.relay() == 0          # still backing off
    assert outbox.relay(force=True) == 1  # operator-triggered reconcile


def test_publisher_purges_an_undelivered_message():
    from fssaira.kafka_backend import KafkaEventPublisher

    class StuckProducer:
        purged = False

        def produce(self, *args, **kwargs):
            pass

        def flush(self, timeout):
            return 1

        def purge(self, **kwargs):
            StuckProducer.purged = True

        def poll(self, timeout):
            return 0

    publisher = KafkaEventPublisher.__new__(KafkaEventPublisher)
    publisher.topic, publisher.flush_timeout, publisher.producer = "t", 0.1, StuckProducer()
    with pytest.raises(RuntimeError, match="undelivered"):
        publisher.append({"event_id": "e"}, key="k")
    assert StuckProducer.purged


# -- every profile, no transport, retention ------------------------------------


def redis_plane(publisher=None):
    import fakeredis

    from fssaira.event_outbox import EventOutbox, RedisOutboxStore
    from fssaira.redis_backend import (
        RedisApprovalUseStore,
        RedisCaseRegister,
        RedisEvidenceLedger,
        RedisObjectStore,
        RedisPendingOutcomeStore,
    )

    client = fakeredis.FakeRedis(decode_responses=True)
    outbox = RedisOutboxStore(client, "t")
    plane = ControlPlane(
        ApplicationProfile.load("profiles/student_support.yaml"),
        register=RedisCaseRegister(client, "t", outbox=outbox),
        evidence=RedisEvidenceLedger(client, TOKEN, "t"),
        evidence_token=TOKEN,
        objects=RedisObjectStore(client, "t"),
        events=EventOutbox(outbox, publisher=publisher),
        outcome_store=RedisPendingOutcomeStore(client, "t"),
        approval_use_store=RedisApprovalUseStore(client, "t"),
    )
    return plane, outbox


def test_redis_profile_survives_a_broker_outage_and_catches_up():
    down = RecordingPublisher(fail=True)
    plane, _outbox = redis_plane(down)
    result = run_workflow(plane)
    assert result.version == 2
    assert plane.unpublished_events == 4
    down.fail = False
    assert plane.relay_events() == 4
    kinds = [v["kind"] for _k, v, _t in down.sent]
    assert kinds == ["resource.registered", "action.proposed", "action.approved",
                     "action.executed"]
    assert plane.unpublished_events == 0


def test_redis_register_writes_the_event_with_the_transition():
    plane, outbox = redis_plane()
    plane.register_resource("S-1", status="draft")
    plane.propose(
        request_id="req-1", requester="agent-1", operation="prepare_case_for_review",
        resource_id="S-1", from_status="draft", to_status="ready_for_officer_review",
        evidence_version="snapshot-1",
    )
    plane.approve("req-1", approver="officer-1", approver_role="student_support_officer")
    plane.register.transition(plane.get_proposal("req-1"))  # no control-plane emit
    row = outbox.get("action.executed:req-1")
    assert row is not None and row["value"]["payload"]["version"] == 2


def test_redis_replay_does_not_duplicate_the_event():
    publisher = RecordingPublisher()
    plane, _outbox = redis_plane(publisher)
    run_workflow(plane)
    assert plane.execute("req-1").replayed
    assert [v["kind"] for _k, v, _t in publisher.sent].count("action.executed") == 1


def test_memory_outbox_keeps_requests_working_during_an_outage():
    from fssaira.event_outbox import EventOutbox, MemoryOutboxStore

    down = RecordingPublisher(fail=True)
    plane = ControlPlane(ApplicationProfile.load("profiles/student_support.yaml"),
                         events=EventOutbox(MemoryOutboxStore(), publisher=down))
    assert run_workflow(plane).version == 2
    assert plane.unpublished_events == 4
    down.fail = False
    assert plane.relay_events() == 4


@pytest.mark.parametrize("backend", ["sql", "redis", "memory"])
def test_without_a_transport_nothing_is_reported_as_owed(tmp_path, backend):
    if backend == "sql":
        _database, plane = build(tmp_path)
    elif backend == "redis":
        plane, _ = redis_plane()
    else:
        from fssaira.event_outbox import EventOutbox, MemoryOutboxStore

        plane = ControlPlane(ApplicationProfile.load("profiles/student_support.yaml"),
                             events=EventOutbox(MemoryOutboxStore()))
    run_workflow(plane)
    assert len(plane.events) == 4
    assert plane.unpublished_events == 0


@pytest.mark.parametrize("backend", ["sql", "redis", "memory"])
def test_old_published_events_are_pruned_and_pending_ones_kept(tmp_path, backend):
    import fakeredis

    from fssaira.event_outbox import (
        EventOutbox,
        MemoryOutboxStore,
        RedisOutboxStore,
        SqlOutboxStore,
    )

    store = {
        "sql": lambda: SqlOutboxStore(open_sqlite(str(tmp_path / "p.sqlite"), evidence_token=TOKEN)),
        "redis": lambda: RedisOutboxStore(fakeredis.FakeRedis(decode_responses=True), "p"),
        "memory": MemoryOutboxStore,
    }[backend]()
    publisher = RecordingPublisher()
    outbox = EventOutbox(store, publisher=publisher, retention_seconds=0.0)
    outbox.append({"event_id": "old", "kind": "k", "payload": {}}, key="r")
    publisher.fail = True
    outbox.append({"event_id": "stuck", "kind": "k", "payload": {}}, key="r")
    import time as _time
    _time.sleep(0.01)
    outbox.prune()  # also runs automatically, at most hourly, on append
    assert [row["event_id"] for row in outbox.read_all()] == ["stuck"]
    assert outbox.unpublished_count() == 1


def test_a_request_relays_only_a_bounded_batch_of_backlog(tmp_path):
    from fssaira.event_outbox import EventOutbox, MemoryOutboxStore

    publisher = RecordingPublisher(fail=True)
    outbox = EventOutbox(MemoryOutboxStore(), publisher=publisher, retry_after=0.0,
                         inline_limit=5)
    for index in range(30):
        outbox.append({"event_id": f"e-{index}", "kind": "k", "payload": {}}, key="r")
    publisher.fail = False
    outbox.append({"event_id": "e-30", "kind": "k", "payload": {}}, key="r")
    assert len(publisher.sent) == 5            # the request paid for five, not 31
    assert outbox.relay(force=True) == 26      # the rest is background or reconcile work


def test_the_background_relay_drains_the_backlog(tmp_path):
    import time as _time

    from fssaira.event_outbox import EventOutbox, MemoryOutboxStore

    publisher = RecordingPublisher(fail=True)
    outbox = EventOutbox(MemoryOutboxStore(), publisher=publisher, retry_after=0.0,
                         inline_limit=1)
    for index in range(10):
        outbox.append({"event_id": f"e-{index}", "kind": "k", "payload": {}}, key="r")
    publisher.fail = False
    outbox.start_background(interval=0.05)
    try:
        deadline = _time.monotonic() + 5
        while outbox.unpublished_count() and _time.monotonic() < deadline:
            _time.sleep(0.05)
    finally:
        outbox.stop_background()
    assert outbox.unpublished_count() == 0 and len(publisher.sent) == 10


def test_the_api_runs_the_background_relay_for_its_lifetime():
    from fastapi.testclient import TestClient

    from fssaira.api import create_app
    from fssaira.event_outbox import EventOutbox, MemoryOutboxStore
    from fssaira.security import Authenticator

    outbox = EventOutbox(MemoryOutboxStore(), publisher=RecordingPublisher())
    plane = ControlPlane(ApplicationProfile.load("profiles/student_support.yaml"), events=outbox)
    with TestClient(create_app(plane, authenticator=Authenticator())):
        assert outbox._thread is not None and outbox._thread.is_alive()
    assert outbox._thread is None
