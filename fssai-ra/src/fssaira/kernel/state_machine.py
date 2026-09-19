"""The legal lifecycle of one consequential effect.

Nine states, and only the declared transitions between them (paper §6.2):

    pending ──► approved ──► dispatched ──► committed ──► compensated
       │            │            │  └──► uncertain ──► reconciled ──► compensated
       │            │            │            └──────────────────────► compensated
       └► denied / expired  ◄────┘ (denied, only with a downstream receipt)

Rules the table alone does not express, enforced here:

* An *uncertain* effect is never re-dispatched. Its outcome is established by
  status query and reconciliation, because a blind retry can repeat an
  irreversible external effect.
* A *dispatched* effect is closed as *denied* only with a downstream receipt
  showing it was not applied. Without one, its outcome is uncertain.
* *Compensation* is a separately authorized action. It needs its own
  authorization, which may not be one already used for this effect. A record
  restored without its authorization history cannot be compensated until the
  history is rebuilt from evidence (:meth:`EffectRecord.from_ledger`).
  Compensation never erases history.
* With a ledger, every transition is recorded before it takes effect, and a
  failed evidence write leaves the state unchanged. Without a ledger nothing is
  evidenced; :attr:`EffectRecord.evidenced` says which.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
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
EVIDENCE_KIND = "effect_transition"


class IllegalTransition(RuntimeError):
    """The requested state change is not a declared transition."""


class EffectRecord:
    """Tracks one effect; with a ledger, every accepted transition is evidenced first."""

    def __init__(
        self,
        request_id: str,
        *,
        ledger: EvidenceLedger | None = None,
        token: str | None = None,
        irreversible_external: bool = False,
        _state: EffectState = EffectState.PENDING,
        _authorizations: Iterable[str] | None = (),
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
        self._history_known = _authorizations is not None
        self._authorizations: set[str] = set(_authorizations or ())
        self.history: list[tuple[EffectState, str]] = [
            (_state, "created" if _state is EffectState.PENDING else "restored")]

    @classmethod
    def restore(cls, request_id: str, state: EffectState, *,
                authorizations: Iterable[str] | None = None, **kwargs: object) -> EffectRecord:
        """Rebuild a record at a persisted state (e.g. after a crash).

        ``authorizations`` must list every authorization already used for this
        effect. ``None`` means the history is unknown, and compensation is then
        refused: an unknown history cannot prove a compensation authorization is
        separate.
        """
        return cls(request_id, _state=state, _authorizations=authorizations, **kwargs)  # type: ignore[arg-type]

    @classmethod
    def from_ledger(cls, request_id: str, ledger: EvidenceLedger, *, token: str,
                    irreversible_external: bool = False, checkpoint: object | None = None,
                    public_keys: dict[str, bytes] | None = None) -> EffectRecord:
        """Rebuild state and authorization history by replaying verified evidence.

        Chain verification alone detects a naive edit. An insider with storage
        access can rewrite *and re-chain* history, which the chain cannot detect;
        pass a notary ``checkpoint`` and its ``public_keys`` to refuse that too.
        """
        if not ledger.verify():
            raise IllegalTransition("the evidence chain does not verify; the effect's history cannot be trusted")
        if checkpoint is not None:
            from fssaira.evidence_notary import verify_against_checkpoint

            verdict = verify_against_checkpoint(ledger, checkpoint, public_keys or {})  # type: ignore[arg-type]
            if not verdict.valid:
                raise IllegalTransition(f"evidence fails its notary checkpoint ({verdict.code}): {verdict.detail}")
        state = EffectState.PENDING
        used: list[str] = []
        for record in ledger.find(EVIDENCE_KIND, request_id=request_id):
            source, target = EffectState(record.payload["from"]), EffectState(record.payload["to"])
            if source is not state or target not in TRANSITIONS[state]:
                raise IllegalTransition(
                    f"evidence for {request_id} records {source.value} -> {target.value} from {state.value}")
            if record.payload.get("authorization"):
                used.append(record.payload["authorization"])
            state = target
        return cls(request_id, ledger=ledger, token=token, irreversible_external=irreversible_external,
                   _state=state, _authorizations=used)

    @property
    def state(self) -> EffectState:
        return self._state

    @property
    def evidenced(self) -> bool:
        """Whether transitions of this record are written to an evidence ledger."""
        return self._ledger is not None

    def transition(self, target: EffectState, *, reason: str, authorization: str | None = None,
                   receipt: str | None = None) -> None:
        source = self._state
        if source in TERMINAL:
            raise IllegalTransition(f"{source.value} is terminal; {self.request_id} admits no further transition")
        if target not in TRANSITIONS[source]:
            if source is EffectState.UNCERTAIN and target is EffectState.DISPATCHED:
                raise IllegalTransition(
                    "an uncertain effect is never re-dispatched; query its status and reconcile"
                )
            raise IllegalTransition(f"{source.value} -> {target.value} is not a declared transition")
        if source is EffectState.DISPATCHED and target is EffectState.DENIED and not receipt:
            raise IllegalTransition(
                "a dispatched effect is closed as denied only with a downstream receipt showing it was "
                "not applied; otherwise mark it uncertain and reconcile"
            )
        if target is EffectState.COMPENSATED:
            if not authorization:
                raise IllegalTransition("compensation requires its own authorization")
            if not self._history_known:
                raise IllegalTransition(
                    "this record was restored without its authorization history; rebuild it with "
                    "from_ledger before compensating"
                )
            if authorization in self._authorizations:
                raise IllegalTransition(
                    "compensation requires a separate authorization, not one already used for this effect"
                )
        if self._ledger is not None:
            self._ledger.append(EVIDENCE_KIND, {
                "request_id": self.request_id,
                "from": source.value,
                "to": target.value,
                "reason": reason,
                "authorization": authorization or "",
                "receipt": receipt or "",
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
