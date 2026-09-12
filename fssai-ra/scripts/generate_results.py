"""Regenerate every number the paper cites.

The paper quotes figures. Figures drift. This script is the single place those
figures come from, and ``tests/test_paper_alignment.py`` fails the build if the
paper quotes a number this script does not produce. That is the whole mechanism
for keeping the repository aligned with its own claims: not discipline, not a
review checklist, but a test.

    python scripts/generate_results.py [--version v1.0.0] [--check]

``--check`` regenerates into a temporary directory and reports whether the
committed results still match, without writing anything. Use it in CI.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fssaira import __version__  # noqa: E402
from fssaira.challenge import run_corpus  # noqa: E402
from fssaira.conformance import memory_bundle, run_conformance, sql_bundle  # noqa: E402
from fssaira.evaluation import EvaluationRunner  # noqa: E402
from fssaira.experiment import run_comparison  # noqa: E402
from fssaira.oversight import (  # noqa: E402
    DeclaredReviewerModel,
    ReviewLoadPolicy,
    run_queue_pressure_trial,
    sweep_oversight,
)
from fssaira.profiles import ApplicationProfile  # noqa: E402
from fssaira.race import run_replay_race  # noqa: E402
from fssaira.verification import verify_profile  # noqa: E402

PROFILE_PATH = ROOT / "profiles" / "student_support.yaml"
#: The second domain exists to test the *method*, not to add a headline. Its
#: figures are generated separately and never merged into the first domain's.
SECOND_PROFILE_PATH = ROOT / "profiles" / "academic_record_correction.yaml"
CHALLENGE_DIR = ROOT / "challenges"
#: Roster used only for the published oversight-capacity arithmetic.
REVIEWER_ROSTER = 11
RESULTS_DIR = ROOT / "evaluation" / "results"


def generate(output_dir: Path, tag: str) -> dict:
    """Run everything and write one file per artifact plus a summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    profile = ApplicationProfile.load(PROFILE_PATH)

    started = time.perf_counter()
    evaluation = EvaluationRunner(profile).run()
    evaluation_seconds = time.perf_counter() - started

    started = time.perf_counter()
    verification = verify_profile(profile)
    verification_seconds = time.perf_counter() - started

    memory_conformance = run_conformance(memory_bundle(profile))
    sql_conformance = run_conformance(sql_bundle(profile=profile))
    comparison = run_comparison()
    race = run_replay_race(profile, callers=32)
    by_arm = {arm["arm"][0]: arm for arm in comparison["arms"]}  # "A", "B", "C"

    # The second domain, run through the identical suite with no library change.
    # Kept in its own variables throughout: borrowing one domain's evidence for
    # another is the failure mode docs/EXTENDING.md exists to prevent.
    second_profile = ApplicationProfile.load(SECOND_PROFILE_PATH)
    second_evaluation = EvaluationRunner(second_profile).run()
    second_verification = verify_profile(second_profile)
    second_conformance = run_conformance(memory_bundle(second_profile))

    oversight_policy = ReviewLoadPolicy()
    oversight = run_queue_pressure_trial(
        profile, arrivals=40, policy=oversight_policy,
        reviewer=DeclaredReviewerModel(),
    )
    capacity = oversight_policy.sustainable_actions_per_day(REVIEWER_ROSTER)
    # The sweep exists because a single trial invites the objection that the
    # parameters were chosen to suit the result. It is generated, not optional.
    sweep = sweep_oversight(profile, arrivals=40)
    corpus = run_corpus(CHALLENGE_DIR)

    evaluation.write_json(output_dir / f"{tag}-student-support.json")
    (output_dir / f"{tag}-verification.json").write_text(
        json.dumps(verification.to_dict(), indent=2) + "\n", encoding="utf-8")
    memory_conformance.write_json(output_dir / f"{tag}-conformance-memory.json")
    sql_conformance.write_json(output_dir / f"{tag}-conformance-sql.json")
    (output_dir / f"{tag}-architecture-comparison.json").write_text(
        json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    (output_dir / f"{tag}-race.json").write_text(
        json.dumps(race.to_dict(), indent=2) + "\n", encoding="utf-8")
    second_evaluation.write_json(output_dir / f"{tag}-academic-record-correction.json")
    (output_dir / f"{tag}-second-domain-verification.json").write_text(
        json.dumps(second_verification.to_dict(), indent=2) + "\n", encoding="utf-8")
    second_conformance.write_json(output_dir / f"{tag}-conformance-second-domain.json")
    (output_dir / f"{tag}-oversight.json").write_text(
        json.dumps(oversight, indent=2) + "\n", encoding="utf-8")
    (output_dir / f"{tag}-oversight-sweep.json").write_text(
        json.dumps(sweep, indent=2) + "\n", encoding="utf-8")
    (output_dir / f"{tag}-adversary-corpus.json").write_text(
        json.dumps(corpus, indent=2) + "\n", encoding="utf-8")

    payload = evaluation.to_dict()
    summary = {
        "schema_version": "1.0",
        "kind": "paper-figures",
        "tag": tag,
        "software_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "note": (
            "Every figure the paper quotes is produced here. A number in the paper "
            "that this file does not contain is a drift bug, and the alignment test "
            "fails the build for it."
        ),
        "figures": {
            # containment
            "adversarial_scenarios_total": evaluation.total,
            "adversarial_scenarios_contained": evaluation.passed,
            "containment_rate": payload["containment"]["containment_rate"],
            "unauthorized_mutations": evaluation.unauthorized_mutations,
            # utility -- the denominator that makes containment meaningful
            "benign_tasks_total": len(evaluation.utility),
            "benign_tasks_completed": evaluation.benign_completed,
            "false_denial_rate": evaluation.false_denial_rate,
            # attribution
            "controls_ablated": evaluation.coverage.controls_declared,
            "controls_load_bearing": evaluation.coverage.controls_load_bearing,
            "authority_coverage": evaluation.coverage.authority_coverage,
            # bounded model checking
            "states_explored": verification.states_explored,
            "model_check_violations": len(verification.violations),
            "invariants_checked": len(verification.invariants),
            "distinct_denial_codes": len(
                [code for code in verification.outcome_histogram if code != "EXECUTED"]
            ),
            # controlled comparison against how agents are built today
            "arm_a_containment": by_arm["A"]["containment_rate"],
            "arm_b_containment": by_arm["B"]["containment_rate"],
            "arm_c_containment": by_arm["C"]["containment_rate"],
            "arm_a_harms": sum(by_arm["A"]["harms"].values()),
            "arm_b_harms": sum(by_arm["B"]["harms"].values()),
            "arm_c_harms": sum(by_arm["C"]["harms"].values()),
            "comparison_attacks": len(comparison["attacks"]),
            "benign_completion_all_arms": by_arm["C"]["benign_completion_rate"],
            # conformance
            "conformance_checks": len(memory_conformance.executed),
            "conformance_backends_verified": 2,
            # randomised property testing: attacks nobody wrote down
            "property_test_cases": _property_case_count(),
            "concurrent_callers": race.callers,
            "concurrent_replay_responses": race.replayed,
            "concurrent_mutations": race.mutations,
            "concurrent_distinct_receipts": race.distinct_receipts,
            # contract and tests
            "contract_requirements": _contract_count(),
            "control_contract_fields": 7,
            "test_count": _test_count(),
            # generalization: the same suite, a second domain, no library change
            "domains_verified": 2,
            "second_domain_states_explored": second_verification.states_explored,
            "second_domain_states_explored_display": (
                f"{second_verification.states_explored:,}"
            ),
            "second_domain_violations": len(second_verification.violations),
            "second_domain_scenarios_total": second_evaluation.total,
            "second_domain_scenarios_contained": second_evaluation.passed,
            "second_domain_benign_total": len(second_evaluation.utility),
            "second_domain_benign_completed": second_evaluation.benign_completed,
            "second_domain_authority_coverage": (
                second_evaluation.coverage.authority_coverage
            ),
            "second_domain_conformance_checks": len(second_conformance.executed),
            "defects_found_by_the_second_domain": 1,
            # oversight as a finite resource
            "oversight_arrivals": oversight["arrivals"],
            "oversight_harms_without_load_control": (
                oversight["summary"]["harmful_executed_without_load_control"]
            ),
            "oversight_harms_with_load_control": (
                oversight["summary"]["harmful_executed_with_load_control"]
            ),
            "oversight_deferred_to_manual": (
                oversight["summary"]["deferred_to_manual_fallback"]
            ),
            "oversight_demand_ratio": (
                oversight["summary"]["demand_to_declared_capacity"]["ratio"]
            ),
            "oversight_reviewer_roster": capacity["reviewers"],
            "oversight_sustainable_per_day": capacity["sustainable_per_day"],
            # Thousands-separated forms, so a claim template can be a readable
            # sentence instead of forcing the paper to write "3520".
            "oversight_sustainable_per_day_display": (
                f"{capacity['sustainable_per_day']:,.0f}"
            ),
            "oversight_binding_constraint": capacity["binding_constraint"],
            "oversight_policy_self_consistent": (
                oversight_policy.declared_consistency()["consistent"]
            ),
            # sensitivity: the answer to "you chose parameters that suited you"
            "sweep_cells_total": sweep["summary"]["cells_total"],
            "sweep_cells_harm_possible": sweep["summary"]["cells_where_harm_was_possible"],
            "sweep_cells_load_bearing": (
                sweep["summary"]["cells_where_the_control_was_load_bearing"]
            ),
            "sweep_cells_harm_reached_zero": sweep["summary"]["cells_where_harm_reached_zero"],
            "sweep_cells_did_not_bind": (
                sweep["summary"]["cells_where_the_control_did_not_bind"]
            ),
            "sweep_cells_nothing_to_contain": sweep["summary"]["cells_with_no_harm_to_contain"],
            "sweep_false_positive_deferrals": (
                sweep["summary"]["deferrals_where_there_was_no_harm_to_contain"]
            ),
            "sweep_smallest_floor_that_fully_contains": (
                sweep["summary"]["smallest_floor_that_fully_contains_everywhere"]
            ),
            # the open adversary corpus
            "corpus_size": corpus["corpus_size"],
            "corpus_live": corpus["live_challenges"],
            "corpus_contained_arm_a": corpus["contained_by_arm"]["A · unguarded"],
            "corpus_contained_arm_c": corpus["contained_by_arm"]["C · FSSAI-RA"],
            "corpus_externally_contributed": len(corpus["externally_contributed"]),
            # timings, so a reader knows the cost of reproducing this
            "evaluation_seconds": round(evaluation_seconds, 2),
            "verification_seconds": round(verification_seconds, 2),
        },
        "verdicts": {
            "all_scenarios_contained": evaluation.all_contained,
            "model_check_holds": verification.holds,
            "memory_profile_conformant": memory_conformance.passed,
            "sql_profile_conformant": sql_conformance.passed,
            "comparison_contains_every_attack": by_arm["C"]["attacks_succeeded"] == 0,
            "containment_costs_no_utility": (
                by_arm["C"]["benign_completion_rate"] >= by_arm["B"]["benign_completion_rate"]
            ),
            "bounded_concurrent_replay_holds": race.passed,
            "second_domain_model_check_holds": second_verification.holds,
            "second_domain_all_scenarios_contained": second_evaluation.all_contained,
            "second_domain_conformant": second_conformance.passed,
            "oversight_load_control_is_load_bearing": (
                oversight["summary"]["load_control_is_load_bearing"]
            ),
            "oversight_control_never_increased_harm": (
                sweep["summary"]["control_never_created_harm"]
            ),
            "oversight_policy_declaration_is_coherent": (
                oversight_policy.declared_consistency()["consistent"]
            ),
            "corpus_fully_contained": (
                corpus["contained_by_arm"]["C · FSSAI-RA"] == corpus["live_challenges"]
            ),
        },
        "limits": [
            (
                "one 32-caller replay race is evaluated in one process; arbitrary concurrent "
                "interleavings and distributed failure modes remain out of scope"
                if limit == "single process; concurrent interleavings are not evaluated here"
                else limit
            )
            for limit in payload["limits"]
        ] + [
            # The limits the new contributions bring with them. Stated here so
            # they travel with every generated artifact rather than living only
            # in a document someone has to remember to read.
            "the reviewer degradation curve is a declared parameter, not a measurement of any "
            "reviewer; no human was observed, and reviewer accuracy under load remains open work",
            "the oversight deferral count is the cost of the control, reported rather than netted "
            "off; refusing an approval preserves the boundary and delays the student",
            "the second domain tests that the method transfers, not that either domain's evidence "
            "applies to the other; each carries its own",
            "the adversary corpus is contributed attacks, not a threat catalogue, and no attack in "
            "it yet comes from outside this project",
        ],
    }
    (output_dir / f"{tag}-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _property_case_count() -> int:
    """How many randomly generated calls the property suite checks."""
    import re

    source = (ROOT / "tests" / "test_properties.py").read_text()
    cases = int(re.search(r"^CASES = ([\d_]+)", source, re.M).group(1).replace("_", ""))
    seeds = len(re.search(r"\[([^\]]+)\]\)\ndef test_the_property_holds", source).group(1).split(","))
    # main sweep (1–3 calls each, counted at the observed mean of 2) + two
    # half-size sweeps + the multi-seed sweep
    return cases * 2 + cases + 200 * seeds


def _contract_count() -> int:
    from fssaira.contract import ControlContract

    return len(ControlContract.load(str(ROOT / "contract")))


def _test_count() -> int:
    """Count collected tests by asking pytest, not by guessing from filenames."""
    import re
    import subprocess

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-header",
             "-p", "no:warnings"],
            cwd=ROOT, capture_output=True, text=True, timeout=300,
        )
    except Exception:  # pragma: no cover - pytest unavailable in a packaged install
        return 0
    # Quiet collection prints one "path/to/test_file.py: N" line per module.
    per_file = re.findall(r"^\S+\.py: (\d+)$", result.stdout, flags=re.MULTILINE)
    if per_file:
        return sum(int(count) for count in per_file)
    match = re.search(r"(\d+) tests? collected", result.stdout)
    return int(match.group(1)) if match else len(
        [line for line in result.stdout.splitlines() if "::" in line]
    )


def render_markdown(summary: dict) -> str:
    figures = summary["figures"]
    verdicts = summary["verdicts"]
    rows = [
        ("Adversarial scenarios contained",
         f"{figures['adversarial_scenarios_contained']}/{figures['adversarial_scenarios_total']}",
         "containment of sampled risk classes, not coverage of a threat catalogue"),
        ("Unauthorized mutations", str(figures["unauthorized_mutations"]),
         "across every denial scenario"),
        ("Benign tasks completed",
         f"{figures['benign_tasks_completed']}/{figures['benign_tasks_total']}",
         "the denominator that makes a containment rate meaningful"),
        ("False-denial rate", f"{figures['false_denial_rate']}",
         "a system that denies everything scores perfectly on containment"),
        ("Authority coverage", f"{figures['authority_coverage']}",
         f"{figures['controls_load_bearing']}/{figures['controls_ablated']} controls restored "
         "their harm when removed"),
        ("States explored (model check)", f"{figures['states_explored']:,}",
         f"{figures['invariants_checked']} invariants, {figures['model_check_violations']} violations"),
        ("Distinct denial controls reached", str(figures["distinct_denial_codes"]),
         "each one exercised by at least one configuration"),
        ("Attacks contained — unguarded arm", f"{round(figures['arm_a_containment'] * 100)}%",
         f"{figures['arm_a_harms']} harmful actions reached the protected asset"),
        ("Attacks contained — prompt-guarded arm", f"{round(figures['arm_b_containment'] * 100)}%",
         f"{figures['arm_b_harms']} harmful actions; an allowlist is a real control"),
        ("Attacks contained — this architecture", f"{round(figures['arm_c_containment'] * 100)}%",
         f"{figures['arm_c_harms']} harmful actions, at no cost to benign completion"),
        ("Conformance checks", str(figures["conformance_checks"]),
         f"passed on {figures['conformance_backends_verified']} independent backend profiles"),
        ("Concurrent replay race",
         f"{figures['concurrent_mutations']} mutation from {figures['concurrent_callers']} callers",
         f"{figures['concurrent_replay_responses']} replay responses, "
         f"{figures['concurrent_distinct_receipts']} distinct receipt; bounded to one process"),
        ("Control-contract requirements", str(figures["contract_requirements"]),
         f"{figures['control_contract_fields']} fields each"),
        ("Deterministic tests", str(figures["test_count"]), "no network, no model weights"),
    ]
    # Kept in a separate block because these answer different questions from the
    # containment table above, and merging them would invite reading an oversight
    # deferral count as though it were a containment failure.
    rows += [
        ("Oversight — sustainable review",
         f"{figures['oversight_sustainable_per_day']:,.0f}/day",
         f"for a roster of {figures['oversight_reviewer_roster']}, bound by the "
         f"{figures['oversight_binding_constraint'].replace('_', ' ')}; declared capacity, "
         "not a measurement of reviewers"),
        ("Oversight — merit failures executed",
         f"{figures['oversight_harms_without_load_control']} → "
         f"{figures['oversight_harms_with_load_control']}",
         "without load control, then with it, on a queue at "
         f"{figures['oversight_demand_ratio']}x declared attentive capacity"),
        ("Oversight — sensitivity sweep",
         f"{figures['sweep_cells_load_bearing']}/{figures['sweep_cells_harm_possible']}",
         f"cells where the control was load-bearing out of those where harm was possible; "
         f"harm reached zero in {figures['sweep_cells_harm_reached_zero']}; "
         f"{figures['sweep_cells_did_not_bind']} did not bind (no deliberation floor configured); "
         f"{figures['sweep_cells_nothing_to_contain']} had no harm to contain"),
        ("Oversight — false-positive cost",
         str(figures["sweep_false_positive_deferrals"]),
         "deferrals across the whole sweep where there was no harm to contain; an "
         "attentive reviewer is not throttled by the shipped policy"),
        ("Oversight — smallest floor that fully contains",
         f"{figures['sweep_smallest_floor_that_fully_contains']:g}s",
         "across every swept cell where harm was possible; the number an institution needs "
         "to set its own policy"),
        ("Oversight — deferred to manual review",
         str(figures["oversight_deferred_to_manual"]),
         "the cost of the control, and a measurement of demand against declared capacity"),
        ("Second domain — states explored",
         f"{figures['second_domain_states_explored']:,}",
         f"{figures['second_domain_violations']} violations; the identical suite, no library change"),
        ("Second domain — containment and utility",
         f"{figures['second_domain_scenarios_contained']}/"
         f"{figures['second_domain_scenarios_total']}, "
         f"{figures['second_domain_benign_completed']}/{figures['second_domain_benign_total']}",
         f"its own evidence, borrowed from no other domain; "
         f"{figures['second_domain_conformance_checks']} conformance checks"),
        ("Second domain — defects it exposed",
         str(figures["defects_found_by_the_second_domain"]),
         "a declared approval role ignored on non-consequential transitions; unreachable with one domain"),
        ("Adversary corpus — contained",
         f"{figures['corpus_contained_arm_c']}/{figures['corpus_live']}",
         f"unguarded arm contained {figures['corpus_contained_arm_a']}; contributed attacks, "
         "not a threat catalogue"),
        ("Adversary corpus — externally contributed",
         str(figures["corpus_externally_contributed"]),
         "the figure that matters; until it is non-zero the corpus samples the maintainers' imagination"),
    ]
    lines = [
        f"# Results — {summary['tag']}",
        "",
        f"Generated {summary['generated_at']} on Python {summary['environment']['python_version']}, "
        f"{summary['environment']['platform']}.",
        "",
        "Regenerate with `python scripts/generate_results.py`. Every figure the paper quotes "
        "comes from this table, and `tests/test_paper_alignment.py` fails the build if the two "
        "disagree.",
        "",
        "| Measure | Result | What it does and does not mean |",
        "|---|---|---|",
    ]
    lines += [f"| {name} | `{value}` | {note} |" for name, value, note in rows]
    lines += [
        "",
        "## Verdicts",
        "",
        f"- All declared scenarios contained: **{verdicts['all_scenarios_contained']}**",
        f"- Authority invariants hold under bounded model checking: **{verdicts['model_check_holds']}**",
        f"- In-memory profile conformant: **{verdicts['memory_profile_conformant']}**",
        f"- Transactional SQL profile conformant: **{verdicts['sql_profile_conformant']}**",
        f"- Second domain conformant under the identical suite: **{verdicts['second_domain_conformant']}**",
        f"- Second domain invariants hold: **{verdicts['second_domain_model_check_holds']}**",
        f"- Review-load control is load-bearing: **{verdicts['oversight_load_control_is_load_bearing']}**",
        f"- The control never increased harm in any swept cell: "
        f"**{verdicts['oversight_control_never_increased_harm']}**",
        f"- The shipped review policy is self-consistent: "
        f"**{verdicts['oversight_policy_declaration_is_coherent']}**",
        f"- Contributed adversary corpus fully contained: **{verdicts['corpus_fully_contained']}**",
        "",
        "## Cost of reproduction",
        "",
        f"The adversarial suite runs in {figures['evaluation_seconds']}s and the bounded model "
        f"check in {figures['verification_seconds']}s on the machine above, with no network "
        "access and no model weights. A second institution can therefore check these numbers "
        "rather than trust them.",
        "",
        "## Limits",
        "",
    ]
    lines += [f"- {limit}" for limit in summary["limits"]]
    lines += [
        "",
        "These are fixture observations in a declared environment. They are not security "
        "probabilities, not a certification, and not evidence of production readiness. See "
        "[`docs/ASSURANCE.md`](../../docs/ASSURANCE.md) for the claim-by-claim boundary.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=f"v{__version__}")
    parser.add_argument("--check", action="store_true",
                        help="regenerate into a temporary directory and compare figures")
    args = parser.parse_args()

    if args.check:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            fresh = generate(Path(directory), args.version)
        committed_path = RESULTS_DIR / f"{args.version}-summary.json"
        if not committed_path.exists():
            print(f"no committed summary at {committed_path}")
            return 1
        committed = json.loads(committed_path.read_text())
        drift = {
            key: (committed["figures"].get(key), value)
            for key, value in fresh["figures"].items()
            # Timings vary by machine; the test count is a repository statistic
            # that grows as contributors add tests. Neither is a scientific
            # result, so neither may fail a drift check.
            if key not in ("evaluation_seconds", "verification_seconds", "test_count")
            and committed["figures"].get(key) != value
        }
        if drift:
            print("committed results have drifted:")
            for key, (was, now) in drift.items():
                print(f"  {key}: committed {was}, regenerated {now}")
            return 1
        print(f"committed results match a fresh run ({len(fresh['figures'])} figures)")
        return 0

    summary = generate(RESULTS_DIR, args.version)
    (RESULTS_DIR / "RESULTS.md").write_text(render_markdown(summary), encoding="utf-8")
    print(json.dumps(summary["figures"], indent=2))
    print(f"\nwrote {args.version} artifacts to {RESULTS_DIR}")
    return 0 if all(summary["verdicts"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
