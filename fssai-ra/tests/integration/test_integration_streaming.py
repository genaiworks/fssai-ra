"""Streaming: each chunk is a release; revocation stops transmission; sent bytes stay disclosed."""
from __future__ import annotations

import pytest

from fssaira.disclosure import DisclosureCode
from fssaira.disclosure_eval import (
    AGENT,
    ARMS,
    NOW,
    SUBJECT_A,
    SUBJECT_B,
    TOKEN,
    DisclosureFixture,
)
from fssaira.evidence import EvidenceLedger
from fssaira.integration.streaming import (
    RECALL_NOTE,
    GovernedStream,
    StreamCode,
    StreamMode,
    StreamStopped,
)
from fssaira.profiles import ApplicationProfile

POLICY = ApplicationProfile.load("profiles/healthcare_record_access.yaml").disclosure


def opened(mode: StreamMode):
    fx = DisclosureFixture(POLICY)
    ledger = EvidenceLedger(TOKEN)
    gate = fx.gate(ARMS["this_architecture"], ledger=ledger)
    grant = fx.grant()
    fx.read(gate, grant)
    sent: list[bytes] = []
    stream = GovernedStream(gate, requester=AGENT, session_id="session-1",
                            recipient=fx.cleared_recipient, purpose=fx.purpose,
                            sink=sent.append, mode=mode, ledger=ledger, ledger_token=TOKEN)
    return fx, gate, grant, stream, sent, ledger


def test_per_chunk_revocation_stops_transmission_and_reports_disclosed_bytes():
    _fx, gate, grant, stream, sent, ledger = opened(StreamMode.PER_CHUNK)
    stream.send("first chunk ", now=NOW + 2)
    stream.send("second chunk ", now=NOW + 3)
    gate.revoke_grant(grant.grant_id, by="data-owner", reason="mid-stream")
    with pytest.raises(StreamStopped) as stopped:
        stream.send("third chunk", now=NOW + 4)
    assert stopped.value.code == DisclosureCode.RELEASE_GRANT_NO_LONGER_CURRENT
    assert sent == [b"first chunk ", b"second chunk "]
    evidence = stream.evidence
    assert evidence.stopped and evidence.bytes_transmitted == len(b"first chunk second chunk ")
    assert evidence.chunks_offered == 3 and evidence.chunks_transmitted == 2
    assert evidence.note == RECALL_NOTE
    with pytest.raises(StreamStopped):
        stream.send("fourth", now=NOW + 5)
    with pytest.raises(StreamStopped):
        stream.finish(now=NOW + 5)
    assert len(sent) == 2
    stop = ledger.find("stream_stopped")[-1].payload
    assert stop["bytes_already_disclosed"] == evidence.bytes_transmitted
    assert len(ledger.find("stream_chunk_disclosed")) == 2
    assert all("chunk" not in str(r.payload) for r in ledger.find("stream_chunk_disclosed"))


def test_per_chunk_consent_withdrawal_stops_transmission():
    fx, gate, _grant, stream, sent, _ledger = opened(StreamMode.PER_CHUNK)
    stream.send("a", now=NOW + 2)
    gate.withdraw_consent(SUBJECT_A, fx.purpose, recorded_by="subject")
    with pytest.raises(StreamStopped) as stopped:
        stream.send("b", now=NOW + 3)
    assert stopped.value.code == DisclosureCode.RELEASE_CONSENT_WITHDRAWN
    assert sent == [b"a"]


def test_buffer_mode_transmits_nothing_when_revoked_before_authorization():
    _fx, gate, grant, stream, sent, _ledger = opened(StreamMode.BUFFER_UNTIL_AUTHORIZED)
    stream.send("one ", now=NOW + 2)
    stream.send("two", now=NOW + 2)
    assert sent == []
    gate.revoke_grant(grant.grant_id, by="data-owner", reason="before finish")
    with pytest.raises(StreamStopped):
        stream.finish(now=NOW + 3)
    assert sent == [] and stream.evidence.bytes_transmitted == 0


def test_buffer_mode_releases_once_when_authorized():
    _fx, _gate, _grant, stream, sent, _ledger = opened(StreamMode.BUFFER_UNTIL_AUTHORIZED)
    stream.send("one ", now=NOW + 2)
    stream.send("two", now=NOW + 2)
    evidence = stream.finish(now=NOW + 3)
    assert sent == [b"one two"] and evidence.completed and len(evidence.receipts) == 1


def test_label_change_mid_stream_stops_under_fixed_context():
    fx, gate, _grant, stream, sent, _ledger = opened(StreamMode.PER_CHUNK)
    stream.send("a", now=NOW + 2)
    wider = fx.grant(grant_id="grant-wide", subjects=[SUBJECT_A, SUBJECT_B])
    fx.read(gate, wider, subjects=[SUBJECT_A, SUBJECT_B])
    assert gate.session_label("session-1").to_dict() != stream.evidence.fixed_label
    with pytest.raises(StreamStopped) as stopped:
        stream.send("b", now=NOW + 3)
    assert stopped.value.code == StreamCode.LABEL_CHANGED
    assert sent == [b"a"]


def test_uncleared_recipient_never_receives_a_byte():
    fx = DisclosureFixture(POLICY)
    gate = fx.gate(ARMS["this_architecture"])
    fx.read(gate, fx.grant())
    recipient, purpose = fx.laundering_recipient()
    sent: list[bytes] = []
    stream = GovernedStream(gate, requester=AGENT, session_id="session-1", recipient=recipient,
                            purpose=purpose, sink=sent.append)
    with pytest.raises(StreamStopped):
        stream.send("x", now=NOW + 2)
    assert sent == []
