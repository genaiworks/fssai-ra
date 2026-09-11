"""Structured Streaming job from inward Kafka events to an Iceberg evidence table."""
import os

from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType, StructField, StructType

from bootstrap_iceberg import build_spark


ENVELOPE_SCHEMA = StructType([
    StructField("trace_id", StringType(), False),
    StructField("value", StructType([
        StructField("source", StringType(), False),
        StructField("text", StringType(), False),
        StructField("stripped", ArrayType(StringType()), True),
    ]), False),
])


def write_batch(batch, _batch_id: int) -> None:
    if batch.rdd.isEmpty():
        return
    batch.writeTo("sovereign.fssaira.imported_evidence").append()


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
            "event.trace_id", "kafka_partition", "kafka_offset", "imported_at",
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
