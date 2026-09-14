"""Red-team mode: point an attacker at the governed university and count what gets through.

    python scripts/conference_redteam.py                       # seeded grammar attacker, 300 attempts
    python scripts/conference_redteam.py --remove context_gate # the same attacks without one control
    python scripts/conference_redteam.py --ollama              # a local model tries instead

The objective is not to make the AI behave. It is to make the AI try to break the system,
and to judge the result by what reached a model, what was released, and what changed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fssaira.redteam import GrammarAttacker, OllamaRedTeam, run_redteam  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--attempts", type=int, default=300)
    parser.add_argument("--seed", type=int, default=1125)
    parser.add_argument("--remove", action="append", default=[])
    parser.add_argument("--ollama", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.ollama:
        attacker = OllamaRedTeam()
        if not attacker.available():
            print("no local Ollama runtime is reachable; nothing was run")
            return 2
    else:
        attacker = GrammarAttacker(seed=args.seed)
    report = run_redteam(attacker, attempts=args.attempts, remove=args.remove).to_dict()
    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0
    removed = f" with {', '.join(args.remove)} removed" if args.remove else ""
    print(f"red team: {report['attacker']}{removed}")
    for move, row in report["by_move"].items():
        print(f"  {move:<24} {row['attempts']:>4} attempts  {row['violations']:>3} succeeded")
    print(f"  total: {report['attempts']} attempts, {report['violations']} succeeded")
    return 0 if report["violations"] == 0 or args.remove else 1


if __name__ == "__main__":
    raise SystemExit(main())
