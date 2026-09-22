"""trustkernel: agents may propose and request; only independent mediators decide.

The public surface is small:

* :class:`trustkernel.world.ScenarioWorld` builds a live world (kernel + pack + cast)
  from ``worlds/<id>/world.yaml``, with any control removable for ablation.
* :mod:`trustkernel.falsification` runs 25 falsifiers and the ablation table.
* :mod:`trustkernel.delegation_eval` compares three delegation architectures.
* :mod:`trustkernel.redteam` and :mod:`trustkernel.adaptive_attack` attack it.
* :mod:`trustkernel.demo` is the talk, runnable.
"""
__version__ = "0.1.0"
