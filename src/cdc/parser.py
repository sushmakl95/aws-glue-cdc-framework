"""Debezium envelope parser.

Responsibilities:
1. Read raw Debezium JSON from S3
2. Unwrap the envelope
3. Compute a stable `pk_hash` from primary key columns (for MERGE + routing)
4. Emit flattened rows matching CDC_FLATTENED_SCHEMA

Why flatten first?
- Debezium's nested structure is expensive to query repeatedly
- A flat structure enables efficient partition pruning and columnar reads downstream
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from src.schemas.debezium import DEBEZIUM_ENVELOPE_SCHEMA


def read_debezium_events(spark: SparkSession, raw_s3_path: str) -> DataFrame:
    """Read raw Debezium JSON events from S3.

    We use PERMISSIVE mode + `_corrupt_record` so one bad event doesn't kill the batch.
    """
    return (
        spark.read.schema(DEBEZIUM_ENVELOPE_SCHEMA)
        .option("mode", "PERMISSIVE")
        .option("columnNameOfCorruptRecord", "_corrupt_record")
        .json(raw_s3_path)
    )


def flatten_envelope(df: DataFrame, pk_columns: list[str]) -> DataFrame:
    """Flatten the Debezium envelope and compute pk_hash.

    `pk_columns` are the source-table PKs used to derive the hash.
    Events with missing required fields are dropped (logged upstream).
    """
    payload = F.col("payload")

    # For deletes, `after` is null — fall back to `before` to extract the PK
    pk_source_expr = F.when(
        payload["op"] == "d", payload["before"]
    ).otherwise(payload["after"])

    # Build a deterministic PK hash
    pk_values = [
        F.coalesce(pk_source_expr[c], F.lit("∅")) for c in pk_columns
    ]
    pk_hash = F.sha2(F.concat_ws("||", *pk_values), 256)

    return (
        df.filter(payload.isNotNull() & payload["op"].isNotNull())
        .select(
            payload["source"]["db"].alias("db_name"),
            payload["source"]["table"].alias("table_name"),
            payload["op"].alias("op"),
            payload["ts_ms"].alias("ts_ms"),
            payload["source"]["ts_ms"].alias("source_ts_ms"),
            (payload["source"]["snapshot"] == F.lit("true")).alias("is_snapshot"),
            payload["source"]["file"].alias("binlog_file"),
            payload["source"]["pos"].alias("binlog_pos"),
            payload["before"].alias("before"),
            payload["after"].alias("after"),
            pk_hash.alias("pk_hash"),
        )
    )


def deduplicate_by_latest(df: DataFrame) -> DataFrame:
    """Keep only the latest event per pk_hash within the batch.

    When CDC events for the same row arrive multiple times within a single
    Glue batch window, we only want the most recent state. Order: ts_ms DESC,
    then binlog_pos DESC as tiebreaker.
    """
    from pyspark.sql.window import Window

    w = Window.partitionBy("pk_hash").orderBy(
        F.col("ts_ms").desc(),
        F.col("binlog_pos").desc_nulls_last(),
    )
    return (
        df.withColumn("_rn", F.row_number().over(w))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )
