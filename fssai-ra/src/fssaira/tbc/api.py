"""Optional HTTP adapter for the TBC model boundary (install the api extra).

Each request owns a SQLite connection. Administrative authority is provisioned
on the service side; no HTTP endpoint grants, restores, or approves authority.
Deployment must isolate the service UID, database and network from model workers.
"""
from __future__ import annotations

from .runtime import TrustRuntime


def create_app(database, passport, *, clock=None, pack="education"):
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from starlette.concurrency import run_in_threadpool

    app = FastAPI(title="Trust by Construction mediation", docs_url=None, redoc_url=None)

    def invoke(token, raw):
        runtime = TrustRuntime(database, passport, authorities={}, clock=clock, pack=pack)
        try:
            return runtime.dispatch(token, raw)
        finally:
            runtime.close()

    # Explicit annotation avoids a local-import/forward-annotation resolution issue.
    async def dispatch(request):
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            return JSONResponse({"ok": False, "code": "DENIED"}, status_code=401)
        token = authorization.removeprefix("Bearer ")
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 16384:
                return JSONResponse({"ok": False, "code": "DENIED"}, status_code=413)
        try:
            text = raw.decode("utf-8")
            result = await run_in_threadpool(invoke, token, text)
        except (ValueError, OSError):
            return JSONResponse({"ok": False, "code": "DENIED"}, status_code=403)
        return JSONResponse(result, status_code=200 if result["ok"] else 403)

    dispatch.__annotations__["request"] = Request
    app.post("/v1/tbc/request")(dispatch)
    return app
