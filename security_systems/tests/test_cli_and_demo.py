"""The command line and the talk run end to end, on every world, and fail loudly when they should."""
import json
from pathlib import Path

import pytest

from trustkernel.cli import main
from trustkernel.world import WorldSpec, available_worlds

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.slow
@pytest.mark.parametrize("world", available_worlds())
def test_the_whole_talk_runs_on_every_world(world, capsys):
    assert main(["demo", "--world", world, "--no-color"]) == 0
    out = capsys.readouterr().out
    assert out.count("SCENE ") == 7
    # Scene 2 must show both halves: the denial, then the leak once the control is removed.
    assert "RECIPIENT_CLASS_NOT_CLEARED" in out and "ATTACK SUCCEEDS" in out
    assert "10 of 10 caught" in out and " 2 of 10 caught" in out
    assert "MUTATIONS=1" in out and "LEDGER_HISTORY_REWRITTEN" in out


def test_the_headline_leak_is_the_real_credential_and_only_after_ablation(capsys):
    main(["demo", "--scene", "2", "--no-color"])
    out = capsys.readouterr().out
    password = "SYNTHETIC-PAY-DB-PW-7f3a"
    deny, leak = out.index("RECIPIENT_CLASS_NOT_CLEARED"), out.index(password)
    assert deny < leak and out.count(password) == 1


def test_pack_check_accepts_real_packs_and_rejects_malicious_ones(capsys):
    for world in available_worlds():
        spec = WorldSpec.load(world)
        assert main(["pack-check", str(spec.pack_path)]) == 0
        assert main(["pack-check", str(spec.malicious_pack_path)]) == 1
    assert "REJECTED" in capsys.readouterr().out


def test_json_output_is_machine_readable(capsys):
    assert main(["falsify", "--only", "F01", "--json"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body[0]["id"] == "F01" and body[0]["result"] == "HELD" and body[0]["world"] == "devtools"


def test_an_unknown_world_is_a_clean_error(capsys):
    assert main(["falsify", "--world", "no-such-world"]) == 2
    assert "known: " in capsys.readouterr().err


@pytest.mark.slow
@pytest.mark.parametrize("world", available_worlds())
def test_committed_evidence_is_what_the_code_produces(world, tmp_path, capsys):
    """Every figure quoted anywhere comes from evidence/<world>.json, and that file is
    regenerated, never edited. If this fails, run `make evidence` and review the diff."""
    fresh = tmp_path / f"{world}.json"
    assert main(["evidence", "--world", world, "--out", str(fresh)]) == 0
    assert fresh.read_text() == (ROOT / "evidence" / f"{world}.json").read_text()
