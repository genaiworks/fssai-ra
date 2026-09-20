"""Run the paper's SDK primitives against synthetic data and real local effects.

    PYTHONPATH=src python scripts/tbc_demo.py --output /tmp/tbc-demo-new

The directory must be new. Tokens are generated for this run and never written
into the report. No network, model download, or paid provider is used.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fssaira.tbc import Guardian, Passport, SDKClient, TaskContract, TrustRuntime  # noqa: E402


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    passport = Passport.parse(json.loads((ROOT / "profiles/tbc/education-passport.json").read_text()))
    task = TaskContract.parse(json.loads((ROOT / "profiles/tbc/education-task.json").read_text()))
    identity = replace(task.scope, destinations=frozenset({"recipient"}))
    tokens = {role: secrets.token_urlsafe(32) for role in ("operator", "source", "reviewer", "recipient")}
    authorities = {token: ("recipient" if role == "recipient" else "named-" + role, role)
                   for role, token in tokens.items()}
    r = TrustRuntime(output / "state.db", passport, authorities=authorities, clock=lambda: 1000)
    try:
        root = r.create_task(tokens["operator"], task, identity_scope=identity, model="offline-scripted", zone="local")
        client = SDKClient(r.dispatch, root["token"])
        client.request_capability()
        context = client.request_context("campus/s1")["context"]
        summary = client.invoke_tool("summarize", context)["artifact"]
        memory = client.persist_memory(summary, "task-notes", retention=100)["memory"]
        remembered = client.read_memory(memory)
        child_scope = replace(identity, operations=frozenset({"request_capability", "receive_message", "derive_artifact"}))
        child = client.request("spawn_agent", scope=child_scope.to_dict(), model="offline-scripted", zone="local", ttl=100)
        child_client = SDKClient(r.dispatch, child["token"])
        child_client.request_capability()
        message = client.request("send_message", recipient=child["agent"], channel="internal", artifact=summary)["message"]
        received = child_client.request("receive_message", message=message)
        proposal = client.propose_effect(context, "correct_transcript", "B", "recipient")
        confirmation = r.confirm_effect(tokens["source"], proposal["proposal"])
        approval = r.approve_effect(tokens["reviewer"], proposal["proposal"], confirmation)
        effect = client.execute_effect(proposal["proposal"], approval)
        escrow = r.authorize_release(tokens["reviewer"], effect["artifact"], "recipient", declassify=True)
        receipt = client.release_artifact(effect["artifact"], "recipient", escrow)
        released = json.loads(r.collect_release(tokens["recipient"], receipt["receipt"]))
        guardian = Guardian(r)
        guardian.contract(task.task, "READ_ONLY", reason="demonstrated assurance loss")
        old_lease_denied = not r.dispatch(root["token"], json.dumps({"op": "derive_artifact", "capability": client.capability, "text": "stale lease"}))["ok"]
        before = r.census(tokens["operator"], task.task)
        r.restore(tokens["operator"], task.task)
        client.request_capability()
        report = {
            "scope": "Synthetic local SQLite reference; deterministic tool adapter and simulated named people.",
            "checks": {
                "memory_preserves_labels": remembered["labels"] == ["synthetic-academic"],
                "airlock_preserves_labels": received["labels"] == ["synthetic-academic"],
                "exact_effect_committed": r.world.record("campus", "s1")["value"] == "B",
                "released_exact_committed_bytes": released == {"resource": "campus/s1", "value": "B", "version": 2},
                "old_lease_denied_after_contraction": old_lease_denied,
                "guardian_state_persisted": before["state"] == "READ_ONLY",
                "evidence_chain_valid": r.world.verify(r.world.checkpoint()),
            },
            "ai_ir": proposal["ai_ir"], "released": released,
            "census": r.census(tokens["operator"], task.task), "checkpoint": r.world.checkpoint(),
        }
        report["passed"] = all(report["checks"].values())
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        return report
    finally:
        r.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.output)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
