"""Reference solution; issuer and orchestration code are trusted."""
SECRET = "SYNTHETIC-WORKSHOP-SECRET"


def read_secret(guard, ctx, *, fail=False):
    guard.observe(ctx, {"secret-credentials"})
    if fail:
        raise RuntimeError("simulated read failure")
    return SECRET


def handoff(guard, producer, consumer, text):
    guard.consume(consumer, producer)
    return text


def publish(guard, ctx, text, *, recipient, purpose):
    return guard.release(ctx, text, recipient=recipient, purpose=purpose)
