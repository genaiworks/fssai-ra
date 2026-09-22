"""Command line: ``trustkernel <command> [--world devtools]``.

Every command runs offline against a synthetic world and prints either a table for a
person or, with ``--json``, the full result for a machine.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import __version__
from .world import ALL_CONTROLS, WorldSpec, WorldSpecError, available_worlds


def _emit(args, payload, table) -> int:
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        table()
    return 0


def cmd_worlds(args) -> int:
    if args.ids:
        print(" ".join(available_worlds()))
        return 0
    rows = [WorldSpec.load(name).to_summary() for name in available_worlds()]

    def table():
        for row in rows:
            print(f"{row['world_id']:<12} {row['title']}")
            print(f"{'':<12} {row['subjects']} subjects · {row['principals']} principals · "
                  f"{row['agents']} agents · {row['resources']} resources · pack {row['pack']}")
    return _emit(args, rows, table)


def cmd_demo(args) -> int:
    from .demo import run

    run(args.world, args.scene, pause=args.pause, color=False if args.no_color else None)
    return 0


def cmd_falsify(args) -> int:
    from .falsification import run_falsifiers

    results = run_falsifiers(args.only or None, world=args.world)

    def table():
        for r in results:
            mark = "HELD    " if r.held else "VIOLATED"
            codes = sorted({a.code for a in r.attempts if a.code})
            print(f"{r.id}  {mark}  {r.name:<28} {r.property}   [{', '.join(codes)}]")
        print(f"\n{sum(r.held for r in results)} of {len(results)} held in world '{args.world}'.")
    _emit(args, [r.to_dict() for r in results], table)
    return 0 if all(r.held for r in results) else 1


def cmd_ablate(args) -> int:
    from .falsification import run_ablation

    rows = run_ablation(args.only or None, world=args.world)

    def table():
        for row in rows:
            d = row.to_dict()
            print(f"{d['falsifier']}  {d['control']:<46} enabled {d['enabled']:<9} disabled {d['disabled']:<9} "
                  f"restored {d['restored']:<9} {d['load_bearing']}")
        print(f"\nIn {sum(r.load_bearing for r in rows)} of {len(rows)} ablations the harm returned "
              f"(world '{args.world}').")
    _emit(args, [r.to_dict() for r in rows], table)
    return 0 if all(r.enabled == 0 and r.restored == 0 for r in rows) else 1


def cmd_delegation(args) -> int:
    from .delegation_eval import ablate_delegation, run_delegation_suite

    report = run_delegation_suite(world=args.world)
    ablation = ablate_delegation(world=args.world)

    def table():
        for arm, row in report.to_dict()["arms"].items():
            print(f"{arm:<18} contained {row['contained']:>2} of {row['of']}   "
                  f"benign chain completed: {row['benign_chain_completed']}")
        print()
        for row in ablation:
            print(f"{row['control']:<30} {row['scenario']:<30} load-bearing: {row['load_bearing']}")
    _emit(args, {**report.to_dict(), "ablation": ablation}, table)
    return 0 if report.holds else 1


def cmd_redteam(args) -> int:
    from .redteam import GrammarAttacker, OllamaRedTeam, run_redteam

    spec = WorldSpec.load(args.world)
    attacker = OllamaRedTeam(spec) if args.live else GrammarAttacker(spec, seed=args.seed)
    if args.live and not attacker.available():
        print("NOT RUN: no Ollama runtime reachable at http://localhost:11434", file=sys.stderr)
        return 2
    report = run_redteam(attacker, attempts=args.attempts, seed=7, remove=args.remove)

    def table():
        for move, row in sorted(report.by_move.items()):
            print(f"{move:<24} {row['attempts']:>4} attempts  {row['violations']:>4} violations")
        removed = f" with {', '.join(report.controls_removed)} removed" if report.controls_removed else ""
        print(f"\n{report.violations} violations in {report.attempts} attacks{removed}.")
    _emit(args, report.to_dict(), table)
    return 0 if args.remove or report.violations == 0 else 1


def cmd_adaptive(args) -> int:
    from .adaptive_attack import run_adaptive

    report = run_adaptive(world=args.world, budget=args.budget, seed=args.seed, remove=args.remove,
                          split=args.split, include_live=args.live, prove_attacker=args.prove_attacker)

    def table():
        for track in report.tracks:
            print(f"{track.name:<8} {track.episodes:>4} episodes  {track.forbidden_outcomes:>4} forbidden outcomes"
                  f"  {track.note}")
        if report.positive_control:
            pc = report.positive_control
            print(f"\npositive control (without {pc['control_removed']}): "
                  f"{pc['forbidden_outcomes']} forbidden outcomes, proving the attacker can win")
    _emit(args, report.to_dict(), table)
    return 0 if args.remove or report.total_forbidden == 0 else 1


def cmd_pack_check(args) -> int:
    from .kernel.pack_floor import check_pack, read_pack

    findings = check_pack(read_pack(args.pack))

    def table():
        if not findings:
            print(f"{args.pack}: at or above the kernel floor.")
        for f in findings:
            print(f"{f.code:<48} {f.where:<52} {f.detail}")
        if findings:
            print(f"\nREJECTED: {len(findings)} finding(s). This pack would weaken the kernel.")
    _emit(args, [f.to_dict() for f in findings], table)
    return 1 if findings else 0


def cmd_check(args) -> int:
    from .world_check import check_world

    worlds = [args.world] if args.world else available_worlds()
    results = {w: check_world(w) for w in worlds}

    def table():
        for world, findings in results.items():
            print(f"{world:<12} {'OK' if not findings else f'{len(findings)} finding(s)'}")
            for f in findings:
                print(f"  {f.code:<34} {f.where:<44} {f.detail}")
    _emit(args, {w: [f.to_dict() for f in fs] for w, fs in results.items()}, table)
    return 1 if any(results.values()) else 0


def cmd_matrix(args) -> int:
    from .matrix import run_matrix

    rows = run_matrix(redteam_attempts=args.attempts)

    def table():
        print(f"{'world':<12} {'falsifiers':>10} {'ablations':>10}  {'delegation (none/per-hop/chain)':<32}"
              f"{'red team':>9} {'w/o executor':>13}")
        for r in rows:
            u, p, c = r.delegation
            print(f"{r.world:<12} {r.falsifiers_held:>4} / {r.falsifiers:<3} {r.ablations_load_bearing:>4} / {r.ablations:<3}"
                  f"  {u:>2} / {p:>2} / {c:>2} of 10{'':<16}{r.redteam_violations:>5}{r.redteam_without_executor:>13}")
    _emit(args, [r.to_dict() for r in rows], table)
    return 0 if all(r.falsifiers_held == r.falsifiers and r.redteam_violations == 0 for r in rows) else 1


def cmd_evidence(args) -> int:
    """Every figure for one world, in one file. Talks, READMEs, and slides quote only this."""
    from .adaptive_attack import run_adaptive
    from .delegation_eval import ablate_delegation, run_delegation_suite
    from .falsification import run_ablation, run_falsifiers
    from .redteam import GrammarAttacker, run_redteam

    started = time.perf_counter()
    spec = WorldSpec.load(args.world)
    falsifiers = run_falsifiers(world=spec)
    ablation = run_ablation(world=spec)
    delegation = run_delegation_suite(world=spec)
    bundle = {
        "world": spec.to_summary(),
        "trustkernel_version": __version__,
        "controls": list(ALL_CONTROLS),
        "summary": {
            "falsifiers_held": sum(r.held for r in falsifiers), "falsifiers": len(falsifiers),
            "ablation_load_bearing": sum(r.load_bearing for r in ablation), "ablation_rows": len(ablation),
            "delegation": {arm: row["contained"] for arm, row in delegation.to_dict()["arms"].items()},
        },
        "falsifiers": [r.to_dict() for r in falsifiers],
        "ablation": [r.to_dict() for r in ablation],
        "delegation": {k: v for k, v in delegation.to_dict().items() if k != "generated_at"},
        "delegation_ablation": ablate_delegation(world=spec),
        "redteam": run_redteam(GrammarAttacker(spec, seed=1125), attempts=300, seed=7).to_dict(),
        "redteam_without_execution_mediator": run_redteam(GrammarAttacker(spec, seed=1125), attempts=300, seed=7,
                                                          remove=["execution_mediator"]).to_dict(),
        "adaptive": run_adaptive(world=spec, budget=60, seed=20260921, prove_attacker=True).to_dict(),
    }
    # Wall-clock time is reported but kept out of the file, so a regenerated bundle is
    # byte-identical unless a figure actually moved.
    seconds = round(time.perf_counter() - started, 1)
    text = json.dumps(bundle, indent=1, sort_keys=True, default=str) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        s = bundle["summary"]
        print(f"{args.out}: {s['falsifiers_held']}/{s['falsifiers']} falsifiers held, "
              f"{s['ablation_load_bearing']}/{s['ablation_rows']} ablations load-bearing, "
              f"delegation {s['delegation']}, in {seconds}s")
    else:
        sys.stdout.write(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trustkernel", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"trustkernel {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def command(name, func, help_text, world=True, json_flag=True):
        p = sub.add_parser(name, help=help_text, description=help_text)
        if world:
            p.add_argument("--world", default="devtools", help="world id or path (default: devtools)")
        if json_flag:
            p.add_argument("--json", action="store_true", help="print the full result as JSON")
        p.set_defaults(func=func)
        return p

    p = command("worlds", cmd_worlds, "list the worlds that ship", world=False)
    p.add_argument("--ids", action="store_true", help="print only world ids, space separated")
    p = command("demo", cmd_demo, "run the talk: seven scenes against a live world", json_flag=False)
    p.add_argument("--scene", type=int, action="append", choices=range(1, 8), help="run only this scene")
    p.add_argument("--pause", type=float, default=0.0, help="seconds between beats, for a stage")
    p.add_argument("--no-color", action="store_true")
    p = command("falsify", cmd_falsify, "run the 25 falsifiers")
    p.add_argument("--only", action="append", help="falsifier id or name (repeatable)")
    p = command("ablate", cmd_ablate, "remove each control in turn and rerun its falsifier")
    p.add_argument("--only", action="append", help="falsifier id or name (repeatable)")
    command("delegation", cmd_delegation, "compare three delegation architectures on the same chains")
    p = command("redteam", cmd_redteam, "seeded grammar attacker (or a local model with --live)")
    p.add_argument("--attempts", type=int, default=300)
    p.add_argument("--seed", type=int, default=1125)
    p.add_argument("--remove", action="append", default=[], choices=ALL_CONTROLS, metavar="CONTROL",
                   help="remove a control first (repeatable)")
    p.add_argument("--live", action="store_true", help="use a local Ollama model as the attacker")
    p = command("adaptive", cmd_adaptive, "static, random, and bandit attackers scored by real effect")
    p.add_argument("--budget", type=int, default=200)
    p.add_argument("--seed", type=int, default=20260921)
    p.add_argument("--split", choices=("dev", "held-out", "all"), default="dev")
    p.add_argument("--remove", action="append", default=[], choices=ALL_CONTROLS, metavar="CONTROL")
    p.add_argument("--live", action="store_true")
    p.add_argument("--prove-attacker", action="store_true", help="also run the positive control")
    p = command("check", cmd_check, "validate a world's wiring against its pack (all worlds by default)",
                world=False)
    p.add_argument("--world", help="one world id or path")
    p = command("matrix", cmd_matrix, "every attack suite against every world", world=False)
    p.add_argument("--attempts", type=int, default=150, help="red-team attacks per world")
    p = command("pack-check", cmd_pack_check, "check a domain pack against the kernel floor", world=False)
    p.add_argument("pack", help="path to a pack YAML")
    p = command("evidence", cmd_evidence, "every figure for one world, as one JSON bundle", json_flag=False)
    p.add_argument("--out", help="write the bundle here instead of stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except WorldSpecError as exc:
        print(f"trustkernel: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
