"""Independently re-verify the archived evidence chain with PySpark.

This job exists because self-verification is not verification. The control plane
can report that its own chain is intact; so could a compromised control plane.
Recomputing the chain from the Iceberg archive, in a different process, with
different credentials, on a different schedule, is what turns tamper-evidence
into something an auditor can rely on.

It reports:

``chain_valid``        every record's hash matches a recomputation over its own fields
``links_intact``       every record's ``prev_hash`` equals the previous record's hash
``sequence_complete``  sequence numbers are contiguous with no gaps
``no_duplicates``      no ``seq`` was archived twice for this ledger
``checkpoint``         with ``--checkpoint``: whether the archive still holds the
                       history an independent notary signed (detects a deleted
                       tail or a fully rewritten chain)

Without ``--checkpoint`` the job checks internal consistency only: a contiguous
but shorter archive passes. ``--since-seq`` trusts the first row's predecessor and
cannot be combined with ``--checkpoint``.

    spark-submit jobs/verify_evidence_chain.py [--ledger-id primary] [--since-seq N]
        [--checkpoint 06-checkpoint.json --public-keys 07-public-keys.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

GENESIS_HASH = "0" * 64


def recompute(seq: int, ts: float, kind: str, payload_json: str, prev_hash: str) -> str:
    body = json.dumps(
        {"seq": seq, "ts": ts, "kind": kind,
         "payload": json.loads(payload_json), "prev": prev_hash},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def verify_rows(rows: list[dict], *, since_seq: int = 0, checkpoint: dict | None = None,
                public_keys: dict[str, str] | None = None) -> dict:
    """Pure verification over archived rows sorted by ``seq``. No Spark needed."""
    if checkpoint is not None and since_seq:
        raise ValueError("--checkpoint verifies the whole chain; drop --since-seq")
    if not rows:
        verdict = {"records": 0, "verdict": "EMPTY"}
        if checkpoint is not None:
            verdict["checkpoint"] = {"valid": checkpoint["count"] == 0,
                                     "code": "LEDGER_TRUNCATED" if checkpoint["count"] else "EMPTY"}
            verdict["verdict"] = "EMPTY" if checkpoint["count"] == 0 else "COMPROMISED"
        return verdict

    seen: dict[int, int] = {}
    for row in rows:
        seen[row["seq"]] = seen.get(row["seq"], 0) + 1
    duplicates = sorted(seq for seq, count in seen.items() if count > 1)
    # Check the chain over one copy of each record; duplicates are reported separately.
    unique, taken = [], set()
    for row in rows:
        if row["seq"] not in taken:
            taken.add(row["seq"])
            unique.append(row)

    previous = GENESIS_HASH if since_seq == 0 else unique[0]["prev_hash"]
    expected_seq = since_seq
    hash_failures, link_failures, gaps = [], [], []
    for row in unique:
        if row["seq"] != expected_seq:
            gaps.append({"expected": expected_seq, "found": row["seq"]})
            expected_seq = row["seq"]
        if row["prev_hash"] != previous:
            link_failures.append(row["seq"])
        if recompute(row["seq"], row["ts"], row["kind"], row["payload_json"],
                     row["prev_hash"]) != row["hash"]:
            hash_failures.append(row["seq"])
        previous = row["hash"]
        expected_seq += 1

    verdict = {
        "records": len(rows),
        "first_seq": unique[0]["seq"],
        "last_seq": unique[-1]["seq"],
        "scope": ("internal consistency plus signed checkpoint" if checkpoint is not None
                  else "internal consistency only; no independent checkpoint"),
        "tail_truncation_checked": checkpoint is not None,
        "chain_valid": not hash_failures,
        "links_intact": not link_failures,
        "sequence_complete": not gaps,
        "no_duplicates": not duplicates,
        "altered_records": hash_failures[:50],
        "broken_links": link_failures[:50],
        "sequence_gaps": gaps[:50],
        "duplicate_seqs": duplicates[:50],
    }
    failed = bool(hash_failures or link_failures or gaps or duplicates)
    if checkpoint is not None:
        from fssaira.evidence import EvidenceRecord
        from fssaira.evidence_notary import Checkpoint, verify_against_checkpoint

        records = [
            EvidenceRecord(row["seq"], row["ts"], row["kind"], json.loads(row["payload_json"]),
                           row["prev_hash"], row["hash"])
            for row in unique
        ]
        keys = {key_id: bytes.fromhex(value) for key_id, value in (public_keys or {}).items()}
        result = verify_against_checkpoint(records, Checkpoint(**checkpoint), keys)
        verdict["checkpoint"] = {"valid": result.valid, "code": result.code,
                                 "detail": result.detail}
        failed = failed or not result.valid
    verdict["verdict"] = "COMPROMISED" if failed else "INTACT"
    return verdict


def main() -> int:
    from bootstrap_iceberg import CATALOG, NAMESPACE, build_spark
    from pyspark.sql import functions as F

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since-seq", type=int, default=0)
    parser.add_argument("--ledger-id", default="primary")
    parser.add_argument("--table", default=f"{CATALOG}.{NAMESPACE}.decision_evidence")
    parser.add_argument("--checkpoint", type=Path,
                        help="signed checkpoint JSON retained outside the archive")
    parser.add_argument("--public-keys", type=Path,
                        help="trusted notary public keys, {key_id: hex}")
    args = parser.parse_args()
    if (args.checkpoint is None) != (args.public_keys is None):
        parser.error("--checkpoint and --public-keys must be given together")

    spark = build_spark("fssaira-verify-evidence")
    rows = [
        row.asDict() for row in
        spark.table(args.table)
        .where((F.col("seq") >= args.since_seq) & (F.col("ledger_id") == args.ledger_id))
        .select("seq", "ts", "kind", "payload_json", "prev_hash", "hash")
        .orderBy("seq")
        .collect()
    ]
    spark.stop()
    verdict = verify_rows(
        rows, since_seq=args.since_seq,
        checkpoint=json.loads(args.checkpoint.read_text()) if args.checkpoint else None,
        public_keys=json.loads(args.public_keys.read_text()) if args.public_keys else None,
    )
    verdict = {"table": args.table, "ledger_id": args.ledger_id, **verdict}
    print(json.dumps(verdict, indent=2))
    return 0 if verdict["verdict"] in {"INTACT", "EMPTY"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
