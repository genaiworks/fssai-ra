"""An unrecognised deployment profile fails closed instead of starting as teaching.

Before this check, any value other than "pilot" or "production" (for example
"prod" or "staging") silently skipped the teaching-defaults refusal and the
backend-assurance refusal.
"""
from __future__ import annotations

import pytest

from fssaira.runtime_factory import DEPLOYMENT_PROFILES, build_control_plane


@pytest.mark.parametrize("value", ["prod", "staging", "Production-1", "pilot ", "  ", "teach"])
def test_an_unrecognised_profile_refuses_to_start(monkeypatch, value):
    monkeypatch.setenv("FSSAI_DEPLOYMENT_PROFILE", value)
    if value.strip().lower() in DEPLOYMENT_PROFILES:
        pytest.skip("normalises to a recognised profile")
    with pytest.raises(RuntimeError, match="FSSAI_DEPLOYMENT_PROFILE"):
        build_control_plane()


def test_the_recognised_profiles_are_exactly_three():
    assert frozenset({"teaching", "pilot", "production"}) == DEPLOYMENT_PROFILES


def test_teaching_is_still_the_default(monkeypatch):
    monkeypatch.delenv("FSSAI_DEPLOYMENT_PROFILE", raising=False)
    for name in ("FSSAI_DATABASE_URL", "FSSAI_REDIS_URL", "FSSAI_KAFKA_BOOTSTRAP", "FSSAI_CONFORMANCE_RECORDS"):
        monkeypatch.delenv(name, raising=False)
    plane = build_control_plane()
    assert plane.backend_assurance["memory"]["code"] == "NOT_REQUIRED_TEACHING"
