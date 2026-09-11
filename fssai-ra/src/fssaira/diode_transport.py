"""A working one-way transport, and the checks that keep it one-way.

:mod:`fssaira.diode` models the *shape* of a data diode: a class with no method
that moves data outward. That is a useful teaching device and a real
architectural constraint, but it runs inside one process, so it cannot
demonstrate the property that matters operationally -- that the high side can
receive without ever being able to reply.

This module is the runnable version. The sender holds a UDP socket it has
shut down for reading; the receiver holds a UDP socket it never writes to. There
is no handshake, no acknowledgement, no retransmission request, and no session.
On a laptop the two ends are separated by the loopback interface; in a
deployment they are separated by a certified data diode or an optical tap, and
*the application code does not change*. That is the point of building it this
way: the software is already written for a link that cannot answer back.

Consequences of having no return channel, all of which are handled here:

* **No retransmission.** A lost datagram is lost. The sender therefore repeats
  each frame ``redundancy`` times and the receiver discards duplicates by
  sequence number. This is the same trade a hardware diode forces.
* **No integrity negotiation.** Each frame carries a SHA-256 of its payload and,
  when a key is configured, an HMAC tag. A receiver that cannot verify a frame
  drops it and counts it; it cannot ask for a resend.
* **No authentication by connection.** Anything that can reach the port can send
  bytes. The HMAC key is what distinguishes an authorised low-side publisher
  from a host on the same segment, and it is why ``require_key`` defaults to
  true.
* **No flow control.** The receiver's queue is bounded and drops oldest-first
  under pressure, recording the loss, because silently blocking the sender would
  reintroduce back-pressure -- a back channel by another name.

Reassembly is supported so that a document larger than one datagram still
crosses in order, with a per-item hash checked after the last chunk arrives.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

MAGIC = b"FSSAI1"
DEFAULT_PORT = 51820
MAX_PAYLOAD = 1200          # conservative, stays under a typical 1500-byte MTU
HEADER_SEPARATOR = b"\n\n"


class DiodeTransportError(RuntimeError):
    """Raised for a configuration mistake, never for a dropped datagram."""


@dataclass(frozen=True)
class Frame:
    item_id: str
    chunk: int
    chunks: int
    item_hash: str
    payload: bytes
    tag: str = ""

    def header(self) -> dict:
        return {
            "item_id": self.item_id,
            "chunk": self.chunk,
            "chunks": self.chunks,
            "item_hash": self.item_hash,
            "tag": self.tag,
        }

    def encode(self) -> bytes:
        header = json.dumps(self.header(), sort_keys=True, separators=(",", ":")).encode()
        return MAGIC + header + HEADER_SEPARATOR + self.payload

    @classmethod
    def decode(cls, datagram: bytes) -> "Frame":
        if not datagram.startswith(MAGIC):
            raise ValueError("not an FSSAI diode frame")
        body = datagram[len(MAGIC):]
        header_bytes, separator, payload = body.partition(HEADER_SEPARATOR)
        if not separator:
            raise ValueError("malformed frame: no header separator")
        header = json.loads(header_bytes.decode())
        return cls(
            item_id=str(header["item_id"]),
            chunk=int(header["chunk"]),
            chunks=int(header["chunks"]),
            item_hash=str(header["item_hash"]),
            payload=payload,
            tag=str(header.get("tag", "")),
        )


def _tag(key: str, item_id: str, chunk: int, payload: bytes) -> str:
    message = f"{item_id}:{chunk}:".encode() + payload
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Low side
# ---------------------------------------------------------------------------


class UdpDiodeSender:
    """Send-only. There is no method here that reads, and the socket cannot.

    ``socket.shutdown(SHUT_RD)`` is attempted at construction so the operating
    system enforces the direction as well as the class. It is best-effort --
    some platforms reject it on an unconnected UDP socket -- and the absence of
    any read method is the property the conformance suite actually checks.
    """

    name = "udp-diode-sender"

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = DEFAULT_PORT,
        *,
        key: str | None = None,
        redundancy: int = 3,
        pace_seconds: float = 0.0,
        max_payload: int = MAX_PAYLOAD,
    ) -> None:
        if redundancy < 1:
            raise DiodeTransportError("redundancy must be at least 1; there is no retransmission request")
        self.target = (host, int(port))
        self.redundancy = int(redundancy)
        self.pace_seconds = float(pace_seconds)
        self.max_payload = int(max_payload)
        self._key = key
        self._sequence = 0
        self.frames_sent = 0
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
        try:
            self._socket.shutdown(socket.SHUT_RD)
        except OSError:
            pass  # platform does not permit it on an unconnected datagram socket

    # The only direction. There is intentionally no receive/read/poll method.
    def send_inward(self, item: dict) -> str:
        body = json.dumps(item, sort_keys=True, default=str).encode()
        item_hash = hashlib.sha256(body).hexdigest()
        self._sequence += 1
        item_id = f"{int(time.time() * 1000):013d}-{self._sequence:06d}"
        chunks = [body[i:i + self.max_payload] for i in range(0, len(body), self.max_payload)] or [b""]
        for index, payload in enumerate(chunks):
            frame = Frame(
                item_id=item_id,
                chunk=index,
                chunks=len(chunks),
                item_hash=item_hash,
                payload=payload,
                tag=_tag(self._key, item_id, index, payload) if self._key else "",
            )
            encoded = frame.encode()
            for _ in range(self.redundancy):
                self._socket.sendto(encoded, self.target)
                self.frames_sent += 1
                if self.pace_seconds:
                    time.sleep(self.pace_seconds)
        return item_id

    def connect(self, high_side_handler: Callable[[dict], None]) -> None:
        """Present for interface compatibility with the in-process channel.

        A real diode sender has no handle on the high side, so this records the
        intent and does nothing. Anything that needs a local copy of what was
        sent should tee it before the boundary, not read it back afterwards.
        """
        self._declared_high_side = getattr(high_side_handler, "__name__", str(high_side_handler))

    def close(self) -> None:
        self._socket.close()

    def __enter__(self) -> "UdpDiodeSender":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# ---------------------------------------------------------------------------
# High side
# ---------------------------------------------------------------------------


@dataclass
class ReceiverStats:
    frames_received: int = 0
    frames_rejected: int = 0
    duplicates_dropped: int = 0
    items_delivered: int = 0
    items_failed_hash: int = 0
    queue_overflows: int = 0

    def snapshot(self) -> dict:
        return {
            "frames_received": self.frames_received,
            "frames_rejected": self.frames_rejected,
            "duplicates_dropped": self.duplicates_dropped,
            "items_delivered": self.items_delivered,
            "items_failed_hash": self.items_failed_hash,
            "queue_overflows": self.queue_overflows,
        }


class UdpDiodeReceiver:
    """Receive-only. Reassembles, verifies, de-duplicates, and delivers.

    It never calls ``sendto``. A receiver that could reply would be a covert
    return path and would void the directional claim for the whole link.
    """

    name = "udp-diode-receiver"

    def __init__(
        self,
        handler: Callable[[dict], None],
        *,
        host: str = "127.0.0.1",
        port: int = DEFAULT_PORT,
        key: str | None = None,
        require_key: bool = True,
        max_items_in_flight: int = 256,
        item_timeout: float = 30.0,
    ) -> None:
        if require_key and not key:
            raise DiodeTransportError(
                "a diode receiver accepts bytes from anything that can reach the port; "
                "configure a key or pass require_key=False and accept that risk explicitly"
            )
        self._handler = handler
        self._key = key
        self._max_in_flight = int(max_items_in_flight)
        self._item_timeout = float(item_timeout)
        self.stats = ReceiverStats()
        self._partial: dict[str, dict] = {}
        self._delivered: set[str] = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
        self._socket.bind((host, int(port)))
        self._socket.settimeout(0.25)
        try:
            self._socket.shutdown(socket.SHUT_WR)
        except OSError:
            pass

    @property
    def port(self) -> int:
        return self._socket.getsockname()[1]

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> "UdpDiodeReceiver":
        self._thread = threading.Thread(target=self._loop, name="diode-receiver", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        self._socket.close()

    def __enter__(self) -> "UdpDiodeReceiver":
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # -- receive path ------------------------------------------------------
    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                datagram, _sender = self._socket.recvfrom(65535)
            except (TimeoutError, socket.timeout):
                self._expire()
                continue
            except OSError:
                break
            self.ingest_datagram(datagram)

    def ingest_datagram(self, datagram: bytes) -> bool:
        """Process one datagram. Exposed so tests need no live socket."""
        self.stats.frames_received += 1
        try:
            frame = Frame.decode(datagram)
        except (ValueError, KeyError, json.JSONDecodeError):
            self.stats.frames_rejected += 1
            return False
        if self._key:
            expected = _tag(self._key, frame.item_id, frame.chunk, frame.payload)
            if not frame.tag or not hmac.compare_digest(expected, frame.tag):
                self.stats.frames_rejected += 1
                return False
        with self._lock:
            if frame.item_id in self._delivered:
                self.stats.duplicates_dropped += 1
                return False
            state = self._partial.get(frame.item_id)
            if state is None:
                if len(self._partial) >= self._max_in_flight:
                    oldest = min(self._partial, key=lambda key: self._partial[key]["first_seen"])
                    del self._partial[oldest]
                    self.stats.queue_overflows += 1
                state = {"chunks": {}, "total": frame.chunks,
                         "hash": frame.item_hash, "first_seen": time.time()}
                self._partial[frame.item_id] = state
            if frame.chunk in state["chunks"]:
                self.stats.duplicates_dropped += 1
                return False
            state["chunks"][frame.chunk] = frame.payload
            if len(state["chunks"]) < state["total"]:
                return False
            body = b"".join(state["chunks"][i] for i in range(state["total"]))
            del self._partial[frame.item_id]
            self._delivered.add(frame.item_id)
            if len(self._delivered) > 10_000:
                self._delivered = set(list(self._delivered)[-5_000:])
        if hashlib.sha256(body).hexdigest() != state["hash"]:
            self.stats.items_failed_hash += 1
            return False
        try:
            item = json.loads(body.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.stats.items_failed_hash += 1
            return False
        self.stats.items_delivered += 1
        self._handler(item)
        return True

    def _expire(self) -> None:
        cutoff = time.time() - self._item_timeout
        with self._lock:
            stale = [key for key, value in self._partial.items() if value["first_seen"] < cutoff]
            for key in stale:
                del self._partial[key]


# ---------------------------------------------------------------------------
# Interface inventory
# ---------------------------------------------------------------------------


@dataclass
class Interface:
    """One declared path in or out of the protected domain."""

    name: str
    direction: str            # inward | outward | bidirectional
    control: str
    owner: str
    note: str = ""


@dataclass
class InterfaceInventory:
    """The governance artifact a diode claim is worthless without.

    A hardware diode governs exactly one link. Every other interface -- an
    administrative SSH session, a monitoring agent, a backup target, a USB port,
    a wireless radio, a vendor maintenance tunnel -- needs its own named control
    and owner, or the directional claim is about a link nobody attacks.

    ``fssaira diode inventory`` prints this, and the conformance suite fails a
    deployment that declares a diode and leaves bidirectional interfaces
    uncontrolled.
    """

    interfaces: list[Interface] = field(default_factory=list)

    def add(self, interface: Interface) -> None:
        self.interfaces.append(interface)

    @property
    def uncontrolled(self) -> list[Interface]:
        return [i for i in self.interfaces if not i.control or not i.owner]

    @property
    def outward_capable(self) -> list[Interface]:
        return [i for i in self.interfaces if i.direction in ("outward", "bidirectional")]

    def to_dict(self) -> dict:
        return {
            "interfaces": [vars(i) for i in self.interfaces],
            "count": len(self.interfaces),
            "outward_capable": len(self.outward_capable),
            "uncontrolled": [i.name for i in self.uncontrolled],
            "complete": not self.uncontrolled,
        }

    @classmethod
    def reference(cls) -> "InterfaceInventory":
        """The interfaces a reader should expect in *any* real deployment."""
        return cls([
            Interface("import link", "inward", "one-way diode or gateway", "Platform Security",
                      "the only path this architecture claims to make directional"),
            Interface("operator HTTPS ingress", "bidirectional", "authenticated reverse proxy",
                      "Platform Security", "carries approvals and console traffic"),
            Interface("administrative shell", "bidirectional", "break-glass, two-person, logged",
                      "Infrastructure Owner", "the path most likely to defeat every other control"),
            Interface("monitoring and telemetry export", "outward", "allowlisted metrics only",
                      "Observability Owner", "a metrics exporter is an egress channel"),
            Interface("backup and restore", "outward", "encrypted, key held separately",
                      "Data Custodian", ""),
            Interface("model artifact update", "inward", "signature check and quarantine",
                      "ML Platform Owner", ""),
            Interface("removable media and console access", "bidirectional", "physical policy",
                      "Facilities", "out of scope for software controls"),
        ])


__all__ = [
    "DEFAULT_PORT", "DiodeTransportError", "Frame", "Interface", "InterfaceInventory",
    "MAX_PAYLOAD", "ReceiverStats", "UdpDiodeReceiver", "UdpDiodeSender",
]
