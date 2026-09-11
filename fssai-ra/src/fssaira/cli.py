"""Command-line interface for profile validation and adversarial evaluation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contract import ControlContract
from .evaluation import EvaluationRunner
from .profiles import ApplicationProfile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fssaira")
    subcommands = parser.add_subparsers(dest="command", required=True)

    validate_profile = subcommands.add_parser("validate-profile", help="validate a domain profile")
    validate_profile.add_argument("profile", type=Path)

    validate_contract = subcommands.add_parser("validate-contract", help="validate control-contract YAML")
    validate_contract.add_argument("contract_directory", type=Path)

    evaluate = subcommands.add_parser("evaluate", help="run adversarial exact-action scenarios")
    evaluate.add_argument("profile", type=Path)
    evaluate.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate-profile":
        profile = ApplicationProfile.load(args.profile)
        print(f"valid profile: {profile.profile_id} v{profile.version} ({len(profile.transitions)} transitions)")
        return 0
    if args.command == "validate-contract":
        contract = ControlContract.load(args.contract_directory)
        contract.validate()
        print(f"valid contract: {len(contract)} requirements")
        return 0

    profile = ApplicationProfile.load(args.profile)
    report = EvaluationRunner(profile).run()
    rendered = json.dumps(report.to_dict(), indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(rendered)
    return 0 if report.all_contained else 1


if __name__ == "__main__":
    raise SystemExit(main())
