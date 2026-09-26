"""Anchoring evidence to time that no single clock controls.

A checkpoint says when it was signed, and the enforcer's clock says so. A
compromised enforcer can move its clock, a forward-secure key
(:mod:`fssaira.forward_secure`) then signs in whatever period that clock names,
and receipts, expiries and revocation cut-through are all measured against a
number the attacker chose.

This module follows the Roughtime design. Several independent time servers each
sign ``(nonce, midpoint, radius)``: "when I saw this nonce, the time was within
``radius`` of ``midpoint``". The client **chains** its requests: each nonce is
the hash of the previous server's signed response and a fresh blind, so the
responses carry a provable order. Two consequences:

* the first nonce is derived from the checkpoint itself, so the anchor proves
  the checkpoint existed no later than the earliest server's upper bound;
* if a later server in the chain reports a time interval that ends before an
  earlier server's interval begins, one of them lied, and the two signed
  responses together are the proof (``misbehaviour``).

The anchored time is the intersection of every server's interval. It must be
non-empty, it must come from ``min_servers`` distinct servers, and the
checkpoint's own claimed time must fall inside it (with a declared tolerance)
for :func:`verify_anchor` to accept.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .evidence_notary import _canonical, _ed25519, _verify_signature


class TimeCode:
    ANCHORED = "TIME_ANCHORED"
    SIGNATURE_INVALID = "TIME_SIGNATURE_INVALID"
    CHAIN_BROKEN = "TIME_CHAIN_BROKEN"
    QUORUM_NOT_MET = "TIME_QUORUM_NOT_MET"
    SOURCES_DISAGREE = "TIME_SOURCES_DISAGREE"
    CLAIM_OUTSIDE = "CHECKPOINT_TIME_UNANCHORED"


@dataclass(frozen=True)
class TimeResponse:
    server: str
    nonce: str
    midpoint: float
    radius: float
    signature: str

    def payload(self) -> bytes:
        return _canonical({"server": self.server, "nonce": self.nonce,
                           "midpoint": self.midpoint, "radius": self.radius})

    def to_dict(self) -> dict:
        return {"server": self.server, "nonce": self.nonce, "midpoint": self.midpoint,
                "radius": self.radius, "signature": self.signature}


class TimeServer:
    def __init__(self, name: str, *, radius: float = 1.0, seed: bytes | None = None,
                 clock: Callable[[], float] | None = None) -> None:
        private_cls, *_ = _ed25519()
        self.name, self.radius = name, float(radius)
        self._key = private_cls.from_private_bytes(seed if seed is not None
                                                   else secrets.token_bytes(32))
        self._clock = clock or time.time

    @property
    def public_keys(self) -> dict[str, bytes]:
        *_, encoding, public_format = _ed25519()
        return {self.name: self._key.public_key().public_bytes(encoding.Raw, public_format.Raw)}

    def respond(self, nonce: bytes) -> TimeResponse:
        unsigned = TimeResponse(self.name, nonce.hex(), round(self._clock(), 6), self.radius, "")
        return TimeResponse(**{**unsigned.__dict__,
                               "signature": self._key.sign(unsigned.payload()).hex()})


def chain_nonce(previous: TimeResponse | bytes, blind: bytes) -> bytes:
    """The next request's nonce: hash of what came before and a fresh blind."""
    before = previous if isinstance(previous, bytes) else previous.payload() + bytes.fromhex(
        previous.signature)
    return hashlib.sha256(before + blind).digest()


@dataclass(frozen=True)
class TimeAnchor:
    subject: str                     # hex digest of what was anchored
    blinds: tuple[str, ...]
    responses: tuple[TimeResponse, ...]

    def to_dict(self) -> dict:
        return {"subject": self.subject, "blinds": list(self.blinds),
                "responses": [r.to_dict() for r in self.responses]}


def anchor(subject: bytes, servers: Sequence[TimeServer], *,
           blind: Callable[[], bytes] = lambda: secrets.token_bytes(16)) -> TimeAnchor:
    """Query ``servers`` in order, chaining nonces from ``subject``."""
    if not servers:
        raise ValueError("an anchor needs at least one time server")
    digest = hashlib.sha256(subject).digest()
    blinds, responses = [], []
    previous: TimeResponse | bytes = digest
    for server in servers:
        b = blind()
        response = server.respond(chain_nonce(previous, b))
        blinds.append(b.hex())
        responses.append(response)
        previous = response
    return TimeAnchor(digest.hex(), tuple(blinds), tuple(responses))


def verify_anchor(anchor_: TimeAnchor, server_keys: dict[str, bytes], *, min_servers: int = 2,
                  claimed_time: float | None = None, tolerance: float = 0.0,
                  subject: bytes | None = None) -> dict:
    """Check signatures, the nonce chain, agreement, quorum and the claimed time."""
    def refuse(code: str, **detail) -> dict:
        return {"code": code, "anchored": False, **detail}

    if subject is not None and hashlib.sha256(subject).hexdigest() != anchor_.subject:
        return refuse(TimeCode.CHAIN_BROKEN, why="the anchor is for a different subject")
    if len(anchor_.blinds) != len(anchor_.responses) or not anchor_.responses:
        return refuse(TimeCode.CHAIN_BROKEN, why="blinds and responses do not pair")
    previous: TimeResponse | bytes = bytes.fromhex(anchor_.subject)
    for blind, response in zip(anchor_.blinds, anchor_.responses, strict=True):
        if chain_nonce(previous, bytes.fromhex(blind)).hex() != response.nonce:
            return refuse(TimeCode.CHAIN_BROKEN, server=response.server)
        problem = _verify_signature(server_keys, response.server, response.signature,
                                    response.payload())
        if problem:
            return refuse(TimeCode.SIGNATURE_INVALID, server=response.server, why=problem)
        previous = response
    # Order is proven by the chain, so a later interval that ends before an
    # earlier one begins is a signed contradiction.
    misbehaviour = []
    for i, earlier in enumerate(anchor_.responses):
        for later in anchor_.responses[i + 1:]:
            if later.midpoint + later.radius < earlier.midpoint - earlier.radius:
                misbehaviour.append({"earlier": earlier.to_dict(), "later": later.to_dict()})
    lo = max(r.midpoint - r.radius for r in anchor_.responses)
    hi = min(r.midpoint + r.radius for r in anchor_.responses)
    servers = sorted({r.server for r in anchor_.responses})
    if misbehaviour or lo > hi:
        return refuse(TimeCode.SOURCES_DISAGREE, misbehaviour=misbehaviour, servers=servers)
    if len(servers) < min_servers:
        return refuse(TimeCode.QUORUM_NOT_MET, servers=servers, min_servers=min_servers)
    result = {"code": TimeCode.ANCHORED, "anchored": True, "earliest": lo, "latest": hi,
              "servers": servers}
    if claimed_time is not None and not (lo - tolerance <= claimed_time <= hi + tolerance):
        return {**result, "code": TimeCode.CLAIM_OUTSIDE, "anchored": False,
                "claimed_time": claimed_time}
    return result


__all__ = ["TimeAnchor", "TimeCode", "TimeResponse", "TimeServer", "anchor", "chain_nonce",
           "verify_anchor"]
