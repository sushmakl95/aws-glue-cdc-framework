"""Lambda: S3 PUT event → trigger Step Functions state machine.

Wired as an S3 bucket notification on the raw CDC path. When Firehose delivers
a new file, this Lambda starts a Step Functions execution that runs the Glue job.

Payload (S3 event):
{
  "Records": [
    {
      "eventName": "ObjectCreated:Put",
      "s3": {
        "bucket": {"name": "..."},
        "object": {"key": "cdc/raw/sales/orders/2026/04/21/..."}
      }
    }
  ]
}
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import boto3

STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]
MIN_BATCH_INTERVAL_SECONDS = int(os.environ.get("MIN_BATCH_INTERVAL_SECONDS", "60"))

sfn = boto3.client("stepfunctions")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    records = event.get("Records", [])
    if not records:
        return {"statusCode": 200, "body": "no records"}

    # Deduplicate by prefix — if 10 files land in the same table/hour we only
    # want one Step Functions execution, not 10.
    prefixes: set[str] = set()
    for rec in records:
        key = rec.get("s3", {}).get("object", {}).get("key", "")
        if not key:
            continue
        # cdc/raw/<db>/<table>/<hour>/...  → cdc/raw/<db>/<table>/<hour>/
        parts = key.split("/")[:5]
        prefixes.add("/".join(parts) + "/")

    started: list[str] = []
    for prefix in prefixes:
        batch_id = uuid.uuid4().hex[:16]
        execution_name = f"s3-{batch_id}"
        input_payload = {
            "batch_id": batch_id,
            "raw_prefix": prefix,
            "trigger": "s3_event",
        }
        try:
            resp = sfn.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=execution_name,
                input=json.dumps(input_payload),
            )
            started.append(resp["executionArn"])
        except sfn.exceptions.ExecutionAlreadyExists:
            # Race: another instance already fired on the same prefix. Safe to skip.
            pass

    return {
        "statusCode": 200,
        "body": json.dumps({"started": started, "count": len(started)}),
    }
