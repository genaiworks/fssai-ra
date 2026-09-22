"""Edit only the three TODO functions. All data is synthetic."""
SECRET = "SYNTHETIC-WORKSHOP-SECRET"


def read_secret(guard, ctx, *, fail=False):
    # TODO 1: Record secret-credentials BEFORE a possible exception.
    if fail:
        raise RuntimeError("simulated read failure")
    return SECRET


def handoff(guard, producer, consumer, text):
    # TODO 2: Carry the producer's label to the consumer.
    return text


def publish(guard, ctx, text, *, recipient, purpose):
    # TODO 3: Apply the release policy before returning text to the channel sink.
    return text
