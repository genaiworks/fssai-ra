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


class KafkaEventPublisher:
    """Idempotent, acknowledged publication of one control-plane event."""

    name = "kafka"

    def __init__(self, bootstrap_servers: str, topic: str = DEFAULT_TOPIC,
                 *, client_id: str = "fssaira-control-plane", flush_timeout: float = 10.0) -> None:
        kafka = _require_kafka()
        self.topic = topic
        self.flush_timeout = flush_timeout
        self.producer = kafka.Producer({
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
        self.producer.flush(self.flush_timeout)
        if not delivered or not isinstance(delivered[0], int):
            raise RuntimeError(f"Kafka publish failed: {delivered[0] if delivered else 'timeout'}")
        return delivered[0]


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
        if message is None or message.error():
            return None
        return self._parse(message)

    @staticmethod
    def _parse(message) -> ConsumedEvent | None:
        try:
            envelope = json.loads(message.value())
        except (json.JSONDecodeError, TypeError):
            return None
        return ConsumedEvent(
            topic=message.topic(),
            partition=message.partition(),
            offset=message.offset(),
            key=(message.key() or b"").decode(errors="replace"),
            value=envelope.get("value", {}),
            trace_id=envelope.get("trace_id", ""),
            published_at=float(envelope.get("published_at", 0.0)),
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
                if message.error():
                    continue
                event = self._parse(message)
                if event is None:
                    self._to_dead_letter({"raw": repr(message.value())[:2000]}, "unparseable")
                    self.consumer.commit(message, asynchronous=False)
                    continue
                try:
                    handler(event)
                except Exception as exc:
                    self._to_dead_letter(
                        {"value": event.value, "trace_id": event.trace_id,
                         "offset": event.offset, "partition": event.partition},
                        f"{type(exc).__name__}: {exc}",
                    )
                self.processed += 1
                self.consumer.commit(message, asynchronous=False)
        finally:
            self.close()

    def _to_dead_letter(self, payload: dict, reason: str) -> None:
        self.dead_lettered += 1
        if self._dead_letter is None:
            return
        # The dead-letter path must never be able to stop the stream it protects.
        with contextlib.suppress(Exception):  # pragma: no cover
            self._dead_letter.append({"reason": reason, **payload}, key="dlq")

    def stop(self) -> None:
        self._running = False

    def close(self) -> None:
        with contextlib.suppress(Exception):  # pragma: no cover
            self.consumer.close()


class EvidenceProjector:
    """Rebuilds a read model of control-plane events for independent monitoring.

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

    def apply(self, event: ConsumedEvent) -> None:
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


__all__ = [
    "ConsumedEvent", "DEAD_LETTER_SUFFIX", "DEFAULT_TOPIC", "EvidenceProjector",
    "IMPORT_TOPIC", "KafkaEventConsumer", "KafkaEventPublisher",
]
