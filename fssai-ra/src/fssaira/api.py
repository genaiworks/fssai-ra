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
``/v1/verification``, ``/v1/conformance``   machine-checked assurance on demand
``/v1/recovery``                            reconciliation, for the named owner

Authentication is real (see :mod:`fssaira.security`) and authorization stays in
the executor. The API never decides whether an approval is valid; it carries the
request to the component that does.
"""
from __future__ import annotations

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


class ProposeTask(BaseModel):
    """Ask the configured model for tool-call proposals. Nothing executes."""

    task: str = Field(min_length=1, max_length=2000)
    evidence: list[str] = Field(default_factory=list, max_length=20)


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


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def create_app(
    runtime: ControlPlane | None = None,
    *,
    authenticator: Authenticator | None = None,
) -> FastAPI:
    plane = build_control_plane() if runtime is None else runtime
    auth = authenticator or Authenticator()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.control_plane = plane
        app.state.authenticator = auth
        yield

    app = FastAPI(
        title="FSSAI-RA Control Plane",
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

    # -- error translation -------------------------------------------------
    @app.exception_handler(ExecutionDenied)
    async def denied_handler(_request: Request, exc: ExecutionDenied):
        return JSONResponse(status_code=409, content={"error": exc.code, "detail": str(exc)})

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
        }

    @app.get("/v1/contract", tags=["governance"])
    def get_contract(directory: str = Query(default="contract")):
        """The seven-field control contract, as machine-readable YAML."""
        from .contract import ControlContract

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

    @app.post("/v1/proposals/{request_id}/approval", status_code=201, tags=["actions"])
    def approve_proposal(request_id: str, request: ApprovalCreate, caller: Caller):
        # The approver's role comes from the authenticated principal, never from
        # the request body. A caller may not nominate the authority it is using.
        return asdict(plane.approve(
            request_id,
            approver=caller.subject,
            approver_role=caller.role,
            ttl_seconds=request.ttl_seconds,
        ))

    @app.post("/v1/proposals/{request_id}/execute", tags=["actions"])
    def execute_proposal(request_id: str, caller: Caller):
        return asdict(plane.execute(request_id))

    @app.get("/v1/proposals/{request_id}/evidence", tags=["evidence"])
    def get_proposal_evidence(request_id: str, caller: Caller):
        return {"request_id": request_id, "records": plane.evidence_for(request_id)}

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
        from .verification import verify_profile

        return verify_profile(plane.profile).to_dict()

    @app.get("/v1/conformance", tags=["assurance"])
    def run_conformance_check(caller: Caller):
        """Behavioural conformance of the *configured* backends, not the reference ones."""
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
        try:
            calls = backend.propose(request.task, evidence)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"model backend failed: {exc}") from exc
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
        return {
            "model": getattr(backend, "name", type(backend).__name__),
            "proposals": proposals,
            "note": "proposals only; the policy enforcement point decides what executes",
        }

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
