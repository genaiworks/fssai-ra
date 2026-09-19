"""Review findings H5, M1 and M7 on the effect state machine, as regression tests."""
from __future__ import annotations

from dataclasses import replace

import pytest

from fssaira.evidence import EvidenceLedger
from fssaira.evidence_notary import EvidenceNotary, rewrite_history
from fssaira.kernel.state_machine import EffectRecord, EffectState, IllegalTransition

S = EffectState
TOKEN = "evidence-write"


def _committed(ledger: EvidenceLedger) -> EffectRecord:
    record = EffectRecord("r", ledger=ledger, token=TOKEN)
    record.transition(S.APPROVED, reason="ok", authorization="approval-7")
    record.transition(S.DISPATCHED, reason="send")
    record.transition(S.COMMITTED, reason="done")
    return record


def test_h5_a_restore_without_history_cannot_reuse_the_original_approval():
    """The exact reviewer scenario: approve with approval-7, commit, restore, compensate with approval-7."""
    _committed(EvidenceLedger(TOKEN))
    restored = EffectRecord.restore("r", S.COMMITTED)
    with pytest.raises(IllegalTransition, match="authorization history"):
        restored.transition(S.COMPENSATED, reason="undo", authorization="approval-7")
    with pytest.raises(IllegalTransition, match="authorization history"):
        restored.transition(S.COMPENSATED, reason="undo", authorization="a-genuinely-new-one")


def test_h5_rebuilding_from_evidence_restores_state_and_blocks_reuse():
    ledger = EvidenceLedger(TOKEN)
    _committed(ledger)
    rebuilt = EffectRecord.from_ledger("r", ledger, token=TOKEN)
    assert rebuilt.state is S.COMMITTED
    with pytest.raises(IllegalTransition, match="separate"):
        rebuilt.transition(S.COMPENSATED, reason="undo", authorization="approval-7")
    rebuilt.transition(S.COMPENSATED, reason="undo", authorization="compensation-1")
    assert rebuilt.state is S.COMPENSATED


def test_h5_an_explicit_history_is_honoured():
    restored = EffectRecord.restore("r", S.COMMITTED, authorizations=["approval-7"])
    with pytest.raises(IllegalTransition, match="separate"):
        restored.transition(S.COMPENSATED, reason="undo", authorization="approval-7")


_ERASED_APPROVAL = {"request_id": "r", "from": "pending", "to": "approved", "reason": "ok",
                   "authorization": "", "receipt": "", "irreversible_external": False}


def test_h5_a_naively_edited_chain_cannot_be_replayed():
    ledger = EvidenceLedger(TOKEN)
    _committed(ledger)
    first = ledger._records[0]
    ledger._records[0] = replace(first, payload=_ERASED_APPROVAL)  # edited without re-chaining
    with pytest.raises(IllegalTransition, match="does not verify"):
        EffectRecord.from_ledger("r", ledger, token=TOKEN)


def test_h5_an_insider_re_chain_is_refused_only_with_a_notary_checkpoint():
    """Erasing approval-7 from history would let it be reused; the chain alone cannot see a re-chain."""
    ledger = EvidenceLedger(TOKEN)
    _committed(ledger)
    notary = EvidenceNotary()
    checkpoint = notary.checkpoint(ledger)
    rewrite_history(ledger, 0, _ERASED_APPROVAL)

    rebuilt = EffectRecord.from_ledger("r", ledger, token=TOKEN)  # the documented limit of the chain
    rebuilt.transition(S.COMPENSATED, reason="undo", authorization="approval-7")

    with pytest.raises(IllegalTransition, match="notary checkpoint"):
        EffectRecord.from_ledger("r", ledger, token=TOKEN, checkpoint=checkpoint, public_keys=notary.public_keys)


def test_h5_an_untampered_ledger_passes_its_checkpoint():
    ledger = EvidenceLedger(TOKEN)
    _committed(ledger)
    notary = EvidenceNotary()
    checkpoint = notary.checkpoint(ledger)
    rebuilt = EffectRecord.from_ledger("r", ledger, token=TOKEN, checkpoint=checkpoint,
                                       public_keys=notary.public_keys)
    assert rebuilt.state is S.COMMITTED


def test_m7_a_dispatched_effect_is_denied_only_with_a_downstream_receipt():
    record = EffectRecord("r")
    record.transition(S.APPROVED, reason="ok")
    record.transition(S.DISPATCHED, reason="send")
    with pytest.raises(IllegalTransition, match="receipt"):
        record.transition(S.DENIED, reason="timed out, probably fine")
    record.transition(S.DENIED, reason="refused downstream", receipt="downstream-refusal-42")
    assert record.state is S.DENIED


def test_m1_evidenced_reports_whether_transitions_are_recorded():
    assert EffectRecord("r", ledger=EvidenceLedger(TOKEN), token=TOKEN).evidenced
    assert not EffectRecord("r").evidenced
