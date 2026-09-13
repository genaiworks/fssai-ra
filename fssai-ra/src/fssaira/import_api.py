"""Low-side import API exposing inward transfer only."""
from __future__ import annotations

import json
import os
import threading
from typing import Protocol

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import __version__
from .atomic_execution import sql_evidence
from .diode import OneWayChannel
from .evidence import EvidenceLedger
from .import_boundary import ImportBoundary, QuarantineError, RawInput
from .kafka_backend import KafkaEventPublisher
from .metrics import Metrics
from .sql_backend import open_sqlite


class ImportRequest(BaseModel):
    source: str = Field(min_length=1, max_length=200)
    content_type: str = Field(min_length=1, max_length=100)
    data: str = Field(max_length=2_000_000)
    signature: str = Field(min_length=64, max_length=128)


class InwardPublisher(Protocol):
    def append(self, value: dict, key: str = "", trace_id: str = "") -> int: ...


def create_import_app(
    *, publisher: InwardPublisher | None = None, trusted_keys: dict[str, str] | None = None
) -> FastAPI:
    """Build the low-side gateway.

    Injection points make the boundary independently testable. The production
    factory still constructs its Kafka publisher and keys from the environment.
    """
    topic = os.getenv("FSSAI_IMPORT_TOPIC", "fssaira.imports")
    if publisher is None:
        bootstrap = os.environ["FSSAI_KAFKA_BOOTSTRAP"]
        publisher = KafkaEventPublisher(bootstrap, topic)
    keys = trusted_keys
    if keys is None:
        try:
            keys = json.loads(os.environ["FSSAI_IMPORT_SOURCE_KEYS_JSON"])
        except (KeyError, json.JSONDecodeError) as exc:
            raise ValueError(
                "FSSAI_IMPORT_SOURCE_KEYS_JSON must be a JSON object of source-to-key mappings"
            ) from exc
    if (
        not isinstance(keys, dict)
        or not all(isinstance(source, str) and source and isinstance(key, str) and key
                   for source, key in keys.items())
    ):
        raise ValueError("trusted import keys must map non-empty source names to non-empty keys")
    try:
        max_size = int(os.getenv("FSSAI_IMPORT_MAX_BYTES", "2000000"))
    except ValueError as exc:
        raise ValueError("FSSAI_IMPORT_MAX_BYTES must be a positive integer") from exc
    if max_size < 1:
        raise ValueError("FSSAI_IMPORT_MAX_BYTES must be a positive integer")
    token = os.getenv("FSSAI_EVIDENCE_TOKEN", "teaching-evidence-writer")
    audit_path = os.getenv("FSSAI_IMPORT_AUDIT_PATH", "").strip()
    audit_database = open_sqlite(audit_path, evidence_token=token) if audit_path else None
    evidence = sql_evidence(audit_database) if audit_database is not None else EvidenceLedger(token)
    diode = OneWayChannel()
    last_offset = {"value": None}
    # The boundary report and response offset live on shared objects. Serialise
    # ingest plus response capture so concurrent callers cannot receive each
    # other's broker acknowledgement.
    ingest_lock = threading.RLock()

    def inward_handler(item: dict) -> None:
        last_offset["value"] = publisher.append(item, key=item["source"])

    diode.connect(inward_handler)
    boundary = ImportBoundary(
        diode,
        evidence,
        token,
        Metrics(),
        trusted_keys=keys,
        allowed_types={"text/plain", "application/json"},
        max_size=max_size,
    )
    app = FastAPI(
        title="FSSAI-RA Inward Import Gateway",
        version=__version__,
        description=(
            "Logical low-side gateway. It exposes no read-back endpoint. Replace its "
            "inward publisher with a certified data-diode receiver for physical assurance."
        ),
    )
    # Expose the boundary and database for deployment diagnostics and focused
    # integration tests; neither is reachable through an HTTP read-back route.
    app.state.import_boundary = boundary
    app.state.audit_database = audit_database
    app.state.audit_evidence = evidence

    if audit_database is not None:
        @app.on_event("shutdown")
        def close_audit_database() -> None:
            audit_database.close()

    @app.middleware("http")
    async def protect_gateway_responses(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        if request.url.path.startswith("/v1/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(QuarantineError)
    async def quarantine_handler(_request, exc: QuarantineError):
        return JSONResponse(status_code=422, content={"status": "quarantined", "reason": str(exc)})

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "direction": "inward-only-api",
            "audit_durable": audit_database is not None,
        }

    @app.post("/v1/imports", status_code=202)
    def import_item(request: ImportRequest):
        with ingest_lock:
            boundary.ingest(RawInput(
                source=request.source,
                content_type=request.content_type,
                size=len(request.data.encode()),
                data=request.data,
                signature=request.signature,
            ))
            return {"status": "accepted", "broker_offset": last_offset["value"]}

    return app
