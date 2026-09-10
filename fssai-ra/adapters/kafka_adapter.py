"""Kafka adapter for the event-transport seam (implements KafkaLike).

Enable with:  pip install kafka-python
Then use KafkaEventLog(bootstrap="host:9092", topic="fssaira.events") in place
of the in-memory EventLog. Ordering, retention, and replay are provided by the
broker; keep per-item hash + trace id in the value envelope as the reference
log does.
"""
from __future__ import annotations

import hashlib
import json


class KafkaEventLog:
    def __init__(self, bootstrap: str, topic: str) -> None:
        try:
            from kafka import KafkaConsumer, KafkaProducer  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise ImportError("KafkaEventLog requires 'kafka-python' (pip install kafka-python)") from exc
        self._topic = topic
        self._producer = KafkaProducer(
            bootstrap_servers=bootstrap,
            value_serializer=lambda v: json.dumps(v, default=str).encode(),
            acks="all", enable_idempotence=True,
        )
        self._KafkaConsumer = KafkaConsumer
        self._bootstrap = bootstrap

    def append(self, value: dict, key: str = "", trace_id: str = "") -> int:
        body = json.dumps(value, sort_keys=True, default=str)
        envelope = {"value": value, "key": key,
                    "trace_id": trace_id or hashlib.sha256(body.encode()).hexdigest()[:12]}
        fut = self._producer.send(self._topic, envelope, key=key.encode() if key else None)
        meta = fut.get(timeout=10)
        return meta.offset

    def read(self, from_offset: int = 0):  # pragma: no cover - needs a broker
        consumer = self._KafkaConsumer(
            self._topic, bootstrap_servers=self._bootstrap,
            auto_offset_reset="earliest", enable_auto_commit=False,
            value_deserializer=lambda b: json.loads(b.decode()),
        )
        return list(consumer)
