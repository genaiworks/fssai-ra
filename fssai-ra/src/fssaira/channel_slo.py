"""A covert-channel service-level objective: bits per minute, not bits per task.

:mod:`fssaira.covert_channels` bounds what one task can signal through the
choices it is allowed to make, and the runtime charges those bits against a
per-task budget. A buyer's security team asks a different question: across
everything running, at most how fast can information leave through allowed
choices? That is a rate, and a declared objective ("at most N bits per minute
per recipient") is what an egress review can sign off.

The bound is ``concurrent_tasks * task_capacity_bits / horizon_minutes``: every
task spends its whole channel capacity in its window, and the windows overlap
as much as concurrency allows. It is an upper bound on the average rate. An
unbounded dimension makes it infinite, and the SLO then fails, because a
dimension nobody bounded has not been bounded.

The error channel toward the model is already closed: ``TrustRuntime.dispatch``
returns only ``DENIED`` to an agent, and the specific refusal code goes to the
decision receipt an auditor reads. One outcome bit per call remains, and it is
the one bit an agent needs to stop.
"""
from __future__ import annotations

import math

from .covert_channels import EgressPolicy


class ChannelCode:
    SLO_MET = "CHANNEL_SLO_MET"
    SLO_EXCEEDED = "CHANNEL_SLO_EXCEEDED"


def rate_bound(policy: EgressPolicy, *, concurrent_tasks: int = 1) -> dict:
    if concurrent_tasks < 1:
        raise ValueError("at least one task runs")
    task_bits = policy.task_capacity_bits()
    minutes = policy.horizon_seconds / 60.0
    rate = math.inf if math.isinf(task_bits) else concurrent_tasks * task_bits / minutes
    return {"task_capacity_bits": None if math.isinf(task_bits) else round(task_bits, 4),
            "horizon_minutes": round(minutes, 4), "concurrent_tasks": concurrent_tasks,
            "bits_per_minute": None if math.isinf(rate) else round(rate, 4),
            "bounded": not math.isinf(rate)}


def check_slo(policy: EgressPolicy, *, slo_bits_per_minute: float,
              concurrent_tasks: int = 1) -> dict:
    bound = rate_bound(policy, concurrent_tasks=concurrent_tasks)
    met = bound["bounded"] and bound["bits_per_minute"] <= slo_bits_per_minute
    return {**bound, "slo_bits_per_minute": slo_bits_per_minute,
            "code": ChannelCode.SLO_MET if met else ChannelCode.SLO_EXCEEDED, "met": met}


__all__ = ["ChannelCode", "check_slo", "rate_bound"]
