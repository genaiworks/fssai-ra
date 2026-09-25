#!/usr/bin/env python3
"""Run the same workload on the small-data and big-data stacks and measure both.

    python scripts/measure_tiers.py --workflows 10 --out audit/tier-footprint.json

For each tier the script builds the images (not timed), starts the stack as its
own throwaway Compose project, and then records:

* **start-up**: seconds from ``compose up`` until the control API is healthy;
* **workload**: ``--workflows`` complete actions through the HTTP API (register,
  propose, review, wait out the enforced deliberation floor, approve, execute),
  run concurrently with the same client as ``scripts/fault_drill.py``;
* **invariants**: every workflow completed, every resource moved exactly once,
  one ``action_outcome`` per workflow, and a valid evidence chain;
* **footprint**: running containers, resident memory after the workload, and the
  size of the images the stack runs.

The small tier additionally runs its evidence worker's full pass (archive plus
independent verification) and records the verdict. The big tier's evidence
plane (Kafka, MinIO, Iceberg REST, Spark) is started, so its cost is measured,
but its Spark archive job is not driven here.

Both projects are removed with their volumes afterwards. The projects are named
``fssaira-tier-small`` and ``fssaira-tier-big`` and use their own host ports, so
an existing ``fssaira`` stack is untouched. One host, one run: the figures show
relative cost on this machine, not capacity.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fault_drill import Api, tokens_from, workflow  # noqa: E402
from smoke_stack import enforced_deliberation_floor, load_env  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

TIERS = {
    "small": {
        "project": "fssaira-tier-small",
        "files": ["deploy/compose.small.yaml"],
        "profiles": [],
        "services": ["control-api", "import-gateway", "evidence-worker"],
        "api_port": 18180, "gateway_port": 18181,
    },
    "big": {
        "project": "fssaira-tier-big",
        "files": ["deploy/compose.yaml"],
        "profiles": ["analytics"],
        "services": ["postgres", "redis", "kafka", "kafka-topics", "control-api", "import-gateway",
                     "minio", "minio-init", "iceberg-rest", "iceberg-bootstrap", "spark-iceberg"],
        "api_port": 18280, "gateway_port": 18281,
    },
}


def compose(tier: dict, env_file: Path, *args: str, check: bool = True,
            env: dict | None = None) -> subprocess.CompletedProcess:
    command = ["docker", "compose", "-p", tier["project"], "--env-file", str(env_file)]
    for file in tier["files"]:
        command += ["-f", file]
    for profile in tier["profiles"]:
        command += ["--profile", profile]
    result = subprocess.run(command + list(args), cwd=ROOT, capture_output=True, text=True,
                            env=env)
    if check and result.returncode:
        raise RuntimeError(f"{' '.join(args[:2])} failed for {tier['project']}: "
                           f"{result.stderr.strip()[-600:]}")
    return result


def docker(*args: str, check: bool = True) -> str:
    return subprocess.run(["docker", *args], check=check, capture_output=True, text=True).stdout


def wait_for(url_check, timeout: float = 300.0) -> float:
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        if url_check():
            return time.monotonic() - started
        time.sleep(1)
    raise RuntimeError("the control API did not become healthy")


def memory_mib(text: str) -> float:
    """Parse the used half of ``docker stats`` MemUsage, e.g. ``512.3MiB / 7.6GiB``."""
    used = text.split("/")[0].strip()
    units = {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "kB": 1 / 1024, "MB": 1, "GB": 1024, "B": 1 / 2**20}
    for unit in sorted(units, key=len, reverse=True):
        if used.endswith(unit):
            return float(used[: -len(unit)]) * units[unit]
    return 0.0


def footprint(project: str) -> dict:
    ids = docker("ps", "-q", "--filter", f"label=com.docker.compose.project={project}").split()
    stats = {}
    if ids:
        for line in docker("stats", "--no-stream", "--format",
                           "{{.Name}}\t{{.MemUsage}}", *ids).splitlines():
            name, usage = line.split("\t")
            stats[name] = round(memory_mib(usage), 1)
    images = set()
    for container in ids:
        images.add(docker("inspect", "-f", "{{.Image}}", container).strip())
    image_mib = sum(int(docker("image", "inspect", "-f", "{{.Size}}", image).strip())
                    for image in images) / 2**20
    return {
        "running_containers": len(ids),
        "memory_mib_total": round(sum(stats.values()), 1),
        "memory_mib_by_container": dict(sorted(stats.items())),
        "distinct_images": len(images),
        "image_mib_total": round(image_mib, 1),
    }


def run_workload(api: Api, count: int, floor: float) -> dict:
    run = uuid.uuid4().hex[:6]
    timings, errors = [], []
    threads = [threading.Thread(target=workflow, args=(api, run, i, timings, errors, floor))
               for i in range(count)]
    started = time.monotonic()
    for thread in threads:
        thread.start()
        time.sleep(0.05)
    for thread in threads:
        thread.join(600)
    seconds = time.monotonic() - started

    moved_once = True
    for i in range(count):
        status, body = api.call("GET", f"/v1/resources/drill-{run}-{i}", role="operator")
        moved_once &= status == 200 and (body.get("status"), body.get("version")) == (
            "ready_for_officer_review", 2)
    outcomes, offset = [], 0
    while True:
        page = api.call("GET", f"/v1/evidence?kind=action_outcome&limit=1000&offset={offset}",
                        role="operator")[1]
        outcomes += page["records"]
        offset += len(page["records"])
        if not page["records"] or offset >= page["total"]:
            break
    mine = {r["payload"]["request_id"] for r in outcomes
            if str(r["payload"].get("request_id", "")).startswith(f"drill-req-{run}-")}
    chain = api.call("GET", "/v1/evidence/verify", role="operator")[1]
    return {
        "workflows": count,
        "deliberation_floor_seconds": floor,
        "wall_seconds": round(seconds, 1),
        "latency_seconds_p50": round(statistics.median(timings), 2) if timings else None,
        "latency_overhead_p50_seconds": (round(statistics.median(timings) - floor, 2)
                                         if timings else None),
        "errors": errors[:5],
        "ledger_records": chain.get("records"),
        "invariants": {
            "every_workflow_completed": len(timings) == count,
            "every_resource_moved_exactly_once": moved_once,
            "one_outcome_per_workflow": len(mine) == count,
            "evidence_chain_valid": chain.get("chain_valid") is True,
        },
    }


def small_evidence_pass(tier: dict) -> dict:
    """Run the small tier's evidence worker once, synchronously, and parse its verdict."""
    container = f"{tier['project']}-evidence-worker-1"
    out = subprocess.run(
        ["docker", "exec", container, "fssaira", "small", "run",
         "--archive", "/var/lib/fssaira/archive/evidence-archive.sqlite3",
         "--log", "/var/lib/fssaira/low-side/import-log.sqlite3",
         "--database", "sqlite:////var/lib/fssaira/control/control.sqlite3",
         "--output", "/tmp/run.json"], capture_output=True, text=True)
    report = json.loads(docker("exec", container, "cat", "/tmp/run.json"))
    verify = report["verify"]
    return {"exit_code": out.returncode, "verdict": verify["verdict"],
            "archived_records": verify["records"]}


def measure(name: str, env_file: Path, count: int, keep: bool) -> dict:
    tier = TIERS[name]
    values = load_env(env_file)
    env = {**os.environ, "FSSAI_API_PORT": str(tier["api_port"]),
           "FSSAI_GATEWAY_PORT": str(tier["gateway_port"]), "FSSAI_MODEL": "deterministic",
           "FSSAI_SMALL_INTERVAL_SECONDS": "3600"}
    compose(tier, env_file, "down", "-v", check=False, env=env)
    # Pull and build everything first, so start-up time excludes downloads and builds.
    compose(tier, env_file, "pull", "--ignore-buildable", "--ignore-pull-failures", "--quiet", *tier["services"], env=env)
    compose(tier, env_file, "build", *tier["services"], env=env)
    api = Api(f"http://127.0.0.1:{tier['api_port']}", tokens_from(values), None)

    def healthy() -> bool:
        try:
            return api.call("GET", "/health", retries=1)[0] == 200
        except RuntimeError:
            return False

    result: dict = {"tier": name, "project": tier["project"], "services": tier["services"]}
    try:
        started = time.monotonic()
        compose(tier, env_file, "up", "-d", *tier["services"], env=env)
        result["startup_seconds_until_api_healthy"] = round(
            (time.monotonic() - started) + wait_for(healthy), 1)
        floor = enforced_deliberation_floor(api.call("GET", "/health")[1])
        result["workload"] = run_workload(api, count, floor)
        if name == "small":
            result["evidence_plane"] = small_evidence_pass(tier)
        time.sleep(10)  # let background work settle before sampling memory
        result["footprint"] = footprint(tier["project"])
    finally:
        if not keep:
            compose(tier, env_file, "down", "-v", check=False, env=env)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", type=Path, default=Path("deploy/.env"))
    parser.add_argument("--workflows", type=int, default=10)
    parser.add_argument("--tier", choices=[*TIERS, "both"], default="both")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--keep", action="store_true", help="leave the stacks running")
    args = parser.parse_args()

    names = list(TIERS) if args.tier == "both" else [args.tier]
    report = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": {"system": platform.system(), "machine": platform.machine(),
                 "cpus": os.cpu_count(),
                 "docker": docker("version", "-f", "{{.Server.Version}}").strip()},
        "tiers": {name: measure(name, args.env_file, args.workflows, args.keep)
                  for name in names},
        "scope": "one host, one run; relative cost on this machine, not capacity",
    }
    if {"small", "big"} <= report["tiers"].keys():
        small, big = report["tiers"]["small"], report["tiers"]["big"]
        report["comparison"] = {
            "containers": [small["footprint"]["running_containers"],
                           big["footprint"]["running_containers"]],
            "memory_ratio_big_over_small": round(
                big["footprint"]["memory_mib_total"] / small["footprint"]["memory_mib_total"], 1),
            "image_ratio_big_over_small": round(
                big["footprint"]["image_mib_total"] / small["footprint"]["image_mib_total"], 1),
            "same_invariants_hold": small["workload"]["invariants"] == big["workload"]["invariants"]
            and all(small["workload"]["invariants"].values()),
        }
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    passed = all(all(t["workload"]["invariants"].values()) for t in report["tiers"].values())
    passed &= report["tiers"].get("small", {}).get("evidence_plane", {}).get(
        "verdict", "INTACT") == "INTACT"
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
