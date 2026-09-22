"""Suite results cached per world, so contract tests and cross-world tests share one run."""
from functools import cache

from trustkernel.falsification import run_ablation, run_falsifiers


@cache
def falsifiers(world: str) -> dict:
    return {r.id: r for r in run_falsifiers(world=world)}


@cache
def ablation(world: str) -> tuple:
    return tuple(run_ablation(world=world))
