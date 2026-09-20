#!/usr/bin/env python3
"""Regenerate or verify conference/evidence/adaptive-results.json.

The adaptive attacker is deterministic for a seed, so the committed artifact must
match a fresh run. This mirrors the pattern of check_resilience.py and keeps the
adaptive numbers the paper quotes honest.

    python scripts/adaptive_evidence.py            # verify (non-zero if drifted)
    python scripts/adaptive_evidence.py --write     # regenerate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fssaira.adaptive_attack import run_adaptive  # noqa: E402

DESTINATION = ROOT / "conference" / "evidence" / "adaptive-results.json"
BUDGET, SEED = 300, 20260921


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="regenerate the artifact")
    # --check is a no-op alias for the default verify mode, so this script reads
    # the same as scripts/conference_evidence.py --check for a reviewer.
    parser.add_argument("--check", action="store_true",
                        help="verify the committed artifact matches a fresh run (the default)")
    args = parser.parse_args()
    report = run_adaptive(budget=BUDGET, seed=SEED, split="all", prove_attacker=True)
    encoded = json.dumps(report.to_dict(), indent=2, default=str) + "\n"
    if args.write:
        DESTINATION.write_text(encoded, encoding="utf-8")
        print(f"Wrote {DESTINATION}")
        return 0
    if not DESTINATION.exists() or json.loads(DESTINATION.read_text()) != json.loads(encoded):
        print("Adaptive evidence differs from a fresh run. Review and run --write.")
        return 1
    total = report.total_forbidden
    pc = report.positive_control["forbidden_outcomes"]
    print(f"Adaptive attack reproduced: {total} forbidden with all controls on, "
          f"{pc} with the execution mediator removed (positive control).")
    return 0 if total == 0 and pc > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
