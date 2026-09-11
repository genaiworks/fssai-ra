"""FastAPI control plane for application-neutral accountable actions."""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .control_plane import ControlPlane
from .exact_action import ExecutionDenied, ExecutionUncertain
from .runtime_factory import build_control_plane, production_configuration_warnings


class Identity(BaseModel):
    subject: str
    role: str


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


def request_identity(
    subject: Annotated[str, Header(alias="X-FSSAI-Identity")],
    role: Annotated[str, Header(alias="X-FSSAI-Role")],
) -> Identity:
    # This header adapter is for the reference deployment. Put an authenticated
    # reverse proxy/OIDC verifier in front of it before relying on these claims.
    return Identity(subject=subject, role=role)


def create_app(runtime: ControlPlane | None = None) -> FastAPI:
    plane = build_control_plane() if runtime is None else runtime

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.control_plane = plane
        yield

    app = FastAPI(
        title="FSSAI-RA Control Plane",
        version="0.5.0",
        description=(
            "Reference API for exact-action proposals, human approval, execution, "
            "evidence, and recovery. Header identity is a replaceable teaching adapter."
        ),
        lifespan=lifespan,
    )

    @app.exception_handler(ExecutionDenied)
    async def denied_handler(_request, exc: ExecutionDenied):
        return JSONResponse(status_code=409, content={"error": exc.code, "detail": str(exc)})

    @app.exception_handler(ExecutionUncertain)
    async def uncertain_handler(_request, exc: ExecutionUncertain):
        return JSONResponse(
            status_code=202,
            content={"error": exc.code, "detail": str(exc), "result": asdict(exc.result)},
        )

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "profile": plane.profile.profile_id,
            "evidence_valid": plane.evidence.verify(),
            "configuration_warnings": production_configuration_warnings(),
        }

    @app.get("/v1/profile")
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

    @app.post("/v1/resources", status_code=201)
    def register_resource(
        request: ResourceCreate,
        identity: Annotated[Identity, Depends(request_identity)],
    ):
        if identity.role != "platform_operator":
            raise HTTPException(status_code=403, detail="platform_operator role required")
        return plane.register_resource(**request.model_dump())

    @app.get("/v1/resources/{resource_id}")
    def get_resource(resource_id: str, _identity: Annotated[Identity, Depends(request_identity)]):
        try:
            return {"resource_id": resource_id, **plane.register.get(resource_id)}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="resource not found") from exc

    @app.post("/v1/proposals", status_code=201)
    def create_proposal(
        request: ProposalCreate,
        identity: Annotated[Identity, Depends(request_identity)],
    ):
        try:
            return asdict(plane.propose(requester=identity.subject, **request.model_dump()))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="resource not found") from exc

    @app.post("/v1/proposals/{request_id}/approval", status_code=201)
    def approve_proposal(
        request_id: str,
        request: ApprovalCreate,
        identity: Annotated[Identity, Depends(request_identity)],
    ):
        return asdict(plane.approve(
            request_id,
            approver=identity.subject,
            approver_role=identity.role,
            ttl_seconds=request.ttl_seconds,
        ))

    @app.post("/v1/proposals/{request_id}/execute")
    def execute_proposal(
        request_id: str,
        _identity: Annotated[Identity, Depends(request_identity)],
    ):
        return asdict(plane.execute(request_id))

    @app.get("/v1/proposals/{request_id}/evidence")
    def get_evidence(
        request_id: str,
        _identity: Annotated[Identity, Depends(request_identity)],
    ):
        return {"request_id": request_id, "records": plane.evidence_for(request_id)}

    @app.post("/v1/reconcile")
    def reconcile(identity: Annotated[Identity, Depends(request_identity)]):
        if identity.role != "platform_operator":
            raise HTTPException(status_code=403, detail="platform_operator role required")
        return {"reconciled": plane.reconcile()}

    return app


def create_default_app() -> FastAPI:
    return create_app()
