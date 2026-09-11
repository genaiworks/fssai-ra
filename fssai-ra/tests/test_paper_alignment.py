"""The paper and the repository must not be able to drift apart.

A companion repository is worth something only if its claims are the paper's
claims. The usual mechanism for keeping the two aligned is discipline, which
fails silently and late: a figure is regenerated, a sentence is not updated, and
by the time a reader checks, the paper is quoting a number the code no longer
produces.

So the figures live in one generated file, and these tests read the paper's
prose and fail the build when it quotes anything else. Changing a number in the
code now forces the sentence to change with it.

Regenerate with ``python scripts/generate_results.py``.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper" / "extended-abstract.md"
DECK = ROOT / "docs" / "presentation" / "slides.html"
SUMMARY = ROOT / "evaluation" / "results" / "v1.0.0-summary.json"


@pytest.fixture(scope="module")
def figures() -> dict:
    assert SUMMARY.exists(), (
        f"{SUMMARY.name} is missing; run python scripts/generate_results.py"
    )
    return json.loads(SUMMARY.read_text())["figures"]


@pytest.fixture(scope="module")
def prose() -> str:
    assert PAPER.exists(), f"{PAPER} is missing"
    return PAPER.read_text(encoding="utf-8")


# Each entry is (description, template). The template is rendered with the
# generated figures and must appear verbatim in the paper.
CLAIMS = [
    ("adversarial containment", "{adversarial_scenarios_contained} of {adversarial_scenarios_total} adversarial scenarios contained"),
    ("model-checked states", "{states_explored} configurations with zero violations"),
    ("model-checked states, restated", "{states_explored} model-checked states with zero invariant violations"),
    ("denial controls reached", "{distinct_denial_codes} distinct denial controls"),
    ("ablation coverage", "{controls_load_bearing} of {controls_ablated} ablated controls restored their harm when removed"),
    ("conformance checks", "{conformance_checks} conformance checks passing on {conformance_backends_verified} backend profiles"),
    ("conformance checks, restated", "{conformance_checks} checks pass on {conformance_backends_verified} independent backend profiles"),
    ("utility baseline", "{benign_tasks_completed} of {benign_tasks_total} benign tasks completed, false-denial rate {false_denial_rate}"),
    ("contract fields", "seven fields"),
]


@pytest.mark.parametrize("description,template", CLAIMS, ids=[c[0] for c in CLAIMS])
def test_every_quoted_figure_matches_a_generated_result(description, template, figures, prose):
    expected = template.format(**figures)
    assert expected in prose, (
        f"the paper no longer states the generated figure for {description}.\n"
        f"  expected the phrase: {expected!r}\n"
        f"  regenerate with: python scripts/generate_results.py, then update the paper"
    )


def test_the_paper_quotes_no_stale_scenario_count(prose):
    """Catch the specific drift this project has already had once.

    Release v0.5.0 reported eight scenarios and forty-two tests. Both grew. A
    sentence left behind quoting the old figures is exactly the failure this
    file exists to prevent.
    """
    stale = [
        "eight of eight declared scenarios",
        "eight-scenario",
        "thirty-two",
        "forty-two tests",
        "42 deterministic tests",
    ]
    for phrase in stale:
        assert phrase not in prose.lower(), f"the paper still contains the stale figure {phrase!r}"


def test_the_quoted_test_count_is_not_an_overstatement(figures, prose):
    """A repository statistic, not a scientific result.

    Adding tests must never fail the build, so this is a floor rather than an
    equality: the paper may quote the count at release, and that count must not
    exceed what the repository actually has.
    """
    match = re.search(r"(\d[\d,]*) deterministic tests", prose)
    assert match, "the paper should state how many deterministic tests back its claims"
    quoted = int(match.group(1).replace(",", ""))
    assert quoted <= figures["test_count"], (
        f"the paper claims {quoted} deterministic tests but the repository has "
        f"{figures['test_count']}"
    )


def test_the_paper_states_its_limits(prose):
    """A results section with no limits section is a marketing document."""
    for phrase in [
        "not security probabilities",
        "Not yet evidenced",
        "logical separation, not independent administrative trust",
    ]:
        assert phrase in prose, f"the paper omits the required limit statement {phrase!r}"


def test_the_paper_reports_utility_beside_containment(prose):
    """The denominator is load-bearing, so its sentence is too."""
    assert "false-denial rate" in prose
    assert "denies everything scores perfectly on containment" in prose


def test_the_repository_url_and_release_are_stated(prose, figures):
    assert "github.com/genaiworks/fssai-ra" in prose
    assert "v1.0.0" in prose, "an extended abstract must cite a fixed release, not a branch"


def test_every_verdict_in_the_summary_is_true():
    """The paper cites a passing run. If the run stops passing, so does this."""
    verdicts = json.loads(SUMMARY.read_text())["verdicts"]
    failing = [name for name, value in verdicts.items() if not value]
    assert not failing, f"the committed results contain failing verdicts: {failing}"


def test_committed_results_match_a_fresh_run():
    """Regenerate everything and compare, so committed JSON cannot go stale."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/generate_results.py", "--check"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_word_count_fits_the_submission_guidance(prose):
    """The call asks for approximately 1,500 words. 'Approximately' is not 2,400."""
    body = prose[prose.index("## 1."):prose.index("---\n\n*Full paper")]
    words = len(re.findall(r"[A-Za-z0-9'’\-]+", body))
    assert 1_300 <= words <= 1_600, f"body is {words} words; the call asks for about 1,500"


# ---------------------------------------------------------------------------
# The deck is a claim surface too
# ---------------------------------------------------------------------------
#
# A slide is read by more people than the paper and is corrected by nobody. A
# figure on a slide that the code no longer produces is the most likely way this
# work would end up overstating itself in public, so the deck is checked on the
# same terms as the prose.


@pytest.fixture(scope="module")
def deck() -> str:
    assert DECK.exists(), f"{DECK} is missing"
    return DECK.read_text(encoding="utf-8")


DECK_CLAIMS = [
    ("adversarial containment", "{adversarial_scenarios_contained}/{adversarial_scenarios_total}"),
    ("model-checked states", "<b>{states_explored}</b>"),
    ("authority coverage", "<b>{authority_coverage}</b>"),
    ("false-denial rate", "<b>{false_denial_rate}</b>"),
    ("benign tasks", "{benign_tasks_completed} of {benign_tasks_total} benign tasks"),
    ("ablation", "{controls_load_bearing} of {controls_ablated} restored their harm"),
    ("conformance", "{conformance_checks} checks, {conformance_backends_verified} backend profiles"),
    ("denial controls", "{distinct_denial_codes} denial controls"),
]


@pytest.mark.parametrize("description,template", DECK_CLAIMS, ids=[c[0] for c in DECK_CLAIMS])
def test_every_figure_on_a_slide_matches_a_generated_result(description, template, figures, deck):
    expected = template.format(**figures)
    assert expected in deck, (
        f"slide figure for {description} has drifted.\n"
        f"  expected: {expected!r}\n"
        f"  regenerate with: python scripts/generate_results.py, then update the deck"
    )


def test_the_deck_quoted_test_count_is_not_an_overstatement(figures, deck):
    match = re.search(r"(\d[\d,]*) deterministic tests", deck)
    assert match, "the deck should say how many deterministic tests back its claims"
    quoted = int(match.group(1).replace(",", ""))
    assert quoted <= figures["test_count"], (
        f"a slide claims {quoted} deterministic tests; the repository has {figures['test_count']}"
    )


def test_the_deck_carries_the_limits_slide(deck):
    """The slide a presenter is most tempted to cut, and least able to afford to."""
    required = [
        "What is <em>not</em> evidenced",
        "logical separation, not independent administrative trust",
        "Not security probabilities",
        "Not a certification",
        "independent audit",
    ]
    missing = [phrase for phrase in required if phrase not in deck]
    assert not missing, f"the deck's limits slide is missing: {missing}"


def test_the_deck_opens_and_closes_on_the_central_rule(deck, prose):
    """The one sentence worth carrying out of the room appears twice, and in the paper."""
    rule = "cannot manufacture the authority to"
    assert deck.count(rule) == 2, (
        f"the rule should appear exactly twice in the deck (open and close), found {deck.count(rule)}"
    )
    assert rule in prose, "the paper and the deck must state the same central rule"


def test_the_deck_and_the_paper_agree_on_the_release(deck, prose):
    assert "v1.0.0" in deck and "v1.0.0" in prose
    assert "github.com/genaiworks/fssai-ra" in deck
