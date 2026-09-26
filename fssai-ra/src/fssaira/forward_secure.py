"""Forward-secure signing: a key stolen today cannot sign yesterday.

The notary and the tree-head signer each hold one long-lived Ed25519 key. An
attacker who takes that key can sign a checkpoint dated last month, and the
signature is as valid as the real one. Witnesses limit the damage to histories
they have not already seen; this module removes the capability itself.

The construction is the simplest forward-secure scheme that uses only standard
signatures (the "certified period keys" scheme): at setup a root key signs one
public key for each time period, together with the schedule that maps time to
period, and the root secret is then discarded. The signer holds only the secret
keys of the current and future periods. :meth:`ForwardSecureSigner.advance`
erases the current period's secret before moving on. A verifier needs only the
root public key.

So a compromise during period ``j`` yields keys for ``j`` and later, and nothing
earlier: the attacker can lie about the future (which witnesses and time anchors
then constrain) but cannot rewrite the signed past. A verifier that also knows
*when* a statement claims to be made (``at``) refuses a signature from any
period other than the one that time falls in, so the stolen key cannot backdate.
"""
from __future__ import annotations

import hashlib
import math
import secrets
from dataclasses import dataclass

from .evidence_notary import _canonical, _ed25519


class ForwardSecureCode:
    VALID = "FS_SIGNATURE_VALID"
    ROOT_UNTRUSTED = "FS_ROOT_UNTRUSTED"
    SCHEDULE_INVALID = "FS_SCHEDULE_INVALID"
    PERIOD_CERT_INVALID = "FS_PERIOD_CERT_INVALID"
    SIGNATURE_INVALID = "FS_SIGNATURE_INVALID"
    WRONG_PERIOD = "FS_WRONG_PERIOD"
    KEY_ERASED = "FS_KEY_ERASED"
    SCHEDULE_EXHAUSTED = "FS_SCHEDULE_EXHAUSTED"


class KeyErased(RuntimeError):
    """The requested period's secret no longer exists anywhere."""


def _raw_public(private) -> bytes:
    *_, encoding, public_format = _ed25519()
    return private.public_key().public_bytes(encoding.Raw, public_format.Raw)


@dataclass(frozen=True)
class Schedule:
    key_id: str
    start: float
    period_seconds: float
    periods: int

    def payload(self) -> bytes:
        return _canonical({"key_id": self.key_id, "start": self.start,
                           "period_seconds": self.period_seconds, "periods": self.periods})

    def period_at(self, at: float) -> int:
        return math.floor((at - self.start) / self.period_seconds)


@dataclass(frozen=True)
class ForwardSecureSignature:
    key_id: str
    period: int
    period_public: str       # hex
    period_cert: str         # root's signature over (key_id, period, period_public)
    schedule_cert: str       # root's signature over the schedule
    signature: str
    schedule: Schedule

    @classmethod
    def from_dict(cls, value: dict) -> ForwardSecureSignature:
        schedule = value["schedule"]
        return cls(value["key_id"], int(value["period"]), value["period_public"],
                   value["period_cert"], value["schedule_cert"], value["signature"],
                   Schedule(value["key_id"], float(schedule["start"]),
                            float(schedule["period_seconds"]), int(schedule["periods"])))

    def to_dict(self) -> dict:
        return {"key_id": self.key_id, "period": self.period,
                "period_public": self.period_public, "period_cert": self.period_cert,
                "schedule_cert": self.schedule_cert, "signature": self.signature,
                "schedule": {"start": self.schedule.start,
                             "period_seconds": self.schedule.period_seconds,
                             "periods": self.schedule.periods}}


def _period_payload(key_id: str, period: int, public_hex: str) -> bytes:
    return _canonical({"key_id": key_id, "period": period, "public": public_hex})


class ForwardSecureSigner:
    """Sign with the current period's key; erase it when the period ends.

    ``seed`` makes the key set deterministic for tests. The seed is consumed at
    construction and not retained, so it is no more of a standing secret than
    the root key; a deployment omits it.
    """

    def __init__(self, *, key_id: str, start: float, period_seconds: float, periods: int,
                 seed: bytes | None = None) -> None:
        if period_seconds <= 0 or periods < 1:
            raise ValueError("a schedule has at least one period of positive length")
        private_cls, *_ = _ed25519()

        def derive(label: bytes):
            material = (hashlib.sha256(seed + label).digest() if seed is not None
                        else secrets.token_bytes(32))
            return private_cls.from_private_bytes(material)

        root = derive(b"root")
        self.schedule = Schedule(key_id, float(start), float(period_seconds), int(periods))
        self.root_public = _raw_public(root)
        self._schedule_cert = root.sign(self.schedule.payload()).hex()
        self._keys: list = []
        self._certs: list[tuple[str, str]] = []
        for period in range(periods):
            key = derive(b"period" + period.to_bytes(8, "big"))
            public_hex = _raw_public(key).hex()
            self._keys.append(key)
            self._certs.append((public_hex, root.sign(_period_payload(key_id, period,
                                                                       public_hex)).hex()))
        del root                          # the root secret exists nowhere after setup
        self.period = 0

    def advance(self, to: int | None = None) -> int:
        """Move to period ``to`` (default: the next), erasing every earlier secret."""
        target = self.period + 1 if to is None else to
        if target < self.period:
            raise ValueError("forward-secure signers only move forward")
        for period in range(self.period, min(target, self.schedule.periods)):
            self._keys[period] = None
        self.period = target
        return target

    def advance_to_time(self, at: float) -> int:
        return self.advance(max(self.period, self.schedule.period_at(at)))

    def retained_periods(self) -> list[int]:
        """Which period secrets still exist: what a thief would get right now."""
        return [p for p, key in enumerate(self._keys) if key is not None]

    def sign(self, payload: bytes) -> ForwardSecureSignature:
        if self.period >= self.schedule.periods:
            raise KeyErased(ForwardSecureCode.SCHEDULE_EXHAUSTED)
        key = self._keys[self.period]
        if key is None:
            raise KeyErased(ForwardSecureCode.KEY_ERASED)
        public_hex, cert = self._certs[self.period]
        return ForwardSecureSignature(self.schedule.key_id, self.period, public_hex, cert,
                                      self._schedule_cert, key.sign(payload).hex(),
                                      self.schedule)


def verify_forward_secure(roots: dict[str, bytes], payload: bytes,
                          signature: ForwardSecureSignature, *, at: float | None = None) -> str:
    """Return :class:`ForwardSecureCode.VALID` or the reason it is not.

    ``at`` is the time the signed statement claims for itself (a checkpoint's
    ``signed_at``). When given, the signature must come from that time's period.
    """
    _private, public_cls, invalid, *_ = _ed25519()
    root = roots.get(signature.key_id)
    if root is None:
        return ForwardSecureCode.ROOT_UNTRUSTED
    root_key = public_cls.from_public_bytes(root)
    try:
        root_key.verify(bytes.fromhex(signature.schedule_cert), signature.schedule.payload())
    except (invalid, ValueError):
        return ForwardSecureCode.SCHEDULE_INVALID
    if signature.schedule.key_id != signature.key_id or not (
            0 <= signature.period < signature.schedule.periods):
        return ForwardSecureCode.SCHEDULE_INVALID
    try:
        root_key.verify(bytes.fromhex(signature.period_cert),
                        _period_payload(signature.key_id, signature.period,
                                        signature.period_public))
    except (invalid, ValueError):
        return ForwardSecureCode.PERIOD_CERT_INVALID
    try:
        public_cls.from_public_bytes(bytes.fromhex(signature.period_public)).verify(
            bytes.fromhex(signature.signature), payload)
    except (invalid, ValueError):
        return ForwardSecureCode.SIGNATURE_INVALID
    if at is not None and signature.schedule.period_at(at) != signature.period:
        return ForwardSecureCode.WRONG_PERIOD
    return ForwardSecureCode.VALID


__all__ = ["ForwardSecureCode", "ForwardSecureSignature", "ForwardSecureSigner", "KeyErased",
           "Schedule", "verify_forward_secure"]
