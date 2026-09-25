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
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fssaira.chain_verification import GENESIS_HASH, recompute, verify_rows  # noqa: E402,F401


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
