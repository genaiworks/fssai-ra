#!/usr/bin/env python3
"""Fault-injection, load and backup/restore drill against a running Compose stack.

    python scripts/fault_drill.py --project fssaira-tls --env-file deploy/.env \\
        --api-url https://127.0.0.1:18080 --ca-file deploy/certs/ca.crt --workflows 40

What it does, in order:

1. Runs ``--workflows`` complete actions concurrently through the HTTP API
   (register, propose, review, approve, execute). Clients retry a step with the
   same request ID after a network error or 5xx, as a careful client should.
2. While that load runs, restarts PostgreSQL, then stops Kafka and starts it again.
3. Checks the invariants that matter: every resource moved exactly once
   (version 2, never 3), exactly one ``action_outcome`` per workflow, a valid
   evidence chain, and an event backlog that drains to zero after reconcile.
4. Dumps the ``fssaira`` schema with ``pg_dump``, restores it into a fresh
   PostgreSQL container, and checks the restored chain head and receipts match.

It prints a JSON report and exits non-zero when any invariant fails. It is a drill
for one topology on one host: it does not qualify multi-node failover, network
partitions or sustained production load.
"""
from __future__ import annotations

import argparse
import json
import ssl
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smoke_stack import enforced_deliberation_floor, load_env  # noqa: E402


class Api:
    def __init__(self, base: str, tokens: dict[str, str], ca_file: Path | None) -> None:
        self.base = base.rstrip("/")
        self.tokens = tokens
        self.context = ssl.create_default_context(cafile=str(ca_file)) if ca_file else None
        #: 5xx responses seen and retried; reported so outages stay visible.
        self.server_errors: list[int] = []

    def call(self, method, path, body=None, role=None, retries=40):
        """Retry transport errors and 5xx with the same payload; return (status, json)."""
        last = None
        for attempt in range(retries):
            headers = {"Content-Type": "application/json"}
            if role:
                headers["Authorization"] = "Bearer " + self.tokens[role]
            request = urllib.request.Request(
                self.base + path, method=method, headers=headers,
                data=None if body is None else json.dumps(body).encode())
            try:
                with urllib.request.urlopen(request, timeout=20, context=self.context) as r:
                    return r.status, json.load(r)
            except urllib.error.HTTPError as exc:
                raw = exc.read() or b"{}"
                try:
                    payload = json.loads(raw)
                except ValueError:  # a proxy or server error page, not the API's JSON
                    payload = {"raw": raw[:200].decode("utf-8", "replace")}
                if exc.code < 500:
                    return exc.code, payload
                last = f"{exc.code} {payload}"
                self.server_errors.append(exc.code)
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
                last = repr(exc)
            time.sleep(min(0.25 * (attempt + 1), 3.0))
        raise RuntimeError(f"{method} {path} kept failing: {last}")


def workflow(api: Api, run: str, index: int, timings: list, errors: list,
             floor: float = 0.0) -> None:
    resource, request_id = f"drill-{run}-{index}", f"drill-req-{run}-{index}"
    started = time.monotonic()
    try:
        status, body = api.call("POST", "/v1/resources",
                                {"resource_id": resource, "status": "draft", "version": 1},
                                role="operator")
        if status not in (201, 409):
            raise RuntimeError(f"register {status} {body}")
        status, body = api.call("POST", "/v1/proposals", {
            "request_id": request_id, "operation": "prepare_case_for_review",
            "resource_id": resource, "from_status": "draft",
            "to_status": "ready_for_officer_review", "evidence_version": "drill-v1"},
            role="agent")
        if status not in (200, 201):
            raise RuntimeError(f"propose {status} {body}")
        path = f"/v1/proposals/{request_id}"
        api.call("POST", path + "/review", role="officer")
        if api.tokens.get("second"):
            api.call("POST", path + "/review", role="second")
        time.sleep(floor + 0.5 if floor else 0)  # the server's deliberation floor
        if api.tokens.get("second"):
            api.call("POST", path + "/endorsement", role="second")
        status, body = api.call("POST", path + "/approval", {"ttl_seconds": 600}, role="officer")
        if status != 201:
            raise RuntimeError(f"approve {status} {body}")
        status, body = api.call("POST", path + "/execute", role="operator")
        if status != 200:
            raise RuntimeError(f"execute {status} {body}")
        timings.append(time.monotonic() - started)
    except Exception as exc:  # reported in the drill output
        errors.append(f"{resource}: {exc}")


def docker(*args, check=True) -> str:
    return subprocess.run(["docker", *args], check=check, capture_output=True, text=True).stdout


def wait_healthy(container: str, timeout: float = 180.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = docker("inspect", "-f", "{{.State.Health.Status}}", container, check=False).strip()
        if state == "healthy":
            return
        time.sleep(2)
    raise RuntimeError(f"{container} did not become healthy")


def tokens_from(env: dict) -> dict[str, str]:
    identities = json.loads(env["FSSAI_AUTH_TOKENS_JSON"])

    def first(role, exclude=None):
        return next((t for t, v in identities.items()
                     if role in v.get("roles", []) and t != exclude), None)

    officer = first("student_support_officer")
    return {"operator": first("platform_operator"), "agent": first("proposer"),
            "officer": officer, "second": first("student_support_officer", officer)}


def backup_and_restore(project: str, env: dict) -> dict:
    """pg_dump the live schema, restore into a fresh server, compare what matters."""
    source = f"{project}-postgres-1"
    user, db = env["POSTGRES_USER"], env["POSTGRES_DB"]
    dump = docker("exec", source, "pg_dump", "-U", user, "-d", db, "--schema=fssaira",
                  "--no-owner", "--no-privileges")
    target = f"{project}-restore-drill"
    docker("rm", "-f", target, check=False)
    docker("run", "-d", "--name", target, "-e", "POSTGRES_PASSWORD=drill-only",
           "-e", "POSTGRES_DB=restore", "postgres:17.6-alpine")
    try:
        for _ in range(60):
            if subprocess.run(["docker", "exec", target, "pg_isready", "-U", "postgres",
                               "-d", "restore"], capture_output=True).returncode == 0:
                break
            time.sleep(1)
        time.sleep(2)
        subprocess.run(["docker", "exec", "-i", target, "psql", "-q", "-v", "ON_ERROR_STOP=1",
                        "-U", "postgres", "-d", "restore"], input=dump, text=True, check=True,
                       capture_output=True)

        def query(container, sql, u, d):
            return docker("exec", container, "psql", "-At", "-U", u, "-d", d, "-c", sql).strip()

        checks = {
            "evidence_head": "SELECT seq || ':' || hash FROM fssaira.evidence ORDER BY seq DESC LIMIT 1",
            "evidence_count": "SELECT COUNT(*) FROM fssaira.evidence",
            "receipts": "SELECT md5(string_agg(request_id || receipt_hash, ',' ORDER BY request_id)) "
                        "FROM fssaira.execution_results",
            "resources": "SELECT md5(string_agg(resource_id || status || version, ',' "
                         "ORDER BY resource_id)) FROM fssaira.resources",
        }
        result = {}
        for name, sql in checks.items():
            live = query(source, sql, user, db)
            restored = query(target, sql, "postgres", "restore")
            result[name] = {"live": live, "restored": restored, "match": live == restored}
        return result
    finally:
        docker("rm", "-f", target, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True, help="Compose project name")
    parser.add_argument("--env-file", type=Path, default=Path("deploy/.env"))
    parser.add_argument("--api-url", default="http://127.0.0.1:8080")
    parser.add_argument("--ca-file", type=Path)
    parser.add_argument("--workflows", type=int, default=40)
    args = parser.parse_args()

    env = load_env(args.env_file)
    api = Api(args.api_url, tokens_from(env), args.ca_file)
    operator_token = api.tokens["operator"]
    run = uuid.uuid4().hex[:6]
    timings, errors = [], []
    health = api.call("GET", "/health")[1]
    floor = enforced_deliberation_floor(health)
    capacity = ((health.get("declared_controls") or {}).get("review_capacity") or {})
    quota = capacity.get("max_approvals_per_window")
    if quota and args.workflows > quota:
        parser.error(f"--workflows {args.workflows} exceeds the enforced review quota of {quota} "
                     "approvals per reviewer per window; the server would rightly refuse the rest. "
                     "Declare a larger capacity (FSSAI_REVIEW_MAX_PER_WINDOW) for a load test.")
    threads = [threading.Thread(target=workflow, args=(api, run, i, timings, errors, floor))
               for i in range(args.workflows)]
    report = {"project": args.project, "workflows": args.workflows, "faults": []}
    started = time.monotonic()
    for index, thread in enumerate(threads):
        thread.start()
        if index == args.workflows // 3:
            docker("restart", f"{args.project}-postgres-1")
            report["faults"].append("postgres restarted")
        if index == (2 * args.workflows) // 3:
            docker("stop", f"{args.project}-kafka-1")
            report["faults"].append("kafka stopped")
        time.sleep(0.05)
    for thread in threads:
        thread.join(600)
    report["seconds"] = round(time.monotonic() - started, 1)
    backlog_during_outage = api.call("GET", "/health")[1].get("unpublished_events")
    docker("start", f"{args.project}-kafka-1")
    report["faults"].append("kafka started")
    wait_healthy(f"{args.project}-kafka-1")
    wait_healthy(f"{args.project}-postgres-1")

    versions = {}
    for i in range(args.workflows):
        status, body = api.call("GET", f"/v1/resources/drill-{run}-{i}", role="operator")
        versions[i] = (body.get("status"), body.get("version")) if status == 200 else (status, None)
    moved_once = all(v == ("ready_for_officer_review", 2) for v in versions.values())
    outcomes, offset = [], 0
    while True:  # page through everything; the API returns oldest first
        page = api.call("GET", f"/v1/evidence?kind=action_outcome&limit=1000&offset={offset}",
                        role="operator")[1]
        outcomes += page["records"]
        offset += len(page["records"])
        if not page["records"] or offset >= page["total"]:
            break
    mine = [r for r in outcomes if str(r["payload"].get("request_id", "")).startswith(
        f"drill-req-{run}-")]
    chain = api.call("GET", "/v1/evidence/verify", role="operator")[1]
    api.tokens["operator"] = operator_token
    reconcile = api.call("POST", "/v1/recovery/reconcile", role="operator")[1]

    report.update({
        "errors": errors[:10],
        "error_count": len(errors),
        "server_errors_retried": len(api.server_errors),
        "latency_seconds": {
            "p50": round(statistics.median(timings), 3) if timings else None,
            "p95": round(sorted(timings)[int(0.95 * (len(timings) - 1))], 3) if timings else None,
            "max": round(max(timings), 3) if timings else None,
        },
        "invariants": {
            "every_workflow_completed": len(timings) == args.workflows,
            "every_resource_moved_exactly_once": moved_once,
            "one_outcome_per_workflow": len(mine) == args.workflows
            and len({r["payload"]["request_id"] for r in mine}) == args.workflows,
            "evidence_chain_valid": chain.get("chain_valid") is True,
            "backlog_seen_during_kafka_outage": (backlog_during_outage or 0) > 0,
            "backlog_drained_after_reconcile": reconcile.get("unpublished_events") == 0,
        },
        "reconcile": reconcile,
        "backup_restore": backup_and_restore(args.project, env),
    })
    report["invariants"]["backup_restore_matches"] = all(
        item["match"] for item in report["backup_restore"].values())
    print(json.dumps(report, indent=2))
    return 0 if all(report["invariants"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
