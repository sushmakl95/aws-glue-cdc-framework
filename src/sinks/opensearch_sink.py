"""OpenSearch sink — indexed mirror for full-text search use cases.

Why OpenSearch?
- Product catalog search requires inverted-index + relevance scoring
- Postgres/Redshift are poor at multi-field prefix/fuzzy search at scale
- OpenSearch bulk API handles 5k-doc batches with low latency

Delete semantics:
- Physical: we call delete_by_id
- Soft: we index the doc with `deleted_at` populated; queries filter it out
"""

from __future__ import annotations

from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from pyspark.sql import DataFrame

from src.schemas.contracts import TableContract
from src.sinks.base import Sink, SinkWriteResult
from src.utils.logging_config import get_logger
from src.utils.secrets import get_secret

log = get_logger(__name__, sink="opensearch")


class OpenSearchSink(Sink):
    """OpenSearch bulk-index writer."""

    def __init__(
        self,
        secret_id: str,
        endpoint: str,
        index_prefix: str = "cdc",
        region: str = "ap-south-1",
        chunk_size: int = 500,
    ):
        self.secret_id = secret_id
        self.endpoint = endpoint
        self.index_prefix = index_prefix
        self.region = region
        self.chunk_size = chunk_size
        self._client: OpenSearch | None = None

    @property
    def name(self) -> str:
        return "opensearch"

    def _index_name(self, contract: TableContract) -> str:
        return f"{self.index_prefix}-{contract.db_name}-{contract.table_name}"

    def connect(self) -> None:
        creds = get_secret(self.secret_id, region=self.region)
        self._client = OpenSearch(
            hosts=[{"host": self.endpoint, "port": 443}],
            http_auth=(creds["username"], creds["password"]),
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )
        # Quick ping to fail fast on auth / network issues
        if not self._client.ping():
            raise RuntimeError("OpenSearch ping failed — check credentials/endpoint")
        log.info("opensearch_connected", endpoint=self.endpoint)

    def close(self) -> None:
        self._client = None

    def write_upserts(
        self, contract: TableContract, df: DataFrame
    ) -> SinkWriteResult:
        if df.rdd.isEmpty():
            return SinkWriteResult(sink=self.name, table=contract.fqn)

        index = self._index_name(contract)
        self._ensure_index(index)

        rows = df.collect()
        if not rows:
            return SinkWriteResult(sink=self.name, table=contract.fqn)

        def _actions():
            for row in rows:
                doc_id = "|".join(str(row[pk]) for pk in contract.primary_keys)
                doc = {c: row[c] for c in contract.attribute_columns if c in row}
                # Preserve primary key columns in the document
                for pk in contract.primary_keys:
                    doc[pk] = row[pk]
                yield {
                    "_op_type": "index",
                    "_index": index,
                    "_id": doc_id,
                    "_source": doc,
                }

        try:
            assert self._client is not None
            success, errors = helpers.bulk(
                self._client,
                _actions(),
                chunk_size=self.chunk_size,
                raise_on_error=False,
            )
            if errors:
                log.warning("opensearch_partial_errors", count=len(errors))
                return SinkWriteResult(
                    sink=self.name,
                    table=contract.fqn,
                    upserted=success,
                    errors=[str(e) for e in errors[:3]],
                )
            return SinkWriteResult(sink=self.name, table=contract.fqn, upserted=success)
        except Exception as exc:
            log.error("opensearch_upsert_failed", index=index, error=str(exc))
            return SinkWriteResult(
                sink=self.name, table=contract.fqn, errors=[str(exc)]
            )

    def write_deletes(
        self, contract: TableContract, df: DataFrame
    ) -> SinkWriteResult:
        if df.rdd.isEmpty():
            return SinkWriteResult(sink=self.name, table=contract.fqn)

        index = self._index_name(contract)
        rows = df.collect()
        if not rows:
            return SinkWriteResult(sink=self.name, table=contract.fqn)

        def _delete_actions():
            for row in rows:
                doc_id = "|".join(str(row[pk]) for pk in contract.primary_keys)
                yield {
                    "_op_type": "delete",
                    "_index": index,
                    "_id": doc_id,
                }

        try:
            assert self._client is not None
            success, errors = helpers.bulk(
                self._client,
                _delete_actions(),
                chunk_size=self.chunk_size,
                raise_on_error=False,
            )
            return SinkWriteResult(
                sink=self.name,
                table=contract.fqn,
                deleted=success,
                errors=[str(e) for e in errors[:3]] if errors else [],
            )
        except Exception as exc:
            log.error("opensearch_delete_failed", index=index, error=str(exc))
            return SinkWriteResult(
                sink=self.name, table=contract.fqn, errors=[str(exc)]
            )

    def _ensure_index(self, index: str) -> None:
        """Create the index with basic settings if it doesn't exist."""
        assert self._client is not None
        if not self._client.indices.exists(index=index):
            self._client.indices.create(
                index=index,
                body={
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 1,
                        "refresh_interval": "5s",
                    }
                },
            )
            log.info("opensearch_index_created", index=index)
