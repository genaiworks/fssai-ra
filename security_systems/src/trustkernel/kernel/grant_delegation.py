"""Delegated data access: a sub-agent receives at most what its parent held.

:mod:`trustkernel.kernel.delegation` governs authority to *act* passed between agents. This
module governs entitlement to *see*. An orchestrator holding a grant to read
attendance for academic support spawns a sub-agent; the sub-agent must not come
away able to read the complete record, for longer, for marketing, in a public zone,
or to show it to someone the parent could not.

Every hop is signed by the delegation service's key and says what it hands on. The
hop is **not** validated when issued, deliberately: a compromised agent can write
any hop it likes. Validation happens at **exchange**, when the leaf presents the
whole chain to the context gate's delegation verifier, which recomputes the
effective entitlement from the root and refuses on the first widening along any of
seven axes:

=============  =============================================
axis           a hop may
=============  =============================================
subjects       name the same subjects or fewer
fields         name the same fields or fewer
classes        name the same data classes or fewer
purpose        keep the purpose exactly
expiry         expire no later than its parent
zones          process in the same zones or fewer
audience       release to the same recipients or fewer
=============  =============================================

The effective grant is signed by the exchange authority whose key the gate trusts,
and remembers its ancestry. Revoking the root or any hop revokes every effective
grant derived through it, so the gate's own revocation check stops the next read
**and** the next release of anything already derived.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Iterable
from dataclasses import dataclass, field, replace

from .disclosure import DisclosureDenied, DisclosureGate, DisclosureGrant, GrantAuthority

AXES = ("subjects", "fields", "classes", "purpose", "expiry", "zones", "audience")


class GrantDelegationCode:
    SIGNATURE_INVALID = "DELEGATED_GRANT_SIGNATURE_INVALID"
    CHAIN_BROKEN = "DELEGATED_GRANT_CHAIN_BROKEN"
    HOLDER_MISMATCH = "DELEGATED_GRANT_HOLDER_MISMATCH"
    DEPTH_EXCEEDED = "DELEGATED_GRANT_DEPTH_EXCEEDED"
    REVOKED = "DELEGATED_GRANT_REVOKED"
    ROOT_NOT_CURRENT = "DELEGATED_GRANT_ROOT_NOT_CURRENT"
    ESCALATION = {axis: f"DELEGATION_{axis.upper()}_ESCALATION" for axis in AXES}
    ZONE_NOT_PERMITTED = "DELEGATED_GRANT_ZONE_NOT_PERMITTED"
    AUDIENCE_NOT_PERMITTED = "DELEGATED_GRANT_AUDIENCE_NOT_PERMITTED"


@dataclass(frozen=True)
class GrantHop:
    hop_id: str
    parent_id: str
    delegator: str
    delegate: str
    purpose: str
    subjects: frozenset[str]
    fields: frozenset[str]
    classes: frozenset[str]
    zones: frozenset[str]
    audience: frozenset[str]
    issued_at: float
    expires_at: float
    signature: str = ""

    def payload(self) -> str:
        return json.dumps({
            "hop_id": self.hop_id, "parent_id": self.parent_id, "delegator": self.delegator,
            "delegate": self.delegate, "purpose": self.purpose, "subjects": sorted(self.subjects),
            "fields": sorted(self.fields), "classes": sorted(self.classes),
            "zones": sorted(self.zones), "audience": sorted(self.audience),
            "issued_at": self.issued_at, "expires_at": self.expires_at,
        }, sort_keys=True)

    def to_dict(self) -> dict:
        return json.loads(self.payload())


@dataclass(frozen=True)
class EffectiveGrant:
    grant: DisclosureGrant
    zones: frozenset[str]
    audience: frozenset[str]
    ancestry: tuple[str, ...]
    chain: tuple[GrantHop, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {"grant": self.grant.to_dict(), "zones": sorted(self.zones),
                "audience": sorted(self.audience), "ancestry": list(self.ancestry),
                "depth": len(self.chain)}


class GrantDelegationService:
    """Issues hops, and verifies whole chains before the gate sees a derived grant."""

    def __init__(self, gate: DisclosureGate, exchange_authority: GrantAuthority, *,
                 hop_secret: str = "reference-grant-delegation-key", max_depth: int = 3,
                 enforce_attenuation: bool = True) -> None:
        self.gate = gate
        self.exchange_authority = exchange_authority
        self._secret = hop_secret
        self.max_depth = max_depth
        self.enforce_attenuation = enforce_attenuation
        self._descendants: dict[str, set[str]] = {}
        self._root_zones = frozenset(gate.policy.all_zones)
        self._root_audience = frozenset(gate.policy.recipients)
        self._counter = 0

    def _sign(self, hop: GrantHop) -> str:
        return hmac.new(self._secret.encode(), hop.payload().encode(), hashlib.sha256).hexdigest()

    def delegate(self, *, parent_id: str, delegator: str, delegate: str, purpose: str,
                 subjects: Iterable[str], fields: Iterable[str], classes: Iterable[str],
                 zones: Iterable[str] | None = None, audience: Iterable[str] | None = None,
                 issued_at: float, expires_at: float) -> GrantHop:
        self._counter += 1
        hop = GrantHop(
            hop_id=f"hop-{self._counter}", parent_id=parent_id, delegator=delegator,
            delegate=delegate, purpose=purpose, subjects=frozenset(subjects),
            fields=frozenset(fields), classes=frozenset(classes),
            zones=frozenset(zones if zones is not None else self._root_zones),
            audience=frozenset(audience if audience is not None else self._root_audience),
            issued_at=issued_at, expires_at=expires_at)
        return replace(hop, signature=self._sign(hop))

    def _refuse(self, code: str, detail: str) -> DisclosureDenied:
        return DisclosureDenied(code, detail)

    def exchange(self, root: DisclosureGrant, chain: Iterable[GrantHop], *, requester: str,
                 now: float) -> EffectiveGrant:
        hops = tuple(chain)
        if len(hops) > self.max_depth:
            raise self._refuse(GrantDelegationCode.DEPTH_EXCEEDED,
                               f"{len(hops)} hops exceed the declared maximum of {self.max_depth}")
        self.gate._verify_grant_signature(root)
        with self.gate.store.atomic() as tx:
            revoked = {gid for gid in (root.grant_id, *(h.hop_id for h in hops)) if tx.is_revoked(gid)}
        if root.grant_id in revoked or now >= root.expires_at:
            raise self._refuse(GrantDelegationCode.ROOT_NOT_CURRENT, "the root grant is revoked or expired")

        held = {"holder": root.holder, "id": root.grant_id, "purpose": root.purpose,
                "subjects": root.subjects, "fields": root.fields, "classes": root.classes,
                "zones": self._root_zones, "audience": self._root_audience,
                "expiry": root.expires_at}
        for depth, hop in enumerate(hops, start=1):
            if not hmac.compare_digest(hop.signature, self._sign(hop)):
                raise self._refuse(GrantDelegationCode.SIGNATURE_INVALID, f"hop {depth} is not authentic")
            if hop.hop_id in revoked:
                raise self._refuse(GrantDelegationCode.REVOKED,
                                   f"hop {depth} was revoked, and everything below it with it")
            if hop.parent_id != held["id"] or hop.delegator != held["holder"]:
                raise self._refuse(GrantDelegationCode.CHAIN_BROKEN,
                                   f"hop {depth} does not descend from the authority before it")
            if self.enforce_attenuation:
                for axis in ("subjects", "fields", "classes", "zones", "audience"):
                    wider = sorted(getattr(hop, axis) - held[axis])
                    if wider:
                        raise self._refuse(GrantDelegationCode.ESCALATION[axis],
                                           f"hop {depth} adds {axis} its delegator does not hold: "
                                           f"{', '.join(wider)}")
                if hop.purpose != held["purpose"]:
                    raise self._refuse(GrantDelegationCode.ESCALATION["purpose"],
                                       f"hop {depth} changes purpose {held['purpose']!r} to {hop.purpose!r}")
                if hop.expires_at > held["expiry"]:
                    raise self._refuse(GrantDelegationCode.ESCALATION["expiry"],
                                       f"hop {depth} outlives the authority it descends from")
            held = {"holder": hop.delegate, "id": hop.hop_id, "purpose": hop.purpose,
                    "subjects": hop.subjects, "fields": hop.fields, "classes": hop.classes,
                    "zones": hop.zones, "audience": hop.audience, "expiry": hop.expires_at}
        if requester != held["holder"]:
            raise self._refuse(GrantDelegationCode.HOLDER_MISMATCH,
                               "the chain was delegated to someone else; chains are not bearer tokens")
        ancestry = (root.grant_id, *(h.hop_id for h in hops))
        effective_id = f"{root.grant_id}/" + "/".join(h.hop_id for h in hops) if hops else root.grant_id
        grant = self.exchange_authority.issue(
            grant_id=effective_id, holder=requester, purpose=held["purpose"],
            subjects=held["subjects"], fields=held["fields"], classes=held["classes"],
            issued_by=f"delegation-exchange:{root.issued_by}", now=now,
            ttl_seconds=max(0.0, held["expiry"] - now), basis=f"delegated from {root.grant_id}")
        for ancestor in ancestry:
            self._descendants.setdefault(ancestor, set()).add(effective_id)
        return EffectiveGrant(grant, frozenset(held["zones"]), frozenset(held["audience"]),
                              ancestry, hops)

    def revoke(self, grant_or_hop_id: str, *, by: str, reason: str) -> list[str]:
        """Revoke one grant or hop and every effective grant derived through it."""
        affected = sorted({grant_or_hop_id, *self._descendants.get(grant_or_hop_id, set())})
        for grant_id in affected:
            self.gate.revoke_grant(grant_id, by=by, reason=reason)
        return affected

    def check_use(self, effective: EffectiveGrant, *, endpoint: str | None = None,
                  recipient: str | None = None) -> None:
        """Zone and audience limits the gate's grant format does not carry."""
        if endpoint is not None:
            zone = self.gate.policy.endpoints.get(endpoint)
            if self.enforce_attenuation and zone not in effective.zones:
                raise self._refuse(GrantDelegationCode.ZONE_NOT_PERMITTED,
                                   f"this delegated grant may not be processed in {zone!r}")
        if recipient is not None and self.enforce_attenuation and recipient not in effective.audience:
            raise self._refuse(GrantDelegationCode.AUDIENCE_NOT_PERMITTED,
                               f"this delegated grant may not be released to {recipient!r}")


__all__ = ["AXES", "EffectiveGrant", "GrantDelegationCode", "GrantDelegationService", "GrantHop"]
