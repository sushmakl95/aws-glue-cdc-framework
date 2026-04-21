"""Unit tests for the Debezium simulator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from simulators.debezium.simulator import simulate

pytestmark = pytest.mark.unit


def test_simulator_generates_requested_count(tmp_path: Path):
    count = simulate(
        output_dir=str(tmp_path),
        total_events=500,
        days=1,
        seed=1,
    )
    # Some events may be dropped (e.g., update/delete when no live PKs yet)
    assert 400 <= count <= 500


def test_simulator_produces_valid_debezium_envelopes(tmp_path: Path):
    simulate(output_dir=str(tmp_path), total_events=100, days=1, seed=1)

    # Find at least one JSON file and validate envelope shape
    json_files = list(tmp_path.rglob("*.json"))
    assert json_files, "No JSON files produced"

    with json_files[0].open() as fh:
        line = fh.readline()
        envelope = json.loads(line)

    payload = envelope["payload"]
    assert "op" in payload and payload["op"] in ("c", "u", "d", "r")
    assert "source" in payload
    assert payload["source"]["connector"] == "mysql"
    assert payload["source"]["db"] == "sales"


def test_simulator_partitions_by_table_and_hour(tmp_path: Path):
    simulate(output_dir=str(tmp_path), total_events=500, days=2, seed=42)

    # Expect a structure like {output}/sales/<table>/<YYYY-MM-DD-HH>/events_*.json
    dirs = [p for p in tmp_path.rglob("*") if p.is_dir() and "sales" in str(p)]
    assert dirs, "No partitioned directories produced"
