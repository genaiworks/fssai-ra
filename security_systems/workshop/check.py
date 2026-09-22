"""Run with python -m workshop.check --implementation starter|step1|step2|solution.

The sink records actual releases. Denials are diagnostics, not the security oracle.
"""
import argparse
import importlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from trustkernel.guard import Guard
from trustkernel.kernel.disclosure import DisclosureDenied
from trustkernel.kernel.exact_action import ExecutionDenied

PACK = Path(__file__).resolve().parents[1] / "worlds/devtools/pack.yaml"
CASES = ("metrics", "secret_public", "secret_security", "reset_session", "failed_read", "two_handoffs", "unknown_recipient")


@dataclass
class Result:
    case: str
    passed: bool
    released: list[str]
    denial: str | None
    label_retained: bool


def evaluate(implementation, case):
    if case not in CASES:
        raise ValueError(f"unknown exercise: {case}")
    guard = Guard.from_pack(PACK)
    reader = guard.root("reader", tools=set())
    summary = guard.root("summary", tools=set())
    publisher = guard.root("publisher", tools=set())
    sink = []
    denial = None
    recipient, purpose = "slack_general", "incident-triage"
    if case == "secret_security":
        recipient, purpose = "security_team", "secret-rotation"
    if case == "unknown_recipient":
        recipient = "undeclared_channel"
    if case in {"metrics", "unknown_recipient"}:
        guard.observe(reader, {"build-telemetry"})
        text = "p99=212ms"
    else:
        try:
            text = implementation.read_secret(guard, reader, fail=case == "failed_read")
        except RuntimeError:
            if case != "failed_read":
                raise
            # Model a value exposed before the read callback lost its receipt.
            text = implementation.SECRET if hasattr(implementation, "SECRET") else "SYNTHETIC-WORKSHOP-SECRET"
    try:
        text = implementation.handoff(guard, reader, summary, text)
        if case == "two_handoffs":
            text = implementation.handoff(guard, summary, publisher, text)
            summary = publisher
        if case == "reset_session":
            summary = replace(summary, session="attacker-chosen-fresh-session")
        released = implementation.publish(guard, summary, text, recipient=recipient, purpose=purpose)
        sink.append(released)
    except (DisclosureDenied, ExecutionDenied) as exc:
        denial = exc.code
    label_retained = "secret-credentials" in guard.label(reader)
    should_release = case in {"metrics", "secret_security"}
    passed = sink == [text] if should_release else sink == []
    if case == "failed_read":
        passed = passed and label_retained
    return Result(case, passed, sink, denial, label_retained)


def load(name):
    module = f"workshop.checkpoints.{name}" if name.startswith("step") else f"workshop.{name}"
    return importlib.import_module(module)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation", choices=("starter", "step1", "step2", "solution"), default="starter")
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    implementation = load(args.implementation)
    results = [evaluate(implementation, case) for case in ([args.case] if args.case else CASES)]
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        for result in results:
            print(f"{'PASS' if result.passed else 'FAIL'} {result.case}: "
                  f"releases={len(result.released)} denial={result.denial or 'none'}")
        print(f"{sum(r.passed for r in results)}/{len(results)} checks passed; "
              "failures are expected in the starter and intermediate checkpoints.")
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
