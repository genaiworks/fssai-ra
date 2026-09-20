"""Explicit effect lifecycle; uncertainty is a reconciliation obligation, never a retry."""
from enum import Enum


class EffectState(str, Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    DISPATCHED = 'dispatched'
    COMMITTED = 'committed'
    UNCERTAIN = 'uncertain'
    RECONCILED = 'reconciled'
    COMPENSATED = 'compensated'
    DENIED = 'denied'
    EXPIRED = 'expired'


_TRANSITIONS = {
    EffectState.PENDING: {EffectState.APPROVED, EffectState.DENIED, EffectState.EXPIRED},
    EffectState.APPROVED: {EffectState.DISPATCHED, EffectState.DENIED, EffectState.EXPIRED},
    EffectState.DISPATCHED: {EffectState.COMMITTED, EffectState.UNCERTAIN},
    EffectState.UNCERTAIN: {EffectState.RECONCILED},
    EffectState.COMMITTED: {EffectState.COMPENSATED},
    EffectState.RECONCILED: {EffectState.COMPENSATED},
}


def transition(current: EffectState, target: EffectState, *, evidence: str = '') -> EffectState:
    if target not in _TRANSITIONS.get(current, set()):
        raise ValueError('illegal effect state transition')
    if target in {EffectState.RECONCILED, EffectState.COMPENSATED} and not evidence.strip():
        raise ValueError('recovery requires independently obtained outcome evidence')
    return target
