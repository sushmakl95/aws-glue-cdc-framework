"""Typed schemas for the Debezium CDC envelope format.

Debezium wraps every CDC event in a standard envelope:
{
  "schema": {...},
  "payload": {
    "before": {...},   // NULL for 'c' (create), populated for 'u' (update), 'd' (delete)
    "after":  {...},   // populated for 'c' (create), 'u' (update); NULL for 'd' (delete)
    "source": {
      "connector": "mysql",
      "db": "sales",
      "table": "orders",
      "ts_ms": 1680000000000,
      "snapshot": "false",
      "version": "1.9.7.Final",
      "file": "mysql-bin.000123",
      "pos": 1456789,
      "server_id": 223344
    },
    "op": "c|u|d|r",   // create | update | delete | read (snapshot)
    "ts_ms": 1680000000123
  }
}

We model this explicitly so downstream code can rely on typed access
rather than dict lookups.
"""

from __future__ import annotations

from pyspark.sql.types import (
    BooleanType,
    LongType,
    MapType,
    StringType,
    StructField,
    StructType,
)

# The `before` and `after` fields are arbitrary row structures — we keep them
# as a Map type to avoid coupling the framework to a specific source schema.
# Individual table processors narrow this via `map_keys` + `map_values` + casts.
DEBEZIUM_SOURCE_SCHEMA = StructType(
    [
        StructField("connector", StringType(), nullable=False),
        StructField("db", StringType(), nullable=False),
        StructField("table", StringType(), nullable=False),
        StructField("ts_ms", LongType(), nullable=False),
        StructField("snapshot", StringType(), nullable=True),
        StructField("version", StringType(), nullable=True),
        StructField("file", StringType(), nullable=True),
        StructField("pos", LongType(), nullable=True),
        StructField("server_id", LongType(), nullable=True),
    ]
)

DEBEZIUM_PAYLOAD_SCHEMA = StructType(
    [
        StructField("before", MapType(StringType(), StringType()), nullable=True),
        StructField("after", MapType(StringType(), StringType()), nullable=True),
        StructField("source", DEBEZIUM_SOURCE_SCHEMA, nullable=False),
        StructField("op", StringType(), nullable=False),
        StructField("ts_ms", LongType(), nullable=False),
    ]
)

DEBEZIUM_ENVELOPE_SCHEMA = StructType(
    [
        StructField("payload", DEBEZIUM_PAYLOAD_SCHEMA, nullable=False),
    ]
)

# Flattened schema we emit after parsing — one row per change event.
CDC_FLATTENED_SCHEMA = StructType(
    [
        StructField("db_name", StringType(), nullable=False),
        StructField("table_name", StringType(), nullable=False),
        StructField("op", StringType(), nullable=False),
        StructField("ts_ms", LongType(), nullable=False),
        StructField("source_ts_ms", LongType(), nullable=False),
        StructField("is_snapshot", BooleanType(), nullable=False),
        StructField("binlog_file", StringType(), nullable=True),
        StructField("binlog_pos", LongType(), nullable=True),
        StructField("before", MapType(StringType(), StringType()), nullable=True),
        StructField("after", MapType(StringType(), StringType()), nullable=True),
        StructField("pk_hash", StringType(), nullable=False),
    ]
)
