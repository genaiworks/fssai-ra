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


def write_batch(batch, _batch_id: int) -> None:
    """Append one micro-batch.

    Delivery is at-least-once: a failure between the Iceberg commit and the
    checkpoint commit replays the batch. The table therefore tolerates duplicate
    rows by design, and readers de-duplicate on ``(kafka_partition,
    kafka_offset)``, which is unique per delivery. Claiming exactly-once here
    would be the sort of quiet inaccuracy this architecture exists to avoid.
    """
    if batch.rdd.isEmpty():
        return
    batch.writeTo(f"{CATALOG}.{NAMESPACE}.imported_evidence").append()


def main() -> None:
    spark = build_spark()
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
    topic = os.getenv("FSSAI_IMPORT_TOPIC", "fssaira.imports")
    checkpoint = os.getenv("FSSAI_CHECKPOINT", "/opt/fssaira/checkpoints/imports")
    stream = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", bootstrap)
        .option("subscribe", topic)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "true")
        .load()
    )
    parsed = (
        stream.select(
            F.from_json(F.col("value").cast("string"), ENVELOPE_SCHEMA).alias("event"),
            F.col("partition").alias("kafka_partition"),
            F.col("offset").alias("kafka_offset"),
            F.col("timestamp").alias("imported_at"),
        )
        .where(F.col("event").isNotNull())
        .select(
            "event.value.source", "event.value.text", "event.value.stripped",
            "event.value.content_hash", "event.trace_id",
            "kafka_partition", "kafka_offset", "imported_at",
        )
    )
    query = (
        parsed.writeStream.foreachBatch(write_batch)
        .option("checkpointLocation", checkpoint)
        .trigger(processingTime="10 seconds")
        .start()
    )
    query.awaitTermination()


if __name__ == "__main__":
    main()
