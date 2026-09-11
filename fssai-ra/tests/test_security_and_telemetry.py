"""Authentication, configuration honesty, and the counters an operator watches.

The v0.5.0 API accepted ``X-FSSAI-Identity`` and warned that it was spoofable.
A warning in a document is not a control, and a demonstration in which anyone can
approve their own award by editing a header does not demonstrate accountable
action. These tests hold the replacement to being real.
"""
import os

import pytest

from fssaira.runtime_factory import configuration_warnings, readiness
from fssaira.security import (
    AuthConfig,
    AuthenticationError,
    Authenticator,
    Principal,
    require_role,
)
from fssaira.telemetry import Telemetry, render_prometheus, samples_from


# ------------------------------------------------------------ authentication


def test_a_bearer_token_resolves_to_a_subject_and_roles():
    principal = Authenticator(AuthConfig()).authenticate(authorization="Bearer dev-officer-token")

    assert principal.subject == "officer.díaz"
    assert principal.has_role("student_support_officer")
    assert principal.method == "token"


def test_an_unknown_or_absent_token_is_refused():
    auth = Authenticator(AuthConfig())

    for credential in (None, "", "Bearer wrong", "Basic dXNlcjpwYXNz"):
        with pytest.raises(AuthenticationError):
            auth.authenticate(authorization=credential)


def test_header_identity_is_refused_unless_a_proxy_is_declared():
    """The v0.5.0 adapter still exists, but can no longer be used by accident."""
    auth = Authenticator(AuthConfig(mode="header"))

    with pytest.raises(AuthenticationError, match="authenticating proxy"):
        auth.authenticate(authorization=None, identity_header="attacker",
                          role_header="platform_operator")


def test_header_identity_works_once_the_operator_accepts_the_risk():
    auth = Authenticator(AuthConfig(mode="header", trust_proxy_headers=True))

    principal = auth.authenticate(
        authorization=None, identity_header="officer.one",
        role_header="student_support_officer,auditor",
    )

    assert principal.roles == ("student_support_officer", "auditor")
    assert principal.method == "proxy-header"


def test_development_credentials_are_announced_not_hidden():
    assert "development bearer tokens are active" in " ".join(AuthConfig().warnings())


def test_a_missing_role_is_a_permission_error_not_an_authentication_one():
    principal = Principal("officer.one", ("student_support_officer",))

    require_role(principal, "student_support_officer")
    with pytest.raises(PermissionError, match="platform_operator"):
        require_role(principal, "platform_operator")


# ------------------------------------------------------- configuration honesty


def test_teaching_defaults_are_reported_as_blocking(monkeypatch):
    for variable in ("FSSAI_APPROVAL_SIGNING_KEY", "FSSAI_EVIDENCE_TOKEN",
                     "FSSAI_DATABASE_URL", "FSSAI_REDIS_URL", "FSSAI_AUTH_TOKENS_JSON"):
        monkeypatch.delenv(variable, raising=False)

    state = readiness()
    codes = {finding["code"] for finding in state["blocking"]}

    assert state["ready_for_pilot"] is False
    assert {"TEACHING_APPROVAL_KEY", "TEACHING_EVIDENCE_TOKEN", "AUTHENTICATION"} <= codes


def test_a_configured_deployment_reports_ready(monkeypatch):
    monkeypatch.setenv("FSSAI_APPROVAL_SIGNING_KEY", "a-real-secret-from-a-vault")
    monkeypatch.setenv("FSSAI_EVIDENCE_TOKEN", "a-real-evidence-credential")
    monkeypatch.setenv("FSSAI_DATABASE_URL", "postgresql://user:pw@db:5432/fssaira")
    monkeypatch.setenv("FSSAI_KAFKA_BOOTSTRAP", "kafka:29092")
    monkeypatch.setenv(
        "FSSAI_AUTH_TOKENS_JSON",
        '{"a-real-token": {"subject": "officer.one", "roles": ["student_support_officer"]}}',
    )

    assert readiness()["ready_for_pilot"] is True


def test_a_non_local_model_endpoint_is_flagged(monkeypatch):
    monkeypatch.setenv("FSSAI_MODEL_BASE_URL", "https://api.some-vendor.com/v1")

    codes = {warning.code for warning in configuration_warnings()}

    assert "NON_LOCAL_MODEL" in codes


def test_an_adversarial_fixture_model_is_blocking(monkeypatch):
    monkeypatch.setenv("FSSAI_MODEL", "compromised")

    blocking = {finding["code"] for finding in readiness()["blocking"]}

    assert "ADVERSARIAL_MODEL" in blocking


def test_durability_is_graded_not_boolean(monkeypatch):
    monkeypatch.delenv("FSSAI_DATABASE_URL", raising=False)
    monkeypatch.delenv("FSSAI_REDIS_URL", raising=False)
    assert "VOLATILE_STATE" in {w.code for w in configuration_warnings()}

    monkeypatch.setenv("FSSAI_REDIS_URL", "redis://redis:6379/0")
    codes = {w.code for w in configuration_warnings()}
    assert "NO_TRANSACTIONAL_DURABILITY" in codes and "VOLATILE_STATE" not in codes

    monkeypatch.setenv("FSSAI_DATABASE_URL", "sqlite:///:memory:")
    codes = {w.code for w in configuration_warnings()}
    assert "NO_TRANSACTIONAL_DURABILITY" not in codes and "VOLATILE_STATE" not in codes


# ------------------------------------------------------------------ telemetry


def test_counters_render_as_prometheus_text():
    from fssaira.metrics import Metrics

    metrics = Metrics(tool_calls_denied=4, egress_blocked=2, class_downgrade_attempts=1)
    body = render_prometheus(samples_from(metrics), {"profile": "student-support"})

    assert "# TYPE fssaira_tool_calls_denied_total counter" in body
    assert 'fssaira_tool_calls_denied_total{profile="student-support"} 4' in body
    assert 'fssaira_class_downgrade_attempts_total{profile="student-support"} 1' in body


def test_a_broken_evidence_store_does_not_break_scraping():
    class Broken:
        def __len__(self):
            raise RuntimeError("store unavailable")

        def verify(self):
            raise RuntimeError("store unavailable")

    samples = samples_from(None, evidence=Broken())

    # Monitoring must survive the thing it monitors failing, and must report the
    # failure rather than omitting the metric.
    assert samples["fssaira_evidence_chain_valid"] == 0


def test_label_values_are_escaped():
    body = render_prometheus({"fssaira_build_info": 1}, {"profile": 'a"quoted\\value'})

    assert 'profile="a\\"quoted\\\\value"' in body


def test_telemetry_accumulates_and_renders():
    telemetry = Telemetry(labels={"service": "control-plane"})
    telemetry.increment("fssaira_mutations_total")
    telemetry.increment("fssaira_mutations_total", 2)
    telemetry.set("fssaira_evidence_records", 9)

    assert telemetry.snapshot()["fssaira_mutations_total"] == 3
    assert 'service="control-plane"' in telemetry.render()
