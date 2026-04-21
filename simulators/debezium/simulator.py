"""Pure-Python Debezium CDC event simulator.

Generates events in the exact Debezium envelope format the real connector emits.
Used for local dev + CI — no Docker, Kafka, or MySQL required.

Writes one JSONL file per (db, table, hour) partition, matching the layout
Kinesis Firehose produces in production.
"""

from __future__ import annotations

import argparse
import json
import random
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from faker import Faker

fake = Faker()

# -----------------------------------------------------------------------------
# Table generators — each returns (primary_key_values, attribute_dict)
# -----------------------------------------------------------------------------
def _gen_customer(customer_id: int) -> tuple[dict, dict]:
    pk = {"customer_id": customer_id}
    attrs = {
        "email": fake.email(),
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "country": fake.country_code(),
        "tier": random.choice(["bronze", "silver", "gold", "platinum"]),
        "created_at": fake.date_time_this_year().isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    return pk, {**pk, **attrs}


def _gen_order(order_id: int, max_customer_id: int) -> tuple[dict, dict]:
    pk = {"order_id": order_id}
    attrs = {
        "customer_id": random.randint(1, max_customer_id),
        "order_status": random.choice(["placed", "paid", "shipped", "delivered", "cancelled"]),
        "total_amount": round(random.uniform(10.0, 2500.0), 2),
        "currency": random.choice(["USD", "EUR", "INR", "GBP"]),
        "placed_at": fake.date_time_this_year().isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    return pk, {**pk, **attrs}


def _gen_product(product_id: int) -> tuple[dict, dict]:
    pk = {"product_id": product_id}
    attrs = {
        "sku": f"SKU-{product_id:08d}",
        "name": fake.catch_phrase(),
        "description": fake.text(max_nb_chars=150),
        "category": random.choice(["electronics", "apparel", "books", "home", "sports"]),
        "price": round(random.uniform(5.0, 500.0), 2),
        "is_active": random.random() > 0.05,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    return pk, {**pk, **attrs}


def _gen_order_item(order_id: int, line_item_id: int) -> tuple[dict, dict]:
    pk = {"order_id": order_id, "line_item_id": line_item_id}
    attrs = {
        "product_id": random.randint(1, 500),
        "quantity": random.randint(1, 5),
        "unit_price": round(random.uniform(10.0, 200.0), 2),
        "discount": round(random.uniform(0.0, 0.3), 2),
    }
    return pk, {**pk, **attrs}


TABLE_GENERATORS = {
    "customers": _gen_customer,
    "orders": _gen_order,
    "products": _gen_product,
    "order_items": _gen_order_item,
}


# -----------------------------------------------------------------------------
# Debezium envelope builder
# -----------------------------------------------------------------------------
def _make_envelope(
    db: str,
    table: str,
    op: str,
    before: dict | None,
    after: dict | None,
    ts: datetime,
    pos: int,
    is_snapshot: bool = False,
) -> dict:
    """Produce a Debezium-formatted envelope."""
    return {
        "payload": {
            "before": {k: str(v) for k, v in before.items()} if before else None,
            "after": {k: str(v) for k, v in after.items()} if after else None,
            "source": {
                "connector": "mysql",
                "db": db,
                "table": table,
                "ts_ms": int(ts.timestamp() * 1000) - random.randint(10, 100),
                "snapshot": "true" if is_snapshot else "false",
                "version": "1.9.7.Final",
                "file": "mysql-bin.000001",
                "pos": pos,
                "server_id": 223344,
            },
            "op": op,
            "ts_ms": int(ts.timestamp() * 1000),
        }
    }


# -----------------------------------------------------------------------------
# Simulator
# -----------------------------------------------------------------------------
def simulate(
    output_dir: str = "data/cdc_events",
    total_events: int = 10_000,
    customer_count: int = 200,
    product_count: int = 500,
    days: int = 3,
    delete_rate: float = 0.02,
    update_rate: float = 0.30,
    seed: int = 42,
) -> int:
    """Generate `total_events` Debezium events bucketed by hour.

    Returns the number of events generated.
    """
    random.seed(seed)
    Faker.seed(seed)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    end = datetime.now(UTC).replace(microsecond=0, second=0)
    start = end - timedelta(days=days)
    total_seconds = int((end - start).total_seconds())

    # Keep track of live PKs per table so we can UPDATE/DELETE them
    live_pks: dict[str, list[dict]] = {
        "customers": [],
        "orders": [],
        "products": [],
        "order_items": [],
    }

    buckets: dict[tuple[str, str], list[dict]] = {}
    pos_counter = 0
    order_id_counter = 0
    line_item_counter = 0

    for _ in range(total_events):
        table = random.choices(
            list(TABLE_GENERATORS.keys()), weights=[0.15, 0.35, 0.10, 0.40]
        )[0]
        op = _choose_op(table, live_pks, delete_rate, update_rate)
        ts = start + timedelta(seconds=random.randint(0, total_seconds))

        before: dict | None = None
        after: dict | None = None

        if op == "c":
            if table == "customers":
                pk, row = _gen_customer(len(live_pks[table]) + 1)
            elif table == "orders":
                order_id_counter += 1
                pk, row = _gen_order(order_id_counter, max(1, len(live_pks["customers"])))
            elif table == "products":
                pk, row = _gen_product(len(live_pks[table]) + 1)
            else:  # order_items
                line_item_counter += 1
                existing_orders = live_pks["orders"]
                order_id = (
                    random.choice(existing_orders)["order_id"]
                    if existing_orders
                    else order_id_counter or 1
                )
                pk, row = _gen_order_item(order_id, line_item_counter)
            after = row
            live_pks[table].append(pk)
        elif op == "u":
            if not live_pks[table]:
                continue
            existing = random.choice(live_pks[table])
            if table == "customers":
                _, before_row = _gen_customer(existing["customer_id"])
                _, after_row = _gen_customer(existing["customer_id"])
            elif table == "orders":
                _, before_row = _gen_order(existing["order_id"], 100)
                _, after_row = _gen_order(existing["order_id"], 100)
            elif table == "products":
                _, before_row = _gen_product(existing["product_id"])
                _, after_row = _gen_product(existing["product_id"])
            else:
                _, before_row = _gen_order_item(existing["order_id"], existing["line_item_id"])
                _, after_row = _gen_order_item(existing["order_id"], existing["line_item_id"])
            before, after = before_row, after_row
        else:  # d
            if not live_pks[table]:
                continue
            existing = live_pks[table].pop(random.randrange(len(live_pks[table])))
            # For simplicity, reconstruct the row as `before`
            if table == "customers":
                _, before = _gen_customer(existing["customer_id"])
            elif table == "orders":
                _, before = _gen_order(existing["order_id"], 100)
            elif table == "products":
                _, before = _gen_product(existing["product_id"])
            else:
                _, before = _gen_order_item(existing["order_id"], existing["line_item_id"])

        pos_counter += 1
        envelope = _make_envelope(
            db="sales",
            table=table,
            op=op,
            before=before,
            after=after,
            ts=ts,
            pos=pos_counter,
        )

        # Bucket by (db, table, hour)
        hour_key = ts.strftime("%Y-%m-%d-%H")
        buckets.setdefault((table, hour_key), []).append(envelope)

    # Write partitions
    count = 0
    for (table, hour_key), envelopes in buckets.items():
        dir_path = output_path / "sales" / table / hour_key
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / f"events_{uuid.uuid4().hex[:10]}.json"
        with file_path.open("w", encoding="utf-8") as fh:
            for env in envelopes:
                fh.write(json.dumps(env) + "\n")
        count += len(envelopes)

    return count


def _choose_op(table: str, live_pks: dict, delete_rate: float, update_rate: float) -> str:
    """Weighted op choice, biased toward having data to work with."""
    if not live_pks[table]:
        return "c"
    r = random.random()
    if r < delete_rate:
        return "d"
    if r < delete_rate + update_rate:
        return "u"
    return "c"


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate Debezium CDC events")
    parser.add_argument("--output-dir", default="data/cdc_events")
    parser.add_argument("--events", type=int, default=10_000)
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    count = simulate(
        output_dir=args.output_dir,
        total_events=args.events,
        days=args.days,
        seed=args.seed,
    )
    print(f"Generated {count:,} CDC events into {args.output_dir}")


if __name__ == "__main__":
    main()
