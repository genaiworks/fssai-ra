"""Streaming as a sequence of disclosures (paper Section 6.1).

A streamed response releases data a piece at a time, so each piece is a release.
:class:`GovernedStream` offers the two modes the paper names:

* ``BUFFER_UNTIL_AUTHORIZED``: nothing is transmitted until the whole response
  has been labelled and released through the real
  :class:`fssaira.disclosure.DisclosureGate`. A revocation before that point
  means nothing leaves.
* ``PER_CHUNK``: every chunk is labelled and released through the gate under a
  **fixed label and recipient context** captured when the stream opens. If the
  session's label changes mid-stream (it read more), or the gate refuses a chunk
  (revocation, consent withdrawal, expiry, clearance), transmission stops before
  that chunk and never resumes.

The evidence (:class:`StreamEvidence`) counts transmitted bytes as **disclosed**.
Bytes already sent cannot be recalled; a stop limits further disclosure only.

Must NOT / residual risk
------------------------
* Must NOT write to the sink except after a successful gate release.
* Must NOT resume a stopped stream; open a new one, which is a new decision.
* Residual: the linearization point is each chunk's release decision. A
  revocation committed after a chunk's release and before the sink finishes
  writing it does not stop that chunk. Transport-level buffering beyond the
  sink (proxies, client caches) is outside this module.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from ..disclosure import DataLabel, DisclosureDenied, DisclosureGate
from ..evidence import EvidenceLedger

RECALL_NOTE = "transmitted bytes are disclosed and cannot be recalled"


class StreamMode(str, Enum):
    BUFFER_UNTIL_AUTHORIZED = "buffer_until_authorized"
    PER_CHUNK = "per_chunk"


class StreamCode:
    LABEL_CHANGED = "STREAM_LABEL_CHANGED_MID_STREAM"
    STOPPED = "STREAM_STOPPED"
    FINISHED = "STREAM_ALREADY_FINISHED"


class StreamStopped(Exception):
    def __init__(self, code: str, evidence: StreamEvidence) -> None:
        super().__init__(code)
        self.code = code
        self.evidence = evidence


@dataclass
class StreamEvidence:
    mode: str
    recipient: str
    purpose: str
    fixed_label: dict
    chunks_offered: int = 0
    chunks_transmitted: int = 0
    bytes_transmitted: int = 0
    transmitted_digests: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)
    stopped: bool = False
    stop_code: str | None = None
    completed: bool = False
    note: str = RECALL_NOTE

    def to_dict(self) -> dict:
        return dict(self.__dict__)


class GovernedStream:
    """Transmit a model response only through gate releases."""

    def __init__(self, gate: DisclosureGate, *, requester: str, session_id: str,
                 recipient: str, purpose: str, sink: Callable[[bytes], None],
                 mode: StreamMode = StreamMode.PER_CHUNK, recipient_id: str = "",
                 ledger: EvidenceLedger | None = None, ledger_token: str = "") -> None:
        self._gate = gate
        self._requester, self._session = requester, session_id
        self._recipient, self._recipient_id, self._purpose = recipient, recipient_id, purpose
        self._sink = sink
        self._mode = StreamMode(mode)
        self._ledger, self._ledger_token = ledger, ledger_token
        label = gate.session_label(session_id)
        self._fixed = label if label is not None else DataLabel.bottom(gate.policy)
        self._buffer: list[str] = []
        self.evidence = StreamEvidence(self._mode.value, recipient, purpose, self._fixed.to_dict())

    def _record(self, kind: str, payload: dict) -> None:
        if self._ledger is not None:
            self._ledger.append(kind, payload, token=self._ledger_token)

    def _stop(self, code: str) -> StreamStopped:
        self.evidence.stopped, self.evidence.stop_code = True, code
        self._buffer.clear()
        self._record("stream_stopped", {"code": code, "recipient": self._recipient,
                                        "bytes_already_disclosed": self.evidence.bytes_transmitted,
                                        "note": RECALL_NOTE})
        return StreamStopped(code, self.evidence)

    def _release_and_send(self, content: str, now: float) -> None:
        output = self._gate.derive_output(requester=self._requester, session_id=self._session,
                                          content=content)
        if output.label != self._fixed:
            raise self._stop(StreamCode.LABEL_CHANGED)
        try:
            receipt = self._gate.release(output, recipient=self._recipient,
                                         recipient_id=self._recipient_id, purpose=self._purpose,
                                         now=now)
        except DisclosureDenied as denied:
            raise self._stop(denied.code) from denied
        data = content.encode("utf-8")
        self._sink(data)
        digest = hashlib.sha256(data).hexdigest()
        self.evidence.chunks_transmitted += 1
        self.evidence.bytes_transmitted += len(data)
        self.evidence.transmitted_digests.append(digest)
        self.evidence.receipts.append(receipt.receipt_id)
        self._record("stream_chunk_disclosed", {"receipt_id": receipt.receipt_id,
                                                "bytes": len(data), "digest": digest,
                                                "recipient": self._recipient})

    def send(self, chunk: str, *, now: float) -> None:
        """Offer one chunk. Raises :class:`StreamStopped` if transmission has stopped."""
        if self.evidence.stopped:
            raise StreamStopped(self.evidence.stop_code or StreamCode.STOPPED, self.evidence)
        if self.evidence.completed:
            raise StreamStopped(StreamCode.FINISHED, self.evidence)
        self.evidence.chunks_offered += 1
        if self._mode is StreamMode.BUFFER_UNTIL_AUTHORIZED:
            self._buffer.append(chunk)
            return
        self._release_and_send(chunk, now)

    def finish(self, *, now: float) -> StreamEvidence:
        """Complete the stream. In buffer mode this is the single release decision."""
        if self.evidence.stopped:
            raise StreamStopped(self.evidence.stop_code or StreamCode.STOPPED, self.evidence)
        if self._mode is StreamMode.BUFFER_UNTIL_AUTHORIZED and self._buffer:
            content = "".join(self._buffer)
            self._buffer.clear()
            self._release_and_send(content, now)
        self.evidence.completed = True
        return self.evidence


__all__ = ["RECALL_NOTE", "GovernedStream", "StreamCode", "StreamEvidence", "StreamMode",
           "StreamStopped"]
