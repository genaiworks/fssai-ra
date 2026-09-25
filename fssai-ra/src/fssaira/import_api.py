"""Low-side import API exposing inward transfer only."""
from __future__ import annotations

import hashlib
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
    #: Optional stable ID chosen by the sender. Send the same ID when retrying:
    #: the gateway then returns the original acceptance instead of publishing
    #: the document again. The signature must cover it (``sign_envelope``).
    ingest_id: str | None = Field(default=None, min_length=1, max_length=128,
                                  pattern=r"^[A-Za-z0-9._:-]+$")


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
        from .envelope_mac import key_from_env

        # The sink rejects imports without this MAC, so a record written to the
        # log by anything other than this gateway never reaches the table.
        mac_key = key_from_env("FSSAI_IMPORT_ENVELOPE_KEY")
        bootstrap = os.getenv("FSSAI_KAFKA_BOOTSTRAP", "").strip()
        log_path = os.getenv("FSSAI_IMPORT_LOG_PATH", "").strip()
        if bootstrap:
            publisher = KafkaEventPublisher(bootstrap, topic, mac_key=mac_key)
        elif log_path:
            # Small-data tier: a durable SQLite log, drained by `fssaira small ingest`.
            from .small_data import SqliteImportLog

            publisher = SqliteImportLog(log_path, mac_key=mac_key, topic=topic)
        else:
            raise ValueError(
                "no inward log configured: set FSSAI_KAFKA_BOOTSTRAP (big-data tier) or "
                "FSSAI_IMPORT_LOG_PATH (small-data tier)")
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

    # Accepted ingest IDs. Kept in the audit database when one is configured, so
    # a retry after a gateway restart is still recognised.
    accepted_ids: dict[str, dict] = {}

    def id_key(source: str, ingest_id: str) -> str:
        return f"{source}\x1f{ingest_id}"

    def seen(source: str, ingest_id: str) -> dict | None:
        if audit_database is None:
            return accepted_ids.get(id_key(source, ingest_id))
        with audit_database.transaction() as unit:
            return unit.objects.get("ingest-id", id_key(source, ingest_id))

    def remember(source: str, ingest_id: str, value: dict) -> None:
        if audit_database is None:
            accepted_ids[id_key(source, ingest_id)] = value
            return
        with audit_database.transaction() as unit:
            unit.objects.put_if_absent("ingest-id", id_key(source, ingest_id), value)

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
            "inward_log": getattr(publisher, "name", type(publisher).__name__),
        }

    @app.post("/v1/imports", status_code=202)
    def import_item(request: ImportRequest):
        raw = RawInput(
            source=request.source,
            content_type=request.content_type,
            size=len(request.data.encode()),
            data=request.data,
            signature=request.signature,
            ingest_id=request.ingest_id,
        )
        with ingest_lock:
            # Authenticate before looking the ID up, so an unauthenticated caller
            # cannot probe which IDs exist. A rejected request goes through
            # ``ingest`` to be quarantined and recorded as usual.
            if raw.ingest_id is not None and boundary.rejection(raw) is None:
                fingerprint = hashlib.sha256(
                    f"{raw.content_type}\x1f{raw.data}".encode()).hexdigest()
                prior = seen(raw.source, raw.ingest_id)
                if prior is not None:
                    if prior["fingerprint"] != fingerprint:
                        return JSONResponse(status_code=409, content={
                            "status": "conflict", "ingest_id": raw.ingest_id,
                            "reason": "ingest_id was already used for different content",
                        })
                    return JSONResponse(status_code=200, content={
                        "status": "duplicate", "broker_offset": prior["broker_offset"],
                        "ingest_id": raw.ingest_id,
                    })
            boundary.ingest(raw)
            # Remember the ID only after the broker acknowledged, so a failed
            # publish leaves the sender free to retry.
            if raw.ingest_id is not None:
                remember(raw.source, raw.ingest_id,
                         {"fingerprint": fingerprint, "broker_offset": last_offset["value"]})
            return {"status": "accepted", "broker_offset": last_offset["value"]}

    return app
