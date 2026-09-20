"""Authority across services, evidence no single custodian can rewrite, and a
promotion gate that will not take anyone's word for readiness.

Three gaps were open here, and they are the ones that decide whether the
architecture survives contact with a real institution.

**Federation.** A task contract is worthless the moment authority crosses a
service boundary by being re-declared on the other side. A federated grant is
therefore a signed, audience-bound, single-use, depth-limited statement whose
scope can only be *intersected* with the receiving service's own ceiling. A
receiving service that would have to widen its ceiling to honour a grant
refuses it; a grant replayed, redirected, expired or re-broadened is refused.

**Witnesses.** An evidence chain kept by one custodian is exactly as trustworthy
as that custodian. A :class:`WitnessSet` requires k-of-n independent signatures
over each evidence head before the head counts as attested, and detects the
specific failure that matters -- two witnesses attesting *different* heads at
the same sequence, which is the signature of a rewritten history.

**Promotion.** A model bundle reaches production when someone can show, freshly
and together: conformance against the real backends, measured host isolation,
qualified transport, witnessed evidence, and no unresolved remote effect. The
gate names every missing item rather than returning a single boolean, because
"not ready" is only useful if it says what is missing.

None of this is deployed infrastructure. It is the contract that deployed
infrastructure must satisfy, written so that a deployment can be tested against
it rather than described as compliant.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

MAX_DELEGATION_DEPTH = 8


class FederationDenied(ValueError):
    """A stable reason code. Never untrusted input, never protected values."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise FederationDenied(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


# -- federated authority ----------------------------------------------------


@dataclass(frozen=True)
class FederatedGrant:
    """Authority offered by one service to another, for one task, once."""

    issuer: str
    audience: str
    task: str
    #: Axis name -> permitted values. Compared by subset, never merged.
    scope: Mapping[str, frozenset[str]]
    depth: int
    expires: float
    nonce: str

    def __post_init__(self) -> None:
        for name in ("issuer", "audience", "task", "nonce"):
            value = getattr(self, name)
            _require(isinstance(value, str) and 0 < len(value) <= 160
                     and value.strip() == value and "*" not in value,
                     "INVALID_GRANT_IDENTIFIER")
        _require(self.issuer != self.audience, "SELF_ISSUED_GRANT")
        _require(type(self.depth) is int and 0 <= self.depth <= MAX_DELEGATION_DEPTH,
                 "INVALID_DEPTH")
        _require(isinstance(self.expires, (int, float)) and self.expires > 0,
                 "INVALID_EXPIRY")
        _require(isinstance(self.scope, Mapping) and self.scope, "EMPTY_SCOPE")
        frozen = {}
        for axis, values in self.scope.items():
            _require(isinstance(axis, str) and axis.isidentifier(), "INVALID_AXIS")
            _require(isinstance(values, (set, frozenset, list, tuple))
                     and 0 < len(values) <= 128, "INVALID_AXIS_VALUES")
            _require(all(isinstance(v, str) and v and "*" not in v for v in values),
                     "INVALID_AXIS_VALUES")
            frozen[axis] = frozenset(values)
        object.__setattr__(self, "scope", frozen)

    def to_dict(self) -> dict:
        return {
            "issuer": self.issuer, "audience": self.audience, "task": self.task,
            "scope": {axis: sorted(values) for axis, values in self.scope.items()},
            "depth": self.depth, "expires": self.expires, "nonce": self.nonce,
        }

    def signature(self, key: bytes) -> str:
        return hmac.new(key, _canonical(self.to_dict()), hashlib.sha256).hexdigest()

    def attenuate(self, *, audience: str, scope: Mapping[str, frozenset[str]],
                  expires: float, nonce: str) -> FederatedGrant:
        """Pass authority onward, never wider and never longer."""
        _require(self.depth > 0, "DELEGATION_DEPTH_EXHAUSTED")
        _require(expires <= self.expires, "DELEGATION_CANNOT_EXTEND_EXPIRY")
        for axis, values in scope.items():
            _require(axis in self.scope, "DELEGATION_CANNOT_ADD_AXIS")
            _require(frozenset(values) <= self.scope[axis], "DELEGATION_CANNOT_WIDEN")
        return FederatedGrant(
            issuer=self.audience, audience=audience, task=self.task,
            scope=scope, depth=self.depth - 1, expires=expires, nonce=nonce)


@dataclass
class FederationPeer:
    """One service's view: its own ceiling, its keys, and what it has consumed."""

    service: str
    #: The widest authority this service will ever exercise, whatever it is offered.
    ceiling: Mapping[str, frozenset[str]]
    #: Per-issuer shared secrets. A missing issuer is an unknown issuer.
    keys: Mapping[str, bytes] = field(default_factory=dict)
    clock: Callable[[], float] = time.time
    _consumed: set[str] = field(default_factory=set, repr=False)

    def accept(self, grant: FederatedGrant, signature: str) -> dict[str, frozenset[str]]:
        """Verify a grant and return the authority actually usable here."""
        key = self.keys.get(grant.issuer)
        _require(key is not None, "UNKNOWN_ISSUER")
        _require(hmac.compare_digest(grant.signature(key), signature), "BAD_SIGNATURE")
        _require(grant.audience == self.service, "WRONG_AUDIENCE")
        _require(self.clock() < grant.expires, "GRANT_EXPIRED")
        identity = f"{grant.issuer}:{grant.nonce}"
        _require(identity not in self._consumed, "GRANT_REPLAYED")

        effective: dict[str, frozenset[str]] = {}
        for axis, values in grant.scope.items():
            local = self.ceiling.get(axis)
            _require(local is not None, "AXIS_OUTSIDE_LOCAL_CEILING")
            # Intersection, never union: a grant cannot teach a service a new
            # capability, only permit part of what it already has.
            permitted = values & local
            _require(permitted, "GRANT_EMPTY_AFTER_INTERSECTION")
            effective[axis] = permitted
        self._consumed.add(identity)
        return effective

    def issue(self, *, audience: str, task: str, scope: Mapping[str, frozenset[str]],
              depth: int, expires: float, nonce: str,
              key: bytes) -> tuple[FederatedGrant, str]:
        """Offer authority this service actually holds. Never more."""
        for axis, values in scope.items():
            _require(axis in self.ceiling, "CANNOT_ISSUE_UNHELD_AXIS")
            _require(frozenset(values) <= self.ceiling[axis], "CANNOT_ISSUE_BEYOND_CEILING")
        grant = FederatedGrant(
            issuer=self.service, audience=audience, task=task, scope=scope,
            depth=depth, expires=expires, nonce=nonce)
        return grant, grant.signature(key)


# -- independent evidence custody -------------------------------------------


@dataclass(frozen=True)
class Attestation:
    witness: str
    sequence: int
    head: str
    signature: str


class WitnessSet:
    """k-of-n independent co-signature over the evidence chain.

    A single custodian can rewrite a chain it alone holds. Requiring k
    signatures from separately keyed witnesses means a rewrite has to corrupt k
    parties at once, and a *partial* rewrite is detected rather than merely
    suspected: two witnesses attesting different heads at one sequence is a
    fork, and forks are surfaced, never averaged away.
    """

    def __init__(self, keys: Mapping[str, bytes], threshold: int) -> None:
        _require(len(keys) >= 2, "A_SINGLE_WITNESS_IS_NOT_A_WITNESS_SET")
        _require(isinstance(threshold, int) and 2 <= threshold <= len(keys),
                 "INVALID_THRESHOLD")
        self._keys = dict(keys)
        self.threshold = threshold
        self._attestations: dict[int, dict[str, Attestation]] = {}

    @staticmethod
    def _sign(key: bytes, sequence: int, head: str) -> str:
        return hmac.new(key, _canonical({"sequence": sequence, "head": head}),
                        hashlib.sha256).hexdigest()

    def attest(self, witness: str, sequence: int, head: str) -> Attestation:
        key = self._keys.get(witness)
        _require(key is not None, "UNKNOWN_WITNESS")
        _require(isinstance(sequence, int) and sequence >= 0, "INVALID_SEQUENCE")
        _require(isinstance(head, str) and len(head) == 64, "INVALID_HEAD")
        attestation = Attestation(witness, sequence, head, self._sign(key, sequence, head))
        existing = self._attestations.setdefault(sequence, {})
        previous = existing.get(witness)
        _require(previous is None or previous.head == head, "WITNESS_CONTRADICTS_ITSELF")
        existing[witness] = attestation
        return attestation

    def verify(self, attestation: Attestation) -> bool:
        key = self._keys.get(attestation.witness)
        if key is None:
            return False
        return hmac.compare_digest(
            self._sign(key, attestation.sequence, attestation.head), attestation.signature)

    def forks(self) -> tuple[dict, ...]:
        """Sequences where witnesses disagree about history."""
        found = []
        for sequence, attestations in sorted(self._attestations.items()):
            heads = {a.head for a in attestations.values() if self.verify(a)}
            if len(heads) > 1:
                found.append({"sequence": sequence, "heads": sorted(heads)})
        return tuple(found)

    def attested(self, sequence: int, head: str) -> bool:
        """Is this head witnessed by enough independent parties, with no fork?"""
        if self.forks():
            return False
        attestations = self._attestations.get(sequence, {})
        agreeing = [a for a in attestations.values()
                    if a.head == head and self.verify(a)]
        return len(agreeing) >= self.threshold

    def status(self, sequence: int, head: str) -> dict:
        attestations = self._attestations.get(sequence, {})
        return {
            "sequence": sequence,
            "head": head,
            "witnesses": sorted(self._keys),
            "threshold": self.threshold,
            "signatures": sorted(a.witness for a in attestations.values()
                                 if a.head == head and self.verify(a)),
            "forks": list(self.forks()),
            "attested": self.attested(sequence, head),
        }


# -- promotion --------------------------------------------------------------

#: Every item a deployment must show, freshly, before it is production.
PROMOTION_REQUIREMENTS = (
    ("conformance", "the conformance suite passed against the deployment's own backends"),
    ("isolation", "host isolation was measured and qualified as production"),
    ("transport", "outbound transport was qualified against the real peer, not the harness"),
    ("witnesses", "the current evidence head is attested by the witness threshold"),
    ("remote_effects", "no outbound effect is in an unresolved state"),
    ("bundle", "the exact model bundle under promotion is the one that was evaluated"),
)


@dataclass(frozen=True)
class PromotionEvidence:
    """What a deployment claims, with the age and identity of each claim."""

    conformance_passed: bool
    conformance_at: float
    isolation_qualification: str
    isolation_at: float
    transport_qualified: bool
    transport_qualification_only: bool
    transport_at: float
    evidence_attested: bool
    unresolved_effects: int
    evaluated_bundle_digest: str
    promoted_bundle_digest: str
    operator: str

    def __post_init__(self) -> None:
        _require(isinstance(self.operator, str) and self.operator.strip(),
                 "PROMOTION_REQUIRES_A_NAMED_OPERATOR")


@dataclass(frozen=True)
class PromotionGate:
    """Refuse promotion, and say exactly what is missing."""

    max_age_seconds: float = 86_400.0

    def evaluate(self, evidence: PromotionEvidence, *, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        missing: list[str] = []

        def stale(at: float, what: str) -> bool:
            if now - at > self.max_age_seconds:
                missing.append(f"{what}: evidence is {int(now - at)}s old "
                               f"(limit {int(self.max_age_seconds)}s)")
                return True
            return False

        if not evidence.conformance_passed:
            missing.append("conformance: the suite did not pass")
        else:
            stale(evidence.conformance_at, "conformance")

        if evidence.isolation_qualification != "production":
            missing.append(
                f"isolation: measured qualification is "
                f"{evidence.isolation_qualification!r}, not 'production'")
        else:
            stale(evidence.isolation_at, "isolation")

        if evidence.transport_qualification_only:
            missing.append(
                "transport: the only transport evidence comes from the loopback "
                "qualification harness, which is not a network peer")
        elif not evidence.transport_qualified:
            missing.append("transport: no qualified transfer was recorded")
        else:
            stale(evidence.transport_at, "transport")

        if not evidence.evidence_attested:
            missing.append("witnesses: the current evidence head is not attested "
                           "by the required number of independent witnesses")
        if evidence.unresolved_effects:
            missing.append(f"remote_effects: {evidence.unresolved_effects} outbound "
                           "effect(s) are in an unresolved state")
        if evidence.evaluated_bundle_digest != evidence.promoted_bundle_digest:
            missing.append("bundle: the bundle being promoted is not the bundle "
                           "that was evaluated")

        return {
            "schema_version": "1.0",
            "kind": "promotion_decision",
            "promoted": not missing,
            "qualification": "production" if not missing else "reference",
            "operator": evidence.operator,
            "requirements": [{"id": rid, "statement": text}
                             for rid, text in PROMOTION_REQUIREMENTS],
            "missing": missing,
            "limits": [
                "promotion checks that required evidence exists, is fresh and is "
                "attributable; it does not re-derive the evidence",
                "a passing gate is a statement about one deployment at one moment",
            ],
        }

    def require(self, evidence: PromotionEvidence, *, now: float | None = None) -> dict:
        decision = self.evaluate(evidence, now=now)
        if not decision["promoted"]:
            raise FederationDenied(
                "promotion refused: " + "; ".join(decision["missing"]))
        return decision


__all__ = [
    "MAX_DELEGATION_DEPTH", "PROMOTION_REQUIREMENTS", "Attestation",
    "FederatedGrant", "FederationDenied", "FederationPeer", "PromotionEvidence",
    "PromotionGate", "WitnessSet",
]
