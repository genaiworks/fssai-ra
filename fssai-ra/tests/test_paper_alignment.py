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
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper" / "extended-abstract.md"
DECK = ROOT / "docs" / "presentation" / "slides.html"
SUMMARY = ROOT / "evaluation" / "results" / "v1.0.0-summary.json"
READMES = (ROOT / "README.md", ROOT.parent / "README.md")


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
    ("denial controls reached", "{distinct_denial_codes} distinct denial controls"),
    ("ablation coverage", "{controls_load_bearing} of {controls_ablated} ablated controls restored their harm when removed"),
    ("conformance checks", "{conformance_checks} conformance checks passing on {conformance_backends_verified} backend profiles"),
    ("utility baseline", "{benign_tasks_completed} of {benign_tasks_total} benign tasks completed, false-denial rate {false_denial_rate}"),
    ("concurrent replay", "{concurrent_callers}-caller race produced {concurrent_mutations} mutation and {concurrent_distinct_receipts} receipt"),
    ("contract fields", "seven fields"),
    # Added with the oversight, generalization, and corpus contributions. A new
    # claim in the paper without an entry here is a figure nothing checks.
    ("oversight capacity", "a roster of {oversight_reviewer_roster} reviewers sustains "
     "{oversight_sustainable_per_day_display} consequential actions per day"),
    ("oversight queue trial", "Without load control, {oversight_harms_without_load_control} "
     "such merit failures execute. With it, {oversight_harms_with_load_control} do, and "
     "{oversight_deferred_to_manual} actions defer to manual review"),
    ("second domain", "{second_domain_states_explored_display} configurations with zero "
     "violations, {second_domain_scenarios_contained} of {second_domain_scenarios_total} "
     "scenarios contained, {second_domain_benign_completed} of "
     "{second_domain_benign_total} benign tasks, {second_domain_conformance_checks} "
     "conformance checks"),
    ("cross-domain matrix", "{domains_verified} independently reported domain packs cover "
     "{domain_pack_states_explored_display} bounded configurations, "
     "{domain_pack_scenarios_contained} of {domain_pack_scenarios_total} hostile scenarios "
     "contained, {domain_pack_benign_completed} of {domain_pack_benign_total} benign tasks "
     "completed, and zero unauthorized mutations"),
    ("oversight sensitivity sweep", "across {sweep_cells_total} parameter combinations the "
     "control was load-bearing in {sweep_cells_load_bearing} of the "
     "{sweep_cells_harm_possible} where harm was possible, harm reached zero in "
     "{sweep_cells_harm_reached_zero}"),
    ("oversight false-positive cost", "drove the false-positive cost to "
     "{sweep_false_positive_deferrals}"),
    # Added with the composition contributions. A new claim in the paper without
    # an entry here is a figure nothing checks — which is the defect the contract
    # coverage work exists to catch, so it would be an embarrassing one to ship.
    ("contract coverage", "**eighteen of twenty-eight were prose bound to nothing.**"),
    ("contract coverage today", "reading {coverage_machine_verified}, "
     "{coverage_organizationally_attested}, {coverage_unverified} today"),
    ("assisted review", "**{assisted_merit_failures_dependent} merit failures with a "
     "dependent assistant, {assisted_merit_failures_independent} with an independent one**"),
    ("delegation chain shapes", "{delegation_states_explored_display} enumerated chain "
     "shapes and zero violations"),
    ("delegation arms", "contains {delegation_contained_caller_checked} of "
     "{delegation_hostile_chains} risk classes where verifying the chain contains "
     "{delegation_contained_this_architecture}"),
    # Added with governed disclosure and the threat catalogue: the second rule
    # and the claim that the safety case does not rest on alignment.
    ("disclosure containment", "**{disclosure_contained} of {disclosure_hostile_total} "
     "hostile data flows were contained**"),
    ("disclosure conventional arm", "**contained {disclosure_contained_access_controlled}**"),
    ("disclosure ablation", "**All {disclosure_checks_load_bearing} checks were load-bearing**"),
    ("disclosure model check", "**{disclosure_states_explored_display} read and release "
     "configurations showed zero violations**"),
    ("disclosure utility", "{disclosure_benign_completed} of {disclosure_benign_total} "
     "legitimate flows completed"),
    ("threat catalogue", "A catalogue of {threats_total} failure classes"),
    ("threat statuses", "**{threats_contained} contained, {threats_bounded} bounded, and "
     "{threats_residual} residual**"),
    ("stateful testing", "**{disclosure_stateful_sequences} sequences and "
     "{disclosure_stateful_steps_display} operations**"),
    ("thesis falsification", "**{thesis_attempts_display} bounded attempts found zero "
     "counterexamples**"),
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


def test_the_paper_states_its_scope(prose):
    """The paper states what its figures are and where assurance concentrates.

    It no longer carries a list of caveats, but it must still tell a reader that
    every figure is regenerable from the repository and name the trusted base,
    so no number can be read as a field measurement it is not.
    """
    for phrase in [
        "reproducible fixture observation",
        "trusted base",
        "research agenda",
    ]:
        assert phrase in prose, f"the paper omits its scope statement {phrase!r}"


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
    """The call asks for approximately 1,500 words.

    The bound was 1,650 — about 10% over — while the abstract argued three
    contributions. It is now **1,900**, raised deliberately when three more were
    added: the contract's own coverage (§2), assisted review (§3), and delegated
    authority (§4). Each is load-bearing for a 2026 panel, and each is stated at
    the shortest length that keeps its figures. The existing sections were
    compressed to pay for most of the increase; the remainder is the honest cost
    of a larger contribution.

    This is the file that makes the number a decision rather than a drift, so
    the reason is recorded here. ``paper/form-ready-abstract.md`` remains the
    artifact written to the form's capped fields and validates separately;
    ``extended-abstract.md`` is the proceedings-style version. If a hard cap
    must be met, ``paper/SUBMISSION.md`` names the cut order.

    Raise this again only with the same kind of entry, and never by cutting the
    limits section to make room.
    """
    body = prose[prose.index("## 1."):prose.index("## References")]
    words = len(re.findall(r"[A-Za-z0-9'’\-]+", body))
    assert 1_300 <= words <= 1_900, f"body is {words} words; the call asks for about 1,500"


SUPPLEMENT = ROOT / "paper" / "composition-supplement.md"

#: Figures the composition supplement states, held to the same standard as the
#: abstract's. A supplement is not a place where numbers stop being checked.
SUPPLEMENT_CLAIMS = [
    ("delegation arms", "| Hostile chains contained | {delegation_contained_unguarded} / "
     "{delegation_hostile_chains} | {delegation_contained_caller_checked} / "
     "{delegation_hostile_chains} | **{delegation_contained_this_architecture} / "
     "{delegation_hostile_chains}** |"),
    ("delegation states", "**{delegation_states_explored_display} configurations with zero violations**"),
    ("assisted merit failures dependent", "| **{assisted_merit_failures_dependent}** | "
     "{assisted_benign_independent} | 0 |"),
    ("assisted unaided baseline", "| **{assisted_merit_failures_unaided}** | "
     "{assisted_benign_unaided} | {assisted_deferrals_unaided} |"),
    ("coverage totals", "**{coverage_machine_verified} machine-verified, "
     "{coverage_organizationally_attested} attested, {coverage_unverified} unverified**, "
     "across {coverage_requirements} requirements"),
]


@pytest.fixture(scope="module")
def supplement() -> str:
    """The supplement with runs of whitespace collapsed.

    Prose reflows when it is edited, and a claim check that breaks because a
    sentence wrapped at a different column is a check nobody keeps. What must
    not change is the words.
    """
    return re.sub(r"\s+", " ", SUPPLEMENT.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "description,template", SUPPLEMENT_CLAIMS, ids=[c[0] for c in SUPPLEMENT_CLAIMS]
)
def test_every_figure_in_the_supplement_matches_a_generated_result(
    description, template, figures, supplement
):
    expected = template.format(**figures)
    assert expected in supplement, (
        f"the composition supplement no longer states the generated figure for "
        f"{description}.\nExpected to find:\n  {expected!r}\n"
        "Regenerate with scripts/generate_results.py and update the supplement."
    )


def test_the_supplement_states_its_limits(supplement):
    """A supplement is where detail goes, not where caveats get dropped."""
    for phrase in (
        "declared parameter",
        "No model was evaluated",
        "No real multi-agent deployment was observed",
        "revocation propagation",
    ):
        assert phrase in supplement, f"the supplement omits the limit {phrase!r}"


def test_the_supplement_reports_the_benign_case_beside_the_containment(supplement):
    """The same discipline the abstract is held to: a control that refuses
    everything contains everything."""
    assert "Benign two-hop chain completes" in supplement
    assert "Benign completed" in supplement


def test_the_supplement_does_not_claim_assistance_removes_the_ceiling(supplement):
    """The independent arm reaches 1, not 0, and that has to survive editing."""
    assert "larger ceiling to compute, not permission to stop computing one" in supplement
    assert "**1, not 0**" in supplement


def test_the_abstract_points_at_the_supplement(prose):
    assert "composition supplement" in prose, (
        "the abstract compresses two contributions and must say where the method is"
    )


def test_the_abstract_opens_on_a_cross_sector_system_problem(prose):
    """The architecture must not collapse back into one education narrative.

    A reviewer should encounter multiple consequential domains immediately and
    understand that the governed object is the complete system, not its model.
    """
    opening = prose[prose.index("## 1."):][:1_200]
    for phrase in ("company", "hospital", "university", "public body"):
        assert phrase in opening, f"the opening no longer establishes the {phrase} domain"
    assert "A safe model cannot answer those questions on behalf of an unsafe system" in opening


def test_the_abstract_connects_governance_to_public_voice(prose):
    """Mediation makes action contestable; the paper says what that enables."""
    assert "attributable and contestable" in prose
    assert "participatory rulemaking" in prose


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
    ("disclosure containment", "<b>{disclosure_contained}/{disclosure_hostile_total}</b>"),
    ("disclosure conventional arm", "<b>{disclosure_contained_access_controlled}/{disclosure_hostile_total}</b>"),
    ("disclosure checks", "{disclosure_checks_load_bearing}/{disclosure_checks_ablated} checks load-bearing"),
    ("disclosure states", "{disclosure_states_explored_display} states, 0 violations"),
    ("threats contained", "<span class=\"hash\"><b>{threats_contained}</b></span>"),
    ("threats bounded", "<span class=\"hash\"><b>{threats_bounded}</b></span>"),
    ("threats residual", "<b class=\"bad\">{threats_residual}</b>"),
    ("threat classes", "{threats_total} failure classes"),
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


# ---------------------------------------------------------------------------
# The READMEs are a claim surface too
# ---------------------------------------------------------------------------
#
# Added after the two top-level READMEs were found quoting 180, 187, and 149
# deterministic tests simultaneously, none of which was the current figure. The
# paper was protected from that class of drift and the front door was not, which
# is backwards: the README is what most readers see first.


@pytest.mark.parametrize("path", READMES, ids=lambda p: p.parent.name + "/README.md")
def test_no_readme_overstates_the_test_count(path, figures):
    assert path.exists(), f"{path} is missing"
    quoted = [
        int(value.replace(",", ""))
        for value in re.findall(r"(\d[\d,]*) deterministic tests", path.read_text(encoding="utf-8"))
    ]
    assert quoted, f"{path} should state how many deterministic tests back its claims"
    for count in quoted:
        assert count <= figures["test_count"], (
            f"{path} claims {count} deterministic tests but the repository has "
            f"{figures['test_count']}"
        )


def test_the_reviewer_guide_quotes_the_current_test_count(figures):
    """The reviewer guide tells a sceptic what ``pytest`` will print.

    It was the one front-door document outside ``READMES`` quoting a figure, and
    it drifted to 394 while the suite grew past 470. A reviewer who runs the
    command and sees a different number has been given a reason to doubt every
    other figure in the repository, which is an expensive way to lose an argument
    you were winning.
    """
    guide = ROOT / "docs" / "REVIEWERS.md"
    assert guide.exists(), f"{guide} is missing"
    quoted = [
        int(value.replace(",", ""))
        for value in re.findall(r"`(\d[\d,]*) passed`", guide.read_text(encoding="utf-8"))
    ]
    assert quoted, "the reviewer guide should say what a passing run prints"
    for count in quoted:
        assert count == figures["test_count"], (
            f"docs/REVIEWERS.md says `{count} passed` but the suite has "
            f"{figures['test_count']} tests"
        )


@pytest.mark.parametrize("path", READMES, ids=lambda p: p.parent.name + "/README.md")
def test_no_readme_quotes_a_stale_oversight_capacity(path, figures):
    """Both READMEs lead with the oversight figure, so both are checked.

    It is the most quotable number in the project and therefore the most likely
    to be repeated somewhere and then left behind when the defaults change.
    """
    expected = (
        f"{figures['oversight_reviewer_roster']} reviewers sustain "
        f"{figures['oversight_sustainable_per_day']:,.0f} actions/day"
    )
    assert expected in path.read_text(encoding="utf-8"), (
        f"{path} no longer states the generated oversight capacity figure: {expected!r}"
    )


# ---------------------------------------------------------------------------
# The file that is actually submitted
# ---------------------------------------------------------------------------
#
# Everything above guards ``paper/extended-abstract.md``, the proceedings-style
# version. The version that is pasted into the UNU form is
# ``paper/form-ready-abstract.md``, and until these tests existed it was the one
# claim surface in the project with no guard at all. That is the wrong way
# round: the extended abstract is what we would like reviewers to read, and the
# form-ready abstract is what they actually receive.
#
# It restates the same results in different prose, so it cannot reuse the
# templates above. It needs its own.

SUBMITTED = ROOT / "paper" / "form-ready-abstract.md"

# Spelled-out numbers are the drift a numeric search cannot see: regenerate the
# figures, grep the abstract for "25", find nothing, and leave "Twenty-five"
# behind. Each entry is (figure key, the word the abstract uses for it).
NUMBER_WORDS = {
    0: "zero",
    4: "four",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    25: "twenty-five",
    26: "twenty-six",
}


@pytest.fixture(scope="module")
def submitted() -> str:
    assert SUBMITTED.exists(), f"{SUBMITTED} is missing"
    return SUBMITTED.read_text(encoding="utf-8")


SUBMITTED_CLAIMS = [
    ("adversarial containment", "{adversarial_scenarios_contained} of {adversarial_scenarios_total} attack scenarios were contained"),
    ("utility baseline", "the false-denial rate was {false_denial_rate}"),
    ("model-checked states", "{states_explored} configurations showed no violation"),
    ("ablation coverage", "{controls_load_bearing} of {controls_ablated} controls were load-bearing"),
    ("concurrent replay", "A {concurrent_callers}-caller replay race produced one change and one receipt"),
    ("unguarded arm", "The unguarded agent let {arm_a_harms} harmful actions through"),
    ("guarded arm harms", "a safety prompt with a tool allowlist let {arm_b_harms} through"),
    ("oversight capacity", "A roster of {oversight_reviewer_roster} reviewers sustains {oversight_sustainable_per_day_display} consequential actions per day"),
    ("oversight queue trial", "When {oversight_arrivals} cases reach one reviewer, "
     "{oversight_harms_without_load_control} approvals that are wrong on merit execute without "
     "load control"),
    ("oversight deferral", "{oversight_deferred_to_manual} cases move to manual review"),
    ("oversight sweep", "Across {sweep_cells_total} parameter settings, the control never raised harm"),
    ("assisted review", "a dependent assistant let {assisted_merit_failures_dependent} errors "
     "through and an independent one let {assisted_merit_failures_independent}"),
    ("cross-domain matrix", "domain packs share one kernel: "
     "{domain_pack_states_explored_display} configurations checked, "
     "{domain_pack_scenarios_contained} of {domain_pack_scenarios_total} hostile scenarios "
     "contained, {domain_pack_benign_completed} of {domain_pack_benign_total} benign tasks completed"),
    ("disclosure containment", "{disclosure_contained} of {disclosure_hostile_total} hostile "
     "data flows were contained"),
    ("disclosure conventional arm", "Conventional access control stopped "
     "{disclosure_contained_access_controlled}"),
    ("disclosure checks and states", "All {disclosure_checks_load_bearing} checks were "
     "load-bearing, {disclosure_states_explored_display} configurations showed no violation, and "
     "{disclosure_benign_completed} of {disclosure_benign_total} legitimate flows completed"),
    ("stateful testing", "{disclosure_stateful_sequences} sequences and "
     "{disclosure_stateful_steps_display} random operations"),
    ("delegation arms", "stopped {delegation_contained_caller_checked} of "
     "{delegation_hostile_chains} chain attacks; checking the whole chain stopped all "
     "{delegation_contained_this_architecture}, across {delegation_states_explored_display} "
     "chain shapes"),
    ("threat catalogue", "Of {threats_total} failure classes"),
    ("threat statuses", "{threats_contained} are contained, {threats_bounded} bounded, and "
     "{threats_residual} set as research goals"),
    ("thesis falsification", "falsifiers made {thesis_attempts_display} attempts to cause an "
     "effect or disclosure from model output alone and found none"),
    ("contract coverage", "coverage now reads {coverage_machine_verified} machine-verified, "
     "{coverage_organizationally_attested} attested, and {coverage_unverified} unverified"),
]


@pytest.mark.parametrize(
    "description,template", SUBMITTED_CLAIMS, ids=[c[0] for c in SUBMITTED_CLAIMS]
)
def test_every_figure_in_the_submitted_abstract_matches_a_generated_result(
    description, template, figures, submitted
):
    expected = template.format(**figures)
    assert expected in submitted, (
        f"the submitted abstract no longer states the generated figure for {description}.\n"
        f"  expected the phrase: {expected!r}\n"
        f"  regenerate with: python scripts/generate_results.py, then update "
        f"paper/form-ready-abstract.md"
    )


SPELLED_CLAIMS = [
    ("comparison attacks", "comparison_attacks", "{word} attacks went to all three designs"),
    ("thesis falsifiers", "thesis_falsifiers", "{word} falsifiers made"),
    ("domain packs", "domains_verified", "{word} domain packs share one kernel"),
]


def test_the_submitted_abstract_states_the_assistance_gain_it_measured(figures, submitted):
    """"Fivefold" is a spelled-out figure the numeric templates cannot see."""
    words = {2.0: "twofold", 3.0: "threefold", 4.0: "fourfold", 5.0: "fivefold"}
    gain = figures["assisted_benign_gain"]
    assert gain in words, f"assisted_benign_gain is now {gain}; update the sentence and this map"
    assert f"raised completed work {words[gain]}" in submitted


@pytest.mark.parametrize(
    "description,key,template", SPELLED_CLAIMS, ids=[c[0] for c in SPELLED_CLAIMS]
)
def test_every_spelled_out_figure_in_the_submitted_abstract_is_current(
    description, key, template, figures, submitted
):
    value = figures[key]
    assert value in NUMBER_WORDS, (
        f"{key} is now {value}, which has no spelled-out form in NUMBER_WORDS; "
        f"add it, then update the sentence in paper/form-ready-abstract.md"
    )
    expected = template.format(word=NUMBER_WORDS[value])
    lowered = submitted.lower()
    assert expected.lower() in lowered, (
        f"the submitted abstract no longer spells out the generated figure for "
        f"{description} ({key} = {value}).\n  expected the phrase: {expected!r}"
    )


def test_the_submitted_abstract_fits_every_form_field():
    """The form truncates silently; a test is the only thing that will not.

    ``scripts/check_submission.py`` counts characters the way the browser
    submits them, with CRLF line endings, because that is the count the form
    applies. Three of the four fields have already been over that limit while
    reading as comfortably inside it.
    """
    spec = importlib.util.spec_from_file_location(
        "check_submission", ROOT / "scripts" / "check_submission.py"
    )
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)

    report = check.validate(SUBMITTED.read_text(encoding="utf-8"))
    failed = {
        name: field
        for name, field in report["sections"].items()
        if not field["valid"]
    }
    assert not failed, (
        "the submitted abstract no longer fits the form's fields: "
        + "; ".join(
            f"{name} is {f['words']} words ({f['word_minimum']}-{f['word_maximum']}) "
            f"and {f['characters']} characters (max {f['character_maximum']})"
            for name, f in failed.items()
        )
    )


def test_the_submitted_abstract_pastes_as_plain_ascii(submitted):
    """A form field is not a typesetter.

    Curly quotes, en dashes and non-breaking spaces survive a Markdown file and
    then arrive in a Microsoft Form as mojibake or as extra characters against a
    cap that three fields are already within twenty characters of. The extended
    abstract may keep its typography; this file is paste payload.
    """
    offenders = sorted({ch for ch in submitted if ord(ch) > 127})
    assert not offenders, (
        "the submitted abstract contains non-ASCII characters that should be "
        "replaced before pasting: "
        + ", ".join(f"{ch!r} (U+{ord(ch):04X})" for ch in offenders)
    )


def test_the_submitted_abstract_states_its_scope(submitted):
    """The version reviewers read says what its figures are, in one line."""
    for phrase in ("reproducible fixture observations", "synthetic domain packs"):
        assert phrase in submitted, (
            f"the submitted abstract should still state its scope; {phrase!r} is missing"
        )


# ---------------------------------------------------------------------------
# The deck and the script that routes it
# ---------------------------------------------------------------------------
#
# The script's paths table was written when the deck was nineteen slides and was
# not updated when four more were added. It therefore told a presenter that the
# full run was "1-19" on a page that also said slide 20 must never be cut, and
# every shortened path ended on the limits slide with the close dropped. The
# timing table below it was correct the whole time, which is what made the
# contradiction survive: both were on the same page and only one was read.

SCRIPT = ROOT / "docs" / "presentation" / "speaker-script.md"


@pytest.fixture(scope="module")
def deck_slides() -> list[str]:
    """The deck's slides, in order, labelled by their eyebrow."""
    blocks = re.split(r"\n\s*\{\s*\n\s*eyebrow:", DECK.read_text(encoding="utf-8"))
    labels = []
    for block in blocks[1:]:
        match = re.match(r'\s*\[\s*"([^"]*)"', block)
        labels.append(match.group(1) if match else "")
    assert labels, "no slides found in the deck; the slide literal's shape has changed"
    return labels


@pytest.fixture(scope="module")
def script() -> str:
    assert SCRIPT.exists(), f"{SCRIPT} is missing"
    return SCRIPT.read_text(encoding="utf-8")


def _narrative_count(deck_slides: list[str]) -> int:
    """Slides the talk runs, excluding the backup slides kept for questions."""
    return sum(1 for label in deck_slides if label.strip().lower() != "backup")


def _paths(script: str) -> dict[str, list[int]]:
    """Every 'Run slides' row of the paths table, expanded from ranges."""
    paths = {}
    for row in re.findall(r"^\|\s*\*\*([^*]+)\*\*\s*\|([^|]+)\|", script, re.M):
        name, cells = row[0].strip(), row[1]
        numbers: list[int] = []
        for token in cells.split(","):
            token = token.strip()
            span = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", token)
            if span:
                numbers.extend(range(int(span.group(1)), int(span.group(2)) + 1))
            elif token.isdigit():
                numbers.append(int(token))
        if numbers:
            paths[name] = numbers
    return paths


def test_the_script_states_the_deck_it_actually_routes(script, deck_slides):
    match = re.search(r"runs \*\*(\d+) slides", script)
    assert match, "the script should say how many slides the deck runs"
    assert int(match.group(1)) == _narrative_count(deck_slides), (
        f"the script says the deck runs {match.group(1)} slides but it has "
        f"{_narrative_count(deck_slides)} narrative slides and "
        f"{len(deck_slides) - _narrative_count(deck_slides)} backup slides"
    )


def test_every_path_runs_slides_that_exist(script, deck_slides):
    paths = _paths(script)
    assert paths, "no paths table found in the script"
    for name, numbers in paths.items():
        assert max(numbers) <= len(deck_slides), (
            f"the {name} path runs slide {max(numbers)}; the deck has "
            f"{len(deck_slides)} slides"
        )


def test_every_path_ends_on_the_close(script, deck_slides):
    """A path that stops earlier ends the talk on whatever preceded the close.

    Before this test the shortened paths ended on the limits slide, which is the
    one slide in the deck written to be the least reassuring thing in the room.
    """
    last = _narrative_count(deck_slides)
    for name, numbers in _paths(script).items():
        assert numbers[-1] == last, (
            f"the {name} path ends on slide {numbers[-1]}, not the close (slide {last})"
        )


def test_no_path_cuts_a_slide_the_script_says_is_never_cut(script, deck_slides):
    """The never-cut rule and the paths table must not contradict each other."""
    stated = {int(n) for n in re.findall(r"Slide (\d+),", script)}
    for clause in re.findall(r"Do not cut ([\d,\s]+(?:or\s*\d+)?)", script):
        stated |= {int(n) for n in re.findall(r"\d+", clause)}
    assert stated, "the script should name the slides it refuses to cut"
    for name, numbers in _paths(script).items():
        missing = sorted(stated - set(numbers))
        assert not missing, (
            f"the {name} path cuts slide(s) {missing}, which the script says are never cut"
        )


# Full manuscript: previously omitted from alignment checks despite the builder's claim.
@pytest.mark.parametrize("template", [
    "{domain_pack_scenarios_contained} of {domain_pack_scenarios_total} hostile scenarios",
    "{disclosure_contained} of {disclosure_hostile_total} hostile data flows",
    "{thesis_attempts_display} bounded attempts",
    "{domain_pack_benign_completed} of {domain_pack_benign_total} benign tasks",
])
def test_full_manuscript_metrics_match_generated_results(template, figures):
    manuscript = (ROOT / "paper" / "trust-by-construction.md").read_text()
    assert template.format(**figures) in manuscript


def test_foundation_claims_have_real_evidence_locators_and_scoped_status():
    register = json.loads((ROOT / "paper" / "foundation-claims.json").read_text())
    ids = [claim["id"] for claim in register["claims"]]
    assert len(ids) == len(set(ids))
    for claim in register["claims"]:
        assert claim["limitation"] and claim["enforcement_point"]
        for path in claim["implementation"] + claim["tests"]:
            assert (ROOT / path).is_file(), path
        if claim["status"] in {"fixture-tested", "selected-regressions-tested", "simulated"}:
            assert claim["tests"] and claim["reproduction_command"]
        else:
            assert claim["status"] in {"source-present-unqualified", "deployment-requirement", "empirical-open"}
