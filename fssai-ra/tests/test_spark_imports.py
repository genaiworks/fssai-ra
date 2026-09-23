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

    def test_a_replay_is_not_a_conflict_but_a_reused_position_is(self):
        from kafka_to_iceberg import position_conflicts
        stored = self.batch([self.valid_body()])
        replay = self.batch([self.valid_body()])
        self.assertEqual(position_conflicts(replay, stored).count(), 0)
        other = self.valid_body().replace('trace-1', 'trace-after-reset')
        self.assertEqual(position_conflicts(self.batch([other]), stored).count(), 1)

    def rows(self, triples):
        return self.spark.createDataFrame(
            triples, "kafka_partition int, kafka_offset long, trace_id string")

    def test_continuity_accepts_an_unchanged_topic(self):
        from kafka_to_iceberg import continuity_problems
        broker = self.rows([(0, 0, "a"), (0, 1, "b"), (0, 2, "c")])
        stored = self.rows([(0, 0, "a"), (0, 1, "b")])
        self.assertEqual(continuity_problems(broker, stored), [])

    def test_continuity_detects_a_recreated_topic(self):
        from kafka_to_iceberg import continuity_problems
        stored = self.rows([(0, 0, "smoke")])
        broker = self.rows([(0, 0, "probe-one"), (0, 1, "probe-two")])
        self.assertEqual(len(continuity_problems(broker, stored)), 1)

    def test_continuity_detects_offsets_going_backwards(self):
        from kafka_to_iceberg import continuity_problems
        stored = self.rows([(0, 0, "a"), (0, 5, "f")])
        broker = self.rows([(0, 0, "a"), (0, 1, "b")])
        self.assertIn("latest is 1", continuity_problems(broker, stored)[0])

    def test_each_generation_has_its_own_checkpoint(self):
        from kafka_to_iceberg import checkpoint_for
        self.assertEqual(checkpoint_for("/c/imports", "1"), "/c/imports")
        self.assertEqual(checkpoint_for("/c/imports/", "3"), "/c/imports-g3")

    def signed_body(self, text="Synthetic public policy", key=b"k" * 32, mac=None):
        import hmac as _hmac
        value = {"source": "policy-office", "text": text, "stripped": [],
                 "content_hash": hashlib.sha256(text.encode()).hexdigest()}
        body = json.dumps({"trace_id": "trace-1", "value": value}, sort_keys=True,
                          separators=(",", ":"), ensure_ascii=False).encode()
        signature = mac or _hmac.new(key, body, hashlib.sha256).hexdigest()
        return json.dumps({"trace_id": "trace-1", "value": value, "mac": signature})

    def test_records_that_bypassed_the_gateway_are_separated_not_imported(self):
        import os

        from kafka_to_iceberg import split_authentic, validate_batch
        os.environ["FSSAI_IMPORT_ENVELOPE_KEY"] = "k" * 32
        try:
            forged = self.signed_body(mac="0" * 64)
            unsigned = self.valid_body()          # well formed, no MAC at all
            batch = self.batch([self.signed_body(), forged, unsigned, "not-json"])
            authentic, rejected = split_authentic(batch)
            self.assertEqual(authentic.count(), 1)
            self.assertEqual(sorted(r.kafka_offset for r in rejected.collect()), [1, 2, 3])
            validate_batch(authentic)             # the authentic record still passes
        finally:
            del os.environ["FSSAI_IMPORT_ENVELOPE_KEY"]

    def test_the_jobs_mac_matches_the_library(self):
        from kafka_to_iceberg import envelope_is_authentic

        from fssaira.envelope_mac import sign
        value = {"source": "s", "text": "Ünïcode ✓", "stripped": ["<script"], "content_hash": "h"}
        envelope = json.dumps({"trace_id": "t", "value": value,
                               "mac": sign(b"k" * 32, value, "t")})
        self.assertTrue(envelope_is_authentic(b"k" * 32, envelope))
        self.assertFalse(envelope_is_authentic(b"x" * 32, envelope))


if __name__ == "__main__":
    unittest.main()
