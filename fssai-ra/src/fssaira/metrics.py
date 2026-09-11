"""Lightweight metrics harness. Counters are the measurable claims a testbed
records: blocked egress, denied tool calls, attempted privilege downgrades,
replays, rollbacks, and tamper detections.

These counters are the raw material for the paper's result tables and for the
Prometheus exposition in :mod:`fssaira.telemetry`. They are deliberately plain
integers so a reader can reproduce a number by hand from the evidence ledger.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields


@dataclass
class Metrics:
    egress_blocked: int = 0
    tool_calls_allowed: int = 0
    tool_calls_denied: int = 0
    high_impact_denied: int = 0
    class_downgrade_attempts: int = 0
    budget_exhausted: int = 0
    replays_ok: int = 0
    quarantined: int = 0
    rollbacks: int = 0
    tamper_detected: int = 0
    mutations: int = 0
    approvals_denied: int = 0
    outcomes_reconciled: int = 0

    def snapshot(self) -> dict:
        return asdict(self)

    def merge(self, other: Metrics) -> Metrics:
        """Sum two snapshots -- used when several runs feed one result table."""
        return Metrics(**{
            f.name: getattr(self, f.name) + getattr(other, f.name) for f in fields(self)
        })

    def reset(self) -> None:
        for f in fields(self):
            setattr(self, f.name, 0)
