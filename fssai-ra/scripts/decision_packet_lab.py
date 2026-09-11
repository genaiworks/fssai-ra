"""A synthetic three-act lab: inspect, alter, then recompute the hashes.

The original fingerprint retained by this script models a separate custodian.
It is a classroom fixture, not independent institutional custody or a field study.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fssaira.control_plane import ControlPlane  # noqa: E402
from fssaira.decision_packet import export_decision_packet  # noqa: E402
from fssaira.packet_verifier import canonical_hash, inspect_packet  # noqa: E402
from fssaira.profiles import ApplicationProfile  # noqa: E402


def run_lab(directory: Path) -> dict:
    names = ("decision-packet.json", "altered-packet.json", "rewritten-packet.json", "lab-report.json")
    if any((directory / name).exists() for name in names):
        raise ValueError("lab outputs already exist; choose a new directory to preserve the previous run")
    directory.mkdir(parents=True, exist_ok=True)
    plane = ControlPlane(ApplicationProfile.load(ROOT / "profiles/student_support.yaml"))
    plane.register_resource("SYNTHETIC-STUDENT-1", status="draft")
    plane.propose(request_id="synthetic-review-1", requester="synthetic-assistant",
                  operation="prepare_case_for_review", resource_id="SYNTHETIC-STUDENT-1",
                  from_status="draft", to_status="ready_for_officer_review",
                  evidence_version="synthetic-evidence-reference-1")
    plane.approve("synthetic-review-1", approver="synthetic-officer", approver_role="student_support_officer")
    plane.execute("synthetic-review-1")
    packet = export_decision_packet(plane, "synthetic-review-1")
    # Keep the expected hash independently of the later edits. A real reviewer
    # must obtain it from an independently trusted custody channel.
    retained = packet["payload_sha256"]
    altered = deepcopy(packet)
    altered["payload"]["proposal"]["case_id"] = "DIFFERENT-STUDENT"
    rewritten = deepcopy(packet)
    rewritten["payload"]["review_context"]["profile"]["manual_fallback"] = "Contact an unauthorized recovery office."
    rewritten["payload_sha256"] = canonical_hash({key: rewritten[key] for key in ("schema", "payload")})
    checks = {
        "original_with_retained_fingerprint": inspect_packet(packet, retained),
        "altered_target": inspect_packet(altered, retained),
        "rewritten_context_without_fingerprint": inspect_packet(rewritten),
        "rewritten_context_with_retained_fingerprint": inspect_packet(rewritten, retained),
    }
    expected = ["anchored_consistent", "inconsistent", "unanchored_consistent", "inconsistent"]
    report = {
        "fixture_only": True,
        "passed": [item["status"] for item in checks.values()] == expected,
        "retained_fingerprint": retained,
        "mutations": plane.register.mutation_count,
        "checks": checks,
        "limitations": "Author-designed synthetic classroom exercise; no independent review or learner-outcome measurement.",
    }
    for name, value in zip(names, (packet, altered, rewritten, report), strict=True):
        (directory / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run_lab(args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    for label, result in report["checks"].items():
        print(f"{label}: {result['status']}")
    print(f"Retain through a separate trusted channel: {report['retained_fingerprint']}")
    print("No source documents or signing keys are included. No educational benefit is claimed.")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
