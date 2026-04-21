"""AWS Secrets Manager client with in-process caching.

Why cached?
- Secrets Manager API calls cost money per call
- In a Glue job with thousands of micro-batches, re-fetching the same credential
  is wasteful and adds latency
- The cache is process-local (no Redis needed); invalidated on job restart

Usage:
    from src.utils.secrets import get_secret

    creds = get_secret("prod/mysql/sales-db")
    # creds is a dict: {"username": "...", "password": "...", "host": "..."}
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.utils.logging_config import get_logger

log = get_logger(__name__)


@lru_cache(maxsize=64)
def get_secret(secret_id: str, region: str = "ap-south-1") -> dict[str, Any]:
    """Fetch and parse a JSON secret from Secrets Manager.

    Raises:
        RuntimeError: if the secret cannot be retrieved or is not valid JSON.
    """
    client = boto3.client("secretsmanager", region_name=region)

    try:
        response = client.get_secret_value(SecretId=secret_id)
    except ClientError as exc:
        log.error("secret_fetch_failed", secret_id=secret_id, error=str(exc))
        raise RuntimeError(f"Failed to fetch secret {secret_id}: {exc}") from exc

    raw = response.get("SecretString")
    if raw is None:
        raise RuntimeError(f"Secret {secret_id} has no SecretString (binary not supported)")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Secret {secret_id} is not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError(f"Secret {secret_id} did not parse to a dict")

    log.info("secret_fetched", secret_id=secret_id, keys=list(parsed.keys()))
    return parsed


def clear_cache() -> None:
    """Clear the in-process secret cache (use after rotation events)."""
    get_secret.cache_clear()
