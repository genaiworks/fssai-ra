"""Import boundary: zero-trust ingestion in front of the diode.

Every inbound artifact is checked for declared type, size, schema, and source
signature, then scanned and stripped of active content before a protocol break
normalizes it and the diode carries it inward. Anything that fails is
quarantined with a reason, never delivered. Imported text is wrapped as
:class:`UntrustedEvidence` so downstream models treat it as data.

**What sanitisation does and does not do.** The marker list below removes
mechanically recognisable active content -- script tags, URL schemes, the
well-known "ignore previous instructions" family. It does not detect
instructions written in ordinary language, and the architecture does not rely on
it doing so. The load-bearing controls are downstream: retrieved text is never
promoted to an instruction, egress tools are denied by default, and
consequential actions need an approval bound to an exact proposal. Sanitisation
is a cheap first filter, reported as such in ``docs/ASSURANCE.md``.

Signature verification uses HMAC over the declared source key. That
authenticates *the channel*, not the truth of the content: a compromised but
correctly-keyed publisher still gets through, which is why poisoned data is
handled by lineage and rollback rather than by the boundary.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass, field

from .bounded_intelligence import UntrustedEvidence
from .diode import OneWayChannel
from .evidence import EvidenceLedger
from .metrics import Metrics

#: Substrings whose presence marks a line as active content. Case-insensitive.
ACTIVE_MARKERS = (
    "<script", "</script", "javascript:", "data:text/html", "vbscript:",
    "<iframe", "<object", "<embed", "onerror=", "onload=",
    "ignore previous", "ignore all previous", "disregard the above",
    "system:", "### system", "<|im_start|>", "[system]",
    "exfiltrate", "send to http", "curl ", "wget ", "http://", "https://",
    "base64,", "eval(", "__import__", "subprocess",
)

#: Patterns removed inline rather than by dropping the whole line, so that a
#: single URL in an otherwise useful paragraph does not destroy the evidence.
INLINE_PATTERNS = (
    re.compile(r"https?://\S+", re.IGNORECASE),
    re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
)


@dataclass
class RawInput:
    source: str
    content_type: str
    size: int
    data: str
    signature: str


@dataclass(frozen=True)
class IngestReport:
    """What the boundary did, for the evidence record and the console."""

    source: str
    accepted: bool
    reason: str = ""
    stripped_markers: tuple[str, ...] = ()
    bytes_in: int = 0
    bytes_out: int = 0
    content_hash: str = ""


class QuarantineError(RuntimeError):
    """Raised when an artifact is rejected. It is never delivered inward."""

    def __init__(self, reason: str, report: IngestReport | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.report = report


class ImportBoundary:
    def __init__(self, diode: OneWayChannel, evidence: EvidenceLedger, append_token: str,
                 metrics: Metrics, *, trusted_keys: dict, allowed_types: set, max_size: int,
                 strip_inline: bool = True) -> None:
        self._diode = diode
        self._evidence = evidence
        self._token = append_token
        self._m = metrics
        self._keys = dict(trusted_keys)
        self._allowed_types = set(allowed_types)
        self._max_size = max_size
        self._strip_inline = strip_inline
        self.last_report: IngestReport | None = None

    # -- administration ----------------------------------------------------
    def trust(self, source: str, key: str) -> None:
        """Register a source key. An administrative act, not an agent action."""
        if not source or not key:
            raise ValueError("source and key must both be non-empty")
        self._keys[source] = key

    def untrust(self, source: str) -> None:
        self._keys.pop(source, None)

    @property
    def trusted_sources(self) -> tuple[str, ...]:
        return tuple(sorted(self._keys))

    @staticmethod
    def sign(key: str, data: str) -> str:
        """Helper so publishers and tests compute the same digest as the check."""
        return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()

    # -- checks ------------------------------------------------------------
    def _expected_sig(self, source: str, data: str) -> str | None:
        key = self._keys.get(source)
        return None if key is None else self.sign(key, data)

    def _reject_reason(self, raw: RawInput) -> str | None:
        if raw.content_type not in self._allowed_types:
            return f"disallowed type {raw.content_type}"
        if raw.size > self._max_size:
            return f"oversize {raw.size}>{self._max_size}"
        if raw.size != len(raw.data.encode()):
            return "declared size does not match payload"
        expected = self._expected_sig(raw.source, raw.data)
        if expected is None:
            return "unknown source"
        if not hmac.compare_digest(expected, raw.signature):
            return "bad or unknown signature"
        return None

    def _sanitize(self, text: str) -> tuple[str, list[str]]:
        lowered = text.lower()
        flags = [marker.strip() for marker in ACTIVE_MARKERS if marker in lowered]
        working = text
        if self._strip_inline:
            for pattern in INLINE_PATTERNS:
                working = pattern.sub("[removed]", working)
        kept = [
            line for line in working.splitlines()
            if not any(marker in line.lower() for marker in ACTIVE_MARKERS)
        ]
        return "\n".join(kept), flags

    # -- the one inward path ----------------------------------------------
    def ingest(self, raw: RawInput) -> UntrustedEvidence:
        reason = self._reject_reason(raw)
        if reason is not None:
            report = IngestReport(raw.source, accepted=False, reason=reason, bytes_in=raw.size)
            self.last_report = report
            self._m.quarantined += 1
            self._evidence.append(
                "quarantine", {"source": raw.source, "reason": reason, "bytes": raw.size},
                token=self._token,
            )
            raise QuarantineError(reason, report)

        clean, flags = self._sanitize(raw.data)
        content_hash = hashlib.sha256(clean.encode()).hexdigest()
        report = IngestReport(
            source=raw.source, accepted=True, stripped_markers=tuple(flags),
            bytes_in=raw.size, bytes_out=len(clean.encode()), content_hash=content_hash,
        )
        self.last_report = report
        evidence = UntrustedEvidence(source=raw.source, text=clean)
        # Protocol break: hand a normalized, minimal record to the diode.
        self._diode.send_inward({
            "source": raw.source, "text": clean, "stripped": flags, "content_hash": content_hash,
        })
        self._evidence.append(
            "ingest",
            {"source": raw.source, "stripped_markers": flags,
             "bytes": report.bytes_out, "content_hash": content_hash},
            token=self._token,
        )
        return evidence


__all__ = [
    "ACTIVE_MARKERS", "ImportBoundary", "IngestReport", "QuarantineError", "RawInput",
]
