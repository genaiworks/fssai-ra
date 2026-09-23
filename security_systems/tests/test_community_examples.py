"""The exported teaching examples must catch observable harm, not arbitrary errors."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
from effect_oracle import demonstrate, observe_attempt  # noqa: E402
from replay_boundary import demonstrate as replay_demo  # noqa: E402


def test_effect_oracle_detects_a_write_followed_by_refusal():
    rows = {row["case"]: row for row in demonstrate()}
    assert all(row["experiment_passed"] for row in rows.values())
    assert rows["write_then_reject"]["refused"]
    assert rows["write_then_reject"]["harmful_effect"]
    assert not rows["reject_before_write"]["harmful_effect"]


def test_broken_attack_does_not_count_as_containment():
    def broken():
        raise ValueError("misconfigured attack")
    with pytest.raises(ValueError):
        observe_attempt(broken, lambda: {}, lambda before, after: False)


def test_cached_receipt_demo_checks_release_and_single_execution():
    result = replay_demo()
    assert result["experiment_passed"]
    assert result["deploy_effects"] == 1
