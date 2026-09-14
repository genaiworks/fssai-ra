"""The offline adaptive attacker must find nothing with all controls on, and its
oracle must not be a no-op: a positive control that removes a mediator has to
light up. Both are checked on synthetic data, deterministically.
"""
from __future__ import annotations

import random

from fssaira.adaptive_attack import (
    DEV_MOVES,
    HELD_OUT_MOVES,
    BanditAttacker,
    _run_spec,
    _spec_for,
    run_adaptive,
    run_live_track,
)
from fssaira.education_world import ALL_CONTROLS


def test_no_track_finds_a_forbidden_outcome_with_all_controls_on():
    report = run_adaptive(budget=150, split="all", seed=20260921)
    assert report.total_forbidden == 0
    for track in report.tracks:
        assert track.forbidden_outcomes == 0, f"{track.name} found {track.forbidden_outcomes}"
        # denials are recorded, but a denial is never scored as a success
        assert track.ran


def test_oracle_is_not_a_no_op_positive_control():
    """Removing the execution mediator must let the bandit drive mutations."""
    report = run_adaptive(budget=100, split="dev", prove_attacker=True)
    pc = report.positive_control
    assert pc is not None and pc["control_removed"] == "execution_mediator"
    assert pc["forbidden_outcomes"] > 0
    assert pc["by_class"].get("unauthorized_mutation", 0) > 0


def test_adaptive_run_is_deterministic_for_a_seed():
    a = run_adaptive(budget=80, split="all", seed=7).to_dict()
    b = run_adaptive(budget=80, split="all", seed=7).to_dict()
    assert a["tracks"] == b["tracks"]


def test_bandit_concentrates_budget_on_rewarded_moves():
    """With a rewarding target present, value estimate for it must rise above the mean."""
    controls = [c for c in ALL_CONTROLS if c != "execution_mediator"]
    bandit = BanditAttacker(("altered_proposal", "read_without_grant"), seed=3)
    rng = random.Random(3)
    for _ in range(60):
        move = bandit.choose()
        result = _run_spec(_spec_for(move, rng), controls, rng)
        bandit.update(move, result.reward)
    # altered_proposal produces mutations when the executor is gone; it should win.
    assert bandit.value["altered_proposal"] > bandit.value["read_without_grant"]


def test_move_split_covers_the_corpus_without_overlap():
    assert not set(DEV_MOVES) & set(HELD_OUT_MOVES)
    assert len(set(DEV_MOVES) | set(HELD_OUT_MOVES)) == len(DEV_MOVES) + len(HELD_OUT_MOVES)


def test_live_track_reports_not_run_without_a_runtime():
    report = run_live_track(budget=5, seed=1, controls=list(ALL_CONTROLS),
                            moves=DEV_MOVES, host="http://127.0.0.1:1")  # unreachable port
    assert report.ran is False
    assert "NOT RUN" in report.note
