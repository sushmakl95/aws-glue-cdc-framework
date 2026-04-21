"""CloudWatch custom metrics emitter.

Why custom metrics vs Glue built-in?
- Glue built-in metrics capture infrastructure (DPU, runtime).
- Business metrics (rows processed per table, DQ failure rate, CDC lag)
  aren't exposed by Glue — we emit them as custom metrics so CloudWatch
  alarms can page on business-level issues.
"""

from __future__ import annotations

import boto3

from src.utils.logging_config import get_logger

log = get_logger(__name__)


class MetricsEmitter:
    """Thin wrapper over CloudWatch PutMetricData."""

    def __init__(self, namespace: str, region: str = "ap-south-1"):
        self.namespace = namespace
        self.client = boto3.client("cloudwatch", region_name=region)

    def emit(
        self,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: dict[str, str] | None = None,
    ) -> None:
        """Send a single metric datum."""
        dim_list = [{"Name": k, "Value": v} for k, v in (dimensions or {}).items()]
        try:
            self.client.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        "MetricName": metric_name,
                        "Value": value,
                        "Unit": unit,
                        "Dimensions": dim_list,
                    }
                ],
            )
        except Exception as exc:
            # Never fail a job just because metrics couldn't send
            log.warning("metric_emit_failed", metric=metric_name, error=str(exc))

    def emit_batch(self, data: list[dict]) -> None:
        """Send up to 20 metrics at once (CloudWatch batch limit)."""
        try:
            for chunk_start in range(0, len(data), 20):
                chunk = data[chunk_start : chunk_start + 20]
                self.client.put_metric_data(Namespace=self.namespace, MetricData=chunk)
        except Exception as exc:
            log.warning("metric_batch_emit_failed", error=str(exc))
