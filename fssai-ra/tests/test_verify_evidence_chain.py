"""The Spark evidence verifier's checks, run on plain rows without Spark."""
import importlib.util
import json
from pathlib import Path

from fssaira.evidence import EvidenceLedger
from fssaira.evidence_notary import EvidenceNotary

JOBS = Path(__file__).resolve().parents[1] / "jobs"
spec = importlib.util.spec_from_file_location("verify_evidence_chain", JOBS / "verify_evidence_chain.py")
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)


def archived(count):
    ledger = EvidenceLedger("token")
    for index in range(count):
        ledger.append("decision", {"request_id": f"r-{index}"}, token="token")
    rows = [
        {"seq": r.seq, "ts": r.ts, "kind": r.kind,
         "payload_json": json.dumps(r.payload, sort_keys=True), "prev_hash": r.prev_hash,
         "hash": r.hash}
        for r in ledger
    ]
    return ledger, rows


def signed(ledger):
    notary = EvidenceNotary()
    checkpoint = notary.checkpoint(list(ledger)).to_dict()
    keys = {key_id: key.hex() for key_id, key in notary.public_keys.items()}
    return checkpoint, keys


def test_intact_archive_passes_with_checkpoint():
    ledger, rows = archived(4)
    checkpoint, keys = signed(ledger)
    verdict = job.verify_rows(rows, checkpoint=checkpoint, public_keys=keys)
    assert verdict["verdict"] == "INTACT" and verdict["tail_truncation_checked"]


def test_deleted_tail_passes_internal_checks_but_fails_checkpoint():
    ledger, rows = archived(4)
    checkpoint, keys = signed(ledger)
    internal = job.verify_rows(rows[:2])
    assert internal["verdict"] == "INTACT"  # the reason a checkpoint is needed
    verdict = job.verify_rows(rows[:2], checkpoint=checkpoint, public_keys=keys)
    assert verdict["verdict"] == "COMPROMISED"
    assert verdict["checkpoint"]["code"] == "LEDGER_TRUNCATED"


def test_duplicate_archive_rows_are_reported():
    _ledger, rows = archived(3)
    verdict = job.verify_rows(rows + [dict(rows[1])])
    assert verdict["duplicate_seqs"] == [1] and verdict["verdict"] == "COMPROMISED"


def test_altered_payload_is_reported():
    _ledger, rows = archived(3)
    rows[1] = {**rows[1], "payload_json": json.dumps({"request_id": "forged"})}
    verdict = job.verify_rows(rows)
    assert verdict["altered_records"] == [1] and verdict["verdict"] == "COMPROMISED"


def test_checkpoint_needs_the_whole_chain():
    ledger, rows = archived(2)
    checkpoint, keys = signed(ledger)
    import pytest
    with pytest.raises(ValueError):
        job.verify_rows(rows[1:], since_seq=1, checkpoint=checkpoint, public_keys=keys)
