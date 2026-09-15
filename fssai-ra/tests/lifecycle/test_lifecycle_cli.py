"""``fssaira <stage>`` exits 0 only when every gate passes, and writes its artifact."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from fssaira import falsification
from fssaira.cli import main

ROOT = Path(__file__).resolve().parents[2]


def _frame(tmp_path: Path, owner: str) -> Path:
    path = tmp_path / "frame.yaml"
    path.write_text(yaml.safe_dump({
        "capability": "benefit decision", "protected_asset": "an applicant's entitlement",
        "harm": "a wrongful denial", "accountable_owner": owner,
        "manual_fallback": "caseworker decision with appeal",
    }))
    return path


def test_frame_exit_codes_follow_the_gate(tmp_path, capsys):
    assert main(["frame", str(_frame(tmp_path, "benefit approver"))]) == 0
    assert "stage frame: PASS" in capsys.readouterr().out
    assert main(["frame", str(_frame(tmp_path, ""))]) == 1
    assert "accountable_owner" in capsys.readouterr().out


def test_contract_gate_writes_its_artifact_and_register(tmp_path, capsys):
    out = tmp_path / "contract.json"
    register = tmp_path / "claims_register.yaml"
    code = main(["contract", str(ROOT / "contract"), "--gate",
                 "--output", str(out), "--register-out", str(register)])
    assert "stage contract: PASS" in capsys.readouterr().out
    assert code == 0
    artifact = json.loads(out.read_text())
    assert artifact["passed"] is True
    assert yaml.safe_load(register.read_text())["counts"] == artifact["artifact"]["counts"]


def test_contract_without_gate_still_shows_the_contract(tmp_path, capsys):
    """The pre-existing command is unchanged: README documents `fssaira contract --output`."""
    out = tmp_path / "contract.json"
    assert main(["contract", str(ROOT / "contract"), "--output", str(out)]) == 0
    capsys.readouterr()
    payload = json.loads(out.read_text())
    assert set(payload) == {"requirements", "count"}
    assert payload["count"] == len(payload["requirements"]) > 0


def test_pack_passes_on_the_repository_and_refuses_the_unfilled_template(capsys):
    assert main(["pack", "--root", str(ROOT)]) == 0
    assert "stage pack: PASS" in capsys.readouterr().out
    assert main(["pack", "--root", str(ROOT), str(ROOT / "packs" / "template.pack.yaml")]) == 1
    capsys.readouterr()


def test_bind_passes_on_the_repository(capsys):
    assert main(["bind", "--root", str(ROOT), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["gates"][0]["gate"] == "no_model_holds_a_key"


def test_operate_needs_a_passing_falsification_of_the_current_configuration(tmp_path, capsys):
    first = falsification.FALSIFIERS[0].id
    artifact = tmp_path / "falsify.json"
    assert main(["falsify", "--root", str(ROOT), "--only", first, "--no-ablation",
                 "--out", str(artifact)]) == 0
    capsys.readouterr()

    assert main(["operate", "--root", str(ROOT)]) == 1
    assert "fssaira falsify" in capsys.readouterr().out

    assert main(["operate", "--root", str(ROOT), "--falsify-artifact", str(artifact)]) == 0
    out = capsys.readouterr().out
    assert "stage operate: PASS" in out
    assert "[NOT RUN] reconciliation_clear" in out


def test_falsify_reports_attempts_and_a_positive_control(capsys):
    first = falsification.FALSIFIERS[0].id
    assert main(["falsify", "--root", str(ROOT), "--only", first, "--no-ablation", "--json"]) == 0
    [gate] = json.loads(capsys.readouterr().out)["gates"]
    assert gate["observed"]["thesis_counterexamples"] == 0
    assert gate["observed"]["positive_control_violations"] > 0
