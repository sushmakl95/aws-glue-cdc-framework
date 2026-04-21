"""Main Glue job: Debezium CDC events → multi-sink fanout.

Invoked by Step Functions on a schedule (or S3 PUT trigger). For each enabled
table contract, parses events, deduplicates, routes by op, and writes to each
configured sink.

Invocation (Glue runtime):
    --raw_s3_path s3://.../cdc/raw
    --config s3://.../config/prod.yaml
    --batch_id <uuid>     (injected by Step Functions)

Local dev: `make run-glue-job` wraps this with a local Spark session.
"""

from __future__ import annotations

import sys
import traceback
from typing import TYPE_CHECKING

# Glue SDK imports — available inside Glue runtime
try:
    from awsglue.context import GlueContext
    from awsglue.job import Job
    from awsglue.utils import getResolvedOptions
    _IN_GLUE = True
except ImportError:
    _IN_GLUE = False
    if TYPE_CHECKING:
        from awsglue.context import GlueContext  # noqa: F401
        from awsglue.job import Job  # noqa: F401

from pyspark.context import SparkContext

from src.cdc import (
    deduplicate_by_latest,
    explode_map_to_columns,
    flatten_envelope,
    read_debezium_events,
    route_by_op,
)
from src.schemas import TABLE_CONTRACTS, TableContract, get_contract
from src.sinks import OpenSearchSink, PostgresSink, RedshiftSink, Sink, SinkWriteResult
from src.utils import (
    IdempotencyTracker,
    MetricsEmitter,
    configure_logging,
    get_logger,
    load_config,
)

REQUIRED_ARGS = ["JOB_NAME", "raw_s3_path", "config_path", "batch_id"]


def build_sinks(cfg: dict, enabled: list[str]) -> dict[str, Sink]:
    """Instantiate sinks based on config. Not yet connected."""
    sinks: dict[str, Sink] = {}
    if "redshift" in enabled:
        rs_cfg = cfg["sinks"]["redshift"]
        sinks["redshift"] = RedshiftSink(
            secret_id=rs_cfg["secret_id"],
            database=rs_cfg["database"],
            schema=rs_cfg["schema"],
            staging_s3_path=rs_cfg["staging_s3_path"],
            iam_role_arn=rs_cfg["iam_role_arn"],
            region=cfg.get("aws_region", "ap-south-1"),
        )
    if "postgres" in enabled:
        pg_cfg = cfg["sinks"]["postgres"]
        sinks["postgres"] = PostgresSink(
            secret_id=pg_cfg["secret_id"],
            database=pg_cfg["database"],
            schema=pg_cfg.get("schema", "public"),
            region=cfg.get("aws_region", "ap-south-1"),
        )
    if "opensearch" in enabled:
        os_cfg = cfg["sinks"]["opensearch"]
        sinks["opensearch"] = OpenSearchSink(
            secret_id=os_cfg["secret_id"],
            endpoint=os_cfg["endpoint"],
            index_prefix=os_cfg.get("index_prefix", "cdc"),
            region=cfg.get("aws_region", "ap-south-1"),
        )
    return sinks


def process_table(
    spark,
    raw_s3_path: str,
    contract: TableContract,
    sinks: dict[str, Sink],
    metrics: MetricsEmitter,
    log,
) -> list[SinkWriteResult]:
    """Process all CDC events for a single table contract."""
    table_path = f"{raw_s3_path}/{contract.db_name}/{contract.table_name}/"
    log.info("table_processing_started", table=contract.fqn, path=table_path)

    try:
        raw = read_debezium_events(spark, table_path)
    except Exception as exc:  # noqa: BLE001
        log.warning("table_read_failed_or_empty", table=contract.fqn, error=str(exc))
        return []

    flat = flatten_envelope(raw, list(contract.primary_keys))
    latest = deduplicate_by_latest(flat)
    total = latest.count()
    if total == 0:
        log.info("table_no_events", table=contract.fqn)
        return []

    routed = route_by_op(latest)
    upserts_typed = explode_map_to_columns(routed.upserts, list(contract.attribute_columns))
    deletes_typed = explode_map_to_columns(routed.deletes, list(contract.attribute_columns))

    results: list[SinkWriteResult] = []
    for sink_name in contract.sinks:
        sink = sinks.get(sink_name)
        if sink is None:
            log.warning("sink_not_enabled", table=contract.fqn, sink=sink_name)
            continue

        upsert_result = sink.write_upserts(contract, upserts_typed)
        delete_result = sink.write_deletes(contract, deletes_typed)
        results.extend([upsert_result, delete_result])

        # Emit per-(table, sink) metrics
        metrics.emit(
            "CdcRowsUpserted",
            upsert_result.upserted,
            dimensions={"Table": contract.fqn, "Sink": sink_name},
        )
        metrics.emit(
            "CdcRowsDeleted",
            delete_result.deleted,
            dimensions={"Table": contract.fqn, "Sink": sink_name},
        )

    log.info(
        "table_processing_complete",
        table=contract.fqn,
        total_events=total,
        results=[{"sink": r.sink, "upserted": r.upserted, "deleted": r.deleted} for r in results],
    )
    return results


def main(args: dict) -> int:
    configure_logging(level="INFO", fmt="json")
    log = get_logger(__name__, job=args["JOB_NAME"], batch_id=args["batch_id"])

    cfg = load_config(args["config_path"]) if not args["config_path"].startswith("s3://") \
        else _load_s3_config(args["config_path"])

    spark = _build_spark(args["JOB_NAME"])
    metrics = MetricsEmitter(
        namespace=cfg.get("metrics_namespace", "CDC/Glue"),
        region=cfg.get("aws_region", "ap-south-1"),
    )
    tracker = IdempotencyTracker(
        table_name=cfg["idempotency_table"],
        region=cfg.get("aws_region", "ap-south-1"),
    )

    if tracker.is_processed(args["JOB_NAME"], args["batch_id"]):
        log.info("batch_already_processed")
        return 0

    tracker.mark_started(args["JOB_NAME"], args["batch_id"])

    total_upserts = 0
    total_deletes = 0
    any_errors = False

    try:
        enabled_sinks = cfg.get("enabled_sinks", ["redshift", "postgres", "opensearch"])
        sinks = build_sinks(cfg, enabled_sinks)

        # Connect all sinks up front — fail fast
        for s in sinks.values():
            s.connect()

        try:
            for fqn, contract in TABLE_CONTRACTS.items():
                results = process_table(
                    spark, args["raw_s3_path"], contract, sinks, metrics, log
                )
                for r in results:
                    total_upserts += r.upserted
                    total_deletes += r.deleted
                    if not r.success:
                        any_errors = True
                        log.error("sink_write_errors", sink=r.sink, errors=r.errors)
        finally:
            for s in sinks.values():
                s.close()

        if any_errors:
            tracker.mark_failed(
                args["JOB_NAME"], args["batch_id"], "One or more sinks had errors"
            )
            return 2

        tracker.mark_succeeded(
            args["JOB_NAME"],
            args["batch_id"],
            row_count=total_upserts + total_deletes,
        )
        log.info(
            "job_complete",
            total_upserts=total_upserts,
            total_deletes=total_deletes,
        )
        return 0

    except Exception as exc:
        log.error("job_failed", error=str(exc), traceback=traceback.format_exc())
        tracker.mark_failed(args["JOB_NAME"], args["batch_id"], str(exc))
        return 1


def _load_s3_config(s3_path: str) -> dict:
    """Load YAML config from S3."""
    import boto3
    import yaml as pyyaml

    bucket, *rest = s3_path.replace("s3://", "").split("/", 1)
    key = rest[0]
    obj = boto3.client("s3").get_object(Bucket=bucket, Key=key)
    return pyyaml.safe_load(obj["Body"].read())


def _build_spark(job_name: str):
    """Build a SparkSession. Uses GlueContext inside Glue, plain Spark locally."""
    if _IN_GLUE:
        sc = SparkContext.getOrCreate()
        glue_context = GlueContext(sc)
        spark = glue_context.spark_session
        job = Job(glue_context)
        job.init(job_name, {})
        return spark
    # Local fallback
    from src.utils.spark_session import get_spark_session
    return get_spark_session(app_name=job_name, master="local[*]")


if __name__ == "__main__":
    if _IN_GLUE:
        args = getResolvedOptions(sys.argv, REQUIRED_ARGS)
    else:
        # Local invocation: parse from sys.argv
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--JOB_NAME", default="cdc-local")
        parser.add_argument("--raw_s3_path", required=True)
        parser.add_argument("--config_path", required=True)
        parser.add_argument("--batch_id", required=True)
        parsed = parser.parse_args()
        args = vars(parsed)

    sys.exit(main(args))
