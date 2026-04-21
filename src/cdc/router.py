"""Operation router: splits flattened CDC events by op type into sink-ready DataFrames.

Debezium `op` codes:
- c = create (INSERT)
- u = update
- d = delete
- r = read (snapshot)

Semantics for sinks:
- UPSERT sinks (Postgres, Redshift dims without SCD2): c/u/r → upsert, d → delete
- SCD2 sinks: c/u/r → new version, d → close open row
- Append-only sinks: c/u/r → append, d → append tombstone
"""

from __future__ import annotations

from dataclasses import dataclass

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


@dataclass(frozen=True)
class RoutedBatch:
    """A batch split by op type."""

    upserts: DataFrame  # c, u, r events with `after` as the row state
    deletes: DataFrame  # d events with `before` as the row identifier


def route_by_op(df: DataFrame) -> RoutedBatch:
    """Split the batch into upsert vs delete sub-DataFrames.

    - Upserts carry the `after` map (post-change state)
    - Deletes carry the `before` map (pre-delete state, for PK lookup)
    """
    upserts = df.filter(F.col("op").isin("c", "u", "r")).select(
        "db_name",
        "table_name",
        "op",
        "ts_ms",
        "source_ts_ms",
        "is_snapshot",
        "pk_hash",
        F.col("after").alias("row"),
    )

    deletes = df.filter(F.col("op") == "d").select(
        "db_name",
        "table_name",
        "ts_ms",
        "source_ts_ms",
        "pk_hash",
        F.col("before").alias("row"),
    )

    return RoutedBatch(upserts=upserts, deletes=deletes)


def explode_map_to_columns(df: DataFrame, attribute_columns: list[str]) -> DataFrame:
    """Convert `row` MapType<string,string> into typed columns.

    Debezium stores all values as strings in the map. Downstream sinks
    cast these to proper types using sink-specific DDL.
    """
    select_exprs = [
        "db_name",
        "table_name",
        "ts_ms",
        "source_ts_ms",
        "pk_hash",
    ]
    # Preserve `op` if present (only on upsert stream)
    if "op" in df.columns:
        select_exprs.append("op")
    if "is_snapshot" in df.columns:
        select_exprs.append("is_snapshot")

    for col in attribute_columns:
        select_exprs.append(F.col("row")[col].alias(col))

    return df.select(*select_exprs)
