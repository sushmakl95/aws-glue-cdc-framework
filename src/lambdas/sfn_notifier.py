"""Lambda: Step Functions state change → SNS notification.

Triggered by EventBridge rule filtering on `aws.states` events for our state
machine. Sends formatted SNS messages for SUCCESS / FAILED / TIMED_OUT states.
"""

from __future__ import annotations

import json
import os
from typing import Any

import boto3

SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]

sns = boto3.client("sns")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    detail = event.get("detail", {})
    status = detail.get("status", "UNKNOWN")
    execution_arn = detail.get("executionArn", "unknown")
    input_data = detail.get("input", "{}")

    try:
        parsed_input = json.loads(input_data)
    except json.JSONDecodeError:
        parsed_input = {}

    subject = f"[CDC Pipeline] Step Functions {status}"
    body_lines = [
        f"Status: {status}",
        f"Execution: {execution_arn}",
        f"Batch ID: {parsed_input.get('batch_id', 'n/a')}",
        f"Trigger: {parsed_input.get('trigger', 'n/a')}",
    ]

    if status == "FAILED":
        cause = detail.get("cause", "")
        body_lines.append(f"Cause: {cause[:500]}")

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=subject[:100],
        Message="\n".join(body_lines),
    )
    return {"statusCode": 200, "body": json.dumps({"notified": True, "status": status})}
