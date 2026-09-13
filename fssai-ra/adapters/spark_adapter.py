"""Spark adapter for the reproducible-data transform seam.

Enable with:  pip install pyspark
Run distributed cleaning/validation while preserving the same lineage record
(code version, input/output hashes, rules) the reference Transformer emits.
"""
from __future__ import annotations

import hashlib
import json


class SparkTransformer:
    CODE_VERSION = "1.0.0"

    def __init__(self, app_name: str = "fssaira") -> None:
        try:
            from pyspark.sql import SparkSession  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise ImportError("SparkTransformer requires 'pyspark' (pip install pyspark)") from exc
        self._spark = SparkSession.builder.appName(app_name).getOrCreate()

    def run(self, records, fn, job="transform", rules=""):  # pragma: no cover - needs Spark
        # Materialise once: callers commonly pass generators. The old adapter
        # consumed one to build the RDD and then hashed an empty second pass,
        # publishing false lineage while returning the right rows.
        inputs = list(records)
        rdd = self._spark.sparkContext.parallelize(inputs)
        rows = rdd.map(fn).collect()

        def h(value):
            return hashlib.sha256(
                json.dumps(value, sort_keys=True, default=str).encode()
            ).hexdigest()
        return rows, {"job": job, "code_version": self.CODE_VERSION,
                      "input_hash": h(inputs), "output_hash": h(rows), "rules": rules,
                      "n_in": len(inputs), "n_out": len(rows)}
