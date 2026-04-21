"""Unified CLI: `cdc-glue [simulate|run|validate]`."""

from __future__ import annotations

import sys

import click


@click.group()
@click.version_option(version="1.0.0")
def cli() -> None:
    """AWS Glue CDC Framework CLI."""


@cli.command()
@click.option("--output-dir", default="data/cdc_events", help="Where to write simulated events")
@click.option("--events", default=10_000, type=int, help="Total events to generate")
@click.option("--seed", default=42, type=int)
def simulate(output_dir: str, events: int, seed: int) -> None:
    """Generate synthetic Debezium CDC events for local testing."""
    from simulators.debezium.simulator import simulate as run_sim

    count = run_sim(output_dir=output_dir, total_events=events, seed=seed)
    click.echo(f"Generated {count:,} events into {output_dir}")


@cli.command()
@click.option("--raw-path", required=True, help="Root path of CDC events (local or s3://)")
@click.option("--config", required=True, type=click.Path(exists=True))
@click.option("--batch-id", default=None, help="Batch ID; auto-generated if omitted")
def run(raw_path: str, config: str, batch_id: str | None) -> None:
    """Run the Glue CDC job locally."""
    import uuid

    from src.glue_jobs.cdc_to_sinks import main

    args = {
        "JOB_NAME": "cdc-local",
        "raw_s3_path": raw_path,
        "config_path": config,
        "batch_id": batch_id or uuid.uuid4().hex[:16],
    }
    sys.exit(main(args))


@cli.command()
@click.option("--config", required=True, type=click.Path(exists=True))
def validate(config: str) -> None:
    """Validate config + table contracts without running the job."""
    from src.schemas import TABLE_CONTRACTS
    from src.utils import load_config

    cfg = load_config(config)
    click.echo(f"Loaded config for env={cfg.get('environment', '?')}")
    click.echo(f"Contracts: {len(TABLE_CONTRACTS)} tables registered")
    for fqn, c in TABLE_CONTRACTS.items():
        click.echo(f"  {fqn:30s}  pk={','.join(c.primary_keys):25s}  sinks={','.join(c.sinks)}")


if __name__ == "__main__":
    cli()
