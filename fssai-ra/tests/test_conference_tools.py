"""The conference tools a presenter and a student actually run: red team, CLI, lab, demo."""
import importlib.util
import json
from pathlib import Path

from fssaira.cli import main
from fssaira.redteam import MOVES, GrammarAttacker, run_redteam

ROOT = Path(__file__).resolve().parents[1]


def _script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_redteam_finds_nothing_with_controls_and_something_without():
    held = run_redteam(GrammarAttacker(seed=3), attempts=60)
    assert held.attempts == 60 and held.violations == 0
    assert set(held.by_move) <= set(MOVES)
    broken = run_redteam(GrammarAttacker(seed=3), attempts=60, remove=["context_gate"])
    assert broken.violations > 0 and broken.examples


def test_cli_falsify_and_pack_check_report_real_outcomes(capsys):
    assert main(["conference", "falsify", "F19", "--json"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body[0]["id"] == "F19" and body[0]["result"] == "HELD"
    assert main(["conference", "pack-check", str(ROOT / "conference/attacks/malicious-domain-pack.yaml")]) == 1
    assert main(["conference", "pack-check", str(ROOT / "conference/education/governed-learning-pack.yaml")]) == 0


def test_lab_runs_attacks_live_and_refuses_unknown_controls():
    lab = _script("conference_lab")
    assert len(lab.catalogue()) >= 20
    blocked = lab.run_attack("F02", [])
    succeeded = lab.run_attack("F02", ["context_gate"])
    assert not blocked["violated"] and succeeded["violated"]
    try:
        lab.run_attack("F02", ["no_such_control"])
    except ValueError:
        pass
    else:
        raise AssertionError("an unknown control must be refused")
    assert lab.run_trace("malicious")["outcome"].startswith("DENIED")


def test_the_lab_page_is_offline_and_theme_aware():
    page = (ROOT / "conference/education/lab.html").read_text(encoding="utf-8")
    assert "<title>" in page and "prefers-color-scheme" in page and "/*RECORDED*/null" in page
    assert "http://" not in page.replace("http://127.0.0.1", "") and "https://" not in page


def test_every_conference_demo_runs_to_completion(capsys):
    demo = _script("conference_demo")
    stage = demo.Stage(0.0)
    for _number, run in sorted(demo.DEMOS.items()):
        run(stage)
    out = capsys.readouterr().out
    assert "ATTACK SUCCEEDS" in out and "COMPLETED with evidence" in out and "UNMEDIATED" not in out
