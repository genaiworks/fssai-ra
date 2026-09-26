"""How many reviewers a declared review floor actually needs.

The runtime enforces a minimum review time and sends anything faster to a
manual route (:mod:`fssaira.oversight`, ``TrustRuntime.approve_effect``). That
is the right control and it produces an operational question the control cannot
answer: with this arrival rate and this floor, how many people must be on shift
so that work waits a tolerable time instead of piling up -- and, worse, instead
of tempting someone to lower the floor?

This is a standard queueing answer. Arrivals are treated as Poisson and review
times as exponential with a mean no shorter than the floor, which is the Erlang
C model call centres staff by. It is an approximation, stated as one: real
review times have a heavier tail, so treat the result as a lower bound and
recalibrate from measured review times (:mod:`fssaira.review_calibration`).

Two levers are modelled because institutions use both:

* a **low-risk lane** whose items are not reviewed before the effect but are
  sampled for post-audit at ``audit_rate`` -- only those samples load reviewers;
* a **utilisation cap**, because a team run at 100% has no slack for the hard
  case, and the hard case is why review exists.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass


def erlang_c(servers: int, load: float) -> float:
    """Probability an arrival waits, for ``servers`` and offered ``load`` in Erlangs."""
    if servers <= 0:
        return 1.0
    if load <= 0:
        return 0.0
    if load >= servers:
        return 1.0
    b = 1.0                                   # Erlang B, computed stably
    for k in range(1, servers + 1):
        b = load * b / (k + load * b)
    return servers * b / (servers - load * (1 - b))


@dataclass(frozen=True)
class ReviewDemand:
    #: Consequential items per hour that need review before the effect.
    arrivals_per_hour: float
    #: Measured mean careful review time, seconds.
    mean_review_seconds: float
    #: The declared deliberation floor, seconds. Service is never faster.
    floor_seconds: float
    #: Items per hour in a low-risk lane (effect first, audit after).
    low_risk_per_hour: float = 0.0
    #: Fraction of the low-risk lane sampled for post-audit.
    audit_rate: float = 0.0
    #: Target: this fraction of items starts review within ``target_wait_seconds``.
    service_level: float = 0.8
    target_wait_seconds: float = 3600.0
    max_utilisation: float = 0.85

    def __post_init__(self) -> None:
        for name in ("arrivals_per_hour", "mean_review_seconds", "floor_seconds",
                     "low_risk_per_hour", "target_wait_seconds"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must not be negative")
        for name in ("audit_rate", "service_level", "max_utilisation"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} is a fraction")


def _metrics(servers: int, rate_per_s: float, service_s: float, target_wait: float) -> dict:
    load = rate_per_s * service_s
    if servers <= load:
        return {"stable": False, "utilisation": None, "p_wait": 1.0, "mean_wait_seconds": None,
                "service_level": 0.0}
    p = erlang_c(servers, load)
    mean_wait = p * service_s / (servers - load)
    sl = 1 - p * math.exp(-(servers - load) * target_wait / service_s)
    return {"stable": True, "utilisation": round(load / servers, 4), "p_wait": round(p, 4),
            "mean_wait_seconds": round(mean_wait, 1), "service_level": round(sl, 4)}


def staffing(demand: ReviewDemand, *, on_shift: int | None = None) -> dict:
    """Reviewers needed, and what the current shift delivers if ``on_shift`` is given."""
    service = max(demand.mean_review_seconds, demand.floor_seconds)
    reviewed_per_hour = demand.arrivals_per_hour + demand.low_risk_per_hour * demand.audit_rate
    rate = reviewed_per_hour / 3600.0
    load = rate * service
    needed = max(1, math.ceil(load / max(demand.max_utilisation, 1e-9)))
    while True:
        m = _metrics(needed, rate, service, demand.target_wait_seconds)
        if (m["stable"] and m["utilisation"] <= demand.max_utilisation
                and m["service_level"] >= demand.service_level):
            break
        needed += 1
    report = {
        "demand": asdict(demand),
        "effective_review_seconds": service,
        "floor_binds": demand.floor_seconds > demand.mean_review_seconds,
        "reviewed_items_per_hour": round(reviewed_per_hour, 3),
        "offered_load_erlangs": round(load, 3),
        "reviewers_needed": needed,
        "at_needed": _metrics(needed, rate, service, demand.target_wait_seconds),
    }
    if on_shift is not None:
        current = _metrics(on_shift, rate, service, demand.target_wait_seconds)
        capacity_per_hour = on_shift * 3600.0 / service * demand.max_utilisation
        report["on_shift"] = on_shift
        report["at_on_shift"] = current
        report["deferred_per_hour"] = round(max(0.0, reviewed_per_hour - capacity_per_hour), 3)
        report["verdict"] = ("STAFFED" if on_shift >= needed else
                             "UNDERSTAFFED_DEFER_NOT_LOWER_FLOOR")
    return report


__all__ = ["ReviewDemand", "erlang_c", "staffing"]
