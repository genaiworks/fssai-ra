"""Broker-free checks for Kafka acknowledgement and poison-message semantics."""
import json

import pytest

from fssaira.kafka_backend import KafkaEventConsumer


class Message:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value

    def topic(self):
        return "events"

    def partition(self):
        return 0

    def offset(self):
        return 7

    def key(self):
        return b"case-1"


class Consumer:
    def __init__(self):
        self.commits = []

    def commit(self, message, asynchronous=False):
        self.commits.append((message, asynchronous))


class DeadLetter:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.items = []

    def append(self, value, key="", trace_id=""):
        if self.fail:
            raise RuntimeError("dlq unavailable")
        self.items.append((key, value))
        return 1


def built_consumer(dead_letter=None):
    instance = KafkaEventConsumer.__new__(KafkaEventConsumer)
    instance.consumer = Consumer()
    instance._dead_letter = dead_letter
    instance.processed = 0
    instance.dead_lettered = 0
    return instance


def valid_message():
    return Message(json.dumps({
        "value": {"kind": "action.proposed", "payload": {"case_id": "case-1"}},
        "trace_id": "trace-1",
        "published_at": 123.0,
    }).encode())


def test_success_is_committed_after_the_handler_returns():
    consumer = built_consumer()
    seen = []

    consumer._process_message(valid_message(), seen.append)

    assert seen[0].trace_id == "trace-1"
    assert consumer.processed == 1
    assert len(consumer.consumer.commits) == 1


def test_handler_failure_without_a_dlq_never_commits_the_source_offset():
    consumer = built_consumer()

    with pytest.raises(RuntimeError, match="offset was not committed"):
        consumer._process_message(valid_message(), lambda _event: 1 / 0)

    assert consumer.consumer.commits == []
    assert consumer.processed == 0


def test_dlq_failure_never_commits_the_source_offset():
    consumer = built_consumer(DeadLetter(fail=True))

    with pytest.raises(RuntimeError, match="dead-letter publication failed"):
        consumer._process_message(valid_message(), lambda _event: 1 / 0)

    assert consumer.consumer.commits == []
    assert consumer.dead_lettered == 0


def test_poison_record_is_committed_only_after_dlq_acknowledgement():
    dlq = DeadLetter()
    consumer = built_consumer(dlq)

    consumer._process_message(Message(b'{"value": []}'), lambda _event: None)

    assert len(dlq.items) == 1
    assert consumer.dead_lettered == 1
    assert len(consumer.consumer.commits) == 1


@pytest.mark.parametrize(
    "payload",
    (b"not-json", b"[]", b'{"value": []}', b'{"value": {}, "published_at": "never"}'),
)
def test_malformed_envelopes_are_not_returned_as_events(payload):
    assert KafkaEventConsumer._parse(Message(payload)) is None
