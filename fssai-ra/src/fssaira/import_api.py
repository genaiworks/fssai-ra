"""Low-side import API exposing inward transfer only."""
from __future__ import annotations

import json
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .diode import OneWayChannel
from .evidence import EvidenceLedger
from .import_boundary import ImportBoundary, QuarantineError, RawInput
from .kafka_backend import KafkaEventPublisher
from .metrics import Metrics


class ImportRequest(BaseModel):
    source: str = Field(min_length=1, max_length=200)
    content_type: str = Field(min_length=1, max_length=100)
    data: str = Field(max_length=2_000_000)
    signature: str = Field(min_length=64, max_length=128)


def create_import_app() -> FastAPI:
    bootstrap = os.environ["FSSAI_KAFKA_BOOTSTRAP"]
    topic = os.getenv("FSSAI_IMPORT_TOPIC", "fssaira.imports")
    keys = json.loads(os.environ["FSSAI_IMPORT_SOURCE_KEYS_JSON"])
    token = os.getenv("FSSAI_EVIDENCE_TOKEN", "teaching-evidence-writer")
    publisher = KafkaEventPublisher(bootstrap, topic)
    diode = OneWayChannel()
    last_offset = {"value": None}

    def inward_handler(item: dict) -> None:
        last_offset["value"] = publisher.append(item, key=item["source"])

    diode.connect(inward_handler)
    boundary = ImportBoundary(
        diode,
        EvidenceLedger(token),
        token,
        Metrics(),
        trusted_keys=keys,
        allowed_types={"text/plain", "application/json"},
        max_size=int(os.getenv("FSSAI_IMPORT_MAX_BYTES", "2000000")),
    )
    app = FastAPI(
        title="FSSAI-RA Inward Import Gateway",
        version="0.5.0",
        description=(
            "Logical low-side gateway. It exposes no read-back endpoint. Replace its "
            "inward publisher with a certified data-diode receiver for physical assurance."
        ),
    )

    @app.exception_handler(QuarantineError)
    async def quarantine_handler(_request, exc: QuarantineError):
        return JSONResponse(status_code=422, content={"status": "quarantined", "reason": str(exc)})

    @app.get("/health")
    def health():
        return {"status": "ok", "direction": "inward-only-api"}

    @app.post("/v1/imports", status_code=202)
    def import_item(request: ImportRequest):
        boundary.ingest(RawInput(
            source=request.source,
            content_type=request.content_type,
            size=len(request.data.encode()),
            data=request.data,
            signature=request.signature,
        ))
        return {"status": "accepted", "broker_offset": last_offset["value"]}

    return app
