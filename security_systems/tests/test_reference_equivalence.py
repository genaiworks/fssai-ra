"""The generalisation changed nothing: the education world reproduces the reference exactly.

``tests/reference/education_reference.json`` was recorded from the reference
implementation *before* its cast was lifted out of Python and into ``world.yaml``.
Every falsifier verdict and denial code, every ablation row, all 33 delegation outcomes,
the red team broken down by move, and every adaptive-attacker track must match.

This is the test that licenses the claim "a new domain is configuration, not a fork".
If a refactor of :mod:`trustkernel.world` moves any figure here, the refactor is wrong.
The world also runs on different key material from the reference, so a pass also shows
the figures do not depend on which keys were used.
"""
import json
from pathlib import Path

import pytest

from trustkernel.adaptive_attack import run_adaptive
from trustkernel.delegation_eval import ablate_delegation, run_delegation_suite
from trustkernel.falsification import run_ablation, run_falsifiers
from trustkernel.redteam import GrammarAttacker, run_redteam

REFERENCE = json.loads((Path(__file__).parent / "reference" / "education_reference.json").read_text())
WORLD = "education"


def test_falsifiers_match_the_reference_attempt_by_attempt():
    ours = [{"id": f.id, "violations": f.violations, "result": "HELD" if f.held else "VIOLATED",
             "attempts": [{"violated": a.violated, "code": a.code} for a in f.attempts]}
            for f in run_falsifiers(world=WORLD)]
    assert ours == REFERENCE["falsifiers"]


@pytest.mark.slow
def test_ablation_matches_the_reference_row_by_row():
    keys = ("falsifier", "control", "mediator", "enabled_violations", "disabled_violations",
            "restored_violations", "load_bearing")
    ours = [{k: row.to_dict()[k] for k in keys} for row in run_ablation(world=WORLD)]
    assert ours == REFERENCE["ablation"]


def test_delegation_suite_matches_the_reference():
    report = run_delegation_suite(world=WORLD).to_dict()
    assert report["arms"] == REFERENCE["delegation"]["arms"]
    assert [{k: o[k] for k in ("arm", "scenario", "contained", "code")} for o in report["outcomes"]] \
        == REFERENCE["delegation"]["outcomes"]
    keys = ("control", "scenario", "load_bearing", "with_control", "without_control")
    assert [{k: r[k] for k in keys} for r in ablate_delegation(world=WORLD)] == REFERENCE["delegation_ablation"]


@pytest.mark.slow
def test_red_team_matches_the_reference_move_by_move():
    held = run_redteam(GrammarAttacker(WORLD, seed=1125), attempts=300, seed=7)
    assert {"violations": held.violations, "by_move": held.by_move} == REFERENCE["redteam"]
    weakened = run_redteam(GrammarAttacker(WORLD, seed=1125), attempts=300, seed=7, remove=["execution_mediator"])
    assert {"violations": weakened.violations, "by_move": weakened.by_move} \
        == REFERENCE["redteam_without_execution_mediator"]


@pytest.mark.slow
def test_adaptive_attacker_matches_the_reference():
    report = run_adaptive(world=WORLD, budget=60, seed=20260921, prove_attacker=True).to_dict()
    keys = ("attacker", "episodes", "forbidden_outcomes", "by_class", "denials_observed")
    assert [{k: t[k] for k in keys} for t in report["tracks"]] == REFERENCE["adaptive"]["tracks"]
    positive = report["positive_control"]
    assert {k: positive[k] for k in ("control_removed", "forbidden_outcomes", "by_class")} \
        == REFERENCE["adaptive"]["positive_control"]
