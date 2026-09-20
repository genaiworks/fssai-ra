"""FastAPI control plane for application-neutral accountable actions.

The API is the narrow waist of the architecture. Everything a person or a
program can do to a governed resource happens through the same three steps --
propose, approve, execute -- with the same checks, whether the caller is the
React console, the CLI, a bounded agent, or a script an institution wrote
itself. There is no second path that skips a step, which is the property that
makes the evidence ledger complete rather than merely well-intentioned.

Route groups
------------
``/health``, ``/readiness``, ``/metrics``   what this deployment actually is
``/v1/profile``, ``/v1/contract``           the governance configuration in force
``/v1/capabilities``                        what a model is permitted to propose
``/v1/resources``                           the authoritative register
``/v1/proposals``                           propose, approve, execute, inspect
``/v1/evidence``                            the decision record and its verification
``/v1/disclosure``                          governed reads and releases (second rule)
``/v1/verification``, ``/v1/conformance``   machine-checked assurance on demand
``/v1/recovery``                            reconciliation, for the named owner

Authentication is real (see :mod:`fssaira.security`) and authorization stays in
the executor. The API never decides whether an approval is valid; it carries the
request to the component that does.
"""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import __version__
from .control_plane import ControlPlane
from .exact_action import ExecutionDenied, ExecutionUncertain
from .runtime_factory import build_control_plane, configuration_warnings, readiness
from .security import AuthenticationError, Authenticator, Principal
from .telemetry import CONTENT_TYPE, render_prometheus, samples_from

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ResourceCreate(BaseModel):
    resource_id: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1, max_length=100)
    version: int = Field(default=1, ge=1)


class ProposalCreate(BaseModel):
    request_id: str | None = Field(default=None, max_length=200)
    operation: str = Field(min_length=1, max_length=200)
    resource_id: str = Field(min_length=1, max_length=200)
    from_status: str = Field(min_length=1, max_length=100)
    to_status: str = Field(min_length=1, max_length=100)
    evidence_version: str = Field(min_length=1, max_length=300)


class ApprovalCreate(BaseModel):
    ttl_seconds: int = Field(default=300, ge=1, le=86400)


EvidenceText = Annotated[str, Field(min_length=1, max_length=20_000)]


class GovernedContext(BaseModel):
    """Records to place in the model's context, released only through the gate."""

    grant_id: str = Field(min_length=1, max_length=200)
    session_id: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1, max_length=200)
    subjects: list[str] = Field(min_length=1, max_length=100)
    fields: list[str] = Field(min_length=1, max_length=200)


class ProposeTask(BaseModel):
    """Ask the configured model for tool-call proposals. Nothing executes."""

    task: str = Field(min_length=1, max_length=2000)
    evidence: list[EvidenceText] = Field(default_factory=list, max_length=20)
    governed_context: GovernedContext | None = None


# ---------------------------------------------------------------------------
# Identity dependency
# ---------------------------------------------------------------------------


def current_principal(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_fssai_identity: Annotated[str | None, Header()] = None,
    x_fssai_role: Annotated[str | None, Header()] = None,
) -> Principal:
    """Establish who is calling, using the app's configured authenticator.

    A 401 here means "I do not know who you are". Whether that identity is
    allowed to do the thing is a separate decision, made later and elsewhere.
    """
    authenticator: Authenticator = request.app.state.authenticator
    try:
        return authenticator.authenticate(
            authorization=authorization,
            identity_header=x_fssai_identity,
            role_header=x_fssai_role,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


#: Every route that touches a governed resource depends on this.
Caller = Annotated[Principal, Depends(current_principal)]


def require(principal: Principal, role: str) -> None:
    if not principal.has_role(role):
        raise HTTPException(status_code=403, detail=f"role '{role}' is required")


def require_one(principal: Principal, *roles: str) -> None:
    if not any(principal.has_role(role) for role in roles):
        raise HTTPException(
            status_code=403,
            detail="one of these roles is required: " + ", ".join(roles),
        )


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def _oversight_samples(plane) -> dict:
    """Review-capacity signals, for the alert an operator actually needs.

    ``fssaira_review_capacity_declared`` is 0 when nothing was declared, which is
    the case worth alerting on first: a deployment with no ceiling looks
    identical to one inside its ceiling on every other metric, right up to the
    point where it is not.

    ``fssaira_review_headroom`` is the fraction of the declared per-window
    ceiling still unused by the busiest reviewer. It reaches 0 when someone is
    saturated and the next arrival takes the manual fallback — which is a
    capacity signal, not an error, and should be treated as one.
    """
    monitor = getattr(plane.authority, "_oversight", None)
    if monitor is None:
        return {"fssaira_review_capacity_declared": 0}

    report = monitor.report()
    samples = {
        "fssaira_review_capacity_declared": 1,
        "fssaira_review_quota_per_window": monitor.policy.max_approvals_per_window,
        "fssaira_review_deliberation_floor_seconds": monitor.policy.min_deliberation_seconds,
        "fssaira_review_approvals_admitted": report.approvals,
        "fssaira_review_escalations": report.escalations,
        "fssaira_review_headroom": report.headroom,
        "fssaira_review_refusals_total": report.refusals_total,
    }
    # Per-code refusal counters, so an operator can tell "we are at the ceiling"
    # apart from "approvals are coming back faster than anyone can read".
    for code, count in report.refusals.items():
        samples[f"fssaira_review_refusals_{code.lower()}"] = count
    return samples


def _declared_controls(plane) -> dict:
    """The deployment's own declarations, or an explicit statement of absence.

    ``null`` here is meaningful and is not the same as a default. It says the
    institution has declared nothing, which is a posture rather than an omission
    — and the matching entry in ``configuration_warnings`` says what that costs.
    """
    from .assisted_review import AssistanceMode, ReviewAssistance
    from .delegation import DelegationPolicy

    monitor = getattr(plane.authority, "_oversight", None)
    assistance = ReviewAssistance.from_env()
    delegation = DelegationPolicy.from_env()

    return {
        "review_capacity": (
            monitor.policy.to_dict() if monitor is not None else None
        ),
        "review_capacity_note": (
            "enforced on this deployment's approval path"
            if monitor is not None
            else "not declared: approvals are unlimited and the ceiling is unbounded"
        ),
        "review_assistance": (
            assistance.to_dict()
            if assistance.mode is not AssistanceMode.UNAIDED
            else {"mode": "unaided", "note": "the full deliberation floor applies"}
        ),
        "delegation": delegation.to_dict() if delegation is not None else None,
        "delegation_note": (
            "declared"
            if delegation is not None
            else "not declared: correct for a single-agent deployment, wrong for one "
                 "that calls a tool server, plugin, or sub-agent"
        ),
        "limits": [
            "these are declarations, not measurements: nothing here inspects which "
            "model reviews this deployment's work, or how attentive any reviewer is",
        ],
    }


def create_app(
    runtime: ControlPlane | None = None,
    *,
    authenticator: Authenticator | None = None,
    model_endpoint: str | None = None,
    disclosure_options: dict | None = None,
) -> FastAPI:
    from .disclosure import DisclosureDenied
    from .disclosure_api import DisclosureRuntime, proposals_output, register_disclosure_routes

    plane = build_control_plane() if runtime is None else runtime
    auth = authenticator or Authenticator()
    disclosure = (
        DisclosureRuntime(plane.profile, plane.evidence,
                          getattr(plane, "evidence_token", "teaching-evidence-writer"),
                          model_endpoint=model_endpoint, **(disclosure_options or {}))
        if plane.profile.disclosure is not None else None
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.control_plane = plane
        app.state.authenticator = auth
        yield

    app = FastAPI(
        title="Trust by Construction Control Plane",
        version=__version__,
        description=(
            "Reference API for exact-action proposals, human approval, execution, "
            "evidence, recovery, and machine-checked assurance. A model may propose "
            "an action; it cannot manufacture the authority to execute it."
        ),
        lifespan=lifespan,
    )
    # Set immediately as well as in lifespan: a test client that never enters the
    # lifespan context must still authenticate rather than fail open or 500.
    app.state.control_plane = plane
    app.state.authenticator = auth

    origins = [
        origin.strip()
        for origin in os.getenv(
            "FSSAI_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8088"
        ).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-FSSAI-Identity", "X-FSSAI-Role"],
    )

    @app.middleware("http")
    async def protect_operational_responses(request: Request, call_next):
        """Keep governed records and authenticated results out of shared caches."""
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/v1/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    from .key_custody import CustodyDenied
    from .privacy_vault import VaultDenied

    @app.exception_handler(CustodyDenied)
    @app.exception_handler(VaultDenied)
    async def privacy_denied_handler(_request: Request, exc):
        return JSONResponse(status_code=403, content={"error": exc.code,
                                                     "detail": "privacy operation denied"})

    # -- error translation -------------------------------------------------
    @app.exception_handler(ExecutionDenied)
    async def denied_handler(_request: Request, exc: ExecutionDenied):
        return JSONResponse(status_code=409, content={"error": exc.code, "detail": str(exc)})

    @app.exception_handler(DisclosureDenied)
    async def disclosure_denied_handler(_request: Request, exc: DisclosureDenied):
        # 403: nothing was disclosed, and retrying the same request cannot change that.
        return JSONResponse(status_code=403, content={"error": exc.code, "detail": exc.detail})

    @app.exception_handler(ExecutionUncertain)
    async def uncertain_handler(_request: Request, exc: ExecutionUncertain):
        # 202: the mutation happened. Repeating it blindly is the wrong move,
        # and the status code is chosen to make a naive client retry-loop stop.
        return JSONResponse(
            status_code=202,
            content={"error": exc.code, "detail": str(exc), "result": asdict(exc.result)},
        )

    # -- introspection -----------------------------------------------------
    @app.get("/health", tags=["introspection"])
    def health():
        model = plane.model
        return {
            "status": "ok",
            "version": __version__,
            "profile": plane.profile.profile_id,
            "durability": plane.durability,
            "evidence_valid": plane.evidence.verify(),
            "evidence_records": len(plane.evidence),
            "pending_outcomes": plane.pending_outcomes,
            "model": model.to_dict() if hasattr(model, "to_dict") else None,
            "authentication": {"mode": auth.config.mode, "warnings": auth.warnings},
            # What this deployment has declared about the three things only an
            # institution can state: how much review it can supply, whether the
            # reviewer's assistant is independent of the proposer, and how far
            # authority may be passed on. Published on /health because an
            # unenforced ceiling is not visible from any other observable — a
            # deployment with no declared capacity looks identical to one inside
            # its capacity right up to the moment it is not.
            "declared_controls": _declared_controls(plane),
            "configuration_warnings": [item.message for item in configuration_warnings()],
        }

    @app.get("/readiness", tags=["introspection"])
    def get_readiness():
        """Whether any known teaching default is still active."""
        return readiness()

    @app.get("/metrics", response_class=PlainTextResponse, tags=["introspection"])
    def metrics():
        samples = samples_from(
            plane.metrics,
            evidence=plane.evidence,
            extra={
                "fssaira_pending_outcomes": plane.pending_outcomes,
                "fssaira_configuration_warnings": len(configuration_warnings()),
                "fssaira_build_info": 1,
                **_oversight_samples(plane),
            },
        )
        body = render_prometheus(
            samples,
            {"profile": plane.profile.profile_id, "version": __version__,
             "durability": plane.durability},
        )
        return Response(content=body, media_type=CONTENT_TYPE)

    # -- governance configuration -----------------------------------------
    @app.get("/v1/profile", tags=["governance"])
    def get_profile():
        return {
            "profile_id": plane.profile.profile_id,
            "version": plane.profile.version,
            "title": plane.profile.title,
            "resource_name": plane.profile.resource_name,
            "owner": plane.profile.owner,
            "manual_fallback": plane.profile.manual_fallback,
            "transitions": [asdict(rule) for rule in plane.profile.transitions],
            "governance": (
                asdict(plane.profile.governance) if plane.profile.governance else None
            ),
            "disclosure": (
                plane.profile.disclosure.summary() if plane.profile.disclosure else None
            ),
        }

    @app.get("/v1/contract", tags=["governance"])
    def get_contract():
        """The seven-field control contract, as machine-readable YAML."""
        from .contract import ControlContract

        # The contract path is deployment configuration, not caller input. The
        # former query parameter let remote callers probe arbitrary directories
        # for YAML files with the expected shape.
        directory = os.getenv("FSSAI_CONTRACT_DIR", "contract")
        try:
            contract = ControlContract.load(directory)
            contract.validate()
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=f"contract unavailable: {exc}") from exc
        return {
            "requirements": [asdict(item) for item in contract],
            "count": len(contract),
            "domains": sorted({item.domain for item in contract}),
        }

    @app.get("/v1/capabilities", tags=["governance"])
    def get_capabilities():
        """What a model may propose, and the review level each proposal carries.

        Served so an operator can see that the action class is configuration,
        not something the model gets to assert at call time.
        """
        from .models.base import CapabilityCatalogue

        return CapabilityCatalogue.default().to_dict()

    @app.get("/v1/interfaces", tags=["governance"])
    def get_interfaces():
        """The interface inventory a directional claim depends on."""
        from .diode_transport import InterfaceInventory

        return InterfaceInventory.reference().to_dict()

    # -- resources ---------------------------------------------------------
    @app.post("/v1/resources", status_code=201, tags=["resources"])
    def register_resource(request: ResourceCreate, caller: Caller):
        require(caller, "platform_operator")
        return plane.register_resource(**request.model_dump())

    @app.get("/v1/resources/{resource_id}", tags=["resources"])
    def get_resource(resource_id: str, caller: Caller):
        try:
            return plane.get_resource(resource_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="resource not found") from exc

    # -- the three-step protocol ------------------------------------------
    def approval_role(proposal, caller: Principal) -> str:
        allowed = plane.profile.required_approval_roles.get(
            (proposal.operation, proposal.from_status, proposal.to_status), frozenset()
        )
        for role in caller.roles:
            if role in allowed:
                return role
        if not allowed and caller.role:
            return caller.role
        raise HTTPException(
            status_code=403,
            detail="one of the profile's approval roles is required for this transition",
        )

    @app.post("/v1/proposals", status_code=201, tags=["actions"])
    def create_proposal(request: ProposalCreate, caller: Caller):
        try:
            return asdict(plane.propose(requester=caller.subject, **request.model_dump()))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="resource not found") from exc

    @app.get("/v1/proposals/{request_id}", tags=["actions"])
    def get_proposal(request_id: str, caller: Caller):
        proposal = plane.get_proposal(request_id)
        approval = plane.objects.get("approval", request_id)
        return {
            "proposal": asdict(proposal),
            "proposal_digest": proposal.digest,
            "approval": approval,
            "result": plane.get_result(request_id),
        }

    @app.post("/v1/proposals/{request_id}/review", status_code=201, tags=["actions"])
    def begin_review(request_id: str, caller: Caller):
        """Start an idempotent, server-timed review session for this proposal."""
        proposal = plane.get_proposal(request_id)
        approval_role(proposal, caller)
        return plane.begin_review(request_id, reviewer=caller.subject)

    @app.post("/v1/proposals/{request_id}/endorsement", status_code=201, tags=["actions"])
    def endorse_review(request_id: str, caller: Caller):
        """Record a second authenticated review when the load policy requires one."""
        proposal = plane.get_proposal(request_id)
        role = approval_role(proposal, caller)
        return plane.endorse_review(
            request_id, reviewer=caller.subject, reviewer_role=role
        )

    @app.post("/v1/proposals/{request_id}/approval", status_code=201, tags=["actions"])
    def approve_proposal(request_id: str, request: ApprovalCreate, caller: Caller):
        # The approver's role comes from the authenticated principal, never from
        # the request body. A caller may not nominate the authority it is using.
        proposal = plane.get_proposal(request_id)
        role = approval_role(proposal, caller)
        endorsement = plane.review_endorsement(request_id)
        if endorsement is not None and endorsement["reviewer"] == caller.subject:
            raise ExecutionDenied(
                "SECOND_REVIEWER_NOT_DISTINCT",
                "the primary approver must differ from the stored second reviewer",
            )
        return asdict(plane.approve(
            request_id,
            approver=caller.subject,
            approver_role=role,
            ttl_seconds=request.ttl_seconds,
            presented_at=plane.review_started_at(request_id, reviewer=caller.subject),
            second_approver=None if endorsement is None else endorsement["reviewer"],
            second_approver_role=(
                None if endorsement is None else endorsement["reviewer_role"]
            ),
        ))

    @app.post("/v1/proposals/{request_id}/execute", tags=["actions"])
    def execute_proposal(request_id: str, caller: Caller):
        return asdict(plane.execute(request_id))

    @app.get("/v1/proposals/{request_id}/evidence", tags=["evidence"])
    def get_proposal_evidence(request_id: str, caller: Caller):
        return {"request_id": request_id, "records": plane.evidence_for(request_id)}

    @app.get("/v1/proposals/{request_id}/packet", tags=["evidence"])
    def export_packet(request_id: str, caller: Caller, response: Response):
        # This private operational artifact contains identities and case references.
        # It is not a public student portal or a redacted disclosure response.
        require(caller, "platform_operator")
        from .decision_packet import export_decision_packet

        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Disposition"] = 'attachment; filename="decision-packet.json"'
        return export_decision_packet(plane, request_id)

    # -- evidence ----------------------------------------------------------
    @app.get("/v1/evidence", tags=["evidence"])
    def list_evidence(
        caller: Caller,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=1000),
        kind: str | None = Query(default=None),
    ):
        return plane.evidence_page(offset=offset, limit=limit, kind=kind)

    @app.get("/v1/evidence/verify", tags=["evidence"])
    def verify_evidence(caller: Caller):
        valid = plane.evidence.verify()
        if not valid:
            plane.metrics.tamper_detected += 1
        return {
            "chain_valid": valid,
            "records": len(plane.evidence),
            "note": "tamper-evidence detects an alteration; it does not prevent one",
        }

    # -- assurance on demand ----------------------------------------------
    @app.get("/v1/verification", tags=["assurance"])
    def run_verification(caller: Caller):
        """Bounded model check of the active profile's authority invariants."""
        require_one(caller, "platform_operator", "auditor")
        from .verification import verify_profile

        return verify_profile(plane.profile).to_dict()

    @app.get("/v1/conformance", tags=["assurance"])
    def run_conformance_check(caller: Caller):
        """Behavioural conformance of the *configured* backends, not the reference ones."""
        require_one(caller, "platform_operator", "auditor")
        from .conformance import Bundle, run_conformance

        bundle = Bundle(
            profile=plane.profile,
            register=plane.register,
            evidence=plane.evidence,
            evidence_token=os.getenv("FSSAI_EVIDENCE_TOKEN", "teaching-evidence-writer"),
            objects=plane.objects,
            events=plane.events,
            model=getattr(plane.model, "backend", None),
            executor_factory=lambda: plane.executor,
        )
        return run_conformance(bundle).to_dict()

    @app.get("/v1/coverage", tags=["assurance"])
    def run_contract_coverage(caller: Caller):
        """Is each control-contract requirement enforced, or only written down?

        Published alongside a deployment for the same reason the conformance
        report is: an operator replacing a component needs to know which
        governance claims are backed by something that runs, which rest on a
        named role's attestation, and which rest on nothing.
        """
        require_one(caller, "platform_operator", "auditor")
        from .coverage import measure_coverage

        directory = os.getenv("FSSAI_CONTRACT_DIR", "contract")
        try:
            return measure_coverage(directory).to_dict()
        except (OSError, ValueError) as exc:
            raise HTTPException(
                status_code=503,
                detail=f"the control contract could not be read from {directory!r}: {exc}",
            ) from exc

    @app.get("/v1/delegation", tags=["assurance"])
    def run_delegation_check(caller: Caller):
        """What a chain of agents confers, across three architectures.

        Reports the scenario suite, the per-invariant ablations, and the bounded
        enumeration of the declared chain space. The deployment's own delegation
        policy is reported with it, because the depth bound and the
        consequential-delegation rule are declared configuration rather than
        constants.
        """
        require_one(caller, "platform_operator", "auditor")
        from .delegation import verify_delegation_space
        from .delegation_eval import ablate_delegation, run_delegation_suite

        return {
            **run_delegation_suite().to_dict(),
            "ablations": ablate_delegation(),
            "verification": verify_delegation_space().to_dict(),
        }

    @app.get("/v1/assisted-review", tags=["assurance"])
    def run_assisted_review_check(caller: Caller):
        """What a review assistant does to this deployment's oversight claim.

        The arms differ only in the declared independence of the assistant. The
        figures are fixture observations against a declared correlation, never a
        measurement of any model — the response says so in its own limits.
        """
        require_one(caller, "platform_operator", "auditor")
        from .assisted_review import run_assisted_review_trial

        return run_assisted_review_trial(plane.profile)

    # -- bounded intelligence ---------------------------------------------
    @app.post("/v1/propose-task", tags=["intelligence"])
    def propose_task(request: ProposeTask, caller: Caller):
        """Run the configured model and return what it *would* like to do.

        Nothing executes. The response is the model's proposal set with each
        call's authoritative action class attached from the capability
        catalogue, so a reviewer sees the real review level rather than whatever
        the model said about itself.
        """
        from .bounded_intelligence import UntrustedEvidence
        from .models.base import CapabilityCatalogue

        backend = getattr(plane.model, "backend", plane.model)
        if backend is None:
            raise HTTPException(status_code=503, detail="no model backend is configured")
        catalogue = CapabilityCatalogue.default()
        evidence = [UntrustedEvidence(source="operator-supplied", text=item)
                    for item in request.evidence]
        context = None
        if disclosure is not None and disclosure.privacy_gate is not None and request.governed_context is None:
            raise HTTPException(status_code=422, detail="privacy profile requires governed context")
        if request.governed_context is not None:
            if disclosure is None:
                raise HTTPException(
                    status_code=404, detail="this profile declares no disclosure policy")
            import time as _time

            context = disclosure.assemble(caller, request.governed_context, _time.time())
            evidence += [
                UntrustedEvidence(source=f"governed:{context.receipt_id}", text=f"{key}: {value}")
                for key, value in sorted(context.values.items())
            ]
        model_task = request.task
        if context is not None and disclosure.privacy_gate is not None:
            sanitize = disclosure.privacy_gate.sanitize_text
            model_task = sanitize(requester=caller.subject, session_id=context.session_id,
                                  content=model_task)
            evidence = [UntrustedEvidence(source=item.source,
                text=sanitize(requester=caller.subject, session_id=context.session_id,
                              content=item.text)) for item in evidence]
        try:
            calls = backend.propose(model_task, evidence)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="model backend failed") from exc
        proposals = []
        for call in calls:
            capability = catalogue.get(call.tool)
            proposals.append({
                "tool": call.tool,
                "operation": call.operation,
                "target": call.target,
                "args": call.args,
                "rationale": call.rationale,
                "declared_class": call.action_class.value,
                "authoritative_class": (
                    capability.action_class.value if capability else "high_impact"
                ),
                "egress": bool(capability and capability.egress),
                "requires_named_human": bool(
                    capability and capability.action_class.value == "high_impact"
                ),
            })
        payload = {
            "model": getattr(backend, "name", type(backend).__name__),
            "proposals": proposals,
            "note": "proposals only; the policy enforcement point decides what executes",
        }
        if context is not None:
            output = proposals_output(disclosure, caller, context.session_id, proposals)
            if disclosure.privacy_gate is not None:
                payload["proposals"] = json.loads(output.content)
            payload["disclosure"] = {
                "context_receipt": context.receipt_id,
                "output_id": output.output_id,
                "label": output.label.to_dict(),
                "note": "the proposal set carries the label of everything its session read; "
                        "release it only through /v1/disclosure/outputs/{id}/release",
            }
        return payload

    register_disclosure_routes(app, disclosure, Caller)

    # -- recovery ----------------------------------------------------------
    @app.post("/v1/recovery/reconcile", tags=["recovery"])
    def reconcile(caller: Caller):
        require(caller, "platform_operator")
        return {
            "reconciled": plane.reconcile(),
            "pending_outcomes": plane.pending_outcomes,
            "durability": plane.durability,
        }

    # Kept for compatibility with v0.5.0 clients and the existing smoke test.
    @app.post("/v1/reconcile", include_in_schema=False)
    def reconcile_legacy(caller: Caller):
        require(caller, "platform_operator")
        return {"reconciled": plane.reconcile()}

    return app


def create_default_app() -> FastAPI:
    return create_app()


__all__ = ["create_app", "create_default_app"]
