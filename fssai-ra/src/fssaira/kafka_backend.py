"""Kafka event publisher for the control-plane event seam."""
from __future__ import annotations

import hashlib
import json


class KafkaEventPublisher:
    def __init__(self, bootstrap_servers: str, topic: str = "fssaira.events") -> None:
        try:
            from confluent_kafka import Producer
        except ImportError as exc:  # pragma: no cover
            raise ImportError("Kafka publisher requires the 'kafka' extra") from exc
        self.topic = topic
        self.producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "enable.idempotence": True,
            "acks": "all",
            "client.id": "fssaira-control-plane",
        })

    def append(self, value: dict, key: str = "", trace_id: str = "") -> int:
        body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        envelope = json.dumps({
            "value": value,
            "trace_id": trace_id or hashlib.sha256(body.encode()).hexdigest()[:16],
        }, sort_keys=True, default=str).encode()
        delivered = []

        def callback(error, message):
            if error is not None:
                delivered.append(error)
            else:
                delivered.append(message.offset())

        self.producer.produce(self.topic, value=envelope, key=key.encode() or None, callback=callback)
        self.producer.flush(10)
        if not delivered or not isinstance(delivered[0], int):
            raise RuntimeError(f"Kafka publish failed: {delivered[0] if delivered else 'timeout'}")
        return delivered[0]
