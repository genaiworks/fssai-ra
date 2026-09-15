"""What a plane is, as data that tests can hold to account.

A plane is a logical responsibility, not a product or a process boundary. Each
plane declares:

* ``responsibility``: what it does;
* ``must_not``: prohibitions, each bound to a pytest node that exercises it, so a
  prohibition with no test cannot be declared;
* ``components``: ``module:Symbol`` references to the code that carries the
  responsibility, each of which must import.

Logical planes in one process are not process isolation. Hostile code running
as the same operating-system user can bypass every in-process check. Separate
identities, hosts and networks are deployment obligations (docs/DEPLOYMENT.md).
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass


class PlaneError(RuntimeError):
    """A plane declares a component that does not exist."""


@dataclass(frozen=True)
class Prohibition:
    text: str
    failure_test: str


@dataclass(frozen=True)
class Plane:
    name: str
    responsibility: str
    must_not: tuple[Prohibition, ...]
    components: tuple[str, ...]
    mediator: bool = False
    untrusted: bool = False

    def load_components(self) -> dict[str, object]:
        """Import every declared component, or raise :class:`PlaneError`."""
        loaded: dict[str, object] = {}
        for reference in self.components:
            module_name, _, symbol = reference.partition(":")
            try:
                module = importlib.import_module(module_name)
                loaded[reference] = getattr(module, symbol)
            except (ImportError, AttributeError) as exc:
                raise PlaneError(f"{self.name}: component {reference!r} does not exist ({exc})") from exc
        return loaded
