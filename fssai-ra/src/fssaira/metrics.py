"""Lightweight metrics harness. Counters are the measurable claims a testbed
records: blocked egress, denied tool calls, replays, rollbacks, tamper
detections. See ``tests/`` for how these are asserted."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Metrics:
    egress_blocked: int = 0
    tool_calls_allowed: int = 0
    tool_calls_denied: int = 0
    high_impact_denied: int = 0
    replays_ok: int = 0
    quarantined: int = 0
    rollbacks: int = 0
    tamper_detected: int = 0

    def snapshot(self) -> dict:
        return asdict(self)
