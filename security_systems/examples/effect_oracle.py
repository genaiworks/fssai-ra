"""A reusable effect oracle. Run: python examples/effect_oracle.py.

This miniature uses only the standard library; it is deliberately independent of
trustkernel's decision logs. The application supplies an independent observer.
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trustkernel.evaluation import Refused, observe_attempt  # noqa: E402


def demonstrate():
    rows = []
    for mode in ("reject_before_write", "write_then_reject", "control_removed", "legitimate_write"):
        record = {"build": "v1"}
        requested = "reviewed-v2" if mode == "legitimate_write" else "unreviewed-v9"

        def attempt(mode=mode, record=record, requested=requested):
            if mode == "reject_before_write":
                raise Refused("denied")
            record["build"] = requested
            if mode == "write_then_reject":
                raise Refused("denied after effect")

        observed = observe_attempt(attempt, lambda record=record: record,
                                   lambda before, after: after["build"] == "unreviewed-v9")
        # A useful control must also let the reviewed operation complete.
        passed = not observed.harmful_effect
        if mode in {"write_then_reject", "control_removed"}:
            passed = observed.harmful_effect  # positive controls must expose the harm
        if mode == "legitimate_write":
            passed = passed and observed.after["build"] == "reviewed-v2"
        rows.append({"case": mode, **asdict(observed), "experiment_passed": passed})
    return rows


if __name__ == "__main__":
    rows = demonstrate()
    print(json.dumps(rows, indent=2))
    raise SystemExit(0 if all(row["experiment_passed"] for row in rows) else 1)
