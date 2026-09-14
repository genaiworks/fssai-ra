"""Model attestation: a model endpoint is trusted for nothing until it is registered.

Governed disclosure decides *where* a data class may be processed by looking up
the zone a domain pack declares for a model endpoint. That lookup trusts a name.
A name is not a model. The endpoint called ``on_premises_model`` may be serving
the weights the institution evaluated, or a fine-tune someone swapped in last
night, or a proxy to a public API that happens to answer on the same port. None
of those is a residency violation by the gate's arithmetic, and every one of them
defeats the reason the zone was declared.

So an endpoint must present evidence that it is what the pack says it is:

* a **manifest** naming the endpoint, its zone, provider, model id, version, the
  digest of the weights or serving artifact, and the evaluation card that
  justified approving it;
* **signed** by a publisher key the institution trusts (Ed25519, so the registry
  holds only public keys and cannot mint a manifest itself);
* whose **zone agrees with the pack**, so a manifest cannot move an endpoint into
  a more permissive zone than the governance record declares;
* and, at the moment of use, a **presented digest** from the serving runtime that
  equals the manifest's. Swapped weights change the digest.

The registry is consulted before the gate releases anything into a context and
by the router before it considers an endpoint at all. Its checks are one
ablatable control, ``model_attestation``, in :data:`fssaira.privacy.PRIVACY_CHECKS`,
deliberately *not* in :data:`fssaira.disclosure.ALL_CHECKS`: the disclosure
figures measure the fourteen disclosure checks and must not move when a new
layer is added beside them.

What this does not establish
----------------------------
The presented digest is reported by the serving runtime. A runtime that lies
about what it loaded defeats this check; closing that needs hardware-rooted
remote attestation (a TEE quote over the loaded weights), which is not
implemented here. A signed manifest says an accountable publisher approved an
artifact; it says nothing about whether the evaluation card was adequate.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Iterable
from dataclasses import dataclass, replace

from .disclosure import DisclosureDenied

#: The check name this module contributes to the privacy suite.
CHECK = "model_attestation"


class ModelAttestationCode:
    """Stable denial codes for the attestation family."""

    ENDPOINT_UNREGISTERED = "MODEL_ENDPOINT_UNREGISTERED"
    MANIFEST_SIGNATURE_INVALID = "MODEL_MANIFEST_SIGNATURE_INVALID"
    MANIFEST_SIGNER_UNTRUSTED = "MODEL_MANIFEST_SIGNER_UNTRUSTED"
    MANIFEST_ZONE_MISMATCH = "MODEL_MANIFEST_ZONE_MISMATCH"
    MANIFEST_ENDPOINT_UNDECLARED = "MODEL_MANIFEST_ENDPOINT_UNDECLARED"
    ARTIFACT_DIGEST_MISMATCH = "MODEL_ARTIFACT_DIGEST_MISMATCH"
    MANIFEST_REVOKED = "MODEL_MANIFEST_REVOKED"
    MANIFEST_EXPIRED = "MODEL_MANIFEST_EXPIRED"
    MANIFEST_INCOMPLETE = "MODEL_MANIFEST_INCOMPLETE"
    IDENTITY_MISMATCH = "MODEL_IDENTITY_MISMATCH"
    PURPOSE_NOT_APPROVED = "MODEL_PURPOSE_NOT_APPROVED"
    CLASS_NOT_APPROVED = "MODEL_CLASS_NOT_APPROVED"


class ModelAttestationDenied(DisclosureDenied):
    """An endpoint could not show it is the model the institution approved.

    A subclass of :class:`DisclosureDenied` so that a refusal raised inside a gate
    decision is recorded as that decision's outcome, like every other refusal.
    """


def artifact_digest(content: bytes) -> str:
    """The digest a manifest pins: SHA-256 over the serving artifact's bytes."""
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _ed25519():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "model attestation needs the 'cryptography' package: pip install 'fssaira[privacy]'"
        ) from exc
    return Ed25519PrivateKey, Ed25519PublicKey, InvalidSignature, Encoding, PublicFormat


@dataclass(frozen=True)
class ModelManifest:
    """What an approved model endpoint is, signed by its publisher."""

    endpoint: str
    zone: str
    provider: str
    model_id: str
    artifact_digest: str
    version: str
    evaluation_card: str
    signer: str
    key_id: str = ""
    signature: str = ""
    #: What the model is approved *for*, not only what it is. Empty tuples mean
    #: "not declared"; a strict registry refuses an undeclared manifest outright.
    capabilities: tuple[str, ...] = ()
    allowed_classes: tuple[str, ...] = ()
    allowed_purposes: tuple[str, ...] = ()
    #: Approval is time-bound: an evaluation card goes stale as the model, the
    #: data, and the threats change. ``0.0`` means no expiry was declared.
    expires_at: float = 0.0
    #: Honest name for the evidence behind the approval. A runtime-reported digest
    #: is not a hardware quote, and the manifest says which one it is.
    attestation_method: str = "publisher-signed-manifest+runtime-reported-digest"

    def signing_payload(self) -> bytes:
        return json.dumps({
            "endpoint": self.endpoint, "zone": self.zone, "provider": self.provider,
            "model_id": self.model_id, "artifact_digest": self.artifact_digest,
            "version": self.version, "evaluation_card": self.evaluation_card,
            "signer": self.signer, "key_id": self.key_id,
            "capabilities": sorted(self.capabilities),
            "allowed_classes": sorted(self.allowed_classes),
            "allowed_purposes": sorted(self.allowed_purposes),
            "expires_at": self.expires_at, "attestation_method": self.attestation_method,
        }, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict:
        return {**json.loads(self.signing_payload()), "signature": self.signature}


class ManifestPublisher:
    """Signs manifests under an Ed25519 key.

    ``seed`` makes the key reproducible for fixtures. A deployment generates the
    key inside its signing service and publishes only :attr:`public_key`.
    """

    def __init__(self, *, key_id: str = "model-publisher-1", signer: str = "model-risk-office",
                 seed: bytes | None = None) -> None:
        private_cls, *_ = _ed25519()
        material = seed if seed is not None else hashlib.sha256(key_id.encode()).digest()
        if len(material) != 32:
            raise ValueError("an Ed25519 seed is exactly 32 bytes")
        self._key = private_cls.from_private_bytes(material)
        self.key_id = key_id
        self.signer = signer

    @property
    def public_key(self) -> bytes:
        *_, encoding, public_format = _ed25519()
        return self._key.public_key().public_bytes(encoding.Raw, public_format.Raw)

    @property
    def trusted_keys(self) -> dict[str, bytes]:
        return {self.key_id: self.public_key}

    def sign(self, manifest: ModelManifest) -> ModelManifest:
        unsigned = replace(manifest, signer=self.signer, key_id=self.key_id, signature="")
        return replace(unsigned, signature=self._key.sign(unsigned.signing_payload()).hex())

    def issue(self, *, endpoint: str, zone: str, provider: str, model_id: str,
              artifact: bytes, version: str = "1", evaluation_card: str = "",
              capabilities: Iterable[str] = (), allowed_classes: Iterable[str] = (),
              allowed_purposes: Iterable[str] = (), expires_at: float = 0.0) -> ModelManifest:
        return self.sign(ModelManifest(
            endpoint=endpoint, zone=zone, provider=provider, model_id=model_id,
            artifact_digest=artifact_digest(artifact), version=version,
            evaluation_card=evaluation_card or f"evaluation-cards/{endpoint}-{version}.md",
            signer=self.signer, capabilities=tuple(sorted(capabilities)),
            allowed_classes=tuple(sorted(allowed_classes)),
            allowed_purposes=tuple(sorted(allowed_purposes)), expires_at=float(expires_at),
        ))


@dataclass(frozen=True)
class AttestedEndpoint:
    """The result of a successful attestation, safe to record as evidence."""

    endpoint: str
    zone: str
    model_id: str
    artifact_digest: str
    manifest_digest: str

    def to_dict(self) -> dict:
        return {"endpoint": self.endpoint, "zone": self.zone, "model_id": self.model_id,
                "artifact_digest": self.artifact_digest, "manifest_digest": self.manifest_digest}


class ModelRegistry:
    """Registered, signed manifests for the endpoints a domain pack declares.

    ``declared_endpoints`` is the pack's ``model_endpoints`` mapping. A manifest
    for an endpoint the pack does not declare, or that claims a different zone,
    is refused at registration: the governance record, not the publisher, decides
    where an endpoint sits.
    """

    def __init__(self, declared_endpoints: dict[str, str], trusted_keys: dict[str, bytes],
                 *, strict: bool = False) -> None:
        self._declared = dict(declared_endpoints)
        self._trusted = dict(trusted_keys)
        #: A strict registry refuses manifests that do not declare expiry, classes,
        #: and purposes. Governed deployments run strict; the legacy router
        #: fixtures predate those fields.
        self.strict = strict
        self._manifests: dict[str, ModelManifest] = {}
        self._revoked: set[str] = set()

    # -- verification ---------------------------------------------------------
    def verify(self, manifest: ModelManifest) -> None:
        _private, public_cls, invalid_signature, *_ = _ed25519()
        key = self._trusted.get(manifest.key_id)
        if key is None:
            raise ModelAttestationDenied(ModelAttestationCode.MANIFEST_SIGNER_UNTRUSTED,
                                         f"manifest key {manifest.key_id!r} is not trusted")
        try:
            public_cls.from_public_bytes(key).verify(bytes.fromhex(manifest.signature),
                                                     manifest.signing_payload())
        except (invalid_signature, ValueError) as exc:
            raise ModelAttestationDenied(ModelAttestationCode.MANIFEST_SIGNATURE_INVALID,
                                         "manifest fields do not match their signature") from exc
        declared = self._declared.get(manifest.endpoint)
        if declared is None:
            raise ModelAttestationDenied(ModelAttestationCode.MANIFEST_ENDPOINT_UNDECLARED,
                                         f"{manifest.endpoint!r} is not declared by the pack")
        if declared != manifest.zone:
            raise ModelAttestationDenied(
                ModelAttestationCode.MANIFEST_ZONE_MISMATCH,
                f"manifest places {manifest.endpoint} in {manifest.zone!r}; the pack declares "
                f"{declared!r}",
            )

    def register(self, manifest: ModelManifest) -> None:
        self.verify(manifest)
        self._manifests[manifest.endpoint] = manifest
        self._revoked.discard(manifest.endpoint)

    def revoke(self, endpoint: str) -> None:
        self._revoked.add(endpoint)

    def is_registered(self, endpoint: str) -> bool:
        return endpoint in self._manifests and endpoint not in self._revoked

    def manifest(self, endpoint: str) -> ModelManifest | None:
        return self._manifests.get(endpoint)

    def registered(self) -> tuple[str, ...]:
        return tuple(sorted(e for e in self._manifests if e not in self._revoked))

    def _store_unverified(self, manifest: ModelManifest) -> None:
        """Write a manifest without verification: models tampering with registry storage."""
        self._manifests[manifest.endpoint] = manifest

    def attest(self, endpoint: str, presented_digest: str, *, now: float | None = None,
               purpose: str | None = None, classes: Iterable[str] = (),
               presented_model_id: str | None = None) -> AttestedEndpoint:
        """Refuse unless ``endpoint`` has a valid, current manifest approving this use.

        The stored manifest is verified again here rather than trusted from
        registration, so a manifest altered in storage is caught at use. Beyond
        identity (signature, zone, digest), the manifest must still be in date and
        must approve the purpose and every data class of the context about to be
        sent: a model approved for coursework feedback is not thereby approved for
        counselling notes.
        """
        manifest = self._manifests.get(endpoint)
        if manifest is None:
            raise ModelAttestationDenied(ModelAttestationCode.ENDPOINT_UNREGISTERED,
                                         f"model endpoint {endpoint!r} has no registered manifest")
        if endpoint in self._revoked:
            raise ModelAttestationDenied(ModelAttestationCode.MANIFEST_REVOKED,
                                         f"the manifest for {endpoint!r} has been revoked")
        self.verify(manifest)
        if not hmac.compare_digest(str(presented_digest), manifest.artifact_digest):
            raise ModelAttestationDenied(
                ModelAttestationCode.ARTIFACT_DIGEST_MISMATCH,
                f"{endpoint} presented an artifact that is not the one its manifest approves",
            )
        if presented_model_id is not None and presented_model_id != manifest.model_id:
            raise ModelAttestationDenied(
                ModelAttestationCode.IDENTITY_MISMATCH,
                f"{endpoint} is serving {presented_model_id!r}; its manifest approves "
                f"{manifest.model_id!r}",
            )
        if self.strict and (not manifest.expires_at or not manifest.allowed_classes
                            or not manifest.allowed_purposes):
            raise ModelAttestationDenied(
                ModelAttestationCode.MANIFEST_INCOMPLETE,
                f"the manifest for {endpoint} does not declare expiry, classes, and purposes",
            )
        if manifest.expires_at and now is not None and now >= manifest.expires_at:
            raise ModelAttestationDenied(ModelAttestationCode.MANIFEST_EXPIRED,
                                         f"the approval of {endpoint} expired")
        if purpose is not None and manifest.allowed_purposes and \
                purpose not in manifest.allowed_purposes:
            raise ModelAttestationDenied(ModelAttestationCode.PURPOSE_NOT_APPROVED,
                                         f"{endpoint} is not approved for {purpose!r}")
        outside = sorted(set(classes) - set(manifest.allowed_classes)) \
            if manifest.allowed_classes or self.strict else []
        if outside:
            raise ModelAttestationDenied(ModelAttestationCode.CLASS_NOT_APPROVED,
                                         f"{endpoint} is not approved for: {', '.join(outside)}")
        return AttestedEndpoint(endpoint, manifest.zone, manifest.model_id,
                                manifest.artifact_digest,
                                hashlib.sha256(manifest.signing_payload()).hexdigest())


def registry_for(declared_endpoints: dict[str, str], publisher: ManifestPublisher,
                 artifacts: dict[str, bytes], *, providers: dict[str, tuple[str, str]] | None = None,
                 skip: Iterable[str] = ()) -> ModelRegistry:
    """A registry with one signed manifest per declared endpoint, for fixtures and demos."""
    registry = ModelRegistry(declared_endpoints, publisher.trusted_keys)
    skipped = set(skip)
    for endpoint, zone in sorted(declared_endpoints.items()):
        if endpoint in skipped:
            continue
        provider, model_id = (providers or {}).get(endpoint, ("unspecified", endpoint))
        registry.register(publisher.issue(endpoint=endpoint, zone=zone, provider=provider,
                                          model_id=model_id, artifact=artifacts[endpoint]))
    return registry


__all__ = [
    "CHECK", "AttestedEndpoint", "ManifestPublisher", "ModelAttestationCode",
    "ModelAttestationDenied", "ModelManifest", "ModelRegistry", "artifact_digest",
    "registry_for",
]
