"""Create the Iceberg namespace and tables used by the reference platform.

Run once before the streaming job. Idempotent: re-running it is safe and is the
documented recovery step after a catalog is rebuilt.
"""
from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.request

from pyspark.sql import SparkSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

CATALOG = os.getenv("ICEBERG_CATALOG", "sovereign")
NAMESPACE = os.getenv("ICEBERG_NAMESPACE", "fssaira")


def build_spark(app_name: str = "fssaira-bootstrap") -> SparkSession:
    return (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config(f"spark.sql.catalog.{CATALOG}", "org.apache.iceberg.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{CATALOG}.type", "rest")
        .config(f"spark.sql.catalog.{CATALOG}.uri",
                os.getenv("ICEBERG_CATALOG_URI", "http://iceberg-rest:8181"))
        .config(f"spark.sql.catalog.{CATALOG}.warehouse",
                os.getenv("ICEBERG_WAREHOUSE", "s3://warehouse/"))
        .config(f"spark.sql.catalog.{CATALOG}.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        .config(f"spark.sql.catalog.{CATALOG}.s3.endpoint",
                os.getenv("S3_ENDPOINT", "http://minio:9000"))
        .config(f"spark.sql.catalog.{CATALOG}.s3.path-style-access", "true")
        .getOrCreate()
    )


def main() -> None:
    from fssaira.iceberg_backend import TABLE_DDL

    # The REST process can be started before its HTTP listener is ready.
    uri = os.getenv("ICEBERG_CATALOG_URI", "http://iceberg-rest:8181")
    for attempt in range(60):
        try:
            with urllib.request.urlopen(uri + "/v1/config", timeout=3):
                break
        except (OSError, urllib.error.URLError):
            if attempt == 59:
                raise RuntimeError("Iceberg catalog did not become ready") from None
            time.sleep(1)
    spark = build_spark()
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {CATALOG}.{NAMESPACE}")
    for name, ddl in TABLE_DDL.items():
        spark.sql(ddl.format(catalog=CATALOG, namespace=NAMESPACE))
        migrate(spark, name)
        print(f"ready: {CATALOG}.{NAMESPACE}.{name}")
    spark.stop()


def migrate(spark, name: str) -> None:
    """Add columns introduced after a table was created, then backfill old rows.

    Existing import rows get the configured topic and generation, which is correct
    because the job has always refused more than one topic per table. Existing
    evidence rows get ledger ``primary``, the archive's default.
    """
    from fssaira.iceberg_backend import TABLE_MIGRATIONS

    table = f"{CATALOG}.{NAMESPACE}.{name}"
    wanted = TABLE_MIGRATIONS.get(name, {})
    present = {field.name for field in spark.table(table).schema.fields}
    values = {"topic": os.getenv("FSSAI_IMPORT_TOPIC", "fssaira.imports"),
              "generation": os.getenv("FSSAI_IMPORT_TOPIC_GENERATION", "1")}
    for column, template in wanted.items():
        if column not in present:
            spark.sql(f"ALTER TABLE {table} ADD COLUMNS ({column} STRING)")
            print(f"migrated: {table} + {column}")
        # An UPDATE commits a snapshot even when it matches nothing; skip it then.
        if spark.sql(f"SELECT 1 FROM {table} WHERE {column} IS NULL LIMIT 1").count():
            value = template.format(**values).replace("'", "''")
            spark.sql(f"UPDATE {table} SET {column} = '{value}' WHERE {column} IS NULL")
            print(f"backfilled: {table}.{column} = {value!r}")


if __name__ == "__main__":
    main()
