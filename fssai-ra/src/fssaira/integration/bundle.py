"""Model bundles: a model change is any change to eight components (paper Section 6.1).

A :class:`ModelBundle` pins, by content digest, the weights, adapter, tokenizer,
runtime, system template, decoding configuration, tool catalogue and retrieval
configuration. Its :attr:`~ModelBundle.digest` is canonical over those eight
digests and the bundle's identity. A :class:`BundleManifest` is signed with
Ed25519 by an accountable publisher.

:class:`BundleRegistry` admits a bundle for use only when:

* its manifest verifies under a trusted publisher key;
* an **independent measurement** of every component (a callable the host runs,
  such as hashing files it loads from protected storage) matches the manifest;
* no component has been observed to change since the last attestation. One
  mismatch **suspends** the endpoint until a new manifest is registered and a
  fresh measurement matches it (re-attestation), even if the component later
  reverts.

A digest the model or its runtime reports about itself is refused as evidence
outright, whether or not it matches (paper Section 6.3: a digest the model
reports about itself is not evidence of the weights actually loaded).

The bundle digest is deliberately usable as a :class:`fssaira.model_registry.ModelManifest`
``artifact_digest`` (see :func:`as_model_manifest`), so the existing endpoint
registry and the privacy router keep working over bundles.

Must NOT / residual risk
------------------------
* Must NOT accept the serving runtime's own report as a measurement.
* Must NOT treat an "empty" component as absent: an unused adapter is pinned as
  the digest of empty bytes, so adding one is a change.
* Residual: the measurement callable runs on the host. If the host, its storage,
  or the loader is compromised, the measurement can be wrong; hardware-rooted
  attestation (a TEE quote over loaded memory) is not implemented and runtime
  claims alone cannot qualify it. A valid signature says an accountable
  publisher approved these bytes, not that the model gives good advice.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..model_registry import ManifestPublisher, ModelManifest

#: The eight components whose change is a model change.
COMPONENTS: tuple[str, ...] = (
    "weights", "adapter", "tokenizer", "runtime", "system_template", "decoding_config",
    "tool_catalogue", "retrieval_config",
)

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")

#: Measurement sources that are, by construction, the thing being measured.
SELF_REPORTED_SOURCES: frozenset[str] = frozenset({
    "runtime", "runtime-self-report", "model", "model-self-report", "endpoint",
})


class BundleCode:
    """Stable refusal codes."""

    INCOMPLETE = "BUNDLE_INCOMPLETE"
    MALFORMED_DIGEST = "BUNDLE_MALFORMED_DIGEST"
    SIGNER_UNTRUSTED = "BUNDLE_SIGNER_UNTRUSTED"
    SIGNATURE_INVALID = "BUNDLE_SIGNATURE_INVALID"
    UNREGISTERED = "BUNDLE_UNREGISTERED"
    NOT_ATTESTED = "BUNDLE_NOT_ATTESTED"
    COMPONENT_CHANGED = "BUNDLE_COMPONENT_CHANGED"
    SUSPENDED = "BUNDLE_SUSPENDED_UNTIL_REATTESTED"
    SELF_REPORTED = "BUNDLE_SELF_REPORTED_DIGEST_NOT_EVIDENCE"
    MEASUREMENT_UNAVAILABLE = "BUNDLE_MEASUREMENT_UNAVAILABLE"
    ENDPOINT_MISMATCH = "BUNDLE_ENDPOINT_MISMATCH"


class BundleRefused(Exception):
    """A bundle could not be admitted for use."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def component_digest(content: bytes) -> str:
    """SHA-256 content digest in the registry's canonical form."""
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _crypto() -> tuple[Any, Any, Any, Any, Any]:
    # `cryptography` is an optional dependency (the `privacy`/`auth`/`platform`/`all`
    # extras); imported lazily so importing this module never requires it, and typed
    # as Any rather than pinned to its classes for the same reason.
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    return Ed25519PrivateKey, Ed25519PublicKey, InvalidSignature, Encoding, PublicFormat


@dataclass(frozen=True)
class ModelBundle:
    """Identity plus eight component digests."""

    bundle_id: str
    endpoint: str
    version: str
    components: Mapping[str, str]

    def __post_init__(self) -> None:
        missing = [name for name in COMPONENTS if name not in self.components]
        extra = sorted(set(self.components) - set(COMPONENTS))
        if missing or extra:
            raise BundleRefused(BundleCode.INCOMPLETE,
                                f"missing={missing} unexpected={extra}")
        for name in COMPONENTS:
            if not isinstance(self.components[name], str) or \
                    not _DIGEST.fullmatch(self.components[name]):
                raise BundleRefused(BundleCode.MALFORMED_DIGEST, name)
        object.__setattr__(self, "components",
                           MappingProxyType({n: self.components[n] for n in COMPONENTS}))

    def canonical(self) -> bytes:
        return json.dumps({"bundle_id": self.bundle_id, "endpoint": self.endpoint,
                           "version": self.version, "components": dict(self.components)},
                          sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

    @property
    def digest(self) -> str:
        return component_digest(self.canonical())

    def changed(self, measured: Mapping[str, str]) -> tuple[str, ...]:
        """Components whose measured digest differs (or is missing)."""
        return tuple(name for name in COMPONENTS
                     if not hmac.compare_digest(str(measured.get(name, "")),
                                                self.components[name]))


@dataclass(frozen=True)
class BundleManifest:
    bundle: ModelBundle
    signer: str
    key_id: str
    signature: str = ""
    attestation_method: str = "publisher-signed-bundle+independent-host-measurement"

    def signing_payload(self) -> bytes:
        return json.dumps({"bundle": json.loads(self.bundle.canonical()),
                           "bundle_digest": self.bundle.digest, "signer": self.signer,
                           "key_id": self.key_id,
                           "attestation_method": self.attestation_method},
                          sort_keys=True, separators=(",", ":")).encode()


class BundlePublisher:
    """Signs bundle manifests with Ed25519. ``seed`` makes fixtures reproducible."""

    def __init__(self, *, key_id: str = "bundle-publisher-1", signer: str = "model-risk-office",
                 seed: bytes | None = None) -> None:
        private_cls, *_ = _crypto()
        material = seed if seed is not None else secrets.token_bytes(32)
        if len(material) != 32:
            raise ValueError("an Ed25519 seed is exactly 32 bytes")
        self._key = private_cls.from_private_bytes(material)
        self.key_id, self.signer = key_id, signer

    @property
    def trusted_keys(self) -> dict[str, bytes]:
        *_, encoding, public_format = _crypto()
        return {self.key_id: self._key.public_key().public_bytes(encoding.Raw, public_format.Raw)}

    def sign(self, bundle: ModelBundle) -> BundleManifest:
        unsigned = BundleManifest(bundle, self.signer, self.key_id)
        return replace(unsigned, signature=self._key.sign(unsigned.signing_payload()).hex())


@dataclass(frozen=True)
class Measurement:
    """An independent measurement source: ``measure(endpoint) -> {component: digest}``."""

    source: str
    measure: Callable[[str], Mapping[str, str]]


def file_measurement(source: str, paths: Mapping[str, Mapping[str, Path]]) -> Measurement:
    """Measure by hashing the files the host loads, per endpoint and component."""
    def measure(endpoint: str) -> Mapping[str, str]:
        return {name: component_digest(Path(path).read_bytes())
                for name, path in paths[endpoint].items()}
    return Measurement(source, measure)


@dataclass(frozen=True)
class BundleAttestation:
    endpoint: str
    bundle_digest: str
    measured_by: str
    components: Mapping[str, str] = field(default_factory=dict)


class BundleRegistry:
    """Admits a bundle for use only under an independent, current measurement."""

    def __init__(self, trusted_keys: Mapping[str, bytes], measurement: Measurement) -> None:
        if measurement.source.strip().lower() in SELF_REPORTED_SOURCES:
            raise BundleRefused(BundleCode.SELF_REPORTED,
                                "the measurement source is the component being measured")
        self._trusted = dict(trusted_keys)
        self._measurement = measurement
        self._manifests: dict[str, BundleManifest] = {}
        self._attested: dict[str, str] = {}
        self._suspended: dict[str, tuple[str, ...]] = {}
        self._lock = threading.RLock()

    def verify(self, manifest: BundleManifest) -> None:
        _private, public_cls, invalid, *_ = _crypto()
        key = self._trusted.get(manifest.key_id)
        if key is None:
            raise BundleRefused(BundleCode.SIGNER_UNTRUSTED, manifest.key_id)
        try:
            public_cls.from_public_bytes(key).verify(bytes.fromhex(manifest.signature),
                                                     manifest.signing_payload())
        except (invalid, ValueError) as exc:
            raise BundleRefused(BundleCode.SIGNATURE_INVALID) from exc

    def register(self, manifest: BundleManifest) -> None:
        """Register (or replace) the manifest for its endpoint. Use still needs attestation."""
        self.verify(manifest)
        with self._lock:
            self._manifests[manifest.bundle.endpoint] = manifest
            self._attested.pop(manifest.bundle.endpoint, None)

    def _measure(self, endpoint: str) -> Mapping[str, str]:
        try:
            return dict(self._measurement.measure(endpoint))
        except Exception as exc:  # any failure to measure is a refusal, never a pass
            raise BundleRefused(BundleCode.MEASUREMENT_UNAVAILABLE, type(exc).__name__) from exc

    def attest(self, endpoint: str, *, runtime_report: Mapping[str, str] | None = None
               ) -> BundleAttestation:
        """(Re-)attest ``endpoint``. ``runtime_report`` is refused as evidence if supplied."""
        if runtime_report is not None:
            raise BundleRefused(BundleCode.SELF_REPORTED,
                                "a runtime's report about itself is not a measurement")
        with self._lock:
            manifest = self._manifests.get(endpoint)
            if manifest is None:
                raise BundleRefused(BundleCode.UNREGISTERED, endpoint)
            self.verify(manifest)
            suspended_for = self._suspended.get(endpoint)
            if suspended_for is not None and manifest.bundle.digest == suspended_for[0]:
                raise BundleRefused(BundleCode.SUSPENDED,
                                    "register a new manifest for the changed bundle")
            measured = self._measure(endpoint)
            changed = manifest.bundle.changed(measured)
            if changed:
                self._suspend(endpoint, manifest, changed)
                raise BundleRefused(BundleCode.COMPONENT_CHANGED, ", ".join(changed))
            self._suspended.pop(endpoint, None)
            self._attested[endpoint] = manifest.bundle.digest
            return BundleAttestation(endpoint, manifest.bundle.digest, self._measurement.source,
                                     MappingProxyType(dict(measured)))

    def _suspend(self, endpoint: str, manifest: BundleManifest, changed: tuple[str, ...]) -> None:
        self._attested.pop(endpoint, None)
        self._suspended[endpoint] = (manifest.bundle.digest, *changed)

    def require_current(self, endpoint: str) -> BundleAttestation:
        """Gate every use: attested, not suspended, and re-measured now."""
        with self._lock:
            manifest = self._manifests.get(endpoint)
            if manifest is None:
                raise BundleRefused(BundleCode.UNREGISTERED, endpoint)
            if endpoint in self._suspended:
                raise BundleRefused(BundleCode.SUSPENDED, ", ".join(self._suspended[endpoint][1:]))
            if self._attested.get(endpoint) != manifest.bundle.digest:
                raise BundleRefused(BundleCode.NOT_ATTESTED, endpoint)
            self.verify(manifest)
            measured = self._measure(endpoint)
            changed = manifest.bundle.changed(measured)
            if changed:
                self._suspend(endpoint, manifest, changed)
                raise BundleRefused(BundleCode.COMPONENT_CHANGED, ", ".join(changed))
            return BundleAttestation(endpoint, manifest.bundle.digest, self._measurement.source,
                                     MappingProxyType(dict(measured)))

    def status(self, endpoint: str) -> dict:
        with self._lock:
            return {"registered": endpoint in self._manifests,
                    "attested": endpoint in self._attested,
                    "suspended_components": list(self._suspended.get(endpoint, ())[1:])}


def as_model_manifest(bundle: ModelBundle, publisher: ManifestPublisher, *, zone: str, provider: str,
                      model_id: str, **fields: Any) -> ModelManifest:
    """A :class:`fssaira.model_registry.ModelManifest` whose artifact digest is the bundle digest."""
    from ..model_registry import ModelManifest

    return publisher.sign(ModelManifest(
        endpoint=bundle.endpoint, zone=zone, provider=provider, model_id=model_id,
        artifact_digest=bundle.digest, version=bundle.version,
        evaluation_card=fields.pop("evaluation_card", f"evaluation-cards/{bundle.bundle_id}.md"),
        signer=publisher.signer,
        attestation_method="publisher-signed-bundle+independent-host-measurement", **fields,
    ))


__all__ = [
    "COMPONENTS", "SELF_REPORTED_SOURCES", "BundleAttestation", "BundleCode", "BundleManifest",
    "BundlePublisher", "BundleRefused", "BundleRegistry", "Measurement", "ModelBundle",
    "as_model_manifest", "component_digest", "file_measurement",
]
