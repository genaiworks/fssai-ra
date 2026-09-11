"""Reproduce the supplemental process/crash evidence without changing v1.0.0.

Run from the project directory. Use --write after reviewing an intentional change.
The committed report includes hashes of the effective profile and tested source.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fssaira.profiles import ApplicationProfile  # noqa: E402
from fssaira.resilience import run_resilience  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="replace the supplemental report")
    args = parser.parse_args()
    destination = ROOT / "evaluation/results/resilience-student-support.json"
    report = run_resilience(ApplicationProfile.load(ROOT / "profiles/student_support.yaml"))
    payload = report.to_dict()
    encoded = json.dumps(payload, indent=2) + "\n"
    if args.write:
        destination.write_text(encoded, encoding="utf-8")
        print(f"Wrote {destination}")
    elif not destination.exists() or json.loads(destination.read_text()) != json.loads(encoded):
        print("Supplemental resilience evidence differs. Review changes and run --write.")
        return 1
    print(f"Two process races and four abrupt-exit recovery cases: {'PASS' if report.passed else 'FAIL'}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
