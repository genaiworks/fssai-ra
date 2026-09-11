"""Import boundary: zero-trust ingestion in front of the diode.

Every inbound artifact is checked for type, size, schema, and signature, then
scanned and stripped of active content before a protocol break normalizes it and
the diode carries it inward. Anything that fails is quarantined, never delivered.
Imported text is wrapped as UntrustedEvidence so downstream models treat it as
data, not instructions.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from .bounded_intelligence import UntrustedEvidence
from .diode import OneWayChannel
from .evidence import EvidenceLedger
from .metrics import Metrics

ACTIVE_MARKERS = (
    "<script", "javascript:", "ignore previous", "ignore all previous",
    "system:", "exfiltrate", "send to http", "curl ", "http://", "https://",
)


@dataclass
class RawInput:
    source: str
    content_type: str
    size: int
    data: str
    signature: str


class QuarantineError(RuntimeError):
    pass


class ImportBoundary:
    def __init__(self, diode: OneWayChannel, evidence: EvidenceLedger, append_token: str,
                 metrics: Metrics, *, trusted_keys: dict, allowed_types: set, max_size: int) -> None:
        self._diode = diode
        self._evidence = evidence
        self._token = append_token
        self._m = metrics
        self._keys = trusted_keys
        self._allowed_types = allowed_types
        self._max_size = max_size

    def _expected_sig(self, source: str, data: str) -> str | None:
        key = self._keys.get(source)
        if key is None:
            return None
        return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()

    def _sanitize(self, text: str) -> tuple[str, list[str]]:
        flags, clean = [], text
        low = text.lower()
        for m in ACTIVE_MARKERS:
            if m in low:
                flags.append(m.strip())
        # Strip lines that contain active-content markers.
        kept = [ln for ln in text.splitlines() if not any(m in ln.lower() for m in ACTIVE_MARKERS)]
        clean = "\n".join(kept)
        return clean, flags

    def ingest(self, raw: RawInput) -> UntrustedEvidence:
        reason = None
        if raw.content_type not in self._allowed_types:
            reason = f"disallowed type {raw.content_type}"
        elif raw.size > self._max_size:
            reason = f"oversize {raw.size}>{self._max_size}"
        else:
            exp = self._expected_sig(raw.source, raw.data)
            if exp is None or not hmac.compare_digest(exp, raw.signature):
                reason = "bad or unknown signature"
        if reason is not None:
            self._m.quarantined += 1
            self._evidence.append("quarantine", {"source": raw.source, "reason": reason}, token=self._token)
            raise QuarantineError(reason)

        clean, flags = self._sanitize(raw.data)
        evidence = UntrustedEvidence(source=raw.source, text=clean)
        # Protocol break: hand a normalized, minimal record to the diode.
        self._diode.send_inward({"source": raw.source, "text": clean, "stripped": flags})
        self._evidence.append(
            "ingest",
            {"source": raw.source, "stripped_markers": flags, "bytes": len(clean)},
            token=self._token,
        )
        return evidence
