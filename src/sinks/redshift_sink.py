"""Redshift sink — SCD2 MERGE or direct upsert.

Two write patterns supported:
1. SCD2: for dimensions. Preserves history of attribute changes via valid_from/valid_to.
2. Upsert: for fact tables. Merge-on-primary-key, latest-wins.

Implementation choice: we write the batch to S3 as Parquet, then run Redshift
COPY + MERGE SQL. This is MUCH faster than `INSERT ... VALUES` per row —
~100-1000x on realistic batches.
"""

from __future__ import annotations

import uuid

import redshift_connector
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from src.schemas.contracts import TableContract
from src.sinks.base import Sink, SinkWriteResult
from src.utils.logging_config import get_logger
from src.utils.secrets import get_secret

log = get_logger(__name__, sink="redshift")


class RedshiftSink(Sink):
    """Redshift sink — uses COPY + MERGE via a staging table."""

    def __init__(
        self,
        secret_id: str,
        database: str,
        schema: str,
        staging_s3_path: str,
        iam_role_arn: str,
        region: str = "ap-south-1",
    ):
        self.secret_id = secret_id
        self.database = database
        self.schema = schema
        self.staging_s3_path = staging_s3_path.rstrip("/")
        self.iam_role_arn = iam_role_arn
        self.region = region
        self._conn: redshift_connector.Connection | None = None

    @property
    def name(self) -> str:
        return "redshift"

    def connect(self) -> None:
        creds = get_secret(self.secret_id, region=self.region)
        self._conn = redshift_connector.connect(
            host=creds["host"],
            port=int(creds.get("port", 5439)),
            database=self.database,
            user=creds["username"],
            password=creds["password"],
            ssl=True,
        )
        self._conn.autocommit = False
        log.info("redshift_connected", database=self.database, host=creds["host"])

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # -------------------------------------------------------------------------
    # Upsert path
    # -------------------------------------------------------------------------
    def write_upserts(self, contract: TableContract, df: DataFrame) -> SinkWriteResult:
        if df.rdd.isEmpty():
            return SinkWriteResult(sink=self.name, table=contract.fqn)

        batch_id = uuid.uuid4().hex[:10]
        target_table = f"{self.schema}.{contract.table_name}"
        staging_table = f"{self.schema}.stg_{contract.table_name}_{batch_id}"
        s3_batch_path = f"{self.staging_s3_path}/{contract.table_name}/{batch_id}/"

        # 1. Write the batch to S3 as Parquet (fast columnar unload)
        row_count = df.count()
        df.write.mode("overwrite").parquet(s3_batch_path)
        log.info("staging_written", path=s3_batch_path, rows=row_count)

        # 2. Use Redshift COPY + MERGE in a single transaction
        assert self._conn is not None
        cur = self._conn.cursor()
        try:
            # Create ephemeral staging table matching target structure
            cur.execute(
                f"CREATE TEMP TABLE {staging_table} (LIKE {target_table})"
            )
            cur.execute(
                f"COPY {staging_table} FROM '{s3_batch_path}' "
                f"IAM_ROLE '{self.iam_role_arn}' "
                f"FORMAT AS PARQUET"
            )

            if contract.scd2:
                self._apply_scd2(cur, contract, target_table, staging_table)
            else:
                self._apply_upsert(cur, contract, target_table, staging_table)

            self._conn.commit()
            log.info(
                "redshift_upsert_complete",
                table=target_table,
                rows=row_count,
                scd2=contract.scd2,
            )
            return SinkWriteResult(sink=self.name, table=contract.fqn, upserted=row_count)
        except Exception as exc:
            self._conn.rollback()
            log.error("redshift_upsert_failed", table=target_table, error=str(exc))
            return SinkWriteResult(
                sink=self.name, table=contract.fqn, errors=[str(exc)]
            )
        finally:
            cur.close()

    def _apply_upsert(
        self, cur, contract: TableContract, target: str, staging: str
    ) -> None:
        """Standard MERGE: delete rows in target that match staging PKs, then INSERT staging."""
        pk_join = " AND ".join(
            f"t.{c} = s.{c}" for c in contract.primary_keys
        )
        cur.execute(f"DELETE FROM {target} t USING {staging} s WHERE {pk_join}")
        cur.execute(f"INSERT INTO {target} SELECT * FROM {staging}")

    def _apply_scd2(
        self, cur, contract: TableContract, target: str, staging: str
    ) -> None:
        """SCD2: close changed rows (valid_to = now, is_current = false), then insert new versions.

        Change detection uses a row hash over attribute columns — deterministic, reusable.
        """
        pk_join = " AND ".join(
            f"t.{c} = s.{c}" for c in contract.primary_keys
        )
        attr_concat = "||'||'||".join(
            f"COALESCE(CAST({c} AS VARCHAR), '')" for c in contract.attribute_columns
        )
        # 1. Close rows whose hash changed
        cur.execute(
            f"""
            UPDATE {target}
            SET valid_to = CURRENT_TIMESTAMP,
                is_current = FALSE
            FROM {staging} s
            WHERE {pk_join.replace('t.', f'{target}.')}
              AND {target}.is_current = TRUE
              AND MD5({attr_concat.replace('COALESCE', f'COALESCE({target}.')}) <> MD5(s.{attr_concat})
            """
        )
        # 2. Insert new versions for changed or new PKs
        cur.execute(
            f"""
            INSERT INTO {target}
            SELECT s.*, CURRENT_TIMESTAMP AS valid_from, NULL::TIMESTAMP AS valid_to, TRUE AS is_current
            FROM {staging} s
            LEFT JOIN {target} t
                ON {pk_join} AND t.is_current = TRUE
            WHERE t.{contract.primary_keys[0]} IS NULL
               OR MD5({attr_concat.replace('s.', 's.')}) <> MD5({attr_concat.replace('s.', 't.')})
            """
        )

    # -------------------------------------------------------------------------
    # Delete path
    # -------------------------------------------------------------------------
    def write_deletes(
        self, contract: TableContract, df: DataFrame
    ) -> SinkWriteResult:
        if df.rdd.isEmpty():
            return SinkWriteResult(sink=self.name, table=contract.fqn)

        # Extract PK values to a small collection (deletes are typically small)
        pk_rows = df.select(
            *[F.col(pk) for pk in contract.primary_keys]
        ).collect()
        if not pk_rows:
            return SinkWriteResult(sink=self.name, table=contract.fqn)

        target_table = f"{self.schema}.{contract.table_name}"
        assert self._conn is not None
        cur = self._conn.cursor()
        try:
            if contract.scd2:
                # Soft-close SCD2: set valid_to on current row
                for row in pk_rows:
                    where = " AND ".join(
                        f"{pk} = %s" for pk in contract.primary_keys
                    )
                    cur.execute(
                        f"UPDATE {target_table} SET valid_to = CURRENT_TIMESTAMP, "
                        f"is_current = FALSE WHERE {where} AND is_current = TRUE",
                        tuple(row[pk] for pk in contract.primary_keys),
                    )
            elif contract.soft_delete:
                for row in pk_rows:
                    where = " AND ".join(
                        f"{pk} = %s" for pk in contract.primary_keys
                    )
                    cur.execute(
                        f"UPDATE {target_table} SET deleted_at = CURRENT_TIMESTAMP "
                        f"WHERE {where}",
                        tuple(row[pk] for pk in contract.primary_keys),
                    )
            else:
                # Physical delete
                for row in pk_rows:
                    where = " AND ".join(
                        f"{pk} = %s" for pk in contract.primary_keys
                    )
                    cur.execute(
                        f"DELETE FROM {target_table} WHERE {where}",
                        tuple(row[pk] for pk in contract.primary_keys),
                    )

            self._conn.commit()
            return SinkWriteResult(
                sink=self.name, table=contract.fqn, deleted=len(pk_rows)
            )
        except Exception as exc:
            self._conn.rollback()
            log.error("redshift_delete_failed", error=str(exc))
            return SinkWriteResult(
                sink=self.name, table=contract.fqn, errors=[str(exc)]
            )
        finally:
            cur.close()
