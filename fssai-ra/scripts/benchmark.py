"""What does the governance layer cost?

A reviewer is entitled to ask, and "negligible" is not an answer. This measures
the added latency of the enforcement path against doing the same work with no
checks at all, on the machine it is run on, and prints the distribution rather
than a single flattering mean.

    python scripts/benchmark.py [--iterations 20000] [--output results.json]

What is measured:

* **Policy decision** — one tool call through the enforcement point, including
  the catalogue lookup, the grant check, argument inspection, and the evidence
  append, against a bare function call that does none of it.
* **Accountable execution** — a full propose → approve → execute cycle,
  including signature verification, digest binding, and two evidence records.
* **Evidence chain verification** — recomputing a whole chain, which is what an
  independent monitor does on a schedule.
* **Bounded model check** — the whole authority space of a profile.

What is *not* measured, and must not be inferred: model inference latency, which
dominates any real deployment and is a property of the model an institution
chooses; network and database round trips; or throughput under concurrency. This
is the cost of the *governance*, isolated, which is the only part this
architecture is responsible for.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def percentiles(samples: list[float]) -> dict:
    ordered = sorted(samples)
    def at(fraction: float) -> float:
        return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]
    return {
        "n": len(ordered),
        "mean_us": round(statistics.fmean(ordered) * 1e6, 2),
        "median_us": round(statistics.median(ordered) * 1e6, 2),
        "p95_us": round(at(0.95) * 1e6, 2),
        "p99_us": round(at(0.99) * 1e6, 2),
        "max_us": round(ordered[-1] * 1e6, 2),
    }


def bench_policy_decision(iterations: int) -> dict:
    from fssaira import ActionClass, FSSAIRAPipeline, ToolCall

    pipeline = FSSAIRAPipeline(enforce_call_budget=False)
    agent = pipeline.make_agent(
        "bench", tools={"read_case", "prepare_recommendation"},
        operations={"read_case", "prepare_recommendation"},
    )
    call = ToolCall("bench", "read_case", "read_case", target="S-104",
                    action_class=ActionClass.REVERSIBLE, args={"target": "S-104"})

    # Baseline: the same work with no governance at all.
    def unchecked() -> dict:
        return {"case": "S-104", "status": "read"}

    baseline, guarded = [], []
    for _ in range(iterations):
        start = time.perf_counter()
        unchecked()
        baseline.append(time.perf_counter() - start)

        start = time.perf_counter()
        pipeline.pep.check(call, agent.agent)
        guarded.append(time.perf_counter() - start)

    return {
        "unchecked_call": percentiles(baseline),
        "enforced_call": percentiles(guarded),
        "overhead_us": round(
            (statistics.fmean(guarded) - statistics.fmean(baseline)) * 1e6, 2
        ),
        "note": (
            "includes the catalogue lookup, grant check, argument inspection, and the "
            "hash-chained evidence append"
        ),
    }


def bench_accountable_execution(iterations: int) -> dict:
    from fssaira import ApplicationProfile, ControlPlane

    profile = ApplicationProfile.load(ROOT / "profiles" / "student_support.yaml")
    samples = []
    for index in range(iterations):
        plane = ControlPlane(profile)
        plane.register_resource(f"B-{index}", status="draft", version=1)
        start = time.perf_counter()
        proposal = plane.propose(
            requester="bench-agent", operation="prepare_case_for_review",
            resource_id=f"B-{index}", from_status="draft",
            to_status="ready_for_officer_review", evidence_version="snap-1",
        )
        plane.approve(proposal.request_id, approver="officer.one",
                      approver_role="student_support_officer")
        plane.execute(proposal.request_id)
        samples.append(time.perf_counter() - start)
    return {
        **percentiles(samples),
        "note": "full propose → approve → execute: HMAC sign and verify, digest "
                "binding, version check, two hash-chained evidence records",
    }


def bench_evidence_verification(chain_lengths: tuple[int, ...]) -> dict:
    from fssaira import EvidenceLedger

    out = {}
    for length in chain_lengths:
        ledger = EvidenceLedger("bench-token")
        for index in range(length):
            ledger.append("action_outcome", {"request_id": f"r{index}"}, token="bench-token")
        start = time.perf_counter()
        assert ledger.verify()
        elapsed = time.perf_counter() - start
        out[f"{length}_records_ms"] = round(elapsed * 1e3, 2)
    out["note"] = "what an independent monitor does on a schedule; linear in chain length"
    return out


def bench_model_check() -> dict:
    from fssaira.profiles import ApplicationProfile
    from fssaira.verification import verify_profile

    profile = ApplicationProfile.load(ROOT / "profiles" / "student_support.yaml")
    start = time.perf_counter()
    report = verify_profile(profile)
    elapsed = time.perf_counter() - start
    return {
        "states_explored": report.states_explored,
        "elapsed_ms": round(elapsed * 1e3, 2),
        "us_per_state": round(elapsed / report.states_explored * 1e6, 2),
        "note": "each state executes the real enforcement code, not a model of it",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--iterations", type=int, default=5_000)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report = {
        "schema_version": "1.0",
        "kind": "benchmark",
        "environment": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "processor": platform.processor() or "unknown",
        },
        "policy_decision": bench_policy_decision(args.iterations),
        "accountable_execution": bench_accountable_execution(min(args.iterations, 2_000)),
        "evidence_verification": bench_evidence_verification((100, 1_000, 10_000)),
        "bounded_model_check": bench_model_check(),
        "not_measured": [
            "model inference latency, which dominates any real deployment and is a "
            "property of the model an institution chooses",
            "network and database round trips",
            "throughput under concurrency",
        ],
    }

    policy = report["policy_decision"]
    execution = report["accountable_execution"]
    print("\n  Governance cost — measured, not asserted\n")
    print(f"  policy decision          median {policy['enforced_call']['median_us']:>8.2f} µs"
          f"   p99 {policy['enforced_call']['p99_us']:>8.2f} µs")
    print(f"  … of which is overhead          {policy['overhead_us']:>8.2f} µs"
          f"   over an unchecked call")
    print(f"  propose→approve→execute  median {execution['median_us']:>8.2f} µs"
          f"   p99 {execution['p99_us']:>8.2f} µs")
    print(f"  verify a 10,000 record chain    "
          f"{report['evidence_verification']['10000_records_ms']:>8.2f} ms")
    print(f"  bounded model check             "
          f"{report['bounded_model_check']['elapsed_ms']:>8.2f} ms"
          f"   for {report['bounded_model_check']['states_explored']} states")
    print("\n  Not measured: model inference, which dominates any real deployment.\n")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"  wrote {args.output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
