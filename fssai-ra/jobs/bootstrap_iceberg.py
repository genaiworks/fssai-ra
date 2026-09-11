"""Create the Iceberg namespace and tables used by the reference platform."""
import os

from pyspark.sql import SparkSession


def build_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("fssaira-bootstrap")
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.sovereign", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.sovereign.type", "rest")
        .config("spark.sql.catalog.sovereign.uri", os.getenv("ICEBERG_CATALOG_URI", "http://iceberg-rest:8181"))
        .config("spark.sql.catalog.sovereign.warehouse", os.getenv("ICEBERG_WAREHOUSE", "s3://warehouse/"))
        .config("spark.sql.catalog.sovereign.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        .config("spark.sql.catalog.sovereign.s3.endpoint", os.getenv("S3_ENDPOINT", "http://minio:9000"))
        .getOrCreate()
    )


def main() -> None:
    spark = build_spark()
    spark.sql("CREATE NAMESPACE IF NOT EXISTS sovereign.fssaira")
    spark.sql("""
        CREATE TABLE IF NOT EXISTS sovereign.fssaira.imported_evidence (
            source STRING NOT NULL,
            text STRING NOT NULL,
            stripped ARRAY<STRING>,
            trace_id STRING NOT NULL,
            kafka_partition INT NOT NULL,
            kafka_offset BIGINT NOT NULL,
            imported_at TIMESTAMP NOT NULL
        ) USING iceberg
        PARTITIONED BY (days(imported_at))
        TBLPROPERTIES ('format-version'='2')
    """)
    spark.sql("""
        CREATE TABLE IF NOT EXISTS sovereign.fssaira.control_events (
            event_kind STRING NOT NULL,
            resource_id STRING,
            payload_json STRING NOT NULL,
            trace_id STRING NOT NULL,
            observed_at TIMESTAMP NOT NULL
        ) USING iceberg
        PARTITIONED BY (days(observed_at))
        TBLPROPERTIES ('format-version'='2')
    """)
    spark.stop()


if __name__ == "__main__":
    main()
