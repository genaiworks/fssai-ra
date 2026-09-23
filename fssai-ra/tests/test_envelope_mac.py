"""Forged Kafka records are rejected, whoever could reach the broker."""
import json

import pytest

from fssaira.envelope_mac import key_from_env, sign, verify
from fssaira.kafka_backend import KafkaEventConsumer, KafkaEventPublisher

KEY = b"k" * 32


def test_a_signed_envelope_verifies_and_any_change_breaks_it():
    value = {"source": "s", "text": "t", "stripped": [], "content_hash": "h"}
    envelope = {"value": value, "trace_id": "tr", "mac": sign(KEY, value, "tr")}
    assert verify(KEY, envelope)
    assert not verify(KEY, {**envelope, "trace_id": "other"})
    assert not verify(KEY, {**envelope, "value": {**value, "text": "forged"}})
    assert not verify(KEY, {k: v for k, v in envelope.items() if k != "mac"})
    assert not verify(b"x" * 32, envelope)


def test_short_keys_are_refused(monkeypatch):
    monkeypatch.setenv("FSSAI_EVENT_ENVELOPE_KEY", "too-short")
    with pytest.raises(ValueError):
        key_from_env("FSSAI_EVENT_ENVELOPE_KEY")


class StubProducer:
    def __init__(self):
        self.sent = []

    def produce(self, topic, value, key=None, callback=None):
        self.sent.append(value)
        callback(None, type("M", (), {"offset": lambda self: 0})())

    def flush(self, timeout):
        return 0


def test_the_publisher_signs_when_it_has_a_key():
    publisher = KafkaEventPublisher.__new__(KafkaEventPublisher)
    publisher.topic, publisher.flush_timeout = "t", 1.0
    publisher.producer, publisher.mac_key = StubProducer(), KEY
    publisher.append({"kind": "x"}, key="k", trace_id="tr")
    envelope = json.loads(publisher.producer.sent[0])
    assert verify(KEY, envelope)


class Message:
    def __init__(self, envelope):
        self._value = json.dumps(envelope).encode()

    def value(self):
        return self._value

    def topic(self):
        return "fssaira.events"

    def partition(self):
        return 0

    def offset(self):
        return 3

    def key(self):
        return b"k"

    def error(self):
        return None


class Commits:
    def commit(self, message, asynchronous=False):
        pass


def test_the_consumer_sends_forged_events_to_the_dead_letter_queue():
    consumer = KafkaEventConsumer.__new__(KafkaEventConsumer)
    consumer.consumer, consumer.processed, consumer.mac_key = Commits(), 0, KEY
    dead = []
    consumer._to_dead_letter = lambda payload, reason: dead.append(reason)
    handled = []
    value = {"kind": "action.executed", "payload": {}}
    consumer._process_message(Message({"value": value, "trace_id": "t", "mac": "0" * 64}),
                              handled.append)
    consumer._process_message(Message({"value": value, "trace_id": "t",
                                       "mac": sign(KEY, value, "t")}), handled.append)
    assert dead == ["envelope MAC missing or invalid"] and len(handled) == 1
