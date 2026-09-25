"""Declaring 'production' requires the protections the docs say production needs."""
import os

import pytest

from fssaira.runtime_factory import configuration_warnings, transport_findings


@pytest.fixture
def env(monkeypatch):
    for name in list(os.environ):
        if name.startswith("FSSAI_"):
            monkeypatch.delenv(name, raising=False)
    return monkeypatch


def codes(findings):
    return {f.code for f in findings}


def test_plaintext_services_and_unauthenticated_events_are_reported(env):
    env.setenv("FSSAI_DATABASE_URL", "postgresql://u:p@postgres:5432/db")
    env.setenv("FSSAI_KAFKA_BOOTSTRAP", "kafka:29092")
    found = codes(transport_findings())
    assert {"PLAINTEXT_DATABASE_TRANSPORT", "PLAINTEXT_EVENT_TRANSPORT",
            "UNAUTHENTICATED_EVENTS", "NO_EVIDENCE_NOTARY"} <= found


def test_a_verified_tls_deployment_reports_none_of_them(env):
    env.setenv("FSSAI_DATABASE_URL",
               "postgresql://u:p@postgres:5432/db?sslmode=verify-full&sslrootcert=/tls/ca.crt")
    env.setenv("FSSAI_KAFKA_BOOTSTRAP", "kafka:29092")
    env.setenv("FSSAI_KAFKA_SECURITY_PROTOCOL", "SSL")
    env.setenv("FSSAI_EVENT_ENVELOPE_KEY", "e" * 48)
    env.setenv("FSSAI_NOTARY_KEY_FILE", "/run/secrets/notary.key")
    assert codes(transport_findings()) == set()


def test_sslmode_require_is_not_verification(env):
    env.setenv("FSSAI_DATABASE_URL", "postgresql://u:p@postgres:5432/db?sslmode=require")
    assert "UNVERIFIED_DATABASE_TLS" in codes(transport_findings())


def test_these_block_a_production_deployment_but_only_warn_elsewhere(env):
    env.setenv("FSSAI_DATABASE_URL", "postgresql://u:p@postgres:5432/db")
    severities = {f.code: f.severity for f in configuration_warnings()}
    assert severities["PLAINTEXT_DATABASE_TRANSPORT"] == "high"
    env.setenv("FSSAI_DEPLOYMENT_PROFILE", "production")
    severities = {f.code: f.severity for f in configuration_warnings()}
    assert severities["PLAINTEXT_DATABASE_TRANSPORT"] == "blocking"


def test_sqlite_is_local_and_not_a_transport_finding(env):
    env.setenv("FSSAI_DATABASE_URL", "sqlite:///var/lib/fssaira/state.sqlite")
    assert "PLAINTEXT_DATABASE_TRANSPORT" not in codes(transport_findings())


def test_a_pilot_with_teaching_defaults_refuses_to_start(env):
    """Fail secure: the refusal happens at start-up, not as a warning read afterwards."""
    from fssaira.runtime_factory import build_control_plane

    env.setenv("FSSAI_MODEL", "deterministic")
    env.setenv("FSSAI_DEPLOYMENT_PROFILE", "pilot")
    with pytest.raises(RuntimeError, match="refusing to start a pilot deployment.*"
                                           "TEACHING_APPROVAL_KEY"):
        build_control_plane(profile_path="profiles/student_support.yaml")


def test_a_mistyped_deployment_profile_refuses_instead_of_falling_back_to_teaching(env):
    from fssaira.runtime_factory import build_control_plane

    env.setenv("FSSAI_MODEL", "deterministic")
    env.setenv("FSSAI_DEPLOYMENT_PROFILE", "prod")
    with pytest.raises(RuntimeError, match="'prod' is not one of"):
        build_control_plane(profile_path="profiles/student_support.yaml")


def test_an_unknown_scale_tier_blocks_a_pilot(env):
    from fssaira.runtime_factory import build_control_plane

    env.setenv("FSSAI_MODEL", "deterministic")
    env.setenv("FSSAI_DEPLOYMENT_PROFILE", "pilot")
    env.setenv("FSSAI_SCALE", "medium")
    with pytest.raises(RuntimeError, match="UNKNOWN_SCALE_TIER"):
        build_control_plane(profile_path="profiles/student_support.yaml")
