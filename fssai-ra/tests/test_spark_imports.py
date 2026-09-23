"""Real Spark parser/validation checks; Iceberg catalog is not required."""
import hashlib
import importlib.util
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

HAS_SPARK = importlib.util.find_spec("pyspark") is not None


@unittest.skipUnless(HAS_SPARK, "requires optional PySpark and Java")
class SparkImportValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pyspark.sql import SparkSession
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jobs"))
        cls.spark = (SparkSession.builder.master("local[1]")
                     .appName("import-validation-test")
                     .config("spark.ui.enabled", "false").getOrCreate())
        cls.spark.sparkContext.setLogLevel("ERROR")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def batch(self, bodies):
        from kafka_to_iceberg import parse_imports
        rows = [(body, "fssaira.imports", 0, i, datetime(2026, 9, 22))
                for i, body in enumerate(bodies)]
        return parse_imports(self.spark.createDataFrame(
            rows, "value string, topic string, partition int, offset long, timestamp timestamp"),
            generation="2")

    def valid_body(self):
        text = "Synthetic public policy"
        return json.dumps({"trace_id": "trace-1", "value": {
            "source": "policy-office", "text": text, "stripped": [],
            "content_hash": hashlib.sha256(text.encode()).hexdigest(),
        }})

    def test_valid_payload_preserves_kafka_identity(self):
        from kafka_to_iceberg import validate_batch
        batch = self.batch([self.valid_body()])
        validate_batch(batch)
        self.assertEqual(batch.first().kafka_offset, 0)
        self.assertEqual(batch.first().source, "policy-office")
        self.assertEqual(batch.first().kafka_topic, "fssaira.imports")
        self.assertEqual(batch.first().topic_generation, "2")

    def test_identity_names_every_parsed_key_column(self):
        from kafka_to_iceberg import IDENTITY
        columns = set(self.batch([self.valid_body()]).columns)
        self.assertTrue(set(IDENTITY) <= columns)

    def test_bad_records_are_preserved_and_fail_before_sink(self):
        from kafka_to_iceberg import write_batch
        for bad in ['not-json', '{}', '{"value": {}}',
                    self.valid_body().replace('Synthetic public policy', 'tampered')]:
            with self.subTest(payload=bad):
                batch = self.batch([self.valid_body(), bad])
                self.assertEqual(batch.count(), 2)
                with self.assertRaisesRegex(ValueError, "batch not committed"):
                    write_batch(batch, 0)


if __name__ == "__main__":
    unittest.main()
