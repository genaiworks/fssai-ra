"""Command-line entry points for the lifecycle stages.

``fssaira frame | contract --gate | bind | falsify`` run one stage each. They
exit 0 when every gate passes and 1 when any gate fails, so a pipeline stops at
the first failed gate. ``--json`` prints the stage result and ``--out`` (or
``--output`` for ``contract``) writes it as the stage's artifact.

``fssaira contract`` predates the lifecycle and shows the contract. Stage 2 is
therefore the opt-in ``--gate`` flag on that command rather than a second parser
with the same name.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from fssaira.lifecycle import stages


def _common(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--json", action="store_true", help="print the stage result as JSON")
    parser.add_argument("--out", type=Path, help="write the stage result (the stage artifact) to this file")
    return parser


def _root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=Path("."),
                        help="repository root holding contract/, tests/ and src/ (default: current directory)")


def _finish(result: stages.StageResult, args: argparse.Namespace) -> int:
    payload = result.to_dict()
    if args.out is not None:
        Path(args.out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"stage {result.stage}: {'PASS' if result.passed else 'FAIL'}")
        for gate in result.gates:
            print(f"  [{'PASS' if gate.passed else 'FAIL'}] {gate.gate}: {gate.detail}")
    return 0 if result.passed else 1


def cmd_frame(args: argparse.Namespace) -> int:
    return _finish(stages.frame(args.path), args)


def cmd_pack(args: argparse.Namespace) -> int:
    return _finish(stages.pack(args.root.resolve(), paths=args.paths or None, evaluate=args.evaluate), args)


def register_pack(sub: argparse._SubParsersAction) -> None:
    """``fssaira pack``: lifecycle stage 3."""
    parser = _common(sub.add_parser(
        "pack", help="lifecycle 3: packs load drift-free at or above the kernel floor"))
    _root(parser)
    parser.add_argument("paths", nargs="*", type=Path,
                        help="pack manifests (default: every packs/*.pack.yaml except the template)")
    parser.add_argument("--evaluate", action="store_true",
                        help="also regenerate each pack's evidence and require it complete")
    parser.set_defaults(func=cmd_pack)


def cmd_bind(args: argparse.Namespace) -> int:
    return _finish(stages.bind(args.root.resolve()), args)


def cmd_falsify(args: argparse.Namespace) -> int:
    return _finish(stages.falsify(args.root.resolve(), include_ablation=not args.no_ablation,
                                  conference_only=args.only or None), args)


def cmd_promote(args: argparse.Namespace) -> int:
    return _finish(stages.promote(
        args.root.resolve(), profile_path=args.profile, backends=args.backend or (),
        records_path=args.records, obligations_path=args.obligations, interfaces_path=args.interfaces,
        falsify_artifact=args.falsify_artifact, rerun_conformance=not args.no_rerun_conformance), args)


def register_promote(sub: argparse._SubParsersAction) -> None:
    """``fssaira promote``: lifecycle stage 6."""
    parser = _common(sub.add_parser(
        "promote", help="lifecycle 6: run every gate the deployment profile requires"))
    _root(parser)
    parser.add_argument("--profile", type=Path, required=True, help="deploy/profiles/<name>.yaml")
    parser.add_argument("--backend", action="append", help="a backend this deployment uses (repeatable)")
    parser.add_argument("--records", type=Path, action="append",
                        help="conformance records JSON (fssaira.kernel.assurance); repeatable, "
                             "one file per backend")
    parser.add_argument("--obligations", type=Path, help="signed Table 4 obligations record YAML")
    parser.add_argument("--interfaces", type=Path, help="interface inventory YAML")
    parser.add_argument("--falsify-artifact", type=Path, help="JSON written by `fssaira falsify --out`")
    parser.add_argument("--no-rerun-conformance", action="store_true",
                        help="trust the records without a fresh memory/sqlite conformance run")
    parser.set_defaults(func=cmd_promote)


def cmd_operate(args: argparse.Namespace) -> int:
    result = stages.operate(args.root.resolve(), falsify_artifact=args.falsify_artifact,
                            allow_not_run=getattr(args, "allow_not_run", False))
    code = _finish(result, args)
    if not args.json:
        for item in result.artifact.get("not_run", []):
            print(f"  [NOT RUN] {item['gate']}: {item['reason']}")
    return code


def add_contract_gate(parser: argparse.ArgumentParser, *, show: Callable[[argparse.Namespace], int]) -> None:
    """Turn the existing ``fssaira contract`` command into stage 2 when ``--gate`` is given.

    Without ``--gate`` the command behaves exactly as before and shows the
    contract. With it, ``--output`` receives the stage artifact and the
    repository root is the parent of the contract directory.
    """
    parser.add_argument("--gate", action="store_true",
                        help="lifecycle 2: fail unless seven fields are filled, named tests exist, "
                             "and no claim is unverified")
    parser.add_argument("--register-out", type=Path, help="with --gate: write the claims register YAML here")
    parser.add_argument("--json", action="store_true", help="with --gate: print the stage result as JSON")

    def dispatch(args: argparse.Namespace) -> int:
        if not args.gate:
            return show(args)
        root = Path(args.contract_directory).resolve().parent
        args.out = args.output
        return _finish(stages.contract(root, register_out=args.register_out), args)

    parser.set_defaults(func=dispatch)


def register(sub: argparse._SubParsersAction) -> None:
    """Add the lifecycle stage commands (other than ``contract``) to ``fssaira``."""
    frame = _common(sub.add_parser("frame", help="lifecycle 1: frame one consequential capability"))
    frame.add_argument("path", type=Path, help="framing YAML: capability, asset, harm, owner, fallback")
    frame.set_defaults(func=cmd_frame)

    register_pack(sub)

    bind = _common(sub.add_parser("bind", help="lifecycle 4: fail if any model holds a key or credential"))
    _root(bind)
    bind.set_defaults(func=cmd_bind)

    falsify = _common(sub.add_parser(
        "falsify", help="lifecycle 5: falsifiers with a positive control, and control ablation"))
    _root(falsify)
    falsify.add_argument("--only", action="append", help="conference falsifier id (repeatable)")
    falsify.add_argument("--no-ablation", action="store_true", help="skip the ablation gate")
    falsify.set_defaults(func=cmd_falsify)

    register_promote(sub)

    operate = _common(sub.add_parser(
        "operate", help="lifecycle 7: fail if the governed configuration changed since falsification"))
    _root(operate)
    operate.add_argument("--falsify-artifact", type=Path,
                         help="JSON written by `fssaira falsify --out`")
    operate.add_argument("--allow-not-run", action="store_true",
                         help="offline check: report live gates (reconciliation, review capacity) as NOT RUN "
                              "instead of failing")
    operate.set_defaults(func=cmd_operate)
