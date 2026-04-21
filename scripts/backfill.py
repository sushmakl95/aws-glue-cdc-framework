"""Historical backfill — replay CDC events for a date range.

Usage:
    python scripts/backfill.py --config config/prod.yaml \\
        --start 2026-03-01 --end 2026-03-31 \\
        --tables sales.orders,sales.customers
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta


def main() -> int:
    parser = argparse.ArgumentParser(description="CDC historical backfill")
    parser.add_argument("--config", required=True)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--tables",
        default="",
        help="Comma-separated list of db.table to backfill (default: all)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from src.glue_jobs.cdc_to_sinks import main as glue_main

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    if end < start:
        print("[error] end date before start date", file=sys.stderr)
        return 1

    dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    print(f"Backfill plan: {len(dates)} days from {start} to {end}")

    if args.dry_run:
        for d in dates:
            print(f"  would process: {d}")
        return 0

    tables = args.tables.split(",") if args.tables else []
    rc_total = 0
    for d in dates:
        for hour in range(24):
            raw_prefix = f"cdc/raw/<db>/<table>/{d.strftime('%Y/%m/%d')}/{hour:02d}/"
            batch_id = f"backfill-{d}-{hour:02d}-{uuid.uuid4().hex[:6]}"
            print(f"Processing {d} {hour:02d}:00 batch={batch_id}")
            gargs = {
                "JOB_NAME": "cdc-backfill",
                "raw_s3_path": raw_prefix,
                "config_path": args.config,
                "batch_id": batch_id,
            }
            rc = glue_main(gargs)
            if rc != 0:
                print(f"[warn] batch {batch_id} failed, continuing")
                rc_total += 1

    print(f"Backfill complete. {rc_total} batches had errors.")
    return 0 if rc_total == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
