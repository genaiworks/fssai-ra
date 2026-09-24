"""The legal lifecycle of one consequential effect.

Nine states, and only the declared transitions between them (paper §6.2):

    pending ──► approved ──► dispatched ──► committed ──► compensated
       │            │            │  └──► uncertain ──► reconciled ──► compensated
       │            │            │            └──────────────────────► compensated
       └► denied / expired  ◄────┘ (denied)

Three rules the table alone does not express are enforced here:

* An *uncertain* effect is never re-dispatched. Its outcome is established by
  status query and reconciliation, because a blind retry can repeat an
  irreversible external effect.
* *Compensation* is a separately authorized action. It needs its own
  authorization, which may not be one already used for this effect.
  Compensation never erases history.
* Every transition is recorded before it takes effect. If evidence cannot be
  written, the transition does not happen.
"""
from __future__ import annotations

from collections.abc import Mapping
from enum import Enum

from fssaira.evidence import EvidenceLedger


class EffectState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DISPATCHED = "dispatched"
    COMMITTED = "committed"
    UNCERTAIN = "uncertain"
    RECONCILED = "reconciled"
    COMPENSATED = "compensated"
    DENIED = "denied"
    EXPIRED = "expired"


_S = EffectState
TRANSITIONS: Mapping[EffectState, frozenset[EffectState]] = {
    _S.PENDING: frozenset({_S.APPROVED, _S.DENIED, _S.EXPIRED}),
    _S.APPROVED: frozenset({_S.DISPATCHED, _S.DENIED, _S.EXPIRED}),
    _S.DISPATCHED: frozenset({_S.COMMITTED, _S.UNCERTAIN, _S.DENIED}),
    _S.UNCERTAIN: frozenset({_S.RECONCILED, _S.COMPENSATED}),
    _S.COMMITTED: frozenset({_S.COMPENSATED}),
    _S.RECONCILED: frozenset({_S.COMPENSATED}),
    _S.COMPENSATED: frozenset(),
    _S.DENIED: frozenset(),
    _S.EXPIRED: frozenset(),
}
TERMINAL: frozenset[EffectState] = frozenset(s for s, targets in TRANSITIONS.items() if not targets)


class IllegalTransition(RuntimeError):
    """The requested state change is not a declared transition."""


class EffectRecord:
    """Tracks one effect; every accepted transition is evidenced first."""

    def __init__(
        self,
        request_id: str,
        *,
        ledger: EvidenceLedger | None = None,
        token: str | None = None,
        irreversible_external: bool = False,
        _state: EffectState = EffectState.PENDING,
    ) -> None:
        if not request_id:
            raise ValueError("an effect needs a stable request identifier")
        # ``is not None``: an empty ledger is falsy and must still receive evidence.
        if ledger is not None and not token:
            raise ValueError("a ledger needs its append token")
        self.request_id = request_id
        self.irreversible_external = irreversible_external
        self._ledger = ledger
        self._token = token
        self._state = _state
        self._authorizations: set[str] = set()
        self.history: list[tuple[EffectState, str]] = [(_state, "restored" if _state is not EffectState.PENDING else "created")]

    @classmethod
    def restore(cls, request_id: str, state: EffectState, **kwargs: object) -> EffectRecord:
        """Rebuild a record at a persisted state (e.g. after a crash)."""
        return cls(request_id, _state=state, **kwargs)  # type: ignore[arg-type]

    @property
    def state(self) -> EffectState:
        return self._state

    def transition(self, target: EffectState, *, reason: str, authorization: str | None = None) -> None:
        source = self._state
        if source in TERMINAL:
            raise IllegalTransition(f"{source.value} is terminal; {self.request_id} admits no further transition")
        if target not in TRANSITIONS[source]:
            if source is EffectState.UNCERTAIN and target is EffectState.DISPATCHED:
                raise IllegalTransition(
                    "an uncertain effect is never re-dispatched; query its status and reconcile"
                )
            raise IllegalTransition(f"{source.value} -> {target.value} is not a declared transition")
        if target is EffectState.COMPENSATED:
            if not authorization:
                raise IllegalTransition("compensation requires its own authorization")
            if authorization in self._authorizations:
                raise IllegalTransition(
                    "compensation requires a separate authorization, not one already used for this effect"
                )
        if self._ledger is not None:
            self._ledger.append("effect_transition", {
                "request_id": self.request_id,
                "from": source.value,
                "to": target.value,
                "reason": reason,
                "authorization": authorization or "",
                "irreversible_external": self.irreversible_external,
            }, token=self._token or "")
        if authorization:
            self._authorizations.add(authorization)
        self._state = target
        self.history.append((target, reason))

    def retry(self) -> None:
        """Retrying is never a transition; an uncertain effect is reconciled instead."""
        if self._state is EffectState.UNCERTAIN:
            raise IllegalTransition("an uncertain effect is reconciled by status query, never retried")
        raise IllegalTransition(
            f"retry is not a transition from {self._state.value}; submit a new governed request"
        )
