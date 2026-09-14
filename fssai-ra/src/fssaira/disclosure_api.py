"""HTTP routes for governed disclosure: the read path of the control plane.

The action routes enforce the first rule: a model may propose an action, it
cannot manufacture the authority to execute it. These routes enforce the second:
a model may request information, it cannot manufacture the entitlement to see
it, and it cannot launder what it saw.

Every decision is made by :class:`fssaira.disclosure.DisclosureGate`. The routes
only establish who is asking, from the authenticated principal, and hold the
server-side grant store so a caller can name a grant but never supply one. Roles
come from the domain pack: grants and revocations need the pack's declared data
or privacy owner, declassification needs the rule's declared approval role, and
break-glass review needs the declared review role.

Teaching keys are used unless ``FSSAI_DISCLOSURE_GRANT_KEY`` and
``FSSAI_DISCLOSURE_DECLASSIFICATION_KEY`` are set. The model endpoint's name
comes from ``FSSAI_MODEL_ENDPOINT`` and must be declared in the pack; an
undeclared endpoint receives nothing.
"""

import json
import os
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .disclosure import (
    DataLabel,
    DeclassificationAuthority,
    DisclosureCode,
    DisclosureDenied,
    DisclosureGate,
    DisclosureGrant,
    GrantAuthority,
)
from .security import Principal

Name = Field(min_length=1, max_length=200)


class RecordLoad(BaseModel):
    subject: str = Name
    fields: dict[str, str] = Field(min_length=1, max_length=200)


class GrantCreate(BaseModel):
    holder: str = Name
    purpose: str = Name
    subjects: list[str] = Field(min_length=1, max_length=100)
    fields: list[str] = Field(min_length=1, max_length=200)
    ttl_seconds: int = Field(default=900, ge=1, le=86400)
    basis: str = Field(default="declared basis", min_length=1, max_length=500)
    break_glass: bool = False
    justification: str = Field(default="", max_length=2000)


class RevocationCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class ConsentWithdrawal(BaseModel):
    subject: str = Name
    purpose: str = Name


class ContextRequest(BaseModel):
    grant_id: str = Name
    session_id: str = Name
    purpose: str = Name
    subjects: list[str] = Field(min_length=1, max_length=100)
    fields: list[str] = Field(min_length=1, max_length=200)


class OutputCreate(BaseModel):
    session_id: str = Name
    content: str = Field(min_length=1, max_length=50_000)


class DeclassifyRequest(BaseModel):
    rule: str = Name


class ReleaseRequest(BaseModel):
    recipient: str = Name
    purpose: str = Name
    recipient_id: str = Field(default="", max_length=200)
    restore_identity: bool = False


class TokenGrant(BaseModel):
    token: str = Field(min_length=20, max_length=16_000)


class BreakGlassReview(BaseModel):
    finding: str = Field(min_length=1, max_length=2000)


def token_verifier_from_env():
    """``FSSAI_DISCLOSURE_TOKEN_ISSUER``, ``_AUDIENCE``, and ``_JWKS_URL``, or nothing."""
    issuer = os.getenv("FSSAI_DISCLOSURE_TOKEN_ISSUER", "")
    if not issuer:
        return None
    from .disclosure_tokens import JwtGrantVerifier

    return JwtGrantVerifier(issuer=issuer,
                            audience=os.getenv("FSSAI_DISCLOSURE_TOKEN_AUDIENCE", ""),
                            jwks_url=os.getenv("FSSAI_DISCLOSURE_TOKEN_JWKS_URL") or None)


def consent_from_env():
    """``FSSAI_DISCLOSURE_CONSENT_URL`` selects a live institutional consent service."""
    url = os.getenv("FSSAI_DISCLOSURE_CONSENT_URL", "")
    if not url:
        return None
    import httpx

    from .disclosure_sources import HttpConsentService

    return HttpConsentService(url, httpx.Client())


def records_from_env():
    """``FSSAI_DISCLOSURE_FHIR_URL`` and ``FSSAI_DISCLOSURE_FHIR_FIELDS`` (JSON field map)."""
    url = os.getenv("FSSAI_DISCLOSURE_FHIR_URL", "")
    if not url:
        return None
    import httpx

    from .disclosure_sources import FhirRecordSource

    fields = json.loads(os.getenv("FSSAI_DISCLOSURE_FHIR_FIELDS", "{}"))
    return FhirRecordSource(url, httpx.Client(), fields=fields)


def _label(label: DataLabel) -> dict:
    return label.to_dict()


class DisclosureRuntime:
    """The gate, its signing authorities, and the server-held grant store."""

    def __init__(self, profile, evidence, evidence_token: str, *,
                 model_endpoint: str | None = None, store=None, records=None,
                 consent=None, token_verifier=None, privacy=None) -> None:
        from .disclosure_store import open_disclosure_store

        if profile.disclosure is None:
            raise ValueError("profile declares no disclosure policy")
        self.profile = profile
        self.policy = profile.disclosure
        self.grant_authority = GrantAuthority(
            secret=os.getenv("FSSAI_DISCLOSURE_GRANT_KEY", "teaching-disclosure-key-not-secret"))
        self.declassifier = DeclassificationAuthority(
            secret=os.getenv("FSSAI_DISCLOSURE_DECLASSIFICATION_KEY",
                             "teaching-declassification-key-not-secret"))
        self.store = store if store is not None else open_disclosure_store(
            os.getenv("FSSAI_DISCLOSURE_STORE", "memory"))
        self.token_verifier = token_verifier if token_verifier is not None else token_verifier_from_env()
        consent = consent if consent is not None else consent_from_env()
        if records is None:
            records = records_from_env()
        self.privacy_config = privacy
        if privacy is not None:
            privacy.validate()
            if self.store.kind != "memory":
                raise ValueError("privacy reference profile requires memory store; durable custody is unqualified")
            if records is not None and records is not privacy.records:
                raise ValueError("privacy profile cannot use a different record source")
            records = privacy.records
        self.gate = DisclosureGate(
            self.policy, records if records is not None else {}, evidence, evidence_token,
            grant_keys=self.grant_authority.trusted_keys,
            declassification_keys=self.declassifier.trusted_keys,
            store=self.store, consent=consent, token_verifier=self.token_verifier,
        )
        self.privacy_gate = None
        if privacy is not None:
            from .privacy_pipeline import PrivacyGate
            self.privacy_gate = PrivacyGate(
                self.gate, privacy.vault, privacy.records,
                identity_fields=privacy.identity_fields, restore_credential=privacy.restore_credential)
        self.model_endpoint = model_endpoint if model_endpoint is not None else os.getenv(
            "FSSAI_MODEL_ENDPOINT", "")

    def put_grant(self, grant: DisclosureGrant) -> None:
        with self.store.atomic() as tx:
            tx.put_grant(grant.grant_id, grant.to_record())

    def get_grant(self, grant_id: str) -> DisclosureGrant | None:
        with self.store.atomic() as tx:
            body = tx.get_grant(grant_id)
        return DisclosureGrant.from_record(body) if body else None

    def grant_count(self) -> int:
        with self.store.atomic() as tx:
            return tx.grant_count()

    @property
    def owner_roles(self) -> set[str]:
        governance = self.profile.governance
        return {governance.data_owner, governance.privacy_owner} if governance else set()

    def assemble(self, caller: Principal, request: ContextRequest, now: float):
        if self.privacy_config is not None:
            config = self.privacy_config
            try:
                digest, model_id = config.runtime_identity(self.model_endpoint)
            except Exception as exc:
                raise DisclosureDenied("MODEL_IDENTITY_UNAVAILABLE",
                                       "serving identity could not be established") from exc
            config.registry.attest(
                self.model_endpoint, digest, presented_model_id=model_id, now=now,
                purpose=request.purpose,
                classes={self.policy.field_classes.get(name, "undeclared") for name in request.fields})
        assemble = self.privacy_gate.context_for_model if self.privacy_gate else self.gate.assemble_context
        return assemble(
            requester=caller.subject, session_id=request.session_id,
            grant=self.get_grant(request.grant_id), purpose=request.purpose,
            subjects=request.subjects, fields=request.fields,
            model_endpoint=self.model_endpoint, now=now,
        )

    def derive(self, *, requester: str, session_id: str, content: str):
        derive = self.privacy_gate.derive if self.privacy_gate else self.gate.derive_output
        return derive(requester=requester, session_id=session_id, content=content)


def register_disclosure_routes(app: FastAPI, runtime: DisclosureRuntime | None, caller_type: Any,
                               clock=None) -> None:
    import time

    now = clock or time.time

    def need() -> DisclosureRuntime:
        if runtime is None:
            raise HTTPException(status_code=404,
                                detail="this profile declares no disclosure policy")
        return runtime

    def require_any(caller: Principal, roles: set[str], what: str) -> str:
        for role in caller.roles:
            if role in roles:
                return role
        raise HTTPException(status_code=403,
                            detail=f"{what} requires one of: {', '.join(sorted(roles))}")

    @app.get("/v1/disclosure", tags=["disclosure"])
    def disclosure_summary(caller: caller_type):
        rt = need()
        return {
            "policy": rt.policy.summary(),
            "privacy_profile": "tokenized-memory-reference" if rt.privacy_gate else "disclosure-only",
            "model_endpoint": rt.model_endpoint or None,
            "model_endpoint_zone": rt.policy.endpoints.get(rt.model_endpoint),
            "grants_held_by_server": rt.grant_count(),
            "state_store": rt.store.kind,
            "open_break_glass_reviews": sorted(rt.gate.open_break_glass),
            "rule": "a model may request information; it cannot manufacture the entitlement "
                    "to see it, and it cannot launder what it saw",
        }

    @app.post("/v1/disclosure/records", status_code=201, tags=["disclosure"])
    def load_records(request: RecordLoad, caller: caller_type):
        rt = need()
        require_any(caller, {"platform_operator"}, "loading records")
        names = rt.gate.load_records(request.subject, request.fields, loaded_by=caller.subject)
        return {"subject": request.subject, "fields": names,
                "note": "values are held by the gate and never echoed or logged"}

    @app.post("/v1/disclosure/grants", status_code=201, tags=["disclosure"])
    def issue_grant(request: GrantCreate, caller: caller_type):
        rt = need()
        if request.break_glass:
            if request.holder != caller.subject:
                raise HTTPException(status_code=403,
                                    detail="break-glass access can only be declared for yourself")
        else:
            require_any(caller, rt.owner_roles, "issuing a grant")
        unknown = sorted(set(request.fields) - set(rt.policy.field_classes))
        if unknown:
            raise HTTPException(status_code=422, detail=f"undeclared fields: {', '.join(unknown)}")
        grant = rt.grant_authority.issue(
            grant_id=f"grant-{uuid.uuid4().hex[:16]}", holder=request.holder,
            purpose=request.purpose, subjects=request.subjects, fields=request.fields,
            classes={rt.policy.field_classes[name] for name in request.fields},
            issued_by=caller.subject, now=now(), ttl_seconds=request.ttl_seconds,
            basis=request.basis, break_glass=request.break_glass,
            justification=request.justification,
        )
        rt.put_grant(grant)
        return grant.to_dict()

    @app.post("/v1/disclosure/grants/token", status_code=201, tags=["disclosure"])
    def register_token_grant(request: TokenGrant, caller: caller_type):
        """Register a grant issued by the institutional authorization server."""
        rt = need()
        if rt.token_verifier is None:
            raise HTTPException(status_code=501,
                                detail="no authorization server is configured for disclosure grants")
        from .disclosure_tokens import TokenRejected

        try:
            grant = rt.token_verifier.grant_from_token(request.token)
        except TokenRejected as exc:
            raise DisclosureDenied(DisclosureCode.GRANT_SIGNATURE_INVALID,
                                   f"grant token rejected: {exc}") from exc
        if grant.holder != caller.subject:
            raise HTTPException(status_code=403,
                                detail="only the holder named in the token may register it")
        rt.put_grant(grant)
        return grant.to_dict()

    @app.post("/v1/disclosure/grants/{grant_id}/revoke", tags=["disclosure"])
    def revoke_grant(grant_id: str, request: RevocationCreate, caller: caller_type):
        rt = need()
        require_any(caller, rt.owner_roles, "revoking a grant")
        if rt.get_grant(grant_id) is None:
            raise HTTPException(status_code=404, detail="unknown grant")
        rt.gate.revoke_grant(grant_id, by=caller.subject, reason=request.reason)
        return {"grant_id": grant_id, "revoked": True}

    @app.post("/v1/disclosure/consent/withdrawals", status_code=201, tags=["disclosure"])
    def withdraw_consent(request: ConsentWithdrawal, caller: caller_type):
        rt = need()
        require_any(caller, rt.owner_roles, "recording a consent withdrawal")
        rt.gate.withdraw_consent(request.subject, request.purpose, recorded_by=caller.subject)
        return {"subject": request.subject, "purpose": request.purpose, "withdrawn": True}

    @app.post("/v1/disclosure/context", tags=["disclosure"])
    def assemble_context(request: ContextRequest, caller: caller_type):
        rt = need()
        context = rt.assemble(caller, request, now())
        return {"receipt_id": context.receipt_id, "session_id": context.session_id,
                "label": _label(context.label), "values": context.values}

    @app.post("/v1/disclosure/outputs", status_code=201, tags=["disclosure"])
    def derive_output(request: OutputCreate, caller: caller_type):
        rt = need()
        output = rt.derive(requester=caller.subject, session_id=request.session_id,
                                       content=request.content)
        return {"output_id": output.output_id, "label": _label(output.label),
                "content_digest": output.digest}

    @app.post("/v1/disclosure/outputs/{output_id}/declassify", status_code=201,
              tags=["disclosure"])
    def declassify(output_id: str, request: DeclassifyRequest, caller: caller_type):
        rt = need()
        rule = rt.policy.declassification.get(request.rule)
        if rule is None:
            raise HTTPException(status_code=404, detail="unknown declassification rule")
        role = require_any(caller, {rule.approval_role}, f"declassification rule {rule.name}")
        output = rt.gate.output(output_id)
        approval = rt.declassifier.approve(output, rule=rule.name, approver=caller.subject,
                                           approver_role=role, now=now())
        lowered = rt.gate.declassify(output, rule=rule.name, approval=approval, now=now())
        return {"output_id": lowered.output_id, "label": _label(lowered.label),
                "content": lowered.content, "approved_by": lowered.declassified_by}

    @app.post("/v1/disclosure/outputs/{output_id}/release", tags=["disclosure"])
    def release(output_id: str, request: ReleaseRequest, caller: caller_type):
        rt = need()
        output = rt.gate.output(output_id)
        if output.holder != caller.subject:
            raise HTTPException(status_code=403,
                                detail="only the principal holding an output may release it")
        if rt.privacy_gate is not None:
            released = rt.privacy_gate.release(
                output, recipient=request.recipient, recipient_id=request.recipient_id,
                purpose=request.purpose, now=now(), restore_identity=request.restore_identity)
            return {"receipt_id": released.receipt.receipt_id, "output_id": output.output_id,
                    "recipient": request.recipient, "purpose": request.purpose,
                    "label": _label(released.receipt.label), "content": released.content,
                    "identity_restored": released.identity_restored}
        if request.restore_identity:
            raise HTTPException(status_code=409, detail="identity restoration requires the privacy profile")
        receipt = rt.gate.release(output, recipient=request.recipient,
                                  recipient_id=request.recipient_id,
                                  purpose=request.purpose, now=now())
        return {"receipt_id": receipt.receipt_id, "output_id": receipt.output_id,
                "recipient": receipt.recipient, "purpose": receipt.purpose,
                "label": _label(receipt.label), "content": output.content}

    @app.post("/v1/disclosure/break-glass/{grant_id}/review", tags=["disclosure"])
    def review_break_glass(grant_id: str, request: BreakGlassReview, caller: caller_type):
        rt = need()
        rule = rt.policy.break_glass
        if rule is None:
            raise HTTPException(status_code=404, detail="this pack declares no emergency access")
        role = require_any(caller, {rule.review_role}, "break-glass review")
        rt.gate.record_break_glass_review(grant_id, reviewer=caller.subject,
                                          reviewer_role=role, finding=request.finding)
        return {"grant_id": grant_id, "reviewed": True}


def proposals_output(runtime: DisclosureRuntime, caller: Principal, session_id: str,
                     proposals: list[dict]):
    """Label a model's proposal set as a governed output of its session."""
    return runtime.derive(
        requester=caller.subject, session_id=session_id,
        content=json.dumps(proposals, sort_keys=True, default=str),
    )


__all__ = [
    "ContextRequest", "DisclosureDenied", "DisclosureRuntime", "proposals_output",
    "register_disclosure_routes",
]
