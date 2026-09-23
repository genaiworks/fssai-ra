"""Run the documented SQL/privacy lab and independently check its artifacts."""
import hashlib
import importlib.util
import json
from pathlib import Path

from fssaira.evidence import EvidenceRecord
from fssaira.evidence_notary import Checkpoint, verify_against_checkpoint

APP = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pipeline_lab", APP / "scripts/pipeline_walkthrough.py")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


def test_sql_lab_and_independent_checkpoint_verification(tmp_path):
    output = tmp_path / "lab"
    report = lab.run(output)
    assert report["verified"] and report["encrypted_rows"] == 4
    def load(name):
        return json.loads((output / name).read_text())
    released = load("04-output.json")
    assert hashlib.sha256(released["released_content"].encode()).hexdigest() == released["sha256"]
    ledger = [EvidenceRecord(**r) for r in load("05-evidence.json")]
    checkpoint = Checkpoint(**load("06-checkpoint.json"))
    keys = {k: bytes.fromhex(v) for k, v in load("07-public-keys.json").items()}
    assert verify_against_checkpoint(ledger, checkpoint, keys).valid
    assert not verify_against_checkpoint(ledger[:-1], checkpoint, keys).valid
    assert "Alice Example" not in (output / "03-model-values.json").read_text()
    assert b"Alice Example" not in (output / "records.sqlite3").read_bytes()
    import pytest
    with pytest.raises(FileExistsError):
        lab.run(output)
