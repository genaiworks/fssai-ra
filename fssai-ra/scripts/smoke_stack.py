#!/usr/bin/env python3
"""Exercise the running Compose stack without third-party HTTP dependencies."""
from __future__ import annotations

import argparse
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


#: TLS context for https endpoints (``--ca-file``); None uses the system trust store.
TLS_CONTEXT = None


def request(
    method: str, url: str, body: dict | None = None, *, token: str | None = None,
):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    encoded = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=encoded, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10, context=TLS_CONTEXT) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / 'deploy/.env')
    parser.add_argument('--api-url', default='http://127.0.0.1:8080')
    parser.add_argument('--gateway-url', default='http://127.0.0.1:8081')
    parser.add_argument('--ca-file', type=Path,
                        help='CA that signed the API and gateway certificates (TLS overlay)')
    args = parser.parse_args()
    if args.ca_file:
        import ssl

        global TLS_CONTEXT
        TLS_CONTEXT = ssl.create_default_context(cafile=str(args.ca_file))
    env = load_env(args.env_file)
    identities = json.loads(env["FSSAI_AUTH_TOKENS_JSON"])

    def token_for(role: str) -> str:
        try:
            return next(
                token for token, identity in identities.items()
                if role in identity.get("roles", [])
            )
        except StopIteration as exc:
            raise RuntimeError(f"deploy/.env has no token for required role {role!r}") from exc

    operator = token_for("platform_operator")
    officer = token_for("student_support_officer")
    agent = token_for("proposer")
    base = args.api_url.rstrip('/')
    suffix = uuid.uuid4().hex[:12]
    resource_id = f"smoke-resource-{suffix}"
    request_id = f"smoke-request-{suffix}"

    status, health = request("GET", f"{base}/health")
    assert status == 200 and health["status"] == "ok"

    status, _ = request("POST", f"{base}/v1/resources", {
        "resource_id": resource_id, "status": "draft", "version": 1,
    }, token=operator)
    assert status == 201
    status, _ = request("POST", f"{base}/v1/proposals", {
        "request_id": request_id,
        "operation": "prepare_case_for_review",
        "resource_id": resource_id,
        "from_status": "draft",
        "to_status": "ready_for_officer_review",
        "evidence_version": "smoke-snapshot-v1",
    }, token=agent)
    assert status == 201
    status, _ = request(
        "POST", f"{base}/v1/proposals/{request_id}/review", {}, token=officer,
    )
    assert status == 201
    status, _ = request(
        "POST", f"{base}/v1/proposals/{request_id}/approval", {"ttl_seconds": 300},
        token=officer,
    )
    assert status == 201
    status, first = request(
        "POST", f"{base}/v1/proposals/{request_id}/execute", {}, token=operator,
    )
    assert status == 200 and first["status"] == "ready_for_officer_review"
    status, replay = request(
        "POST", f"{base}/v1/proposals/{request_id}/execute", {}, token=operator,
    )
    assert status == 200 and replay["replayed"] is True
    assert replay["receipt_hash"] == first["receipt_hash"]
    status, evidence = request(
        "GET", f"{base}/v1/proposals/{request_id}/evidence", token=operator,
    )
    assert status == 200 and len(evidence["records"]) == 2

    source_keys = json.loads(env["FSSAI_IMPORT_SOURCE_KEYS_JSON"])
    source, key = next(iter(source_keys.items()))
    data = "Smoke-tested low-side observation."
    signature = hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()
    status, imported = request("POST", f"{args.gateway_url.rstrip('/')}/v1/imports", {
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
