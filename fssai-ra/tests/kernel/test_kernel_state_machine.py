"""Consequential effects move only along declared transitions, with evidence.

The reference table below is written independently of the implementation; the
exhaustive test compares all 81 ordered state pairs against it.
"""
from __future__ import annotations

import itertools

import pytest

from fssaira.evidence import EvidenceError, EvidenceLedger
from fssaira.kernel.state_machine import (
    TERMINAL,
    EffectRecord,
    EffectState,
    IllegalTransition,
)

S = EffectState
REFERENCE = {
    (S.PENDING, S.APPROVED), (S.PENDING, S.DENIED), (S.PENDING, S.EXPIRED),
    (S.APPROVED, S.DISPATCHED), (S.APPROVED, S.DENIED), (S.APPROVED, S.EXPIRED),
    (S.DISPATCHED, S.COMMITTED), (S.DISPATCHED, S.UNCERTAIN), (S.DISPATCHED, S.DENIED),
    (S.UNCERTAIN, S.RECONCILED), (S.UNCERTAIN, S.COMPENSATED),
    (S.COMMITTED, S.COMPENSATED), (S.RECONCILED, S.COMPENSATED),
}
TOKEN = "evidence-write"


def _drive(record: EffectRecord, *path: EffectState) -> None:
    for state in path:
        auth = "comp-approval-1" if state is S.COMPENSATED else None
        record.transition(state, reason=f"to {state.value}", authorization=auth)


def test_the_nine_states():
    assert {s.value for s in EffectState} == {
        "pending", "approved", "dispatched", "committed", "uncertain",
        "reconciled", "compensated", "denied", "expired",
    }
    assert {S.DENIED, S.EXPIRED, S.COMPENSATED} == TERMINAL


@pytest.mark.parametrize("source,target", list(itertools.product(EffectState, EffectState)))
def test_only_declared_transitions_are_legal(source, target):
    ledger = EvidenceLedger(TOKEN)
    record = EffectRecord.restore("req-1", source, ledger=ledger, token=TOKEN)
    auth = "comp-approval-1" if target is S.COMPENSATED else None
    if (source, target) in REFERENCE:
        record.transition(target, reason="test", authorization=auth)
        assert record.state is target
    else:
        with pytest.raises(IllegalTransition):
            record.transition(target, reason="test", authorization=auth)
        assert record.state is source


def test_happy_path_records_one_evidence_record_per_transition():
    ledger = EvidenceLedger(TOKEN)
    record = EffectRecord("req-1", ledger=ledger, token=TOKEN)
    _drive(record, S.APPROVED, S.DISPATCHED, S.COMMITTED)
    kinds = [(r.payload["from"], r.payload["to"]) for r in ledger.find("effect_transition")]
    assert kinds == [("pending", "approved"), ("approved", "dispatched"), ("dispatched", "committed")]
    assert ledger.verify()
    assert [s for s, _ in record.history] == [S.PENDING, S.APPROVED, S.DISPATCHED, S.COMMITTED]


def test_an_empty_ledger_still_receives_evidence():
    """An empty EvidenceLedger is falsy; the record must not treat it as absent."""
    ledger = EvidenceLedger(TOKEN)
    assert not ledger
    record = EffectRecord("req-1", ledger=ledger, token=TOKEN)
    record.transition(S.DENIED, reason="policy")
    assert len(ledger) == 1


def test_an_uncertain_irreversible_effect_is_never_retried():
    record = EffectRecord("req-1", irreversible_external=True)
    _drive(record, S.APPROVED, S.DISPATCHED, S.UNCERTAIN)
    with pytest.raises(IllegalTransition, match="uncertain"):
        record.transition(S.DISPATCHED, reason="retry")
    with pytest.raises(IllegalTransition, match="reconcil"):
        record.retry()


def test_compensation_requires_a_separate_authorization():
    record = EffectRecord("req-1")
    _drive(record, S.APPROVED, S.DISPATCHED)
    record.transition(S.COMMITTED, reason="done")
    with pytest.raises(IllegalTransition, match="authorization"):
        record.transition(S.COMPENSATED, reason="undo")
    record.transition(S.COMPENSATED, reason="undo", authorization="comp-approval-1")
    assert record.state is S.COMPENSATED


def test_compensation_cannot_reuse_the_original_approval():
    record = EffectRecord("req-1")
    record.transition(S.APPROVED, reason="ok", authorization="approval-7")
    _drive(record, S.DISPATCHED)
    record.transition(S.COMMITTED, reason="done")
    with pytest.raises(IllegalTransition, match="separate"):
        record.transition(S.COMPENSATED, reason="undo", authorization="approval-7")


def test_terminal_states_admit_nothing():
    for terminal in TERMINAL:
        record = EffectRecord.restore("req-1", terminal)
        for target in EffectState:
            with pytest.raises(IllegalTransition):
                record.transition(target, reason="x", authorization="a-new-one")


def test_evidence_failure_aborts_the_transition():
    ledger = EvidenceLedger(TOKEN)
    record = EffectRecord("req-1", ledger=ledger, token="wrong-token")
    with pytest.raises(EvidenceError):
        record.transition(S.APPROVED, reason="ok")
    assert record.state is S.PENDING
    assert len(ledger) == 0
