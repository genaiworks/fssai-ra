"""Independently re-verify the archived evidence chain with PySpark.

This job exists because self-verification is not verification. The control plane
can report that its own chain is intact; so could a compromised control plane.
Recomputing the chain from the Iceberg archive, in a different process, with
different credentials, on a different schedule, is what turns tamper-evidence
into something an auditor can rely on.

It reports three things:

``chain_valid``       every record's hash matches a recomputation over its own fields
``links_intact``      every record's ``prev_hash`` equals the previous record's hash
``sequence_complete`` sequence numbers are 0..n-1 with no gaps

A gap is the interesting result. A hash chain makes an *edit* obvious; a
truncation is only obvious if someone is counting, which is what
``sequence_complete`` does.

    spark-submit jobs/verify_evidence_chain.py [--since-seq N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

from pyspark.sql import functions as F

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bootstrap_iceberg import CATALOG, NAMESPACE, build_spark  # noqa: E402

GENESIS_HASH = "0" * 64


def recompute(seq: int, ts: float, kind: str, payload_json: str, prev_hash: str) -> str:
    body = json.dumps(
        {"seq": seq, "ts": ts, "kind": kind,
         "payload": json.loads(payload_json), "prev": prev_hash},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since-seq", type=int, default=0)
    parser.add_argument("--table", default=f"{CATALOG}.{NAMESPACE}.decision_evidence")
    args = parser.parse_args()

    spark = build_spark("fssaira-verify-evidence")
    rows = (
        spark.table(args.table)
        .where(F.col("seq") >= args.since_seq)
        .select("seq", "ts", "kind", "payload_json", "prev_hash", "hash")
        .orderBy("seq")
        .collect()
    )
    if not rows:
        print(json.dumps({"records": 0, "verdict": "EMPTY"}))
        spark.stop()
        return 0

    previous = GENESIS_HASH if args.since_seq == 0 else rows[0]["prev_hash"]
    expected_seq = args.since_seq
    hash_failures, link_failures, gaps = [], [], []

    for row in rows:
        if row["seq"] != expected_seq:
            gaps.append({"expected": expected_seq, "found": row["seq"]})
            expected_seq = row["seq"]
        if row["prev_hash"] != previous:
            link_failures.append(row["seq"])
        if recompute(row["seq"], row["ts"], row["kind"], row["payload_json"], row["prev_hash"]) != row["hash"]:
            hash_failures.append(row["seq"])
        previous = row["hash"]
        expected_seq += 1

    verdict = {
        "table": args.table,
        "records": len(rows),
        "first_seq": rows[0]["seq"],
        "last_seq": rows[-1]["seq"],
        "chain_valid": not hash_failures,
        "links_intact": not link_failures,
        "sequence_complete": not gaps,
        "altered_records": hash_failures[:50],
        "broken_links": link_failures[:50],
        "sequence_gaps": gaps[:50],
        "verdict": "INTACT" if not (hash_failures or link_failures or gaps) else "COMPROMISED",
    }
    print(json.dumps(verdict, indent=2))
    spark.stop()
    return 0 if verdict["verdict"] == "INTACT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
