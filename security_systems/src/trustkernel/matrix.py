"""Every attack suite against every world: the portability claim as one table."""
from __future__ import annotations

from dataclasses import dataclass

from .delegation_eval import run_delegation_suite
from .falsification import run_ablation, run_falsifiers
from .redteam import GrammarAttacker, run_redteam
from .world import WorldSpec, available_worlds


@dataclass(frozen=True)
class MatrixRow:
    world: str
    title: str
    falsifiers_held: int
    falsifiers: int
    ablations_load_bearing: int
    ablations: int
    delegation: tuple[int, int, int]      # unguarded, per-hop, whole-chain
    redteam_violations: int
    redteam_without_executor: int
    redteam_attempts: int

    def to_dict(self) -> dict:
        return {**self.__dict__, "delegation": dict(zip(("unguarded", "per_hop", "whole_chain"), self.delegation, strict=True))}


def run_matrix(worlds=None, *, redteam_attempts: int = 150) -> list[MatrixRow]:
    rows = []
    for world in worlds or available_worlds():
        spec = WorldSpec.load(world)
        falsifiers = run_falsifiers(world=spec)
        ablation = run_ablation(world=spec)
        arms = run_delegation_suite(world=spec).to_dict()["arms"]
        held = run_redteam(GrammarAttacker(spec, seed=1125), attempts=redteam_attempts, seed=7)
        weakened = run_redteam(GrammarAttacker(spec, seed=1125), attempts=redteam_attempts, seed=7,
                               remove=["execution_mediator"])
        rows.append(MatrixRow(spec.world_id, spec.title, sum(r.held for r in falsifiers), len(falsifiers),
                              sum(r.load_bearing for r in ablation), len(ablation),
                              tuple(arms[a]["contained"] for a in ("unguarded", "caller_checked", "this_architecture")),
                              held.violations, weakened.violations, redteam_attempts))
    return rows


__all__ = ["MatrixRow", "run_matrix"]
