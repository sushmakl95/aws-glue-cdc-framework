"""SparkSession factory for Glue job local dev.

Glue 4.0 provides `SparkContext`, `GlueContext`, and `SparkSession` automatically
inside the Glue runtime. For local dev (pytest, manual runs), we construct
equivalents here.
"""

from __future__ import annotations

from typing import Any

from pyspark.sql import SparkSession


def get_spark_session(
    app_name: str = "aws-glue-cdc-framework",
    master: str | None = None,
    configs: dict[str, Any] | None = None,
) -> SparkSession:
    """Return a SparkSession. Reuses an existing one if available."""
    active = SparkSession.getActiveSession()
    if active is not None:
        return active

    builder = SparkSession.builder.appName(app_name)
    if master:
        builder = builder.master(master)
    if configs:
        for key, value in configs.items():
            builder = builder.config(key, str(value))
    return builder.getOrCreate()
