"""The demonstration must work, because it is what people will actually see.

A demo that has drifted is worse than no demo: it fails in front of an audience,
after the claims have been made. So the hero demonstration runs in CI, every act
of it, and its narration is checked against the behaviour it claims to show.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "scripts" / "demo.py"


def run_demo(*args: str) -> str:
    result = subprocess.run(
        [sys.executable, str(DEMO), "--fast", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
        env={"PATH": "/usr/bin:/bin", "NO_COLOR": "1", "HOME": str(Path.home())},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.fixture(scope="module")
def output() -> str:
    return run_demo()


@pytest.mark.parametrize("act", range(1, 7))
def test_every_act_runs_on_its_own(act):
    """A presenter jumping straight to act four must not hit an error."""
    assert f"ACT {act}" in run_demo("--act", str(act))


def test_the_demo_shows_a_denial_before_it_shows_a_success(output):
    """The order is the argument: refusal first, then that work still happens."""
    assert output.index("QUARANTINED") < output.index("executed")


def test_the_demo_shows_every_load_bearing_control(output):
    for marker in [
        "QUARANTINED",            # the import boundary
        "no return path",         # directionality
        "EGRESS_BLOCKED",         # default-deny egress
        "NO_APPROVER_AVAILABLE",  # a named human for consequential actions
        "APPROVAL_PAYLOAD_MISMATCH",  # approval bound to an exact proposal
        "EvidenceError",          # the guarded write path
        "CHAIN BROKEN",           # tamper-evidence
    ]:
        assert marker in output, f"the demo no longer shows {marker}"


def test_the_demo_shows_legitimate_work_completing(output):
    """A demo that only shows refusals argues for not deploying anything."""
    assert "executed" in output
    assert "replayed" in output
    assert "one mutation" in output


def test_the_demo_states_what_it_does_not_prove(output):
    assert "stripping removes mechanical injection only" in output
    assert "detectable; it was not prevented" in output
    assert "Not a certification" in output


def test_the_comparison_act_reports_all_three_arms(output):
    assert "unguarded" in output and "prompt-guarded" in output and "FSSAI-RA" in output
    assert "0/7 contained" in output
    assert "7/7 contained" in output
    assert "The containment cost nothing" in output


def test_the_demo_needs_no_network_and_no_model():
    """The claim that it runs on a disconnected laptop, checked rather than asserted."""
    source = DEMO.read_text()
    for forbidden in ("urllib", "requests", "httpx", "socket.create_connection", "OllamaModel"):
        assert forbidden not in source, f"the demo reaches for {forbidden}"
