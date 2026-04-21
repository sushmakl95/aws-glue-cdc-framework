"""Postgres sink — native UPSERT via INSERT ... ON CONFLICT DO UPDATE.

Why Postgres in addition to Redshift?
- Redshift is columnar, great for analytics but bad at point lookups
- Operational microservices need a row-store replica with sub-ms reads
- Same CDC pipeline feeds both; no dual-write from the app

We batch INSERTs using psycopg2.extras.execute_values for speed (10-50x
faster than individual INSERTs).
"""

from __future__ import annotations

import psycopg2
import psycopg2.extras
from pyspark.sql import DataFrame

from src.schemas.contracts import TableContract
from src.sinks.base import Sink, SinkWriteResult
from src.utils.logging_config import get_logger
from src.utils.secrets import get_secret

log = get_logger(__name__, sink="postgres")


class PostgresSink(Sink):
    """Postgres sink — upsert with ON CONFLICT DO UPDATE."""

    def __init__(
        self,
        secret_id: str,
        database: str,
        schema: str = "public",
        batch_size: int = 1000,
        region: str = "ap-south-1",
    ):
        self.secret_id = secret_id
        self.database = database
        self.schema = schema
        self.batch_size = batch_size
        self.region = region
        self._conn: psycopg2.extensions.connection | None = None

    @property
    def name(self) -> str:
        return "postgres"

    def connect(self) -> None:
        creds = get_secret(self.secret_id, region=self.region)
        self._conn = psycopg2.connect(
            host=creds["host"],
            port=int(creds.get("port", 5432)),
            dbname=self.database,
            user=creds["username"],
            password=creds["password"],
            sslmode="require",
        )
        self._conn.autocommit = False
        log.info("postgres_connected", database=self.database, host=creds["host"])

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def write_upserts(
        self, contract: TableContract, df: DataFrame
    ) -> SinkWriteResult:
        if df.rdd.isEmpty():
            return SinkWriteResult(sink=self.name, table=contract.fqn)

        # Materialize locally — Postgres doesn't have a bulk-load from S3
        # (unless using aws_s3 extension on RDS, which we don't assume).
        rows = df.collect()
        if not rows:
            return SinkWriteResult(sink=self.name, table=contract.fqn)

        all_columns = list(contract.primary_keys) + list(contract.attribute_columns)
        target = f"{self.schema}.{contract.table_name}"
        pk_cols = ", ".join(contract.primary_keys)
        update_clause = ", ".join(
            f"{c} = EXCLUDED.{c}" for c in contract.attribute_columns
        )
        column_list = ", ".join(all_columns)

        sql = (
            f"INSERT INTO {target} ({column_list}) VALUES %s "
            f"ON CONFLICT ({pk_cols}) DO UPDATE SET {update_clause}"
        )

        # Build tuple sequence honoring column order
        tuples = [tuple(row[c] for c in all_columns) for row in rows]

        assert self._conn is not None
        cur = self._conn.cursor()
        try:
            psycopg2.extras.execute_values(
                cur, sql, tuples, page_size=self.batch_size
            )
            self._conn.commit()
            log.info("postgres_upsert_complete", table=target, rows=len(tuples))
            return SinkWriteResult(
                sink=self.name, table=contract.fqn, upserted=len(tuples)
            )
        except Exception as exc:
            self._conn.rollback()
            log.error("postgres_upsert_failed", table=target, error=str(exc))
            return SinkWriteResult(
                sink=self.name, table=contract.fqn, errors=[str(exc)]
            )
        finally:
            cur.close()

    def write_deletes(
        self, contract: TableContract, df: DataFrame
    ) -> SinkWriteResult:
        if df.rdd.isEmpty():
            return SinkWriteResult(sink=self.name, table=contract.fqn)

        rows = df.collect()
        if not rows:
            return SinkWriteResult(sink=self.name, table=contract.fqn)

        target = f"{self.schema}.{contract.table_name}"
        pk_predicate = " AND ".join(f"{c} = %s" for c in contract.primary_keys)
        sql = (
            f"UPDATE {target} SET deleted_at = CURRENT_TIMESTAMP "
            f"WHERE {pk_predicate}"
            if contract.soft_delete
            else f"DELETE FROM {target} WHERE {pk_predicate}"
        )

        assert self._conn is not None
        cur = self._conn.cursor()
        try:
            for row in rows:
                cur.execute(sql, tuple(row[c] for c in contract.primary_keys))
            self._conn.commit()
            return SinkWriteResult(
                sink=self.name, table=contract.fqn, deleted=len(rows)
            )
        except Exception as exc:
            self._conn.rollback()
            log.error("postgres_delete_failed", table=target, error=str(exc))
            return SinkWriteResult(
                sink=self.name, table=contract.fqn, errors=[str(exc)]
            )
        finally:
            cur.close()
