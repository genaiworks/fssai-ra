"""Verify one Kafka-to-Iceberg import run from an independent Spark process.

The verifier checks the actual table, not the streaming process log: expected
trace presence, content hash, duplicate Kafka positions, current snapshot, and
the source-position identity used by the MERGE sink.

Usage (inside the analytics image)::

    spark-submit jobs/verify_import_pipeline.py --trace-id live-valid-1
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from pyspark.sql import functions as F

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from bootstrap_iceberg import CATALOG, NAMESPACE, build_spark  # noqa: E402


def verify(*, trace_id: str, table: str) -> dict:
    spark = build_spark("fssaira-verify-import")
    try:
        frame = spark.table(table)
        matches = frame.where(F.col("trace_id") == trace_id)
        row_count = matches.count()
        bad_hashes = frame.where(
            F.col("content_hash").isNull()
            | (F.col("content_hash") != F.sha2(F.col("text"), 256))
        ).count()
        duplicate_positions = (
            frame.groupBy("kafka_topic", "topic_generation", "kafka_partition", "kafka_offset")
            .count()
            .where(F.col("count") > 1)
            .count()
        )
        snapshots = spark.sql(
            f"SELECT snapshot_id, committed_at FROM {table}.snapshots ORDER BY committed_at"
        ).collect()
        result = {
            "table": table,
            "trace_id": trace_id,
            "trace_rows": row_count,
            "bad_hashes": bad_hashes,
            "duplicate_kafka_positions": duplicate_positions,
            "snapshot_count": len(snapshots),
            "latest_snapshot_id": None if not snapshots else str(snapshots[-1]["snapshot_id"]),
            "verdict": "PASS" if row_count == 1 and bad_hashes == 0 and duplicate_positions == 0 else "FAIL",
        }
        print(json.dumps(result, indent=2, default=str))
        return result
    finally:
        spark.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--table", default=f"{CATALOG}.{NAMESPACE}.imported_evidence")
    args = parser.parse_args()
    return 0 if verify(trace_id=args.trace_id, table=args.table)["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
