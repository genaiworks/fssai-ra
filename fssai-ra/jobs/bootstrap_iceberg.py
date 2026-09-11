"""Create the Iceberg namespace and tables used by the reference platform.

Run once before the streaming job. Idempotent: re-running it is safe and is the
documented recovery step after a catalog is rebuilt.
"""
from __future__ import annotations

import os
import sys

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

    spark = build_spark()
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {CATALOG}.{NAMESPACE}")
    for name, ddl in TABLE_DDL.items():
        spark.sql(ddl.format(catalog=CATALOG, namespace=NAMESPACE))
        print(f"ready: {CATALOG}.{NAMESPACE}.{name}")
    spark.stop()


if __name__ == "__main__":
    main()
