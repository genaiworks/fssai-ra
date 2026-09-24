"""Model bundles: any component change blocks use until re-attested; self-reports are not evidence."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from fssaira.integration.bundle import (
    COMPONENTS,
    BundleCode,
    BundlePublisher,
    BundleRefused,
    BundleRegistry,
    Measurement,
    ModelBundle,
    as_model_manifest,
    component_digest,
    file_measurement,
)
from fssaira.model_registry import ManifestPublisher, ModelRegistry

ENDPOINT = "on_premises_model"


def materialise(tmp_path: Path) -> dict[str, Path]:
    paths = {}
    for name in COMPONENTS:
        path = tmp_path / f"{name}.bin"
        path.write_bytes(b"" if name == "adapter" else f"synthetic {name} v1".encode())
        paths[name] = path
    return paths


def setup(tmp_path: Path):
    paths = materialise(tmp_path)
    bundle = ModelBundle("tutor-bundle", ENDPOINT, "1",
                         {n: component_digest(p.read_bytes()) for n, p in paths.items()})
    publisher = BundlePublisher(seed=b"\x01" * 32)
    registry = BundleRegistry(publisher.trusted_keys,
                              file_measurement("host-loader-hash", {ENDPOINT: paths}))
    manifest = publisher.sign(bundle)
    registry.register(manifest)
    return paths, bundle, publisher, registry, manifest


def test_bundle_requires_all_eight_components_with_canonical_digests():
    good = {n: component_digest(n.encode()) for n in COMPONENTS}
    with pytest.raises(BundleRefused) as refused:
        ModelBundle("b", ENDPOINT, "1", {k: v for k, v in good.items() if k != "tokenizer"})
    assert refused.value.code == BundleCode.INCOMPLETE
    with pytest.raises(BundleRefused) as refused:
        ModelBundle("b", ENDPOINT, "1", {**good, "weights": "sha256:ABC"})
    assert refused.value.code == BundleCode.MALFORMED_DIGEST
    reordered = ModelBundle("b", ENDPOINT, "1", dict(reversed(list(good.items()))))
    assert reordered.digest == ModelBundle("b", ENDPOINT, "1", good).digest


@pytest.mark.parametrize("component", COMPONENTS)
def test_any_single_component_change_blocks_use_until_reattested(tmp_path, component):
    paths, bundle, publisher, registry, _manifest = setup(tmp_path)
    registry.attest(ENDPOINT)
    assert registry.require_current(ENDPOINT).bundle_digest == bundle.digest

    original = paths[component].read_bytes()
    paths[component].write_bytes(original + b" changed")
    with pytest.raises(BundleRefused) as refused:
        registry.require_current(ENDPOINT)
    assert refused.value.code == BundleCode.COMPONENT_CHANGED and component in refused.value.detail

    # Reverting the bytes does not silently restore trust.
    paths[component].write_bytes(original)
    with pytest.raises(BundleRefused) as refused:
        registry.require_current(ENDPOINT)
    assert refused.value.code == BundleCode.SUSPENDED
    with pytest.raises(BundleRefused) as refused:
        registry.attest(ENDPOINT)
    assert refused.value.code == BundleCode.SUSPENDED

    # Re-attestation: a new signed manifest for the changed bundle, then a fresh measurement.
    paths[component].write_bytes(original + b" changed")
    changed = ModelBundle(bundle.bundle_id, ENDPOINT, "2",
                          {**bundle.components,
                           component: component_digest(paths[component].read_bytes())})
    registry.register(publisher.sign(changed))
    with pytest.raises(BundleRefused) as refused:
        registry.require_current(ENDPOINT)
    assert refused.value.code in (BundleCode.SUSPENDED, BundleCode.NOT_ATTESTED)
    registry.attest(ENDPOINT)
    assert registry.require_current(ENDPOINT).bundle_digest == changed.digest


def test_runtime_self_reported_digest_is_rejected_even_when_it_matches(tmp_path):
    _paths, bundle, _publisher, registry, _manifest = setup(tmp_path)
    with pytest.raises(BundleRefused) as refused:
        registry.attest(ENDPOINT, runtime_report=dict(bundle.components))
    assert refused.value.code == BundleCode.SELF_REPORTED
    with pytest.raises(BundleRefused) as refused:
        registry.require_current(ENDPOINT)
    assert refused.value.code == BundleCode.NOT_ATTESTED
    with pytest.raises(BundleRefused) as refused:
        BundleRegistry({}, Measurement("runtime-self-report", lambda _e: bundle.components))
    assert refused.value.code == BundleCode.SELF_REPORTED


def test_lying_runtime_is_caught_by_independent_measurement(tmp_path):
    paths, bundle, _publisher, registry, _manifest = setup(tmp_path)
    paths["weights"].write_bytes(b"substituted fine-tune")
    lying_report = dict(bundle.components)  # the runtime claims the approved weights
    assert lying_report["weights"] == bundle.components["weights"]
    with pytest.raises(BundleRefused) as refused:
        registry.attest(ENDPOINT)
    assert refused.value.code == BundleCode.COMPONENT_CHANGED


def test_signature_and_measurement_failures_refuse(tmp_path):
    paths, bundle, publisher, registry, manifest = setup(tmp_path)
    forged = replace(manifest, bundle=ModelBundle(bundle.bundle_id, ENDPOINT, "1",
                                                  {**bundle.components,
                                                   "system_template": component_digest(b"x")}))
    with pytest.raises(BundleRefused) as refused:
        registry.register(forged)
    assert refused.value.code == BundleCode.SIGNATURE_INVALID
    rogue = BundlePublisher(key_id="rogue", seed=b"\x02" * 32)
    with pytest.raises(BundleRefused) as refused:
        registry.register(rogue.sign(bundle))
    assert refused.value.code == BundleCode.SIGNER_UNTRUSTED
    paths["tokenizer"].unlink()
    with pytest.raises(BundleRefused) as refused:
        registry.attest(ENDPOINT)
    assert refused.value.code == BundleCode.MEASUREMENT_UNAVAILABLE


def test_bundle_digest_interoperates_with_model_registry(tmp_path):
    _paths, bundle, _publisher, registry, _manifest = setup(tmp_path)
    attestation = registry.attest(ENDPOINT)
    publisher = ManifestPublisher(seed=b"\x03" * 32)
    models = ModelRegistry({ENDPOINT: "on-premises"}, publisher.trusted_keys)
    models.register(as_model_manifest(bundle, publisher, zone="on-premises", provider="local",
                                      model_id="tutor"))
    attested = models.attest(ENDPOINT, attestation.bundle_digest)
    assert attested.artifact_digest == bundle.digest
