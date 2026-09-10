"""Import boundary: a software model of a one-way data diode.

A hardware diode permits data to travel low-side -> high-side over a single
link and makes the reverse direction physically impossible. This class models
that property in code: it exposes :meth:`send_inward` and *deliberately provides
no method to move data outward*. Egress attempts therefore have no ordinary API
to call. This is the structural half of "no ordinary path for sensitive-data
egress"; the enforcement half (denying egress-capable tools) lives in the
policy enforcement point.

Production note: back this with a real hardware diode / cross-domain solution.
The class boundary here mirrors the physical boundary so application code is
identical in both cases.
"""
from __future__ import annotations

from typing import Callable


class DiodeBreachError(RuntimeError):
    """Raised if inward delivery is attempted with no high-side handler wired."""


class OneWayChannel:
    def __init__(self) -> None:
        self._high_side: Callable[[dict], None] | None = None

    def connect(self, high_side_handler: Callable[[dict], None]) -> None:
        """Wire the protected-domain receiver. Called once at assembly time."""
        self._high_side = high_side_handler

    def send_inward(self, item: dict) -> None:
        """Move one validated item low-side -> high-side. The only direction."""
        if self._high_side is None:
            raise DiodeBreachError("diode has no high-side handler connected")
        self._high_side(item)

    # There is intentionally no send_outward / read_back method.
