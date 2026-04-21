"""Idempotency tracker backed by DynamoDB.

Why DynamoDB (not Delta/S3 like Repo #1)?
- CDC jobs run in AWS Glue, not on Spark-with-Delta
- DynamoDB offers conditional-write primitives ideal for idempotency
- Single-digit-ms latency; scales horizontally
- IAM-integrated; no bespoke auth

Tracker record:
    pk = f"{job_name}#{batch_id}"
    status = STARTED | SUCCESS | FAILED
    started_at, completed_at, row_count, error_message
    ttl = now + 30 days (auto-cleanup)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import boto3
from botocore.exceptions import ClientError

from src.utils.logging_config import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class BatchStatus:
    batch_id: str
    job_name: str
    status: str
    started_at: str
    completed_at: str | None
    row_count: int | None
    error_message: str | None


class IdempotencyTracker:
    """DynamoDB-backed idempotency + audit log."""

    def __init__(self, table_name: str, region: str = "ap-south-1"):
        self.table_name = table_name
        self.table = boto3.resource("dynamodb", region_name=region).Table(table_name)

    def _pk(self, job_name: str, batch_id: str) -> str:
        return f"{job_name}#{batch_id}"

    def is_processed(self, job_name: str, batch_id: str) -> bool:
        """Return True if this batch has already completed successfully."""
        try:
            resp = self.table.get_item(Key={"pk": self._pk(job_name, batch_id)})
        except ClientError as exc:
            log.warning("idempotency_check_failed", error=str(exc))
            return False

        item = resp.get("Item")
        return item is not None and item.get("status") == "SUCCESS"

    def mark_started(self, job_name: str, batch_id: str) -> str:
        """Insert STARTED record. Raises if batch already exists."""
        now = datetime.now(UTC).isoformat()
        ttl = int((datetime.now(UTC) + timedelta(days=30)).timestamp())
        try:
            self.table.put_item(
                Item={
                    "pk": self._pk(job_name, batch_id),
                    "job_name": job_name,
                    "batch_id": batch_id,
                    "status": "STARTED",
                    "started_at": now,
                    "ttl": ttl,
                },
                ConditionExpression="attribute_not_exists(pk)",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise RuntimeError(f"Batch {batch_id} already started for job {job_name}") from exc
            raise
        return now

    def mark_succeeded(self, job_name: str, batch_id: str, row_count: int) -> None:
        now = datetime.now(UTC).isoformat()
        self.table.update_item(
            Key={"pk": self._pk(job_name, batch_id)},
            UpdateExpression="SET #s = :s, completed_at = :c, row_count = :r",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "SUCCESS", ":c": now, ":r": row_count},
        )

    def mark_failed(self, job_name: str, batch_id: str, error: str) -> None:
        now = datetime.now(UTC).isoformat()
        self.table.update_item(
            Key={"pk": self._pk(job_name, batch_id)},
            UpdateExpression="SET #s = :s, completed_at = :c, error_message = :e",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "FAILED", ":c": now, ":e": error[:1000]},
        )

    def wait_for_completion(
        self, job_name: str, batch_id: str, timeout_seconds: int = 300, poll_interval: int = 5
    ) -> BatchStatus:
        """Poll DynamoDB until the batch is SUCCESS or FAILED (used by Step Functions)."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            resp = self.table.get_item(Key={"pk": self._pk(job_name, batch_id)})
            item = resp.get("Item") or {}
            status = item.get("status")
            if status in ("SUCCESS", "FAILED"):
                return BatchStatus(
                    batch_id=batch_id,
                    job_name=job_name,
                    status=status,
                    started_at=item.get("started_at", ""),
                    completed_at=item.get("completed_at"),
                    row_count=item.get("row_count"),
                    error_message=item.get("error_message"),
                )
            time.sleep(poll_interval)
        raise TimeoutError(f"Batch {batch_id} did not complete within {timeout_seconds}s")
