"""Check that the lab teaches observable disclosure and catches a fake refusal."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workshop.check import CASES, evaluate, load  # noqa: E402


@pytest.mark.parametrize("case", CASES)
def test_workshop_solution(case):
    assert evaluate(load("solution"), case).passed


@pytest.mark.parametrize("name", ("starter", "step1", "step2"))
def test_incomplete_exercises_actually_leak(name):
    result = evaluate(load(name), "secret_public")
    assert not result.passed
    assert result.released == ["SYNTHETIC-WORKSHOP-SECRET"]


def test_unknown_recipient_denied_and_benign_work_preserved():
    for name in ("starter", "step1", "step2", "solution"):
        assert evaluate(load(name), "metrics").passed
        assert evaluate(load(name), "secret_security").passed


def test_a_refusal_string_is_not_a_release_gate():
    solution = load("solution")
    mutant = SimpleNamespace(read_secret=solution.read_secret, handoff=solution.handoff,
                             publish=lambda *a, **k: "DENIED")
    result = evaluate(mutant, "secret_public")
    assert not result.passed and result.released == ["DENIED"]
