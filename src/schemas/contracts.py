"""Table-specific CDC contracts.

A 'contract' defines a source table's:
- Primary key column(s)
- Business attribute columns
- Soft-delete behavior (physical DELETE vs logical deleted_at)
- Target mapping (which sinks this table fans out to)

Adding a new CDC'd table = adding a new TableContract entry here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SinkTarget = Literal["redshift", "postgres", "opensearch"]


@dataclass(frozen=True)
class TableContract:
    """Contract for one source table."""

    db_name: str
    table_name: str
    primary_keys: tuple[str, ...]
    attribute_columns: tuple[str, ...]
    sinks: tuple[SinkTarget, ...]
    soft_delete: bool = False
    scd2: bool = False
    description: str = ""

    @property
    def fqn(self) -> str:
        """Fully qualified name: `db.table`."""
        return f"{self.db_name}.{self.table_name}"


# -----------------------------------------------------------------------------
# Table registry — explicit, committed contracts
# -----------------------------------------------------------------------------
TABLE_CONTRACTS: dict[str, TableContract] = {
    "sales.customers": TableContract(
        db_name="sales",
        table_name="customers",
        primary_keys=("customer_id",),
        attribute_columns=(
            "email",
            "first_name",
            "last_name",
            "country",
            "tier",
            "created_at",
            "updated_at",
        ),
        sinks=("redshift", "postgres"),
        scd2=True,  # preserve tier changes over time
        description="Customer master — SCD2 on dimensional changes",
    ),
    "sales.orders": TableContract(
        db_name="sales",
        table_name="orders",
        primary_keys=("order_id",),
        attribute_columns=(
            "customer_id",
            "order_status",
            "total_amount",
            "currency",
            "placed_at",
            "updated_at",
        ),
        sinks=("redshift", "postgres"),
        scd2=False,  # current-state fact, not dimension
        description="Order header — upsert on primary key",
    ),
    "sales.order_items": TableContract(
        db_name="sales",
        table_name="order_items",
        primary_keys=("order_id", "line_item_id"),
        attribute_columns=("product_id", "quantity", "unit_price", "discount"),
        sinks=("redshift",),
        scd2=False,
        description="Order line items — composite PK, upsert only",
    ),
    "sales.products": TableContract(
        db_name="sales",
        table_name="products",
        primary_keys=("product_id",),
        attribute_columns=(
            "sku",
            "name",
            "description",
            "category",
            "price",
            "is_active",
            "updated_at",
        ),
        sinks=("redshift", "postgres", "opensearch"),
        soft_delete=True,
        scd2=False,
        description="Product catalog — also indexed in OpenSearch for search",
    ),
}


def get_contract(db: str, table: str) -> TableContract | None:
    """Fetch a table contract by (db, table). Returns None if unknown."""
    return TABLE_CONTRACTS.get(f"{db}.{table}")


def contracts_for_sink(sink: SinkTarget) -> list[TableContract]:
    """All contracts that fan out to a given sink."""
    return [c for c in TABLE_CONTRACTS.values() if sink in c.sinks]
