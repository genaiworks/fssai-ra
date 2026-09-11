"""The one-way path, exercised as a transport rather than described as a shape.

An in-process class with no read method demonstrates intent. A socket that has
been shut down for reading, carrying framed and authenticated datagrams to a
receiver that never calls ``sendto``, demonstrates the property the deployment
actually depends on.
"""
import hashlib
import json
import time

import pytest

from fssaira.diode import (
    OneWayChannel,
    ReturnPathError,
    assert_no_return_path,
    describe_channel,
)
from fssaira.diode_transport import (
    DiodeTransportError,
    Frame,
    InterfaceInventory,
    UdpDiodeReceiver,
    UdpDiodeSender,
)

KEY = "shared-low-side-key"


@pytest.fixture
def receiver():
    received = []
    instance = UdpDiodeReceiver(received.append, port=0, key=KEY)
    instance.received = received
    yield instance
    instance.stop()


def frame_for(item: dict, *, tag: str = "", item_id: str = "x-1") -> Frame:
    body = json.dumps(item, sort_keys=True).encode()
    return Frame(item_id, 0, 1, hashlib.sha256(body).hexdigest(), body, tag=tag)


def test_an_item_crosses_the_loopback_diode_and_arrives_intact(receiver):
    receiver.start()
    sender = UdpDiodeSender("127.0.0.1", receiver.port, key=KEY, redundancy=3)

    sender.send_inward({"source": "partner", "text": "a" * 5000})
    sender.send_inward({"source": "partner", "text": "short"})
    _wait_for(lambda: len(receiver.received) == 2)
    sender.close()

    assert [len(item["text"]) for item in receiver.received] == [5000, 5]
    # Redundancy exists because there is no retransmission request. The receiver
    # must therefore discard the copies rather than deliver duplicates.
    assert receiver.stats.duplicates_dropped > 0
    assert receiver.stats.items_delivered == 2


def test_neither_end_exposes_a_return_path(receiver):
    sender = UdpDiodeSender("127.0.0.1", 51999, key=KEY)
    try:
        assert_no_return_path(sender)
        assert_no_return_path(OneWayChannel())
    finally:
        sender.close()

    summary = describe_channel(OneWayChannel())
    assert summary["one_way"] is True
    assert summary["public_methods"] == ["connect", "send_inward"]


def test_a_channel_that_can_read_back_is_rejected():
    class HelpfulButWrong:
        def send_inward(self, item):  # pragma: no cover - never called
            ...

        def read_back(self):  # the regression this check exists to catch
            return {}

    with pytest.raises(ReturnPathError, match="read_back"):
        assert_no_return_path(HelpfulButWrong())


def test_an_unauthenticated_frame_is_dropped(receiver):
    accepted = receiver.ingest_datagram(frame_for({"text": "trust me"}, tag="0" * 64).encode())

    assert accepted is False
    assert receiver.received == []
    assert receiver.stats.frames_rejected == 1


def test_a_corrupted_payload_is_dropped_rather_than_delivered(receiver):
    from fssaira.diode_transport import _tag

    body = b'{"text": "tampered in flight"}'
    frame = Frame("x-2", 0, 1, hashlib.sha256(b"different bytes").hexdigest(), body,
                  tag=_tag(KEY, "x-2", 0, body))

    assert receiver.ingest_datagram(frame.encode()) is False
    assert receiver.stats.items_failed_hash == 1
    assert receiver.received == []


def test_a_receiver_without_a_key_must_state_the_risk():
    """Anything that can reach the port can send bytes. That must be deliberate."""
    with pytest.raises(DiodeTransportError, match="configure a key"):
        UdpDiodeReceiver(lambda item: None, port=0)

    explicit = UdpDiodeReceiver(lambda item: None, port=0, require_key=False)
    explicit.stop()


def test_redundancy_below_one_is_refused():
    with pytest.raises(DiodeTransportError, match="no retransmission request"):
        UdpDiodeSender(redundancy=0)


def test_the_interface_inventory_names_every_path_a_claim_depends_on():
    inventory = InterfaceInventory.reference()
    payload = inventory.to_dict()

    assert payload["complete"] is True, payload["uncontrolled"]
    assert payload["outward_capable"] >= 4, (
        "a deployment with one inward link and no outward interfaces is not a real deployment"
    )
    assert any("administrative shell" in item.name for item in inventory.interfaces)


def test_an_interface_without_an_owner_is_flagged():
    inventory = InterfaceInventory.reference()
    from fssaira.diode_transport import Interface

    inventory.add(Interface("vendor maintenance tunnel", "bidirectional", "", "", ""))

    assert inventory.to_dict()["complete"] is False
    assert "vendor maintenance tunnel" in inventory.to_dict()["uncontrolled"]


def _wait_for(predicate, timeout: float = 3.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met before the timeout")
