"""Security overhead, measured separately from model inference.

    python scripts/conference_benchmark.py [--iterations 200] [--ollama] [--out PATH]

Timings depend on the machine and are never compared by ``--check`` or quoted as fixed
figures. Each mediator operation is timed against the education world; model latency is
timed separately (the deterministic model, and a local Ollama model when ``--ollama`` is
given and reachable) so that governance cost is not hidden inside inference cost.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fssaira.education_models import HonestAssistant, OllamaAssistant  # noqa: E402
from fssaira.education_world import EducationWorld  # noqa: E402


def measure(label: str, action, iterations: int) -> dict:
    samples = []
    for _ in range(iterations):
        started = time.perf_counter()
        action()
        samples.append((time.perf_counter() - started) * 1000)
    samples.sort()
    return {"operation": label, "iterations": iterations,
            "median_ms": round(statistics.median(samples), 4),
            "p95_ms": round(samples[int(len(samples) * 0.95) - 1], 4),
            "throughput_per_s": round(1000 / statistics.mean(samples), 1)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--ollama", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "conference" / "benchmarks" / "latest.json")
    args = parser.parse_args()
    n = args.iterations
    world = EducationWorld()
    fields = ("student_name", "attendance_rate", "current_grades")
    grant = world.grant(holder="support-agent", purpose="academic-support", subjects=["stu-a1f3"],
                        fields=fields, ttl_seconds=10**7)
    counter = {"i": 0}

    def gated_read():
        counter["i"] += 1
        world.read(requester="support-agent", grant=grant, purpose="academic-support", subjects=["stu-a1f3"],
                   fields=fields, session_id=f"bench-{counter['i']}")

    row = world.records._row("stu-a1f3", "student_name")
    results = [
        measure("raw decrypt of one field (no mediation)",
                lambda: world.custody.decrypt(world._gate_key, row, subject="stu-a1f3", field="student_name"), n),
        measure("record fetch, three fields (decrypt only)", lambda: world.records.fetch("stu-a1f3", fields), n),
        measure("model attestation", lambda: world.attest("campus_local_model", purpose="academic-support",
                                                           fields=fields), n),
        measure("governed read: attest + 14 gate checks + decrypt + tokenize + evidence", gated_read, n),
        measure("tokenize one identifier", lambda: world.vault.tokenize_text(
            "Mei Ling Chan attended", session_id="bench", identifiers=[("stu-a1f3", "NAME", "Mei Ling Chan")]), n),
        measure("encrypt one field", lambda: world.custody.encrypt(world._ingest, subject="stu-a1f3", field="bench",
                                                                     data_class="student-academic", plaintext="x" * 64), n),
        measure("evidence append", lambda: world.ledger.append("bench", {"n": 1}, token="education-world-evidence-writer"), n),
        measure("signed receipt (Ed25519)", lambda: world.notary.sign_receipt("bench", {"n": 1}), n),
    ]

    def governed_action():
        proposal = world.propose(requester="support-agent", operation="correct_transcript_grade",
                                 resource="transcript:stu-c9d4:MATH101",
                                 to_status="grade:A" if world.register.get("transcript:stu-c9d4:MATH101")["status"] != "grade:A" else "grade:B")
        world.review.items.clear()
        world.review._decisions.clear()
        approval = world.review_and_approve(proposal, reviewer="dr-lin")
        world.execute(proposal, approval)

    results.append(measure("governed action: review queue + Ed25519 approval + executor + receipt",
                           governed_action, min(n, 100)))
    model = HonestAssistant()
    results.append(measure("model inference: deterministic model", lambda: model.respond({"kind": "support"}), n))
    ollama = "not requested"
    if args.ollama:
        local = OllamaAssistant()
        if local.available():
            results.append(measure(f"model inference: ollama {local.model_id}",
                                   lambda: local.respond({"kind": "support"}), 5))
            ollama = "measured"
        else:
            ollama = "requested but no local Ollama runtime was reachable"
    report = {"machine": {"python": platform.python_version(), "platform": platform.platform(),
                          "processor": platform.processor()},
              "note": "Local timings; not comparable across machines; not quoted as fixed figures.",
              "ollama": ollama, "results": results}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for item in results:
        print(f"  {item['median_ms']:>9.3f} ms median  {item['p95_ms']:>9.3f} ms p95  {item['operation']}")
    print(f"  ollama: {ollama}\n  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
