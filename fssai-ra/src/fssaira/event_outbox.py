"""Transactional event outbox for the SQL profile.

Why this module exists
----------------------
Before the outbox, the control plane published each lifecycle event straight to
Kafka *after* the database had committed. Two failures followed:

* PostgreSQL committed, Kafka was down: the change happened but no event was
  ever published, and nothing recorded that one was owed.
* The same outage raised an error from ``execute`` even though the state change
  had committed, so the caller saw a failure for a change that had succeeded.

The outbox removes both. Each event is written to the ``event_outbox`` table.
``action.executed`` is written by :class:`~fssaira.atomic_execution.AtomicExecutor`
inside the same transaction as the state change, so the two commit together or
not at all. A relay then publishes pending rows in ``seq`` order and stamps them
published. A broker outage leaves rows pending; it never fails the request.

Delivery is **at least once**. A crash between publishing and stamping, or two
relays running at once, can publish an event twice. Every event carries a stable
``event_id`` (for example ``action.executed:<request_id>``) and is sent with that
ID as its trace ID, so consumers deduplicate on it --
:class:`~fssaira.kafka_backend.EvidenceProjector` does.
"""
from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable

from .event_transport import Event
from .sql_backend import SqlDatabase

log = logging.getLogger(__name__)


class OutboxRelay:
    """Publish pending outbox rows, oldest first, and stamp each one published."""

    def __init__(self, database: SqlDatabase, publisher, *, batch_size: int = 100) -> None:
        self.database = database
        self.publisher = publisher
        self.batch_size = batch_size

    def relay_once(self) -> int:
        """Publish everything pending now. Stops and re-raises at the first failure.

        Stopping at the first failure keeps per-key order: a later event is never
        published ahead of an earlier one that the broker refused.
        """
        published = 0
        while True:
            with self.database.transaction() as unit:
                batch = unit.events.pending(self.batch_size)
            if not batch:
                return published
            for row in batch:
                # Publish outside any transaction: a network call must not hold
                # database locks.
                self.publisher.append(row["value"], key=row["key"], trace_id=row["event_id"])
                with self.database.transaction() as unit:
                    unit.events.mark_published(row["event_id"])
                published += 1


class SqlEventOutbox:
    """The control plane's event log when state lives in SQL.

    Implements the same ``append``/``read`` surface as
    :class:`~fssaira.event_transport.EventLog`. ``append`` stores the event and,
    when a publisher is configured, tries to relay immediately.

    After a failed relay, inline attempts pause for ``retry_after`` seconds
    (``FSSAI_EVENT_RELAY_BACKOFF_SECONDS``, default 30). Without the pause, every
    request during a broker outage would wait for the producer's delivery
    timeout. ``relay(force=True)``, used by ``/v1/recovery/reconcile``, ignores
    the pause.
    """

    def __init__(self, database: SqlDatabase, *, publisher=None,
                 retry_after: float | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.database = database
        self.publisher = publisher
        self._relay = OutboxRelay(database, publisher) if publisher is not None else None
        self.retry_after = (
            float(os.getenv("FSSAI_EVENT_RELAY_BACKOFF_SECONDS", "30"))
            if retry_after is None else retry_after
        )
        self._clock = clock
        self._paused_until = 0.0

    def append(self, value: dict, key: str = "", trace_id: str = "") -> int:
        event_id = value.get("event_id") or trace_id
        if not event_id:
            raise ValueError("an outbox event needs a stable event_id")
        with self.database.transaction() as unit:
            unit.events.enqueue(event_id, key, value)
            seq = unit.events.get(event_id)["seq"]
        self.relay()
        return seq

    def relay(self, *, force: bool = False) -> int:
        """Best-effort publication of every pending event. Returns the number sent."""
        if self._relay is None:
            return 0
        if not force and self._clock() < self._paused_until:
            return 0
        try:
            sent = self._relay.relay_once()
        except Exception as exc:  # broker down: keep rows pending, keep serving
            self._paused_until = self._clock() + self.retry_after
            log.warning("event relay deferred for %.0fs; %d event(s) pending: %s",
                        self.retry_after, self.unpublished_count(), exc)
            return 0
        self._paused_until = 0.0
        return sent

    def read(self, from_offset: int = 0) -> list[Event]:
        return [
            Event(row["seq"], row["created_at"], row["key"], row["value"],
                  row["event_id"], row["event_id"])
            for row in self.read_all() if row["seq"] >= from_offset
        ]

    def read_all(self) -> list[dict]:
        with self.database.transaction() as unit:
            return unit.events.all()

    def pending(self) -> list[dict]:
        with self.database.transaction() as unit:
            return unit.events.pending()

    def unpublished_count(self) -> int:
        with self.database.transaction() as unit:
            return unit.events.unpublished_count()

    def __len__(self) -> int:
        with self.database.transaction() as unit:
            return unit.events.count()


__all__ = ["OutboxRelay", "SqlEventOutbox"]
