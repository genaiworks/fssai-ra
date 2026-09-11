#!/usr/bin/env python3
"""Exercise the running Compose stack without third-party HTTP dependencies."""
from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def request(
    method: str, url: str, body: dict | None = None, *,
    role: str = "platform_operator", subject: str = "stack-smoke-test",
):
    headers = {
        "Content-Type": "application/json",
        "X-FSSAI-Identity": subject,
        "X-FSSAI-Role": role,
    }
    encoded = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=encoded, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def main() -> None:
    env = load_env(ROOT / "deploy" / ".env")
    base = "http://127.0.0.1:8080"
    suffix = uuid.uuid4().hex[:12]
    resource_id = f"smoke-resource-{suffix}"
    request_id = f"smoke-request-{suffix}"

    status, health = request("GET", f"{base}/health")
    assert status == 200 and health["status"] == "ok"

    status, _ = request("POST", f"{base}/v1/resources", {
        "resource_id": resource_id, "status": "draft", "version": 1,
    })
    assert status == 201
    status, _ = request("POST", f"{base}/v1/proposals", {
        "request_id": request_id,
        "operation": "prepare_case_for_review",
        "resource_id": resource_id,
        "from_status": "draft",
        "to_status": "ready_for_officer_review",
        "evidence_version": "smoke-snapshot-v1",
    }, role="agent")
    assert status == 201
    status, _ = request(
        "POST", f"{base}/v1/proposals/{request_id}/approval", {"ttl_seconds": 300},
        role="student_support_officer", subject="stack-smoke-reviewer",
    )
    assert status == 201
    status, first = request("POST", f"{base}/v1/proposals/{request_id}/execute", {})
    assert status == 200 and first["status"] == "ready_for_officer_review"
    status, replay = request("POST", f"{base}/v1/proposals/{request_id}/execute", {})
    assert status == 200 and replay["replayed"] is True
    assert replay["receipt_hash"] == first["receipt_hash"]
    status, evidence = request("GET", f"{base}/v1/proposals/{request_id}/evidence")
    assert status == 200 and len(evidence["records"]) == 2

    source_keys = json.loads(env["FSSAI_IMPORT_SOURCE_KEYS_JSON"])
    source, key = next(iter(source_keys.items()))
    data = "Smoke-tested low-side observation."
    signature = hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()
    status, imported = request("POST", "http://127.0.0.1:8081/v1/imports", {
        "source": source,
        "content_type": "text/plain",
        "data": data,
        "signature": signature,
    })
    assert status == 202 and imported["status"] == "accepted"

    print(json.dumps({
        "status": "passed",
        "profile": health["profile"],
        "resource_id": resource_id,
        "idempotent_replay": replay["replayed"],
        "evidence_records": len(evidence["records"]),
        "import_broker_offset": imported["broker_offset"],
    }, indent=2))


if __name__ == "__main__":
    main()
