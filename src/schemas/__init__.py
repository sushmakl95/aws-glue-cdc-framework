"""Typed schemas and table contracts for CDC processing."""

from src.schemas.contracts import (
    TABLE_CONTRACTS,
    SinkTarget,
    TableContract,
    contracts_for_sink,
    get_contract,
)
from src.schemas.debezium import (
    CDC_FLATTENED_SCHEMA,
    DEBEZIUM_ENVELOPE_SCHEMA,
    DEBEZIUM_PAYLOAD_SCHEMA,
    DEBEZIUM_SOURCE_SCHEMA,
)

__all__ = [
    "CDC_FLATTENED_SCHEMA",
    "DEBEZIUM_ENVELOPE_SCHEMA",
    "DEBEZIUM_PAYLOAD_SCHEMA",
    "DEBEZIUM_SOURCE_SCHEMA",
    "TABLE_CONTRACTS",
    "SinkTarget",
    "TableContract",
    "contracts_for_sink",
    "get_contract",
]
