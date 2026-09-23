"""Descriptive local microbenchmark plus a declared benign workload grid.

No external model or service. Run from security_systems:
python benchmarks/guard_workloads.py --samples 1000 --out evidence/guard-workloads.json
"""
import argparse
import importlib.metadata
import json
import platform
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trustkernel.guard import ActionClass, Guard  # noqa: E402


def percentile(values, fraction):
    values = sorted(values)
    return values[min(len(values) - 1, int((len(values) - 1) * fraction))]


def deployment_callback(effects):
    def deploy(service, build):
        effects.append((service, build))
        return build
    return deploy


def benign_grid():
    """24 authored read cases and 12 approved mutations with legitimate replay."""
    completed = 0
    failures = []
    for resource in ("payments", "billing", "search", "catalog"):
        guard = Guard()
        effects = []

        @guard.tool(resource="service")
        def read(service, detail):
            return {"service": service, "detail": detail}

        deploy = guard.tool(resource="service", action_class=ActionClass.HIGH_IMPACT, approver_role="human")(
            deployment_callback(effects))

        root = guard.root("coordinator", tools={"read", "deploy"}, resources={resource})
        worker = guard.spawn(root, "reader", tools={"read"})
        for ctx in (root, worker):
            for detail in (None, {"healthy": True}, [1, "two", 3.5]):
                try:
                    assert read(ctx, service=resource, detail=detail) == {"service": resource, "detail": detail}
                    completed += 1
                except Exception as exc:
                    failures.append(f"read/{resource}/{ctx.principal}: {type(exc).__name__}")
        for build in ("v1", "v2", "v3"):
            try:
                proposal = guard.propose(root, "deploy", resource=resource, service=resource, build=build)
                approval = guard.approve(proposal, approver="reviewer", role="human")
                for _ in range(2):
                    assert deploy(root, service=resource, build=build, approval=approval) == build
                assert effects.count((resource, build)) == 1
                completed += 1
            except Exception as exc:
                failures.append(f"deploy/{resource}/{build}: {type(exc).__name__}")
    return {"authored_cases": 36, "completed": completed, "failures": failures,
            "limits": "Fixed authored grid; not a real-workload false-denial estimate."}


def measure(samples):
    timings = {}
    for depth in (0, 1, 3):
        guard = Guard()

        @guard.tool(resource="service")
        def read(service):
            return service

        ctx = guard.root("root", tools={"read"}, resources={"svc"})
        for hop in range(depth):
            ctx = guard.spawn(ctx, f"worker-{hop}", tools={"read"})
        for _ in range(20):
            read(ctx, service="svc")
        elapsed = []
        for _ in range(samples):
            start = time.perf_counter_ns()
            read(ctx, service="svc")
            elapsed.append((time.perf_counter_ns() - start) / 1000)
        timings[f"guard_depth_{depth}"] = {"samples": samples, "median_us": statistics.median(elapsed),
                                          "p95_us": percentile(elapsed, .95)}
    return timings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.samples < 20:
        parser.error("use at least 20 samples")
    report = {"schema_version": 1, "python": platform.python_version(),
              "system": platform.system(), "machine": platform.machine(),
              "dependencies": {p: importlib.metadata.version(p) for p in ("cryptography", "pyyaml")},
              "benign_grid": benign_grid(), "read_latency": measure(args.samples),
              "measurement_scope": "Warm, sequential, in-process read calls including guard logging. "
              "No network, model, approval signing, contention, or baseline speedup claim. "
              "One process run; not a deployment SLA. Timing is descriptive, not a CI threshold."}
    body = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(body)
    print(body)
    return 0 if report["benign_grid"]["completed"] == 36 and not report["benign_grid"]["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
