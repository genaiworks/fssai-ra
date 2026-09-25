"""An out-of-process witness: a compromised enforcer cannot get a rewritten past co-signed."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fssaira.evidence import EvidenceLedger
from fssaira.evidence_notary import EvidenceNotary, rewrite_history
from fssaira.iceberg_backend import archive_evidence
from fssaira.small_data import SqliteArchiveStore
from fssaira.witness import CheckpointWitness, WitnessRefused, verify_cosignature

TOKEN = "witness-test"
ROOT = Path(__file__).resolve().parents[1]


def rows(records, start=0):
    return [{"seq": r.seq, "ts": r.ts, "kind": r.kind,
             "payload_json": json.dumps(r.payload, sort_keys=True),
             "prev_hash": r.prev_hash, "hash": r.hash} for r in list(records)[start:]]


def grow(ledger, count, prefix="r"):
    start = len(ledger)
    for index in range(start, start + count):
        ledger.append("decision", {"request_id": f"{prefix}-{index}"}, token=TOKEN)
    return ledger


@pytest.fixture
def setup(tmp_path):
    notary = EvidenceNotary(seed=b"n" * 32)
    witness = CheckpointWitness(tmp_path / "witness", notary_keys=notary.public_keys,
                                seed=b"w" * 32)
    return notary, witness, grow(EvidenceLedger(TOKEN), 3)


def test_the_first_checkpoint_is_verified_from_genesis_when_records_are_given(setup):
    notary, witness, ledger = setup
    checkpoint = notary.checkpoint(ledger)
    cosigned = witness.cosign(checkpoint, rows(ledger))
    assert cosigned.first_seen == "genesis-verified"
    assert verify_cosignature(checkpoint, cosigned, witness.public_keys) == (True, "COSIGNED")
    # The same count and head again is consistent, and is co-signed again.
    assert witness.cosign(notary.checkpoint(ledger)).first_seen == "extension"


def test_without_records_the_first_checkpoint_is_trusted_on_first_use_and_says_so(setup):
    notary, witness, ledger = setup
    assert witness.cosign(notary.checkpoint(ledger)).first_seen == "trusted-on-first-use"


def test_growth_is_cosigned_only_with_records_that_chain_from_the_witnessed_head(setup):
    notary, witness, ledger = setup
    witness.cosign(notary.checkpoint(ledger), rows(ledger))
    grow(ledger, 2)
    with pytest.raises(WitnessRefused) as refused:
        witness.cosign(notary.checkpoint(ledger))
    assert refused.value.code == "WITNESS_EXTENSION_REQUIRED"
    checkpoint = notary.checkpoint(ledger)
    cosigned = witness.cosign(checkpoint, rows(ledger, 3))
    assert (cosigned.count, cosigned.first_seen) == (5, "extension")
    assert verify_cosignature(checkpoint, cosigned, witness.public_keys) == (True, "COSIGNED")


def test_an_enforcer_holding_the_notary_key_cannot_get_a_rewritten_past_cosigned(setup):
    """The attack the witness exists for: rewrite an old record, recompute, sign it."""
    notary, witness, ledger = setup
    witness.cosign(notary.checkpoint(ledger), rows(ledger))
    rewrite_history(ledger, 1, {"request_id": "forged"})
    assert ledger.verify()  # internally consistent: the chain alone cannot tell

    with pytest.raises(WitnessRefused) as fork:
        witness.cosign(notary.checkpoint(ledger))  # same length, different head
    assert fork.value.code == "WITNESS_FORK"

    grow(ledger, 2, prefix="after")
    with pytest.raises(WitnessRefused) as longer:
        witness.cosign(notary.checkpoint(ledger), rows(ledger, 3))  # longer, rewritten chain
    assert longer.value.code == "WITNESS_INCONSISTENT"


def test_a_truncated_ledger_is_a_rollback(setup):
    notary, witness, ledger = setup
    witness.cosign(notary.checkpoint(ledger), rows(ledger))
    shorter = EvidenceLedger(TOKEN)
    for record in list(ledger)[:2]:
        shorter.append(record.kind, record.payload, token=TOKEN)
    with pytest.raises(WitnessRefused) as refused:
        witness.cosign(notary.checkpoint(shorter))
    assert refused.value.code == "WITNESS_ROLLBACK"


def test_a_checkpoint_from_an_untrusted_notary_is_refused(setup):
    _notary, witness, ledger = setup
    impostor = EvidenceNotary(seed=b"x" * 32)
    with pytest.raises(WitnessRefused) as refused:
        witness.cosign(impostor.checkpoint(ledger))
    assert refused.value.code == "WITNESS_NOTARY_UNTRUSTED"


def test_a_cosignature_vouches_for_exactly_one_checkpoint(setup):
    notary, witness, ledger = setup
    first = notary.checkpoint(ledger)
    cosigned = witness.cosign(first, rows(ledger))
    grow(ledger, 1)
    assert verify_cosignature(notary.checkpoint(ledger), cosigned, witness.public_keys) == \
        (False, "WITNESS_MISMATCH")


def test_witnessed_state_survives_a_restart(setup, tmp_path):
    notary, witness, ledger = setup
    witness.cosign(notary.checkpoint(ledger), rows(ledger))
    again = CheckpointWitness(tmp_path / "witness", notary_keys=notary.public_keys, seed=b"w" * 32)
    rewrite_history(ledger, 0, {"request_id": "forged"})
    with pytest.raises(WitnessRefused) as refused:
        again.cosign(notary.checkpoint(ledger))
    assert refused.value.code == "WITNESS_FORK"
    log = (tmp_path / "witness" / "cosignatures.jsonl").read_text().splitlines()
    assert len(log) == 1


def test_the_witness_runs_as_its_own_process_with_its_own_key(tmp_path):
    """The CLI is the deployment shape: a separate process reading the archive."""
    notary = EvidenceNotary(seed=b"n" * 32)
    ledger = grow(EvidenceLedger(TOKEN), 4)
    archive = SqliteArchiveStore(tmp_path / "archive.sqlite3")
    archive_evidence(ledger, archive)
    archive.close()
    key = tmp_path / "witness.key"
    key.write_text(os.urandom(32).hex())
    key.chmod(0o600)
    notary_keys = tmp_path / "notary-keys.json"
    notary_keys.write_text(json.dumps({k: v.hex() for k, v in notary.public_keys.items()}))

    def cosign(checkpoint):
        path = tmp_path / "checkpoint.json"
        path.write_text(json.dumps(checkpoint.to_dict()))
        out = tmp_path / "result.json"
        run = subprocess.run(
            [sys.executable, "-m", "fssaira.cli", "witness", "cosign", "--dir", str(tmp_path / "w"),
             "--key-file", str(key), "--notary-keys", str(notary_keys),
             "--checkpoint", str(path), "--archive", str(tmp_path / "archive.sqlite3"),
             "--output", str(out)],
            cwd=ROOT, capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
        return run.returncode, json.loads(out.read_text())

    code, result = cosign(notary.checkpoint(ledger))
    assert code == 0 and result["cosignature"]["first_seen"] == "genesis-verified"
    rewrite_history(ledger, 2, {"request_id": "forged"})
    code, result = cosign(notary.checkpoint(ledger))
    assert (code, result["code"]) == (2, "WITNESS_FORK")
