"""The browser calculator must compute what the enforcement code computes.

A take-home tool that disagrees with the implementation is worse than no tool:
an institution would plan a roster against one number and be refused by another,
and it would be refused in production rather than in the calculator. Two copies
of a formula in two languages is exactly the drift this project builds tests to
prevent everywhere else, so the calculator is checked on the same terms.

The JavaScript is extracted from the page and executed with Node against the
same inputs as :class:`fssaira.oversight.ReviewLoadPolicy`. Where Node is not
available the tests skip rather than pass quietly — a skipped check is visible
in the run, a vacuous one is not.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from fssaira.oversight import ReviewLoadPolicy

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "oversight" / "index.html"
NODE = shutil.which("node")

#: (reviewers, hours/day, minutes to review one case, quota per hour). Chosen to
#: cover both binding constraints and both ways a declaration can contradict
#: itself, not just the shipped defaults.
CASES = [
    (11, 4, 0.75, 60),    # the shipped defaults
    (1, 8, 1.0, 60),      # a single reviewer, a full day
    (4, 4, 10.0, 60),     # a long reading: attention binds
    (4, 4, 0.25, 5),      # a tight quota: quota binds, and contradicts the floor
    (40, 2, 0.5, 200),    # a large roster and a quota that never fires
    (2, 0.5, 2.0, 15),    # a small clinic-sized deployment
]


def _js_source() -> str:
    text = PAGE.read_text(encoding="utf-8")
    match = re.search(r"\n  function compute\(v\) \{.*?\n  \}\n", text, re.S)
    assert match, "the calculator no longer exposes a compute() function to check"
    return match.group(0)


@pytest.fixture(scope="module")
def js_results() -> list[dict]:
    if NODE is None:  # pragma: no cover - environment dependent
        pytest.skip("node is not available; cannot cross-check the browser calculator")
    script = (
        _js_source()
        + "\nconst cases = " + json.dumps([
            {"reviewers": r, "hours": h, "floor": f, "quota": q, "demand": 0}
            for r, h, f, q in CASES
        ])
        + ";\nconsole.log(JSON.stringify(cases.map(compute)));\n"
    )
    completed = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def _policy(hours: float, floor_minutes: float, quota: int) -> ReviewLoadPolicy:
    return ReviewLoadPolicy(
        max_approvals_per_window=quota,
        window_seconds=3_600.0,
        min_deliberation_seconds=floor_minutes * 60.0,
        second_reviewer_after=None,
        reviewing_seconds_per_day=hours * 3_600.0,
    )


def test_the_page_exists_and_is_self_contained():
    """No build step, no bundler, and no network call for anything but fonts."""
    text = PAGE.read_text(encoding="utf-8")

    assert "<script" in text and "src=" not in text.split("<script")[1][:200]
    for forbidden in ("fetch(", "XMLHttpRequest", "localStorage", "sessionStorage"):
        assert forbidden not in text, f"the calculator must not use {forbidden}"
    # Fonts are the only external reference, and the stack degrades without them.
    external = re.findall(r'https?://[^\s"\']+', text)
    assert all("fonts.g" in url or "github.com" in url for url in external), external


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"r{c[0]}_h{c[1]}_f{c[2]}_q{c[3]}")
def test_the_calculator_agrees_with_the_enforcement_code(case, js_results):
    reviewers, hours, floor_minutes, quota = case
    index = CASES.index(case)
    js = js_results[index]
    capacity = _policy(hours, floor_minutes, quota).sustainable_actions_per_day(reviewers)

    assert js["quotaCeiling"] == pytest.approx(capacity["policy_ceiling_per_day"])
    assert js["attentionCeiling"] == pytest.approx(capacity["attention_ceiling_per_day"])
    assert js["ceiling"] == pytest.approx(capacity["sustainable_per_day"])


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"r{c[0]}_h{c[1]}_f{c[2]}_q{c[3]}")
def test_the_calculator_names_the_same_binding_constraint(case, js_results):
    reviewers, hours, floor_minutes, quota = case
    js = js_results[CASES.index(case)]
    capacity = _policy(hours, floor_minutes, quota).sustainable_actions_per_day(reviewers)

    expected = "quota" if capacity["binding_constraint"] == "policy_quota" else "reading time"
    assert js["binds"] == expected


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"r{c[0]}_h{c[1]}_f{c[2]}_q{c[3]}")
def test_the_calculator_flags_the_same_incoherent_declarations(case, js_results):
    """The consistency diagnostic must agree, or the tool teaches the wrong lesson."""
    _, hours, floor_minutes, quota = case
    js = js_results[CASES.index(case)]
    coherence = _policy(hours, floor_minutes, quota).declared_consistency()

    assert js["permitted"] == pytest.approx(coherence["floor_permits_per_window"])
    # The library rounds the published ratio to three decimals; compare at that
    # precision rather than pretending the two are bit-identical.
    assert js["ratio"] == pytest.approx(coherence["ratio"], abs=5e-4)
    # The page's thresholds and the library's must classify identically.
    js_verdict = "consistent" if 0.5 <= js["ratio"] <= 2.0 else "inconsistent"
    assert js_verdict == ("consistent" if coherence["consistent"] else "inconsistent")


def test_the_page_states_that_no_reviewer_was_observed():
    """The caveat travels with the tool, not only with the paper."""
    text = PAGE.read_text(encoding="utf-8")

    assert "No reviewer was observed" in text
    assert "declare" in text


def test_the_page_offers_no_fifth_option():
    """The tool must not imply that reviewers can simply go faster."""
    text = PAGE.read_text(encoding="utf-8")

    assert "no fifth option where the reviewers simply go faster" in text


# ---------------------------------------------------------------------------
# The assistance multiplier
# ---------------------------------------------------------------------------
#
# The calculator gained a second formula when it learned about review
# assistance, and a second formula is a second chance to drift. It is checked on
# the same terms as the ceiling arithmetic: extracted, executed, and compared
# against the Python across every mode and every independence score.

#: Every combination a user of the page can produce.
ASSISTANCE_CASES = [
    (mode, score)
    for mode in ("unaided", "summarised", "recommended")
    for score in (0, 1, 2, 3)
]


def _js_multiplier_source() -> str:
    text = PAGE.read_text(encoding="utf-8")
    match = re.search(r"\n  function floorMultiplier\(mode, score\) \{.*?\n  \}\n", text, re.S)
    assert match, "the calculator no longer exposes floorMultiplier() to check"
    return match.group(0)


@pytest.fixture(scope="module")
def js_multipliers() -> list[float]:
    if NODE is None:  # pragma: no cover - environment dependent
        pytest.skip("node is not available; cannot cross-check the browser calculator")
    script = (
        _js_multiplier_source()
        + "\nconst cases = " + json.dumps(ASSISTANCE_CASES)
        + ";\nconsole.log(JSON.stringify(cases.map(([m, s]) => floorMultiplier(m, s))));\n"
    )
    completed = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@pytest.mark.parametrize("index,case", list(enumerate(ASSISTANCE_CASES)), ids=lambda c: str(c))
def test_the_calculator_earns_the_same_floor_as_the_enforcement_code(index, case, js_multipliers):
    """A delegate planning against the page must not be refused by the gate.

    The page tells an institution what reading time its declaration earns. If
    that disagrees with ``AssistedReviewPolicy``, the institution configures a
    floor the page approved and the deployment refuses to start — which is the
    correct failure in the wrong place, hours after the decision was made.
    """
    from fssaira.assisted_review import AssistanceMode, ReviewAssistance

    if not isinstance(case, tuple):  # parametrize id helper passes the case through
        return
    mode, score = case
    flags = [True] * score + [False] * (3 - score)
    assistance = ReviewAssistance(
        mode=AssistanceMode(mode),
        independent_model=flags[0],
        independent_evidence=flags[1],
        adversarial_posture=flags[2],
        declared_by="test",
    )
    assert js_multipliers[index] == pytest.approx(assistance.floor_multiplier, abs=1e-4), (
        f"the page and the enforcement code disagree for {mode} at {score}/3 independence"
    )


def test_an_unaided_reader_keeps_the_whole_reading_time(js_multipliers):
    for index, (mode, _score) in enumerate(ASSISTANCE_CASES):
        if mode == "unaided":
            assert js_multipliers[index] == 1.0


def test_a_fully_dependent_assistant_earns_no_reduction(js_multipliers):
    """The judgement the page exists to convey: throughput is bought with
    independence, and a deployment that declared none has bought none."""
    for index, (mode, score) in enumerate(ASSISTANCE_CASES):
        if mode != "unaided" and score == 0:
            assert js_multipliers[index] == 1.0


def test_the_page_declares_the_three_independence_properties():
    """A delegate should leave with the procurement language, not a number."""
    text = PAGE.read_text(encoding="utf-8")
    for phrase in ("different model", "different evidence path", "adversarial posture"):
        assert phrase in text, f"the page no longer names {phrase!r}"


def test_the_page_says_assistance_does_not_remove_the_ceiling():
    text = PAGE.read_text(encoding="utf-8")
    assert "does not make attention infinite" in text
