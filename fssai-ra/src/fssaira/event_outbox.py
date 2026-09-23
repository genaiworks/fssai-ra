"""Transactional event outbox: committed changes always have a durable event.

Why this module exists
----------------------
Before the outbox, the control plane published each lifecycle event straight to
Kafka *after* its state store had committed. Two failures followed:

* The store committed, Kafka was down: the change happened but no event was
  ever published, and nothing recorded that one was owed.
* The same outage raised an error from ``execute`` even though the state change
  had committed, so the caller saw a failure for a change that had succeeded.

The outbox removes both. Each event is first written to an outbox store, then a
relay publishes pending events in ``seq`` order and marks them published. A
broker outage leaves events pending; it never fails the request.

Three stores implement the same small interface:

* :class:`SqlOutboxStore` -- the ``event_outbox`` table. ``AtomicExecutor``
  writes ``action.executed`` inside the state transaction.
* :class:`RedisOutboxStore` -- Redis hash and sorted sets. ``RedisCaseRegister``
  writes ``action.executed`` inside the same ``MULTI/EXEC`` as the transition.
* :class:`MemoryOutboxStore` -- the teaching profile; lost on restart.

Delivery is **at least once**. A crash between publishing and marking, or two
relays running at once, can publish an event twice. Every event carries a stable
``event_id`` (for example ``action.executed:<request_id>``) and is sent with that
ID as its trace ID, so consumers deduplicate on it --
:class:`~fssaira.kafka_backend.EvidenceProjector` does.

With no publisher configured there is no transport to owe anything to, so events
are recorded as published when written. Published events older than
``FSSAI_EVENT_OUTBOX_RETENTION_SECONDS`` (default seven days) are pruned.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Protocol

from .event_transport import Event

log = logging.getLogger(__name__)

DEFAULT_RETENTION_SECONDS = 7 * 24 * 3600


class OutboxStore(Protocol):
    def enqueue(self, event_id: str, key: str, value: dict,
                *, published: bool = False) -> bool: ...
    def get(self, event_id: str) -> dict | None: ...
    def pending(self, limit: int | None = None) -> list[dict]: ...
    def all(self) -> list[dict]: ...
    def mark_published(self, event_id: str) -> None: ...
    def count(self) -> int: ...
    def unpublished_count(self) -> int: ...
    def prune_published(self, before: float) -> int: ...


# ---------------------------------------------------------------------------
# Stores
# ---------------------------------------------------------------------------


class SqlOutboxStore:
    """``event_outbox`` table access, one short transaction per call."""

    def __init__(self, database) -> None:
        self.database = database

    def enqueue(self, event_id, key, value, *, published=False) -> bool:
        with self.database.transaction() as unit:
            inserted = unit.events.enqueue(event_id, key, value)
            if inserted and published:
                unit.events.mark_published(event_id)
            return inserted

    def get(self, event_id):
        with self.database.transaction() as unit:
            return unit.events.get(event_id)

    def pending(self, limit=None):
        with self.database.transaction() as unit:
            return unit.events.pending(limit)

    def all(self):
        with self.database.transaction() as unit:
            return unit.events.all()

    def mark_published(self, event_id):
        with self.database.transaction() as unit:
            unit.events.mark_published(event_id)

    def count(self):
        with self.database.transaction() as unit:
            return unit.events.count()

    def unpublished_count(self):
        with self.database.transaction() as unit:
            return unit.events.unpublished_count()

    def prune_published(self, before):
        with self.database.transaction() as unit:
            return unit.events.prune_published(before)


class RedisOutboxStore:
    """Outbox in Redis: a hash of rows plus two sorted sets ordered by ``seq``.

    ``{prefix}:outbox:rows``      event_id -> JSON row
    ``{prefix}:outbox:all``       every event, score = seq
    ``{prefix}:outbox:pending``   unpublished events, score = seq
    ``{prefix}:outbox:seq``       sequence counter
    """

    def __init__(self, client, prefix: str = "fssaira") -> None:
        self.client = client
        self.rows = f"{prefix}:outbox:rows"
        self.all_key = f"{prefix}:outbox:all"
        self.pending_key = f"{prefix}:outbox:pending"
        self.seq_key = f"{prefix}:outbox:seq"

    def row(self, event_id: str, key: str, value: dict, seq: int, *, published: bool) -> str:
        now = time.time()
        return json.dumps({
            "event_id": event_id, "seq": seq, "key": key, "value": value,
            "created_at": now, "published_at": now if published else None,
        }, sort_keys=True, default=str)

    def queue_in(self, pipe, event_id: str, key: str, value: dict, seq: int,
                 *, published: bool = False) -> None:
        """Add the writes for one event to an open ``MULTI`` pipeline."""
        pipe.hset(self.rows, event_id, self.row(event_id, key, value, seq, published=published))
        pipe.zadd(self.all_key, {event_id: seq})
        if not published:
            pipe.zadd(self.pending_key, {event_id: seq})

    def next_seq(self) -> int:
        return int(self.client.incr(self.seq_key))

    def enqueue(self, event_id, key, value, *, published=False) -> bool:
        import redis

        seq = self.next_seq()  # a gap after a lost race is harmless
        while True:
            try:
                with self.client.pipeline() as pipe:
                    pipe.watch(self.rows)
                    if pipe.hexists(self.rows, event_id):
                        pipe.unwatch()
                        return False
                    pipe.multi()
                    self.queue_in(pipe, event_id, key, value, seq, published=published)
                    pipe.execute()
                    return True
            except redis.WatchError:
                continue

    def _load(self, raw) -> dict:
        return json.loads(raw)

    def get(self, event_id):
        raw = self.client.hget(self.rows, event_id)
        return None if raw is None else self._load(raw)

    def _rows(self, ids) -> list[dict]:
        if not ids:
            return []
        return [self._load(raw) for raw in self.client.hmget(self.rows, ids) if raw is not None]

    def pending(self, limit=None):
        end = -1 if limit is None else int(limit) - 1
        return self._rows(self.client.zrange(self.pending_key, 0, end))

    def all(self):
        return self._rows(self.client.zrange(self.all_key, 0, -1))

    def mark_published(self, event_id):
        row = self.get(event_id)
        if row is None or row["published_at"] is not None:
            return
        row["published_at"] = time.time()
        with self.client.pipeline() as pipe:
            pipe.multi()
            pipe.hset(self.rows, event_id, json.dumps(row, sort_keys=True, default=str))
            pipe.zrem(self.pending_key, event_id)
            pipe.execute()

    def count(self):
        return int(self.client.zcard(self.all_key))

    def unpublished_count(self):
        return int(self.client.zcard(self.pending_key))

    def prune_published(self, before):
        removed = 0
        for row in self.all():
            if row["published_at"] is not None and row["published_at"] < before:
                with self.client.pipeline() as pipe:
                    pipe.multi()
                    pipe.hdel(self.rows, row["event_id"])
                    pipe.zrem(self.all_key, row["event_id"])
                    pipe.execute()
                removed += 1
        return removed


class MemoryOutboxStore:
    """In-process outbox for the teaching profile. Lost on restart."""

    def __init__(self) -> None:
        self._rows: dict[str, dict] = {}
        self._seq = 0
        self._lock = threading.RLock()

    def enqueue(self, event_id, key, value, *, published=False) -> bool:
        with self._lock:
            if event_id in self._rows:
                return False
            self._seq += 1
            now = time.time()
            self._rows[event_id] = {
                "event_id": event_id, "seq": self._seq, "key": key, "value": value,
                "created_at": now, "published_at": now if published else None,
            }
            return True

    def get(self, event_id):
        with self._lock:
            row = self._rows.get(event_id)
            return None if row is None else dict(row)

    def all(self):
        with self._lock:
            return sorted((dict(r) for r in self._rows.values()), key=lambda r: r["seq"])

    def pending(self, limit=None):
        rows = [r for r in self.all() if r["published_at"] is None]
        return rows if limit is None else rows[:limit]

    def mark_published(self, event_id):
        with self._lock:
            row = self._rows.get(event_id)
            if row is not None and row["published_at"] is None:
                row["published_at"] = time.time()

    def count(self):
        with self._lock:
            return len(self._rows)

    def unpublished_count(self):
        return len(self.pending())

    def prune_published(self, before):
        with self._lock:
            old = [k for k, r in self._rows.items()
                   if r["published_at"] is not None and r["published_at"] < before]
            for k in old:
                del self._rows[k]
            return len(old)


def _as_store(target) -> OutboxStore:
    """Accept a store, or a ``SqlDatabase`` for backwards compatibility."""
    return SqlOutboxStore(target) if hasattr(target, "transaction") else target


# ---------------------------------------------------------------------------
# Relay and event log
# ---------------------------------------------------------------------------


class OutboxRelay:
    """Publish pending outbox events, oldest first, and mark each one published."""

    def __init__(self, store, publisher, *, batch_size: int = 100) -> None:
        self.store = _as_store(store)
        self.publisher = publisher
        self.batch_size = batch_size

    def relay_once(self) -> int:
        """Publish everything pending now. Stops and re-raises at the first failure.

        Stopping at the first failure keeps per-key order: a later event is never
        published ahead of an earlier one that the broker refused.
        """
        published = 0
        while True:
            batch = self.store.pending(self.batch_size)
            if not batch:
                return published
            for row in batch:
                # Publish outside any transaction: a network call must not hold locks.
                self.publisher.append(row["value"], key=row["key"], trace_id=row["event_id"])
                self.store.mark_published(row["event_id"])
                published += 1


class EventOutbox:
    """The control plane's event log, backed by an outbox store.

    Implements the same ``append``/``read`` surface as
    :class:`~fssaira.event_transport.EventLog`. ``append`` stores the event and,
    when a publisher is configured, tries to relay immediately.

    After a failed relay, inline attempts pause for ``retry_after`` seconds
    (``FSSAI_EVENT_RELAY_BACKOFF_SECONDS``, default 30). Without the pause, every
    request during a broker outage would wait for the producer's delivery
    timeout. ``relay(force=True)``, used by ``/v1/recovery/reconcile``, ignores
    the pause.
    """

    def __init__(self, store, *, publisher=None, retry_after: float | None = None,
                 retention_seconds: float | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.store = _as_store(store)
        self.publisher = publisher
        self._relay = OutboxRelay(self.store, publisher) if publisher is not None else None
        self.retry_after = (
            float(os.getenv("FSSAI_EVENT_RELAY_BACKOFF_SECONDS", "30"))
            if retry_after is None else retry_after
        )
        self.retention_seconds = (
            float(os.getenv("FSSAI_EVENT_OUTBOX_RETENTION_SECONDS", DEFAULT_RETENTION_SECONDS))
            if retention_seconds is None else retention_seconds
        )
        self._clock = clock
        self._paused_until = 0.0
        self._next_prune = 0.0

    def append(self, value: dict, key: str = "", trace_id: str = "") -> int:
        event_id = value.get("event_id") or trace_id
        if not event_id:
            raise ValueError("an outbox event needs a stable event_id")
        self.store.enqueue(event_id, key, value, published=self._relay is None)
        if self._relay is None:
            # The executor may already have written this event as pending inside
            # its transaction; with no transport, nothing is owed.
            self.store.mark_published(event_id)
        seq = self.store.get(event_id)["seq"]
        self.relay()
        self._maybe_prune()
        return seq

    def relay(self, *, force: bool = False) -> int:
        """Best-effort publication of every pending event. Returns the number sent."""
        if self._relay is None:
            return 0
        if not force and self._clock() < self._paused_until:
            return 0
        try:
            sent = self._relay.relay_once()
        except Exception as exc:  # broker down: keep events pending, keep serving
            self._paused_until = self._clock() + self.retry_after
            log.warning("event relay deferred for %.0fs; %d event(s) pending: %s",
                        self.retry_after, self.unpublished_count(), exc)
            return 0
        self._paused_until = 0.0
        return sent

    def prune(self) -> int:
        """Delete published events older than the retention period."""
        return self.store.prune_published(time.time() - self.retention_seconds)

    def _maybe_prune(self) -> None:
        now = self._clock()
        if now >= self._next_prune:
            self._next_prune = now + 3600.0
            try:
                self.prune()
            except Exception as exc:  # pruning must never fail a request
                log.warning("event outbox pruning skipped: %s", exc)

    def read(self, from_offset: int = 0) -> list[Event]:
        return [
            Event(row["seq"], row["created_at"], row["key"], row["value"],
                  row["event_id"], row["event_id"])
            for row in self.read_all() if row["seq"] >= from_offset
        ]

    def read_all(self) -> list[dict]:
        return self.store.all()

    def pending(self) -> list[dict]:
        return self.store.pending()

    def unpublished_count(self) -> int:
        return self.store.unpublished_count()

    def __len__(self) -> int:
        return self.store.count()


class SqlEventOutbox(EventOutbox):
    """:class:`EventOutbox` over the SQL ``event_outbox`` table."""

    def __init__(self, database, **options) -> None:
        super().__init__(SqlOutboxStore(database), **options)
        self.database = database


__all__ = [
    "EventOutbox", "MemoryOutboxStore", "OutboxRelay", "OutboxStore", "RedisOutboxStore",
    "SqlEventOutbox", "SqlOutboxStore",
]
