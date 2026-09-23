"""Kafka publication and consumption for the event-transport domain.

A log is transport, not a system of record. Retention and compaction can drop
events, so the durable decision evidence lives in the evidence ledger and pinned
snapshots, never here. What the log provides is ordering, replay, and the
ability for a projection to be rebuilt from scratch -- which is what makes an
independent monitor possible.

The publisher is idempotent (``enable.idempotence``, ``acks=all``) so a broker
retry cannot duplicate an event. The consumer commits offsets *after* the
handler succeeds, so the delivery guarantee is at-least-once and the handler
must be idempotent. That is stated rather than papered over: a projection that
silently assumed exactly-once would be the kind of quiet incorrectness this
architecture exists to avoid.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import signal
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass

DEFAULT_TOPIC = "fssaira.events"
IMPORT_TOPIC = "fssaira.imports"
DEAD_LETTER_SUFFIX = ".dlq"


def _require_kafka():
    try:
        import confluent_kafka  # noqa: F401
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Kafka support requires the 'kafka' extra: pip install 'fssaira[kafka]'"
        ) from exc
    return confluent_kafka


def kafka_security_config() -> dict:
    """librdkafka TLS settings from the environment; empty for a plaintext broker.

    ``FSSAI_KAFKA_SECURITY_PROTOCOL=SSL`` and ``FSSAI_KAFKA_SSL_CA_LOCATION=<ca.crt>``
    make every producer and consumer verify the broker's certificate and host name.
    """
    protocol = os.getenv("FSSAI_KAFKA_SECURITY_PROTOCOL", "").strip().upper()
    if not protocol or protocol == "PLAINTEXT":
        return {}
    if protocol != "SSL":
        raise ValueError("FSSAI_KAFKA_SECURITY_PROTOCOL must be PLAINTEXT or SSL")
    config = {"security.protocol": "SSL", "ssl.endpoint.identification.algorithm": "https"}
    ca = os.getenv("FSSAI_KAFKA_SSL_CA_LOCATION")
    if ca:
        config["ssl.ca.location"] = ca
    return config


class KafkaEventPublisher:
    """Idempotent, acknowledged publication of one control-plane event."""

    name = "kafka"

    def __init__(self, bootstrap_servers: str, topic: str = DEFAULT_TOPIC,
                 *, client_id: str = "fssaira-control-plane", flush_timeout: float = 10.0) -> None:
        kafka = _require_kafka()
        self.topic = topic
        self.flush_timeout = flush_timeout
        self.producer = kafka.Producer({
            **kafka_security_config(),
            "bootstrap.servers": bootstrap_servers,
            "enable.idempotence": True,
            "acks": "all",
            "max.in.flight.requests.per.connection": 5,
            "retries": 10,
            "client.id": client_id,
        })

    def append(self, value: dict, key: str = "", trace_id: str = "") -> int:
        body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        envelope = json.dumps({
            "value": value,
            "trace_id": trace_id or hashlib.sha256(body.encode()).hexdigest()[:16],
            "published_at": time.time(),
        }, sort_keys=True, default=str).encode()
        delivered: list = []

        def callback(error, message):
            delivered.append(error if error is not None else message.offset())

        self.producer.produce(self.topic, value=envelope, key=key.encode() or None, callback=callback)
        remaining = self.producer.flush(self.flush_timeout)
        if remaining:
            # Drop the undelivered copy. Otherwise the client keeps it queued and
            # delivers it when the broker returns, while the caller (the outbox
            # relay) also resends it: a needless duplicate.
            self._purge()
            raise RuntimeError(f"Kafka publish timed out with {remaining} message(s) undelivered")
        if not delivered or not isinstance(delivered[0], int):
            raise RuntimeError(f"Kafka publish failed: {delivered[0] if delivered else 'timeout'}")
        return delivered[0]

    def _purge(self) -> None:
        purge = getattr(self.producer, "purge", None)
        if purge is not None:
            purge(in_queue=True, in_flight=True, blocking=False)
            self.producer.poll(0)


@dataclass(frozen=True)
class ConsumedEvent:
    topic: str
    partition: int
    offset: int
    key: str
    value: dict
    trace_id: str
    published_at: float


class KafkaEventConsumer:
    """At-least-once consumption with an explicit dead-letter path.

    Offsets are committed only after the handler returns, so a crash re-delivers
    rather than loses. A message the handler cannot process is routed to
    ``<topic>.dlq`` and the stream continues: a single poisoned record must not
    be able to stop an evidence projection, because a stalled projection is the
    same as no monitoring at all.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topics: list[str] | str,
        group_id: str,
        *,
        from_beginning: bool = True,
        dead_letter: bool = True,
    ) -> None:
        kafka = _require_kafka()
        self.topics = [topics] if isinstance(topics, str) else list(topics)
        self.consumer = kafka.Consumer({
            **kafka_security_config(),
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest" if from_beginning else "latest",
        })
        self.consumer.subscribe(self.topics)
        self._dead_letter = (
            KafkaEventPublisher(bootstrap_servers, self.topics[0] + DEAD_LETTER_SUFFIX,
                                client_id="fssaira-dlq")
            if dead_letter else None
        )
        self._running = False
        self.processed = 0
        self.dead_lettered = 0

    def poll(self, timeout: float = 1.0) -> ConsumedEvent | None:
        message = self.consumer.poll(timeout)
        if message is None:
            return None
        if not self._broker_message_is_usable(message):
            return None
        return self._parse(message)

    @staticmethod
    def _broker_message_is_usable(message) -> bool:
        error = message.error()
        if not error:
            return True
        kafka = _require_kafka()
        if error.code() == kafka.KafkaError._PARTITION_EOF:
            return False
        raise RuntimeError(f"Kafka consume failed: {error}")

    @staticmethod
    def _parse(message) -> ConsumedEvent | None:
        try:
            envelope = json.loads(message.value())
            if not isinstance(envelope, dict) or not isinstance(envelope.get("value"), dict):
                return None
            published_at = float(envelope.get("published_at", 0.0))
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        return ConsumedEvent(
            topic=message.topic(),
            partition=message.partition(),
            offset=message.offset(),
            key=(message.key() or b"").decode(errors="replace"),
            value=envelope["value"],
            trace_id=envelope.get("trace_id", ""),
            published_at=published_at,
        )

    def stream(self, timeout: float = 1.0) -> Iterator[ConsumedEvent]:
        self._running = True
        while self._running:
            event = self.poll(timeout)
            if event is not None:
                yield event

    def run(self, handler: Callable[[ConsumedEvent], None], *, timeout: float = 1.0) -> None:
        """Consume until interrupted. Commits only after the handler succeeds."""
        self._running = True

        def stop(*_args):  # pragma: no cover - signal path
            self._running = False

        try:
            signal.signal(signal.SIGTERM, stop)
            signal.signal(signal.SIGINT, stop)
        except ValueError:  # pragma: no cover - not the main thread
            pass

        try:
            while self._running:
                message = self.consumer.poll(timeout)
                if message is None:
                    continue
                if not self._broker_message_is_usable(message):
                    continue
                self._process_message(message, handler)
        finally:
            self.close()

    def _process_message(self, message, handler: Callable[[ConsumedEvent], None]) -> None:
        """Process and commit one message only after success or durable DLQ publication."""
        event = self._parse(message)
        if event is None:
            self._to_dead_letter({"raw": repr(message.value())[:2000]}, "unparseable")
        else:
            try:
                handler(event)
            except Exception as exc:
                self._to_dead_letter(
                    {"value": event.value, "trace_id": event.trace_id,
                     "offset": event.offset, "partition": event.partition},
                    f"{type(exc).__name__}: {exc}",
                )
        # Reaching this line means the handler succeeded or a DLQ publisher
        # acknowledged the failure record. Otherwise _to_dead_letter raises and
        # the source offset remains uncommitted for recovery.
        self.consumer.commit(message, asynchronous=False)
        self.processed += 1

    def _to_dead_letter(self, payload: dict, reason: str) -> None:
        if self._dead_letter is None:
            raise RuntimeError(
                "message processing failed and no dead-letter publisher is configured; "
                "source offset was not committed"
            )
        try:
            self._dead_letter.append({"reason": reason, **payload}, key="dlq")
        except Exception as exc:
            raise RuntimeError(
                "dead-letter publication failed; source offset was not committed"
            ) from exc
        self.dead_lettered += 1

    def stop(self) -> None:
        self._running = False

    def close(self) -> None:
        with contextlib.suppress(Exception):  # pragma: no cover
            self.consumer.close()


class EvidenceProjector:
    """Rebuilds a read model of control-plane events for independent monitoring.

    This in-memory read model is idempotent for ordered partition delivery and
    for an event republished by the outbox relay (same ``event_id``, new offset).
    After restart, rebuild from the beginning; offsets and projected rows are
    not persistent here. A durable projection must commit both atomically.

    The projector is intentionally separate from the control plane. If the same
    process that decides also reports, an operator has one story and no way to
    check it. Running this against the log gives a second, independently
    derivable view -- which is the only kind of monitoring that can contradict
    the system it monitors.
    """

    def __init__(self) -> None:
        self.by_resource: dict[str, list[dict]] = {}
        self.counts: dict[str, int] = {}
        self.last_offset: dict[str, int] = {}
        #: Stable ``event_id`` values already applied. The SQL outbox relay
        #: delivers at least once, so one event can reach a *new* offset twice.
        self.seen_event_ids: set[str] = set()

    def apply(self, event: ConsumedEvent) -> None:
        # One ordered consumer per partition: ignore broker redelivery/replay.
        position = f"{event.topic}/{event.partition}"
        if event.offset <= self.last_offset.get(position, -1):
            return
        event_id = event.value.get("event_id")
        if event_id is not None and event_id in self.seen_event_ids:
            self.last_offset[position] = event.offset
            return
        if event_id is not None:
            self.seen_event_ids.add(event_id)
        kind = event.value.get("kind", "unknown")
        payload = event.value.get("payload", {})
        resource = (
            payload.get("resource_id") or payload.get("case_id") or event.key or "unknown"
        )
        self.counts[kind] = self.counts.get(kind, 0) + 1
        self.last_offset[f"{event.topic}/{event.partition}"] = event.offset
        self.by_resource.setdefault(resource, []).append({
            "kind": kind, "trace_id": event.trace_id, "offset": event.offset, "payload": payload,
        })

    def timeline(self, resource_id: str) -> list[dict]:
        return list(self.by_resource.get(resource_id, ()))

    def summary(self) -> dict:
        return {
            "resources": len(self.by_resource),
            "events_by_kind": dict(sorted(self.counts.items())),
            "last_offsets": dict(sorted(self.last_offset.items())),
        }


class DurableEvidenceProjector:
    """:class:`EvidenceProjector` whose view and Kafka positions survive restarts.

    Each event is applied in one database transaction that writes the projected
    row, records its ``event_id``, and advances the partition's next offset. A
    crash therefore leaves either the whole event applied or none of it, and a
    restarted consumer resumes from :meth:`resume_offsets` instead of rebuilding
    from the beginning. Events redelivered at an old offset, or republished by
    the outbox relay under the same ``event_id`` at a new offset, are skipped.

    ``url`` is ``sqlite:///path`` or ``postgresql://…``. Keep this database apart
    from the control plane's, so the monitor can contradict it.
    """

    def __init__(self, url: str, schema: str = "fssaira_projection") -> None:
        from .sql_backend import SQLITE, open_postgres, open_sqlite

        if url.startswith("sqlite://"):
            path = url.replace("sqlite:///", "").replace("sqlite://", "") or ":memory:"
            self.database = open_sqlite(path, schema, create_schema=False)
        elif url.startswith(("postgres://", "postgresql://")):
            self.database = open_postgres(url, schema, create_schema=False)
        else:
            raise ValueError("projection URL must be sqlite:/// or postgresql://")
        d, t = self.database.dialect, self.database.table
        statements = [] if d is SQLITE else [f"CREATE SCHEMA IF NOT EXISTS {schema}"]
        statements += [
            f"""CREATE TABLE IF NOT EXISTS {t('projection_positions')} (
                    topic {d.text_type} NOT NULL, kafka_partition {d.big_int} NOT NULL,
                    next_offset {d.big_int} NOT NULL, PRIMARY KEY (topic, kafka_partition))""",
            f"""CREATE TABLE IF NOT EXISTS {t('projection_seen')} (
                    event_id {d.text_type} PRIMARY KEY)""",
            f"""CREATE TABLE IF NOT EXISTS {t('projection_events')} (
                    topic {d.text_type} NOT NULL, kafka_partition {d.big_int} NOT NULL,
                    kafka_offset {d.big_int} NOT NULL, resource {d.text_type} NOT NULL,
                    kind {d.text_type} NOT NULL, trace_id {d.text_type} NOT NULL,
                    payload {d.json_type} NOT NULL,
                    PRIMARY KEY (topic, kafka_partition, kafka_offset))""",
        ]
        with self.database.transaction() as unit:
            for statement in statements:
                unit.execute(statement)

    def _store_position(self, unit, topic: str, partition: int, next_offset: int) -> None:
        unit.execute(
            f"INSERT INTO {self.database.table('projection_positions')} "
            "(topic, kafka_partition, next_offset) VALUES (?, ?, ?) "
            "ON CONFLICT (topic, kafka_partition) DO UPDATE SET next_offset = EXCLUDED.next_offset",
            (topic, partition, next_offset),
        )

    def apply(self, event: ConsumedEvent) -> bool:
        """Apply one event. Returns ``False`` when it was a duplicate."""
        t = self.database.table
        with self.database.transaction() as unit:
            row = unit.one(
                f"SELECT next_offset FROM {t('projection_positions')} "
                "WHERE topic = ? AND kafka_partition = ?", (event.topic, event.partition))
            if row is not None and event.offset < int(row[0]):
                return False
            event_id = event.value.get("event_id")
            duplicate = event_id is not None and unit.one(
                f"SELECT 1 FROM {t('projection_seen')} WHERE event_id = ?", (event_id,)
            ) is not None
            if not duplicate:
                payload = event.value.get("payload", {})
                resource = (payload.get("resource_id") or payload.get("case_id")
                            or event.key or "unknown")
                unit.execute(
                    f"INSERT INTO {t('projection_events')} (topic, kafka_partition, kafka_offset, "
                    "resource, kind, trace_id, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (event.topic, event.partition, event.offset, resource,
                     event.value.get("kind", "unknown"), event.trace_id,
                     self.database.dumps(payload)),
                )
                if event_id is not None:
                    unit.execute(f"INSERT INTO {t('projection_seen')} (event_id) VALUES (?)",
                                 (event_id,))
            self._store_position(unit, event.topic, event.partition, event.offset + 1)
            return not duplicate

    def resume_offsets(self) -> dict[tuple[str, int], int]:
        """Where a restarted consumer should continue, per topic and partition."""
        with self.database.transaction() as unit:
            return {(r[0], int(r[1])): int(r[2]) for r in unit.all(
                f"SELECT topic, kafka_partition, next_offset "
                f"FROM {self.database.table('projection_positions')}")}

    def timeline(self, resource_id: str) -> list[dict]:
        with self.database.transaction() as unit:
            rows = unit.all(
                f"SELECT kind, trace_id, kafka_offset, payload "
                f"FROM {self.database.table('projection_events')} WHERE resource = ? "
                "ORDER BY topic, kafka_partition, kafka_offset", (resource_id,))
        return [{"kind": r[0], "trace_id": r[1], "offset": int(r[2]),
                 "payload": self.database.loads(r[3])} for r in rows]

    def summary(self) -> dict:
        with self.database.transaction() as unit:
            kinds = unit.all(f"SELECT kind, COUNT(*) FROM {self.database.table('projection_events')} "
                             "GROUP BY kind ORDER BY kind")
            resources = unit.one(
                f"SELECT COUNT(DISTINCT resource) FROM {self.database.table('projection_events')}")
        return {
            "resources": int(resources[0]) if resources else 0,
            "events_by_kind": {r[0]: int(r[1]) for r in kinds},
            "last_offsets": {f"{topic}/{partition}": offset - 1
                             for (topic, partition), offset in sorted(self.resume_offsets().items())},
        }


__all__ = [
    "ConsumedEvent", "DEAD_LETTER_SUFFIX", "DEFAULT_TOPIC", "DurableEvidenceProjector",
    "EvidenceProjector",
    "IMPORT_TOPIC", "KafkaEventConsumer", "KafkaEventPublisher",
]
