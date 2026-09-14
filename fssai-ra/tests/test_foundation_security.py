"""Security regressions found while auditing the full-paper claims."""
import hashlib

import pytest

from fssaira.evidence_notary import EvidenceNotary
from fssaira.model_registry import (
    ManifestPublisher,
    ModelAttestationDenied,
    ModelRegistry,
)


@pytest.mark.parametrize("factory", [ManifestPublisher, EvidenceNotary])
def test_default_signing_key_cannot_be_recreated_from_public_key_id(factory):
    first, second = factory(key_id="public-id"), factory(key_id="public-id")
    forged = factory(key_id="public-id", seed=hashlib.sha256(b"public-id").digest())
    def public(obj):
        return obj.public_key if isinstance(obj, ManifestPublisher) else obj.public_keys
    assert public(first) != public(second)
    assert public(first) != public(forged)


@pytest.mark.parametrize("factory", [ManifestPublisher, EvidenceNotary])
def test_explicit_fixture_seeds_remain_reproducible(factory):
    first, second = factory(seed=b"x" * 32), factory(seed=b"x" * 32)
    if isinstance(first, ManifestPublisher):
        assert first.public_key == second.public_key
    else:
        assert first.public_keys == second.public_keys


def registry(expires=100.0):
    publisher = ManifestPublisher(seed=b"x" * 32)
    manifest = publisher.issue(endpoint="local", zone="private", provider="fixture",
        model_id="model", artifact=b"weights", expires_at=expires,
        allowed_classes=("restricted",), allowed_purposes=("support",))
    gate = ModelRegistry({"local": "private"}, publisher.trusted_keys, strict=True)
    gate.register(manifest)
    return gate, manifest


def test_expiry_is_enforced_when_caller_omits_time(monkeypatch):
    gate, manifest = registry()
    monkeypatch.setattr("fssaira.model_registry.time.time", lambda: 101.0)
    with pytest.raises(ModelAttestationDenied, match="MODEL_MANIFEST_EXPIRED"):
        gate.attest("local", manifest.artifact_digest)


@pytest.mark.parametrize("now", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_authorization_clock_fails_closed(now):
    gate, manifest = registry()
    with pytest.raises(ModelAttestationDenied, match="MODEL_MANIFEST_INCOMPLETE"):
        gate.attest("local", manifest.artifact_digest, now=now)


def test_current_manifest_allows_legitimate_use_and_expiry_boundary_denies():
    gate, manifest = registry()
    assert gate.attest("local", manifest.artifact_digest, now=99.0,
        purpose="support", classes=("restricted",)).model_id == "model"
    with pytest.raises(ModelAttestationDenied, match="MODEL_MANIFEST_EXPIRED"):
        gate.attest("local", manifest.artifact_digest, now=100.0)


@pytest.mark.parametrize("statuses", [(), ("declared-residual",), ("unreadable", "declared-residual"), ("unknown",), ("READABLE",)])
def test_erasure_does_not_claim_complete_when_evidence_is_missing(statuses):
    from fssaira.privacy_pipeline import ErasureVerification, LocationCheck
    report = ErasureVerification("subject", tuple(
        LocationCheck(str(i), status, "fixture") for i, status in enumerate(statuses)))
    assert not report.complete


def test_erasure_success_is_explicitly_scoped_to_supplied_locations():
    from fssaira.privacy_pipeline import ErasureVerification, LocationCheck
    report = ErasureVerification("subject", (LocationCheck("primary", "unreadable", "fixture"),))
    assert report.complete
    assert "supplied locations" in report.to_dict()["scope"]
