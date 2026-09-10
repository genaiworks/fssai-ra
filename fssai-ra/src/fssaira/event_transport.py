"""Event-transport domain: a durable, ordered, replayable log (Kafka-like).

The in-memory ``EventLog`` implements the properties the contract requires -
strict ordering by offset, per-item hash + trace id, and replay from any
offset - with no external infrastructure, so tests run anywhere. Swap in the
Kafka adapter (``adapters/kafka_adapter.py``) for production; the ``KafkaLike``
Protocol is the seam.

Contract caveat: a log is transport, not the system of record. Retention and
compaction can drop events, so durable decision evidence lives in the evidence
ledger and pinned snapshots, not here.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable


@dataclass(frozen=True)
class Event:
    offset: int
    ts: float
    key: str
    value: dict
    trace_id: str
    hash: str


@runtime_checkable
class KafkaLike(Protocol):
    def append(self, value: dict, key: str = ..., trace_id: str = ...) -> int: ...
    def read(self, from_offset: int = ...) -> list[Event]: ...


class EventLog:
    def __init__(self) -> None:
        self._events: list[Event] = []

    def append(self, value: dict, key: str = "", trace_id: str = "") -> int:
        offset = len(self._events)
        ts = time.time()
        body = json.dumps({"offset": offset, "key": key, "value": value}, sort_keys=True, default=str)
        h = hashlib.sha256(body.encode()).hexdigest()
        self._events.append(Event(offset, ts, key, value, trace_id or h[:12], h))
        return offset

    def read(self, from_offset: int = 0) -> list[Event]:
        return list(self._events[from_offset:])

    def replay(self, from_offset: int, handler: Callable[[Event], None]) -> int:
        n = 0
        for ev in self._events[from_offset:]:
            handler(ev)
            n += 1
        return n

    def __len__(self) -> int:
        return len(self._events)
