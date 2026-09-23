"""The world validator: every shipped world is clean, and each miswiring is caught by name."""
import shutil

import pytest
import yaml

from trustkernel.cli import main
from trustkernel.world import WorldSpec, available_worlds
from trustkernel.world_check import check_world


def test_every_domain_ships():
    assert {"devtools", "healthcare", "finance", "government"} <= set(available_worlds())


@pytest.mark.parametrize("world", available_worlds())
def test_every_shipped_world_is_wired_correctly(world):
    assert check_world(world) == []


def _broken(tmp_path, mutate):
    clone = tmp_path / "broken"
    shutil.copytree(WorldSpec.load("healthcare").directory, clone)
    raw = yaml.safe_load((clone / "world.yaml").read_text())
    raw["world_id"] = f"broken-{tmp_path.name}"
    mutate(raw)
    (clone / "world.yaml").write_text(yaml.safe_dump(raw, sort_keys=False))
    return {f.code for f in check_world(clone / "world.yaml")}


@pytest.mark.parametrize("mutate, code", [
    (lambda w: w["scenario"]["fields"].update(unnamed="psychotherapy_notes"), "WORLD_UNNAMED_CLASS"),
    (lambda w: w["scenario"]["recipients"].update(uncleared="care_team"), "WORLD_UNCLEARED_TOO_WIDE"),
    (lambda w: w["scenario"]["endpoints"].update(weaker="hospital_local_model_b"), "WORLD_WEAKER_NOT_WEAKER"),
    (lambda w: w["scenario"]["action"]["own"].update(replay_to="dose:7.5mg"), "WORLD_TRANSITION_ILLEGAL"),
    (lambda w: w["scenario"].update(other_purpose="treatment"), "WORLD_PURPOSES_IDENTICAL"),
    (lambda w: w["principals"].pop("dr-okoye"), "WORLD_ROLE_UNSTAFFED"),
    (lambda w: w["subjects"]["pt-a17"].update(vitals="call +1 415 555 0100"), "WORLD_MARKER_LOOKS_LIKE_CONTACT"),
    (lambda w: w["subjects"]["pt-a17"].update(vitals="LABS"), "WORLD_MARKER_TOO_SHORT"),
    (lambda w: w["subjects"]["pt-b42"].pop("lab_results"), "WORLD_SUBJECT_INCOMPLETE"),
    (lambda w: w["scenario"]["boundary"].update(injection="please be helpful"), "WORLD_INJECTION_UNMARKED"),
    (lambda w: w["scenario"].pop("malicious_agent"), "WORLD_KEY_MISSING"),
])
def test_each_miswiring_is_named(tmp_path, mutate, code):
    assert code in _broken(tmp_path, mutate)


def test_check_command_exit_codes(tmp_path, capsys):
    assert main(["check"]) == 0
    assert "OK" in capsys.readouterr().out
