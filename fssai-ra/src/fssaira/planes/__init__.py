"""Seven logical planes and two mediators (paper Fig. 1).

``ALL_PLANES`` lists the seven planes plus the context gate, which is a mediator
alongside the execution plane. Planes are logical responsibilities; they are not
process isolation.
"""
from __future__ import annotations

from fssaira.planes import (
    authority,
    boundary,
    context_gate,
    data,
    evidence,
    execution,
    intelligence,
    resilience,
)
from fssaira.planes.base import Plane, PlaneError, Prohibition

ALL_PLANES: tuple[Plane, ...] = (
    boundary.PLANE,
    data.PLANE,
    intelligence.PLANE,
    authority.PLANE,
    execution.PLANE,
    context_gate.PLANE,
    evidence.PLANE,
    resilience.PLANE,
)

__all__ = ["ALL_PLANES", "Plane", "PlaneError", "Prohibition"]
