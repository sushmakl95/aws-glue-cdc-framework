"""Base sink abstraction.

Every sink implements a narrow contract:
- connect()      — establish/reuse a connection
- write_upserts() — apply c/u/r events
- write_deletes() — apply d events (either physical delete or soft-delete)
- close()        — cleanup

The Glue job iterates through enabled sinks for each table contract, calling
these methods. This pattern means adding a new sink (e.g., Snowflake, Mongo)
requires only a new class — no changes to the Glue job.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from pyspark.sql import DataFrame

from src.schemas.contracts import TableContract


@dataclass
class SinkWriteResult:
    """Outcome of writing a batch to a single sink."""

    sink: str
    table: str
    upserted: int = 0
    deleted: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class Sink(ABC):
    """Abstract sink — all target-specific writers extend this."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier (e.g., 'redshift', 'postgres')."""

    @abstractmethod
    def connect(self) -> None:
        """Establish any required connections / prepare DDL."""

    @abstractmethod
    def write_upserts(
        self, contract: TableContract, df: DataFrame
    ) -> SinkWriteResult:
        """Write create/update/read events."""

    @abstractmethod
    def write_deletes(
        self, contract: TableContract, df: DataFrame
    ) -> SinkWriteResult:
        """Write delete events (physical or soft)."""

    @abstractmethod
    def close(self) -> None:
        """Release resources."""

    def __enter__(self) -> Sink:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
