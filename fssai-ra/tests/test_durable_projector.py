"""The monitoring projection survives restarts and never double counts."""
import pytest

from fssaira.kafka_backend import ConsumedEvent, DurableEvidenceProjector


def event(offset, event_id, kind="action.executed", case="S-1", partition=0):
    return ConsumedEvent("fssaira.events", partition, offset, case,
                         {"event_id": event_id, "kind": kind, "payload": {"case_id": case}},
                         event_id, 0.0)


def test_projection_and_position_survive_a_restart(tmp_path):
    url = f"sqlite:///{tmp_path / 'projection.sqlite'}"
    first = DurableEvidenceProjector(url)
    first.apply(event(0, "resource.registered:S-1", "resource.registered"))
    first.apply(event(1, "action.executed:r-1"))
    restarted = DurableEvidenceProjector(url)
    assert restarted.summary()["events_by_kind"] == {"action.executed": 1,
                                                     "resource.registered": 1}
    assert restarted.resume_offsets() == {("fssaira.events", 0): 2}
    assert [e["kind"] for e in restarted.timeline("S-1")] == ["resource.registered",
                                                               "action.executed"]


def test_redelivery_and_republished_events_are_ignored(tmp_path):
    projector = DurableEvidenceProjector(f"sqlite:///{tmp_path / 'p.sqlite'}")
    projector.apply(event(5, "action.executed:r-1"))
    projector.apply(event(5, "action.executed:r-1"))   # broker redelivery
    projector.apply(event(9, "action.executed:r-1"))   # outbox relay resend
    assert projector.summary()["events_by_kind"] == {"action.executed": 1}
    assert projector.resume_offsets() == {("fssaira.events", 0): 10}


def test_a_failed_apply_leaves_no_partial_state(tmp_path, monkeypatch):
    projector = DurableEvidenceProjector(f"sqlite:///{tmp_path / 'p.sqlite'}")
    projector.apply(event(0, "e-0"))
    original = projector._store_position

    def crash(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("crash before commit")

    monkeypatch.setattr(projector, "_store_position", crash)
    with pytest.raises(RuntimeError):
        projector.apply(event(1, "e-1"))
    monkeypatch.undo()
    assert projector.summary()["events_by_kind"] == {"action.executed": 1}
    assert projector.resume_offsets() == {("fssaira.events", 0): 1}
    projector.apply(event(1, "e-1"))  # the retry is applied once
    assert projector.summary()["events_by_kind"] == {"action.executed": 2}


def test_partitions_are_tracked_independently(tmp_path):
    projector = DurableEvidenceProjector(f"sqlite:///{tmp_path / 'p.sqlite'}")
    projector.apply(event(3, "a", partition=0))
    projector.apply(event(1, "b", partition=1))
    assert projector.resume_offsets() == {("fssaira.events", 0): 4, ("fssaira.events", 1): 2}
