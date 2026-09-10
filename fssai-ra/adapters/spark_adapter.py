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
        rdd = self._spark.sparkContext.parallelize(list(records))
        rows = rdd.map(fn).collect()
        h = lambda x: hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()
        return rows, {"job": job, "code_version": self.CODE_VERSION,
                      "input_hash": h(list(records)), "output_hash": h(rows), "rules": rules}
