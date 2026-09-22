"""Suite results cached per world, so contract tests and cross-world tests share one run."""
from functools import lru_cache

from trustkernel.falsification import run_ablation, run_falsifiers


@lru_cache(maxsize=None)
def falsifiers(world: str) -> dict:
    return {r.id: r for r in run_falsifiers(world=world)}


@lru_cache(maxsize=None)
def ablation(world: str) -> tuple:
    return tuple(run_ablation(world=world))
