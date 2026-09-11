"""Port definitions: the seams every FSSAI-RA deployment may replace.

The reference implementation ships one adapter per port (in-memory for
teaching, Redis/Postgres/Kafka for the distributed profile). Everything in this
module is a :class:`typing.Protocol`, so an adapter never imports or subclasses
framework code -- it only has to match a shape. That keeps the assurance
argument honest: a replacement is acceptable when the conformance suite
(``fssaira conformance``) still passes against it, not because it inherits from
a blessed base class.

Ports are grouped by the five architectural domains plus the cross-cutting
services (identity, clock, telemetry) that must be administered independently
of the agent runtime.
"""
from __future__ import annotations

from typing import Any, Iterable, Iterator, Protocol, runtime_checkable

# --------------------------------------------------------------------------
# Domain 1 - import boundary
# --------------------------------------------------------------------------


@runtime_checkable
class InwardChannel(Protocol):
    """A transport that moves items low-side -> high-side and nothing back.

    Implementations MUST NOT expose a read-back, reply, or acknowledgement
    method. ``fssaira.diode.assert_no_return_path`` enforces that by inspection
    and is exercised by the conformance suite.
    """

    def connect(self, high_side_handler: Any) -> None: ...
    def send_inward(self, item: dict) -> None: ...


@runtime_checkable
class ImportSink(Protocol):
    """Where validated inward items land on the high side."""

    def append(self, value: dict, key: str = ..., trace_id: str = ...) -> int: ...


# --------------------------------------------------------------------------
# Domain 2 - event transport
# --------------------------------------------------------------------------


@runtime_checkable
class EventBus(Protocol):
    """Durable, ordered, replayable transport. Kafka is one implementation."""

    def append(self, value: dict, key: str = ..., trace_id: str = ...) -> int: ...


@runtime_checkable
class ReplayableEventBus(EventBus, Protocol):
    """An event bus that can also be read back from an offset for projections."""

    def read(self, from_offset: int = ...) -> list: ...


# --------------------------------------------------------------------------
# Domain 3 - reproducible data
# --------------------------------------------------------------------------


@runtime_checkable
class SnapshotStoreLike(Protocol):
    """Versioned, rollback-able table state with a content manifest."""

    def commit(self, rows: Iterable, parent: str | None = ..., note: str = ...) -> str: ...
    def read(self, snapshot_id: str) -> list: ...
    def manifest(self, snapshot_id: str) -> str: ...
    def rollback(self, snapshot_id: str) -> str: ...


# --------------------------------------------------------------------------
# Domain 4 - bounded intelligence
# --------------------------------------------------------------------------


@runtime_checkable
class ModelBackendPort(Protocol):
    """A model proposes tool calls. It never decides whether they execute."""

    name: str

    def propose(self, task: str, evidence: list) -> list: ...


@runtime_checkable
class ModelHealth(Protocol):
    """Optional: a backend that can report reachability without proposing."""

    def health(self) -> dict: ...


# --------------------------------------------------------------------------
# Domain 5 - accountable action
# --------------------------------------------------------------------------


@runtime_checkable
class RegisterPort(Protocol):
    """The authoritative resource register: the only thing a mutation changes."""

    def get(self, case_id: str) -> dict: ...
    def seed(self, case_id: str, *, status: str, version: int = ...) -> bool: ...
    def result_for(self, request_id: str) -> Any: ...
    def transition(self, proposal: Any) -> Any: ...

    @property
    def mutation_count(self) -> int: ...


@runtime_checkable
class EvidencePort(Protocol):
    """Append-only, tamper-evident decision record with a guarded write path."""

    def append(self, kind: str, payload: dict, *, token: str) -> Any: ...
    def verify(self) -> bool: ...
    def find(self, kind: str | None = ..., **match: Any) -> list: ...
    def __iter__(self) -> Iterator: ...
    def __len__(self) -> int: ...


@runtime_checkable
class ObjectStorePort(Protocol):
    """Durable key/value for proposals, approvals, and receipts."""

    def put(self, namespace: str, key: str, value: dict) -> None: ...
    def get(self, namespace: str, key: str) -> dict | None: ...


@runtime_checkable
class ApprovalUseStorePort(Protocol):
    """First-writer-wins binding of one approval to one request (replay guard)."""

    def bind(self, approval_id: str, request_id: str) -> tuple[str, bool]: ...


@runtime_checkable
class PendingOutcomeStorePort(Protocol):
    """Outbox-shaped store for outcomes whose evidence append has not landed."""

    def put(self, outcome: Any) -> None: ...
    def remove(self, request_id: str) -> None: ...
    def get(self, request_id: str) -> Any: ...
    def values(self) -> tuple: ...
    def __len__(self) -> int: ...


@runtime_checkable
class TransactionalOutcomeStore(PendingOutcomeStorePort, Protocol):
    """A store that can commit the mutation and its outcome record atomically.

    This is the port that upgrades the architecture's weakest documented link.
    An implementation that satisfies it (see ``postgres_backend``) turns
    "record the intent, hope the outcome lands" into a single durable
    transaction, so a crash between the two is impossible rather than merely
    detectable. Adapters that cannot offer atomicity must not claim this port.
    """

    def atomic(self) -> Any:
        """Return a context manager whose scope commits register + outbox together."""


# --------------------------------------------------------------------------
# Cross-cutting
# --------------------------------------------------------------------------


@runtime_checkable
class Clock(Protocol):
    """Injectable time. Tests and evaluations must never race a wall clock."""

    def now(self) -> float: ...


class SystemClock:
    def now(self) -> float:
        import time

        return time.time()


class FrozenClock:
    """Deterministic clock for evaluation, model checking, and replay."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self._t = float(start)

    def now(self) -> float:
        return self._t

    def advance(self, seconds: float) -> float:
        self._t += float(seconds)
        return self._t


__all__ = [
    "InwardChannel", "ImportSink",
    "EventBus", "ReplayableEventBus",
    "SnapshotStoreLike",
    "ModelBackendPort", "ModelHealth",
    "RegisterPort", "EvidencePort", "ObjectStorePort",
    "ApprovalUseStorePort", "PendingOutcomeStorePort", "TransactionalOutcomeStore",
    "Clock", "SystemClock", "FrozenClock",
]
