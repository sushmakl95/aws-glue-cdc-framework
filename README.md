# AWS Glue CDC Framework

> Production-grade Change Data Capture framework using AWS Glue, Debezium, Kinesis, Step Functions. Mirrors patterns from large-scale enterprise data migrations (MySQL → Redshift / Postgres / OpenSearch) with full CDC semantics, SCD2 merges, and idempotent replay.

[![CI](https://github.com/sushmakl95/aws-glue-cdc-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/sushmakl95/aws-glue-cdc-framework/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![AWS Glue 4.0](https://img.shields.io/badge/aws--glue-4.0-orange.svg)](https://docs.aws.amazon.com/glue/)
[![Terraform 1.7+](https://img.shields.io/badge/terraform-1.7%2B-purple.svg)](https://www.terraform.io/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

---

## Author

**Sushma K L** — Senior Data Engineer
📍 Bengaluru, India
💼 [LinkedIn](https://www.linkedin.com/in/sushmakl1995/) • 🐙 [GitHub](https://github.com/sushmakl95) • ✉️ sushmakl95@gmail.com

---

## Problem Statement

A fast-growing e-commerce platform has a **MySQL operational database** (orders, customers, inventory) feeding real product decisions. The analytics team needs:

1. **Near-real-time replication** into **Redshift** for BI dashboards
2. **Operational read replica** in **Postgres** for microservices
3. **Full-text search index** in **OpenSearch** for product discovery
4. **No dual-writes** from the application — pure CDC via binlog

Traditional ETL (hourly batch `SELECT *`) has three problems:
- ❌ Hours-long source-table locks for large tables
- ❌ Deletes in MySQL never propagate → stale downstream data
- ❌ Latency floor of ~1 hour — insufficient for near-real-time dashboards

This project implements an **industry-standard CDC pipeline**:

**MySQL binlog → Debezium → Kinesis → S3 → AWS Glue (PySpark) → Redshift / Postgres / OpenSearch**

with exactly-once semantics, schema evolution handling, and a sub-5-minute latency target.

## Architecture

```
┌─────────────┐
│   MySQL     │  binlog
│ (ops DB)    │─────────┐
└─────────────┘         ▼
                ┌──────────────────┐
                │ Kafka Connect +  │
                │ Debezium MySQL   │
                │ source connector │
                └────────┬─────────┘
                         │ CDC events (JSON, Debezium envelope)
                         ▼
                ┌──────────────────┐
                │  Amazon Kinesis  │
                │  Data Streams    │
                └────────┬─────────┘
                         │ Kinesis Firehose
                         ▼
                ┌──────────────────┐
                │   S3 raw CDC     │
                │   (partitioned)  │
                └────────┬─────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────────────┐
  │             AWS Glue Job (PySpark)                   │
  │  • Parse Debezium envelope                           │
  │  • Apply DQ rules + schema validation                │
  │  • Route by op: c/u/d/r → appropriate sink handler   │
  │  • Write idempotent MERGE per target                 │
  └────────┬──────────────────┬──────────────────┬───────┘
           │                  │                  │
           ▼                  ▼                  ▼
    ┌──────────┐       ┌──────────┐       ┌──────────┐
    │ Redshift │       │ Postgres │       │OpenSearch│
    │ (SCD2)   │       │ (upsert) │       │ (index)  │
    └──────────┘       └──────────┘       └──────────┘

      [ orchestrated by Step Functions + EventBridge ]
      [ credentials in Secrets Manager                ]
      [ metrics + alarms in CloudWatch                ]
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design decisions and trade-offs.

## Key Features

| Area | Implementation |
|---|---|
| **CDC source** | Debezium MySQL connector — captures INSERT/UPDATE/DELETE from binlog without source impact |
| **Ingestion** | Kinesis Data Streams (scalable shards) → Firehose → S3 (partitioned by table + hour) |
| **Processing** | AWS Glue 4.0 (Spark 3.3, Python 3.10) — reusable framework processes any Debezium-formatted table |
| **Exactly-once** | Idempotent MERGE using `(pk, ts_ms, lsn)` — replay-safe |
| **Schema evolution** | Additive column changes propagate automatically; breaking changes quarantined |
| **Orchestration** | Step Functions state machine — Glue job → DQ validation → sink fanout → notification |
| **Triggers** | EventBridge (scheduled) + S3 PUT events (reactive) + manual (backfill) |
| **Sinks** | Redshift (SCD2 dim), Postgres (upsert), OpenSearch (indexed mirror) |
| **Security** | Secrets Manager for all DB creds; IAM least-privilege; VPC-isolated Glue jobs |
| **Observability** | CloudWatch dashboards, structured JSON logs, custom metrics, SNS alerting |
| **Local dev** | Docker Compose stack (MySQL + Kafka + Kafka Connect + Debezium) OR pure-Python simulator |
| **Cost control** | Glue job bookmark; Kinesis on-demand mode; Redshift pause/resume; tight IAM |
| **CI/CD** | Lint + security + Terraform validate + manual-deploy workflows |

## Repository Structure

```
aws-glue-cdc-framework/
├── .github/workflows/       # CI (lint/security/tf) + manual deploy
├── compose/                 # Docker Compose: MySQL + Kafka + Debezium (local dev)
├── config/                  # Environment configs (dev/staging/prod)
├── data/                    # Seed MySQL data + sample CDC events
├── docs/                    # Architecture, performance, cost, runbook
├── infra/terraform/         # IaC for all AWS resources (reference-only)
│   └── modules/             # vpc, iam, s3, glue, redshift, rds, kinesis,
│                            # stepfunctions, lambda, secrets, opensearch,
│                            # eventbridge, monitoring
├── simulators/debezium/     # Pure-Python Debezium event generator (no Docker)
├── src/
│   ├── cdc/                 # Debezium envelope parsing, op routing
│   ├── glue_jobs/           # Glue job entrypoints
│   ├── sinks/               # Redshift, Postgres, OpenSearch writers
│   ├── schemas/             # Typed contracts
│   ├── utils/               # Logging, secrets, idempotency
│   └── lambdas/             # EventBridge-triggered Lambdas
├── stepfunctions/           # State machine JSON definitions
├── scripts/                 # Deploy, backfill, ops utilities
└── tests/                   # Unit (fast) + integration (Spark + Delta)
```

## Quick Start (Local Dev)

Requires: Python 3.11, Java 17, Docker (optional).

```bash
# 1. Clone and install
git clone https://github.com/sushmakl95/aws-glue-cdc-framework.git
cd aws-glue-cdc-framework
make install-dev

# 2a. Option A — Pure Python simulator (no Docker)
make simulate-cdc

# 2b. Option B — Realistic Debezium (Docker Compose)
docker compose -f compose/docker-compose.yml up -d
make seed-mysql
make register-debezium-connector
# CDC events now flow through Kafka in real-time

# 3. Run the Glue job locally (PySpark) against generated events
make run-glue-job

# 4. Run tests
make test
```

See [docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md) for full setup.

## ⚠️ Cloud Deployment Cost Warning

**DO NOT run `terraform apply` without reading [docs/COST_ANALYSIS.md](docs/COST_ANALYSIS.md).**

Estimated monthly cost if fully deployed: **~$720/month** (Redshift dc2.large cluster + OpenSearch + Kinesis + Glue runtime).

This project is designed as a **reference implementation**. All development and testing runs on your laptop for $0. Terraform code ships as infrastructure-as-code demonstration, not as a "deploy me" button.

## Performance Benchmarks

Measured on a synthetic 10M-event CDC stream (1 week of a mid-volume MySQL DB):

| Glue Job Configuration | Runtime | Cost/Run |
|---|---|---|
| Baseline (5 G.1X DPUs, no tuning) | 38 min | $2.85 |
| + Partition pruning on raw S3 | 24 min | $1.80 |
| + Executor tuning (10 G.1X, parallelism=60) | 14 min | $1.05 |
| + Glue Job Bookmark (incremental only) | 6 min | $0.45 |
| + Dynamic frame → DataFrame + broadcast dim join | 3 min | $0.22 |

**Net: 12.7× faster, 13× cheaper vs baseline.** See [docs/PERFORMANCE.md](docs/PERFORMANCE.md).

## Design Decisions

| Decision | Chose | Why |
|---|---|---|
| CDC method | Debezium (binlog) | Low source impact, captures deletes, exact ordering |
| Transport | Kinesis → S3 | Decouples ingestion from processing; enables replay |
| Processor | AWS Glue (Spark) | Native AWS, autoscales, catalog integration |
| Exactly-once | MERGE on `(pk, ts_ms)` | Ordered events + Delta semantics guarantee idempotency |
| SCD2 | Hash-based change detection | Deterministic; same pattern as Lakehouse repo |
| Multi-sink fanout | Step Functions parallel state | Each sink independent; failures don't block others |
| Credentials | Secrets Manager | No hardcoded creds; rotatable; audit logged |

## License

MIT — see [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome.
