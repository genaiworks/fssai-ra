"""Field indicators for a governed-disclosure pilot, computed from evidence.

Software tests cannot say whether a deployment serves people well. A pilot can,
if it measures the right things from the start. Every indicator here is computed
from the hash-chained evidence the gate already writes, so a pilot needs no extra
logging, and no indicator requires reading a protected value.

What these numbers can show: how often access is refused and why, how quickly
emergency access is reviewed, how often a model claims a lower label than its
inputs, how often value-level labelling falls back to the session, and whether
the evidence chain is intact.

What they cannot show is listed in every report, so nobody mistakes an indicator
for an outcome: whether a refusal was correct, whether care or service suffered,
whether a released output was accurate or fair, and whether a reviewer paid
attention. Those need the study design in ``docs/PILOT_PROTOCOL.md``.
"""
from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Iterable


def export_records(ledger) -> list[dict]:
    """Evidence records as JSON-ready dictionaries, in chain order."""
    return [{"seq": r.seq, "ts": r.ts, "kind": r.kind, "payload": r.payload,
             "prev_hash": r.prev_hash, "hash": r.hash} for r in ledger]


def _normalise(records: Iterable) -> list[dict]:
    rows = []
    for record in records:
        if isinstance(record, dict):
            rows.append(record)
        else:
            rows.append({"seq": record.seq, "ts": record.ts, "kind": record.kind,
                         "payload": record.payload, "prev_hash": record.prev_hash,
                         "hash": record.hash})
    return rows


def _chain_intact(rows: list[dict]) -> bool | None:
    from .evidence import GENESIS_HASH, _digest

    if not rows or not all({"seq", "ts", "kind", "payload", "prev_hash", "hash"} <= set(r)
                           for r in rows):
        return None
    previous = GENESIS_HASH
    for index, row in enumerate(rows):
        if row["seq"] != index or row["prev_hash"] != previous:
            return False
        if _digest(row["seq"], row["ts"], row["kind"], row["payload"], row["prev_hash"]) != row["hash"]:
            return False
        previous = row["hash"]
    return True


def _outcomes(rows: list[dict], kind: str) -> dict:
    outcomes = [r["payload"] for r in rows if r["kind"] == f"{kind}_outcome"]
    released = sum(1 for p in outcomes if p.get("released"))
    denied = Counter(p.get("code", "UNKNOWN") for p in outcomes if not p.get("released"))
    attempts = sum(1 for r in rows if r["kind"] == f"{kind}_intent")
    return {
        "attempts": attempts, "released": released, "refused": sum(denied.values()),
        "unfinished": attempts - len(outcomes),
        "refusals_by_code": dict(sorted(denied.items())),
        "refusal_rate": round(sum(denied.values()) / len(outcomes), 4) if outcomes else None,
    }


def disclosure_metrics(records: Iterable) -> dict:
    rows = _normalise(records)
    labelled = [r["payload"] for r in rows if r["kind"] == "output_labelled"]
    due = {r["payload"]["grant_id"]: r["ts"] for r in rows if r["kind"] == "break_glass_review_due"}
    reviewed = {r["payload"]["grant_id"]: r["ts"] for r in rows if r["kind"] == "break_glass_reviewed"}
    latencies = [reviewed[g] - due[g] for g in reviewed if g in due]
    stamps = [r["ts"] for r in rows if "ts" in r]
    return {
        "kind": "disclosure-pilot-indicators",
        "evidence": {"records": len(rows), "intact": _chain_intact(rows),
                     "first_ts": min(stamps) if stamps else None,
                     "last_ts": max(stamps) if stamps else None},
        "reads": _outcomes(rows, "disclosure"),
        "releases": _outcomes(rows, "release"),
        "declassifications": _outcomes(rows, "declassification"),
        "outputs": {
            "labelled": len(labelled),
            "by_provenance": dict(Counter(p.get("provenance", "session") for p in labelled)),
            "claimed_downgrade_attempts": sum(1 for p in labelled if p.get("claimed_downgrade_attempt")),
            "value_label_fell_back_to_session": sum(
                1 for p in labelled if p.get("undeclared_source_detected")),
        },
        "break_glass": {
            "opened": len(due), "reviewed": len(reviewed),
            "awaiting_review": len(set(due) - set(reviewed)),
            "review_latency_seconds": {
                "median": round(statistics.median(latencies), 3) if latencies else None,
                "max": round(max(latencies), 3) if latencies else None,
            },
        },
        "revocations": sum(1 for r in rows if r["kind"] == "disclosure_grant_revoked"),
        "consent_withdrawals": sum(1 for r in rows if r["kind"] == "consent_withdrawn"),
        "cannot_measure": [
            "whether any refusal or release was the right decision for the person concerned",
            "effects on care, service, cost, or staff workload",
            "accuracy, fairness, or harm of released outputs",
            "reviewer attention or quality during break-glass review",
            "paraphrased or inferred disclosure that no label captured",
        ],
    }


__all__ = ["disclosure_metrics", "export_records"]
