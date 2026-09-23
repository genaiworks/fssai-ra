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


def make_envelope_verifier(key: bytes):
    """A self-contained check of the gateway's HMAC over ``{"trace_id", "value"}``.

    Returned as a nested function so Spark ships it to Python workers by value:
    they need neither this module nor fssaira on their path. A test pins it to
    ``fssaira.envelope_mac``'s canonical form.
    """
    def verify(raw):
        import hashlib
        import hmac
        import json

        try:
            envelope = json.loads(raw)
            body = json.dumps({"trace_id": envelope.get("trace_id", ""),
                               "value": envelope["value"]},
                              sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                              default=str).encode("utf-8")
            mac = envelope.get("mac")
            return isinstance(mac, str) and hmac.compare_digest(
                hmac.new(key, body, hashlib.sha256).hexdigest(), mac)
        except (TypeError, ValueError, KeyError, AttributeError):
            return False

    return verify


def envelope_is_authentic(key: bytes, raw: str | None) -> bool:
    return make_envelope_verifier(key)(raw)


def envelope_key() -> bytes | None:
    raw = os.getenv("FSSAI_IMPORT_ENVELOPE_KEY", "").strip()
    return raw.encode("utf-8") if raw else None


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


def split_authentic(batch):
    """Separate records the gateway signed from records it did not.

    Returns ``(authentic, rejected)``; ``rejected`` is ``None`` without an envelope
    key. A record without a valid MAC did not come through the gateway's source
    check, so it is not data to import. It is quarantined rather than allowed to
    stop the stream: otherwise one forged write would halt every later import.
    """
    key = envelope_key()
    if key is None or "raw_envelope" not in batch.columns:
        return batch, None
    from pyspark.sql.types import BooleanType

    verify = F.udf(make_envelope_verifier(key), BooleanType())
    marked = batch.withColumn("_authentic", verify(F.col("raw_envelope")))
    return (marked.where(F.col("_authentic")).drop("_authentic"),
            marked.where(~F.col("_authentic")).drop("_authentic"))


def quarantine(rejected, table: str) -> int:
    """Record rejected positions, never their content, idempotently."""
    rows = rejected.select(
        *IDENTITY, F.coalesce(F.col("trace_id"), F.lit("")).alias("trace_id"),
        F.lit("envelope MAC missing or invalid").alias("reason"),
        F.sha2(F.coalesce(F.col("raw_envelope"), F.lit("")), 256).alias("raw_sha256"),
        F.current_timestamp().alias("quarantined_at"),
    ).dropDuplicates(IDENTITY)
    count = rows.count()
    if count:
        view = "fssaira_import_quarantine"
        rows.createOrReplaceTempView(view)
        rejected.sparkSession.sql(f"""
            MERGE INTO {table} target USING {view} source
            ON target.kafka_topic = source.kafka_topic
               AND target.topic_generation = source.topic_generation
               AND target.kafka_partition = source.kafka_partition
               AND target.kafka_offset = source.kafka_offset
            WHEN NOT MATCHED THEN INSERT *
        """)
        print(f"WARNING: quarantined {count} import record(s) without a valid gateway MAC "
              f"in {table}; investigate who can write to the import topic", flush=True)
    return count


def position_conflicts(batch, existing):
    """Rows whose Kafka position is already stored with *different* content.

    A replay of a committed batch is the same Kafka record, so its ``trace_id``
    and ``content_hash`` match the stored row and MERGE skips it correctly. A
    different record at a stored position means the topic was reset or recreated
    without raising ``FSSAI_IMPORT_TOPIC_GENERATION``; skipping it would lose it.
    """
    on = [F.col(f"s.{column}") == F.col(f"t.{column}") for column in IDENTITY]
    return (
        batch.alias("s").join(existing.alias("t"), on)
        .where((F.col("s.trace_id") != F.col("t.trace_id"))
               | (F.col("s.content_hash") != F.col("t.content_hash")))
        .select(*[F.col(f"s.{column}") for column in IDENTITY])
    )


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
    batch, rejected = split_authentic(batch)
    if rejected is not None:
        quarantine(rejected, f"{CATALOG}.{NAMESPACE}.quarantined_imports")
    if batch.rdd.isEmpty():
        return
    validate_batch(batch)
    prepared = batch.drop("raw_envelope").dropDuplicates(IDENTITY)
    table = f"{CATALOG}.{NAMESPACE}.imported_evidence"
    bounds = prepared.agg(F.min("kafka_offset"), F.max("kafka_offset")).first()
    existing = (
        batch.sparkSession.table(table)
        .where(F.col("kafka_offset").between(bounds[0], bounds[1]))
        .select(*IDENTITY, "trace_id", "content_hash")
    )
    if position_conflicts(prepared, existing).limit(1).count():
        raise ValueError(
            "Kafka positions already hold different records: the topic was reset or "
            "recreated. Raise FSSAI_IMPORT_TOPIC_GENERATION; batch not committed")
    view = "fssaira_import_microbatch"
    prepared.createOrReplaceTempView(view)
    batch.sparkSession.sql(f"""
        MERGE INTO {table} target
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
            F.col("value").cast("string").alias("raw_envelope"),
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
            "kafka_partition", "kafka_offset", "imported_at", "raw_envelope",
        )
    )


def continuity_problems(kafka_rows, stored_rows) -> list[str]:
    """Signs that the topic was reset since the sink last wrote this generation.

    ``kafka_rows`` holds ``kafka_partition, kafka_offset, trace_id`` for the records
    the broker has now; ``stored_rows`` the same columns for rows already in the
    table under this topic and generation. Two signs of a reset:

    * the table holds a higher offset than the broker's latest, or
    * the broker's earliest record differs from the stored record at that position.

    Either means a restarted stream could skip records silently, because its
    checkpoint refers to positions of a topic that no longer exists.
    """
    problems = []
    live = {r[0]: (r[1], r[2]) for r in kafka_rows.groupBy("kafka_partition")
            .agg(F.min("kafka_offset"), F.max("kafka_offset")).collect()}
    stored_max = {r[0]: r[1] for r in stored_rows.groupBy("kafka_partition")
                  .agg(F.max("kafka_offset")).collect()}
    for partition, highest_stored in stored_max.items():
        first, last = live.get(partition, (None, -1))
        if highest_stored > last:
            problems.append(f"partition {partition}: table holds offset {highest_stored} "
                            f"but the broker's latest is {last}")
            continue
        broker = kafka_rows.where((F.col("kafka_partition") == partition)
                                  & (F.col("kafka_offset") == first)).select("trace_id").first()
        stored = stored_rows.where((F.col("kafka_partition") == partition)
                                   & (F.col("kafka_offset") == first)).select("trace_id").first()
        if broker is not None and stored is not None and broker[0] != stored[0]:
            problems.append(f"partition {partition}: offset {first} holds a different record "
                            "than the one already stored")
    return problems


def check_topic_continuity(spark, bootstrap: str, topic: str, generation: str) -> None:
    """Refuse to start when the topic was reset under the current generation."""
    reader = (spark.read.format("kafka").option("kafka.bootstrap.servers", bootstrap)
              .option("subscribe", topic).option("startingOffsets", "earliest")
              .option("endingOffsets", "latest"))
    for key, value in kafka_tls_options().items():
        reader = reader.option(key, value)
    parsed = parse_imports(reader.load(), generation)
    kafka_rows = parsed.select("kafka_partition", "kafka_offset", "trace_id")
    stored_rows = (spark.table(f"{CATALOG}.{NAMESPACE}.imported_evidence")
                   .where((F.col("kafka_topic") == topic)
                          & (F.col("topic_generation") == generation))
                   .select("kafka_partition", "kafka_offset", "trace_id"))
    problems = continuity_problems(kafka_rows, stored_rows)
    if problems:
        raise RuntimeError(
            "the import topic was reset or recreated since generation "
            f"{generation} was written ({'; '.join(problems)}). Raise "
            "FSSAI_IMPORT_TOPIC_GENERATION to start a new generation; nothing was written")


def checkpoint_for(base: str, generation: str) -> str:
    """Each generation gets its own checkpoint, so raising the generation always
    re-reads the topic from the beginning instead of trusting stale positions.
    Generation 1 keeps the plain path, so existing deployments keep their progress."""
    return base if generation == "1" else f"{base.rstrip('/')}-g{generation}"


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
    # Client certificate (PEM file: private key then certificate) for mutual TLS.
    keystore = os.getenv("FSSAI_KAFKA_SSL_KEYSTORE_PEM")
    if keystore:
        options.update({"kafka.ssl.keystore.type": "PEM",
                        "kafka.ssl.keystore.location": keystore})
    return options


def main() -> None:
    spark = build_spark()
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
    topic = os.getenv("FSSAI_IMPORT_TOPIC", "fssaira.imports")
    if "," in topic:
        raise ValueError("one immutable Kafka topic per import table/checkpoint is required")
    if envelope_key() is None and \
            os.getenv("FSSAI_IMPORT_ALLOW_UNSIGNED", "").lower() != "true":
        raise RuntimeError(
            "FSSAI_IMPORT_ENVELOPE_KEY is not set, so the job cannot tell gateway imports "
            "from records written straight to Kafka. Set the key (the gateway's), or set "
            "FSSAI_IMPORT_ALLOW_UNSIGNED=true to accept that risk explicitly")
    generation = os.getenv("FSSAI_IMPORT_TOPIC_GENERATION", "1")
    checkpoint = checkpoint_for(
        os.getenv("FSSAI_CHECKPOINT") or "/opt/fssaira/checkpoints/imports", generation)
    check_topic_continuity(spark, bootstrap, topic, generation)
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
    parsed = parse_imports(stream, generation)
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
