"""Compatibility exports for the maintained Kafka adapters.

Use :class:`fssaira.kafka_backend.KafkaEventPublisher` for writes and
:class:`fssaira.kafka_backend.KafkaEventConsumer` for replay. The former
``kafka-python`` sketch ignored ``from_offset`` and could block forever in
``read``; keeping two implementations also let delivery guarantees drift.
"""
from __future__ import annotations

from fssaira.kafka_backend import KafkaEventConsumer, KafkaEventPublisher


class KafkaEventLog(KafkaEventPublisher):
    """Backward-compatible publisher name from the pre-1.0 examples."""

    def __init__(self, bootstrap: str, topic: str) -> None:
        super().__init__(bootstrap, topic)

    def read(self, from_offset: int = 0):
        raise RuntimeError(
            "KafkaEventLog.read was removed because its from_offset argument was ignored. "
            "Use KafkaEventConsumer with a dedicated group and explicit offset policy."
        )


__all__ = ["KafkaEventConsumer", "KafkaEventLog", "KafkaEventPublisher"]
