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


#: A row's stable identity in the sink, used for in-batch de-duplication and MERGE.
IDENTITY = ["kafka_topic", "topic_generation", "kafka_partition", "kafka_offset"]


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
    merges on the record's stable Kafka identity: topic, topic generation,
    partition and offset. This makes a replay idempotent at the table boundary
    instead of merely promising that every future reader will remember to
    de-duplicate it. The generation distinguishes a deleted and recreated topic,
    whose offsets restart at zero; raise ``FSSAI_IMPORT_TOPIC_GENERATION`` when
    you recreate one.
    """
    if batch.rdd.isEmpty():
        return
    validate_batch(batch)
    prepared = batch.dropDuplicates(IDENTITY)
    view = "fssaira_import_microbatch"
    prepared.createOrReplaceTempView(view)
    batch.sparkSession.sql(f"""
        MERGE INTO {CATALOG}.{NAMESPACE}.imported_evidence target
        USING {view} source
        ON target.kafka_topic = source.kafka_topic
           AND target.topic_generation = source.topic_generation
           AND target.kafka_partition = source.kafka_partition
           AND target.kafka_offset = source.kafka_offset
        WHEN NOT MATCHED THEN INSERT *
    """)


def parse_imports(stream, generation: str = "1"):
    """Preserve malformed rows for explicit validation rather than dropping them."""
    return (
        stream.select(
            F.from_json(F.col("value").cast("string"), ENVELOPE_SCHEMA).alias("event"),
            F.col("topic").alias("kafka_topic"),
            F.lit(generation).alias("topic_generation"),
            F.col("partition").alias("kafka_partition"),
            F.col("offset").alias("kafka_offset"),
            F.col("timestamp").alias("imported_at"),
        )
        .select(
            "event.value.source", "event.value.text", "event.value.stripped",
            "event.value.content_hash", "event.trace_id",
            "kafka_topic", "topic_generation",
            "kafka_partition", "kafka_offset", "imported_at",
        )
    )


def kafka_tls_options() -> dict:
    """Kafka source options for a TLS broker; empty for plaintext.

    The Java client verifies the broker's host name by default. The CA is read
    as PEM, so no Java keystore is needed.
    """
    if os.getenv("FSSAI_KAFKA_SECURITY_PROTOCOL", "").strip().upper() != "SSL":
        return {}
    options = {"kafka.security.protocol": "SSL"}
    ca = os.getenv("FSSAI_KAFKA_SSL_CA_LOCATION")
    if ca:
        options.update({"kafka.ssl.truststore.type": "PEM",
                        "kafka.ssl.truststore.location": ca})
    return options


def main() -> None:
    spark = build_spark()
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
    topic = os.getenv("FSSAI_IMPORT_TOPIC", "fssaira.imports")
    if "," in topic:
        raise ValueError("one immutable Kafka topic per import table/checkpoint is required")
    checkpoint = os.getenv("FSSAI_CHECKPOINT", "/opt/fssaira/checkpoints/imports")
    reader = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", bootstrap)
        .option("subscribe", topic)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "true")
    )
    for key, value in kafka_tls_options().items():
        reader = reader.option(key, value)
    stream = reader.load()
    parsed = parse_imports(stream, os.getenv("FSSAI_IMPORT_TOPIC_GENERATION", "1"))
    writer = (
        parsed.writeStream.foreachBatch(write_batch)
        .option("checkpointLocation", checkpoint)
    )
    if os.getenv("FSSAI_AVAILABLE_NOW", "false").lower() == "true":
        writer = writer.trigger(availableNow=True)
    else:
        writer = writer.trigger(processingTime="10 seconds")
    query = writer.start()
    try:
        query.awaitTermination()
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
