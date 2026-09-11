"""Prometheus exposition and optional OpenTelemetry tracing.

Observability is a control, not a convenience. Two of the architecture's claims
are only meaningful if someone is watching: tamper-evidence detects an edit
*that a monitor notices*, and fail-secure denial preserves service *if the
denial rate is visible to the people who own the manual fallback*. A deployment
with no metrics has a hash chain nobody verifies and a denial nobody answers.

Metric names are stable and are the same names used in the paper's result
tables, so a reader can map a figure to a live gauge.

Note on egress: a metrics endpoint is an outbound interface. It appears in
:class:`fssaira.diode_transport.InterfaceInventory` for that reason, and the
exporter deliberately publishes counters only -- never payloads, identifiers, or
record contents -- so that scraping it cannot become a data path.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

#: name -> (type, help). Keep in step with :class:`fssaira.metrics.Metrics`.
DEFINITIONS: dict[str, tuple[str, str]] = {
    "fssaira_tool_calls_allowed_total": ("counter", "Tool calls authorized by the policy enforcement point"),
    "fssaira_tool_calls_denied_total": ("counter", "Tool calls denied by the policy enforcement point"),
    "fssaira_egress_blocked_total": ("counter", "Outbound attempts denied by default-deny egress"),
    "fssaira_high_impact_denied_total": ("counter", "Consequential actions denied for want of a named human"),
    "fssaira_class_downgrade_attempts_total": ("counter", "Callers that understated their own action class"),
    "fssaira_quarantined_total": ("counter", "Artifacts refused at the import boundary"),
    "fssaira_rollbacks_total": ("counter", "Snapshot rollbacks performed"),
    "fssaira_tamper_detected_total": ("counter", "Evidence-chain verification failures observed"),
    "fssaira_mutations_total": ("counter", "Authoritative resource mutations performed"),
    "fssaira_outcomes_reconciled_total": ("counter", "Pending outcomes reconciled after interruption"),
    "fssaira_evidence_records": ("gauge", "Records currently in the evidence ledger"),
    "fssaira_evidence_chain_valid": ("gauge", "1 when the evidence chain verifies, 0 when it does not"),
    "fssaira_pending_outcomes": ("gauge", "Outcomes awaiting evidence reconciliation"),
    "fssaira_configuration_warnings": ("gauge", "Active production-readiness warnings"),
    "fssaira_model_reachable": ("gauge", "1 when the configured model backend answered its health check"),
    "fssaira_build_info": ("gauge", "Build and profile labels; always 1"),
}

_COUNTER_FROM_METRIC = {
    "tool_calls_allowed": "fssaira_tool_calls_allowed_total",
    "tool_calls_denied": "fssaira_tool_calls_denied_total",
    "egress_blocked": "fssaira_egress_blocked_total",
    "high_impact_denied": "fssaira_high_impact_denied_total",
    "class_downgrade_attempts": "fssaira_class_downgrade_attempts_total",
    "quarantined": "fssaira_quarantined_total",
    "rollbacks": "fssaira_rollbacks_total",
    "tamper_detected": "fssaira_tamper_detected_total",
    "mutations": "fssaira_mutations_total",
    "outcomes_reconciled": "fssaira_outcomes_reconciled_total",
}


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def render_prometheus(samples: dict[str, Any], labels: dict[str, str] | None = None) -> str:
    """Render a metric dictionary as a Prometheus text exposition."""
    label_text = ""
    if labels:
        inner = ",".join(f'{key}="{_escape(value)}"' for key, value in sorted(labels.items()))
        label_text = "{" + inner + "}"
    lines: list[str] = []
    for name, value in sorted(samples.items()):
        kind, description = DEFINITIONS.get(name, ("gauge", "FSSAI-RA metric"))
        lines.append(f"# HELP {name} {description}")
        lines.append(f"# TYPE {name} {kind}")
        if isinstance(value, bool):
            value = int(value)
        lines.append(f"{name}{label_text} {value}")
    return "\n".join(lines) + "\n"


def samples_from(metrics: Any = None, *, evidence: Any = None, extra: dict | None = None) -> dict:
    """Collect a metric snapshot from the live control-plane objects."""
    samples: dict[str, Any] = {}
    if metrics is not None:
        snapshot = metrics.snapshot() if hasattr(metrics, "snapshot") else dict(metrics)
        for field_name, metric_name in _COUNTER_FROM_METRIC.items():
            if field_name in snapshot:
                samples[metric_name] = snapshot[field_name]
    if evidence is not None:
        try:
            samples["fssaira_evidence_records"] = len(evidence)
            samples["fssaira_evidence_chain_valid"] = int(bool(evidence.verify()))
        except Exception:  # pragma: no cover - a broken store must not break scraping
            samples["fssaira_evidence_chain_valid"] = 0
    samples.update(extra or {})
    return samples


@dataclass
class Telemetry:
    """Process-wide counters plus an optional tracer."""

    service: str = "fssaira-control-plane"
    labels: dict = field(default_factory=dict)
    _counters: dict = field(default_factory=dict)

    def increment(self, name: str, amount: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + amount

    def set(self, name: str, value: float) -> None:
        self._counters[name] = value

    def snapshot(self) -> dict:
        return dict(self._counters)

    def render(self, extra: dict | None = None) -> str:
        return render_prometheus({**self._counters, **(extra or {})}, self.labels)


def configure_tracing(service_name: str = "fssaira-control-plane") -> bool:
    """Enable OpenTelemetry tracing when the optional dependency is installed.

    Returns ``False`` and changes nothing when it is not, because an observability
    dependency must never be the reason an authorization service fails to start.
    """
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return False
    try:  # pragma: no cover - optional dependency
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return False
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")))
    trace.set_tracer_provider(provider)
    return True


def instrument_fastapi(app: Any) -> bool:  # pragma: no cover - optional dependency
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        return False
    FastAPIInstrumentor.instrument_app(app)
    return True


class Timer:
    """Tiny context manager for latency numbers in the evaluation report."""

    def __init__(self) -> None:
        self.elapsed = 0.0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self.elapsed = time.perf_counter() - self._start


__all__ = [
    "CONTENT_TYPE", "DEFINITIONS", "Telemetry", "Timer",
    "configure_tracing", "instrument_fastapi", "render_prometheus", "samples_from",
]
