"""CDC event parsing and routing."""

from src.cdc.parser import deduplicate_by_latest, flatten_envelope, read_debezium_events
from src.cdc.router import RoutedBatch, explode_map_to_columns, route_by_op

__all__ = [
    "RoutedBatch",
    "deduplicate_by_latest",
    "explode_map_to_columns",
    "flatten_envelope",
    "read_debezium_events",
    "route_by_op",
]
