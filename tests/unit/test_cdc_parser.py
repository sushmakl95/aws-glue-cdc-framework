"""Unit tests for CDC envelope parser + router."""

from __future__ import annotations

import pytest

from src.cdc.parser import deduplicate_by_latest, flatten_envelope
from src.cdc.router import route_by_op

pytestmark = pytest.mark.unit


def _envelope(op: str, pk_val: int, ts_ms: int, pos: int = 1):
    """Build a minimal Debezium envelope row dict."""
    before = {"customer_id": str(pk_val), "email": "old@example.com"} if op in ("u", "d") else None
    after = {"customer_id": str(pk_val), "email": "new@example.com"} if op in ("c", "u", "r") else None
    return {
        "payload": {
            "before": before,
            "after": after,
            "source": {
                "connector": "mysql",
                "db": "sales",
                "table": "customers",
                "ts_ms": ts_ms - 10,
                "snapshot": "false",
                "file": "bin.000001",
                "pos": pos,
            },
            "op": op,
            "ts_ms": ts_ms,
        }
    }


def test_flatten_envelope_creates_pk_hash(spark):
    envelopes = [_envelope("c", 1, 1000)]
    df = spark.createDataFrame(envelopes)
    flat = flatten_envelope(df, pk_columns=["customer_id"])
    row = flat.collect()[0]

    assert row["db_name"] == "sales"
    assert row["table_name"] == "customers"
    assert row["op"] == "c"
    assert row["pk_hash"] is not None
    assert len(row["pk_hash"]) == 64  # sha2-256 hex


def test_flatten_envelope_delete_uses_before_for_pk(spark):
    """For deletes, `after` is null — pk must come from `before`."""
    envelopes = [_envelope("d", 42, 2000)]
    df = spark.createDataFrame(envelopes)
    flat = flatten_envelope(df, pk_columns=["customer_id"])
    rows = flat.collect()

    assert len(rows) == 1
    assert rows[0]["op"] == "d"
    assert rows[0]["pk_hash"] is not None  # derived from `before`


def test_deduplicate_keeps_latest_by_ts_ms(spark):
    """Multiple events for same PK in one batch — only the latest wins."""
    envelopes = [
        _envelope("c", 7, 1000, pos=1),
        _envelope("u", 7, 2000, pos=2),
        _envelope("u", 7, 3000, pos=3),
    ]
    df = spark.createDataFrame(envelopes)
    flat = flatten_envelope(df, pk_columns=["customer_id"])
    deduped = deduplicate_by_latest(flat)
    rows = deduped.collect()

    assert len(rows) == 1
    assert rows[0]["ts_ms"] == 3000
    assert rows[0]["op"] == "u"


def test_route_by_op_splits_upserts_and_deletes(spark):
    envelopes = [
        _envelope("c", 1, 1000),
        _envelope("u", 2, 2000),
        _envelope("d", 3, 3000),
        _envelope("r", 4, 4000),
    ]
    df = spark.createDataFrame(envelopes)
    flat = flatten_envelope(df, pk_columns=["customer_id"])
    routed = route_by_op(flat)

    upsert_ops = {r["op"] for r in routed.upserts.collect()}
    delete_count = routed.deletes.count()

    assert upsert_ops == {"c", "u", "r"}
    assert delete_count == 1
