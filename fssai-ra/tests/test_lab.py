"""The lab must not tell a room to run a command that does not exist.

A facilitator discovers a broken command in front of twenty people, on conference
wifi, with no way to debug it. That is the worst possible place to find drift, so
every command the lab prints is checked against the real parser and the real
scripts directory.
"""
import re
from pathlib import Path

import pytest

from fssaira.cli import build_parser

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "docs" / "LAB.md"


@pytest.fixture(scope="module")
def lab() -> str:
    assert LAB.exists(), f"{LAB} is missing"
    return LAB.read_text(encoding="utf-8")


def _subcommands() -> set[str]:
    actions = [a for a in build_parser()._actions if getattr(a, "choices", None)]
    return set(actions[0].choices) if actions else set()


def test_every_fssaira_subcommand_the_lab_cites_exists(lab):
    cited = set(re.findall(r"^\s*fssaira ([a-z][a-z-]*)", lab, re.M))

    assert cited, "the lab should show some commands"
    unknown = sorted(cited - _subcommands())
    assert not unknown, f"the lab cites commands that do not exist: {unknown}"


def test_every_script_the_lab_cites_exists(lab):
    cited = set(re.findall(r"python (scripts/[\w./-]+\.py)", lab))

    assert cited, "the lab should show some scripts"
    missing = sorted(path for path in cited if not (ROOT / path).exists())
    assert not missing, f"the lab cites scripts that do not exist: {missing}"


def test_every_relative_link_in_the_lab_resolves(lab):
    links = re.findall(r"\]\((?!https?:)([^)#]+)", lab)

    assert links, "the lab should link to its companion artifacts"
    missing = sorted(link for link in links if not (LAB.parent / link).exists())
    assert not missing, f"the lab links to paths that do not exist: {missing}"


def test_the_lab_runs_without_network_or_model_weights(lab):
    """Its central promise. A command needing a download would break it."""
    assert "GPU, no model weights, no Docker" in lab
    # The one model-backed exercise must name an offline backend.
    assert "--name class-downgrading" in lab


def test_the_lab_states_what_it_does_not_measure(lab):
    """A lab that claims a learning gain it never measured is the failure mode."""
    assert "does not measure" in lab
    assert "no learning gain is claimed" in lab


def test_the_lab_keeps_the_exercises_that_carry_the_argument(lab):
    """Cutting exercise 2 or 3 leaves a demonstration, not a lab."""
    assert "Never cut 2 or 3" in lab
