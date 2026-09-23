"""Structured Streaming job from inward Kafka events to an Iceberg evidence table."""
import os

from bootstrap_iceberg import CATALOG, NAMESPACE, build_spark
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType, StructField, StructType

ENVELOPE_SCHEMA = StructType([
    StructField("trace_id", StringType(), False),
    StructField("value", StructType([
        StructField("source", StringType(), False),
        StructField("text", StringType(), False),
        StructField("stripped", ArrayType(StringType()), True),
        StructField("content_hash", StringType(), True),
    ]), False),
])


def validate_batch(batch) -> None:
    """Refuse malformed/tampered imports before any sink commit."""
    invalid = batch.where(
        F.col("source").isNull() | F.col("text").isNull()
        | F.col("trace_id").isNull() | F.col("content_hash").isNull()
        | (F.col("content_hash") != F.sha2(F.col("text"), 256))
    )
    if invalid.limit(1).count():
        # Fail before the sink/checkpoint commit. Never silently skip a bad event.
        # Do not log the payload: a quarantine writer needs separate authorization.
        raise ValueError("invalid import envelope or content hash; batch not committed")


def write_batch(batch, _batch_id: int) -> None:
    """Append one micro-batch.

    Delivery from ``foreachBatch`` is at-least-once: a failure between the
    Iceberg commit and checkpoint commit can replay a batch. The sink therefore
    merges on Kafka's stable ``(partition, offset)`` identity. This makes a
    replay idempotent at the table boundary instead of merely promising that
    every future reader will remember to de-duplicate it.
    """
    if batch.rdd.isEmpty():
        return
    validate_batch(batch)
    prepared = batch.dropDuplicates(["kafka_partition", "kafka_offset"])
    view = "fssaira_import_microbatch"
    prepared.createOrReplaceTempView(view)
    batch.sparkSession.sql(f"""
        MERGE INTO {CATALOG}.{NAMESPACE}.imported_evidence target
        USING {view} source
        ON target.kafka_partition = source.kafka_partition
           AND target.kafka_offset = source.kafka_offset
        WHEN NOT MATCHED THEN INSERT *
    """)


def parse_imports(stream):
    """Preserve malformed rows for explicit validation rather than dropping them."""
    return (
        stream.select(
            F.from_json(F.col("value").cast("string"), ENVELOPE_SCHEMA).alias("event"),
            F.col("partition").alias("kafka_partition"),
            F.col("offset").alias("kafka_offset"),
            F.col("timestamp").alias("imported_at"),
        )
        .select(
            "event.value.source", "event.value.text", "event.value.stripped",
            "event.value.content_hash", "event.trace_id",
            "kafka_partition", "kafka_offset", "imported_at",
        )
    )


def main() -> None:
    spark = build_spark()
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
    topic = os.getenv("FSSAI_IMPORT_TOPIC", "fssaira.imports")
    if "," in topic:
        raise ValueError("one immutable Kafka topic per import table/checkpoint is required")
    checkpoint = os.getenv("FSSAI_CHECKPOINT", "/opt/fssaira/checkpoints/imports")
    stream = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", bootstrap)
        .option("subscribe", topic)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "true")
        .load()
    )
    parsed = parse_imports(stream)
    query = (
        parsed.writeStream.foreachBatch(write_batch)
        .option("checkpointLocation", checkpoint)
        .trigger(processingTime="10 seconds")
        .start()
    )
    query.awaitTermination()


if __name__ == "__main__":
    main()
