"""Unit tests for table contracts and schema module."""

from __future__ import annotations

import pytest

from src.schemas.contracts import TABLE_CONTRACTS, contracts_for_sink, get_contract

pytestmark = pytest.mark.unit


def test_all_contracts_have_primary_keys():
    for fqn, contract in TABLE_CONTRACTS.items():
        assert contract.primary_keys, f"{fqn} missing primary_keys"


def test_all_contracts_have_at_least_one_sink():
    for fqn, contract in TABLE_CONTRACTS.items():
        assert contract.sinks, f"{fqn} has no sinks configured"


def test_get_contract_returns_none_for_unknown():
    assert get_contract("unknown", "table") is None


def test_get_contract_returns_known():
    contract = get_contract("sales", "customers")
    assert contract is not None
    assert contract.table_name == "customers"
    assert "customer_id" in contract.primary_keys


def test_contracts_for_sink_filters_correctly():
    opensearch_contracts = contracts_for_sink("opensearch")
    assert len(opensearch_contracts) >= 1
    # products is the only table indexed in OpenSearch
    assert any(c.table_name == "products" for c in opensearch_contracts)


def test_scd2_contracts_have_valid_attributes():
    scd2_contracts = [c for c in TABLE_CONTRACTS.values() if c.scd2]
    for c in scd2_contracts:
        assert c.attribute_columns, f"{c.fqn} is SCD2 but has no attribute_columns"
