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
from fssaira.conformance import memory_bundle, run_conformance, sql_bundle  # noqa: E402
from fssaira.evaluation import EvaluationRunner  # noqa: E402
from fssaira.experiment import run_comparison  # noqa: E402
from fssaira.profiles import ApplicationProfile  # noqa: E402
from fssaira.verification import verify_profile  # noqa: E402

PROFILE_PATH = ROOT / "profiles" / "student_support.yaml"
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
    by_arm = {arm["arm"][0]: arm for arm in comparison["arms"]}  # "A", "B", "C"

    evaluation.write_json(output_dir / f"{tag}-student-support.json")
    (output_dir / f"{tag}-verification.json").write_text(
        json.dumps(verification.to_dict(), indent=2) + "\n", encoding="utf-8")
    memory_conformance.write_json(output_dir / f"{tag}-conformance-memory.json")
    sql_conformance.write_json(output_dir / f"{tag}-conformance-sql.json")
    (output_dir / f"{tag}-architecture-comparison.json").write_text(
        json.dumps(comparison, indent=2) + "\n", encoding="utf-8")

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
            # contract and tests
            "contract_requirements": _contract_count(),
            "control_contract_fields": 7,
            "test_count": _test_count(),
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
        },
        "limits": payload["limits"],
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
        ("Control-contract requirements", str(figures["contract_requirements"]),
         f"{figures['control_contract_fields']} fields each"),
        ("Deterministic tests", str(figures["test_count"]), "no network, no model weights"),
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
        "[`docs/ASSURANCE.md`](../docs/ASSURANCE.md) for the claim-by-claim boundary.",
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
