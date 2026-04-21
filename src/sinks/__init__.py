"""Target sink writers — Redshift, Postgres, OpenSearch."""

from src.sinks.base import Sink, SinkWriteResult
from src.sinks.opensearch_sink import OpenSearchSink
from src.sinks.postgres_sink import PostgresSink
from src.sinks.redshift_sink import RedshiftSink

__all__ = [
    "OpenSearchSink",
    "PostgresSink",
    "RedshiftSink",
    "Sink",
    "SinkWriteResult",
]
