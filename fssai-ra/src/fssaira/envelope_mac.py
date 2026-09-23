"""Authenticate Kafka envelopes end to end.

Kafka in this stack does not authenticate producers: anything that can reach the
broker can write to ``fssaira.imports`` or ``fssaira.events``. TLS encrypts that
traffic but does not change who may write. Without an authenticator, a forged
import skips the gateway's source-signature check entirely -- Spark's content
hash is computed by whoever wrote the record -- and a forged lifecycle event
misleads the independent monitor.

Each producer therefore adds ``mac``: HMAC-SHA256 over the canonical JSON of
``{"trace_id", "value"}`` under a key only legitimate producers and consumers
hold (``FSSAI_IMPORT_ENVELOPE_KEY`` for imports, ``FSSAI_EVENT_ENVELOPE_KEY`` for
lifecycle events). Consumers reject a missing or wrong MAC. This proves the
record came from a key holder and was not altered; it does not stop a key holder
from lying, and it does not hide content (use TLS for that).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os


def canonical(value: dict, trace_id: str) -> bytes:
    return json.dumps({"trace_id": trace_id, "value": value}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def sign(key: bytes, value: dict, trace_id: str) -> str:
    return hmac.new(key, canonical(value, trace_id), hashlib.sha256).hexdigest()


def verify(key: bytes, envelope: dict) -> bool:
    mac = envelope.get("mac")
    if not isinstance(mac, str) or not isinstance(envelope.get("value"), dict):
        return False
    expected = sign(key, envelope["value"], str(envelope.get("trace_id", "")))
    return hmac.compare_digest(expected, mac)


def key_from_env(name: str) -> bytes | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    if len(raw) < 32:
        raise ValueError(f"{name} must be at least 32 characters")
    return raw.encode("utf-8")


__all__ = ["canonical", "key_from_env", "sign", "verify"]
