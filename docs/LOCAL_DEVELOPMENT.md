# Local Development

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.11 | Runtime |
| Java | 17 | Required by Spark 3.5 |
| Docker | 24+ (optional) | For realistic Debezium stack |
| Make | any | Convenience |

## Setup

```bash
git clone https://github.com/sushmakl95/aws-glue-cdc-framework.git
cd aws-glue-cdc-framework
make install-dev
source .venv/bin/activate
```

## Two development paths

### Path A — Pure Python simulator (recommended, no Docker)

The simulator generates Debezium-shaped events directly to disk. No MySQL, Kafka, or Debezium required. Fastest iteration cycle.

```bash
# Generate 10k events
make simulate-cdc

# Run the Glue job against them
make run-glue-job
```

Good for:
- Testing framework logic (parser, router, DQ rules)
- CI tests
- Rapid iteration on new features
- Zero-resource dev on any machine

Limitation: does not exercise the Kinesis/Firehose ingestion path. For that, use Path B.

### Path B — Docker Compose stack (realistic)

Brings up MySQL + Zookeeper + Kafka + Kafka Connect + Debezium + Kafka UI. End-to-end real-world CDC, no cloud needed.

```bash
# 1. Start the stack
docker compose -f compose/docker-compose.yml up -d

# 2. Wait for MySQL to be healthy (~30s), then seed
make seed-mysql

# 3. Register the Debezium connector
make register-debezium-connector

# 4. Make changes to MySQL and watch events flow through Kafka
docker exec -it cdc-mysql mysql -u root -pdebezium sales
> INSERT INTO customers (email) VALUES ('test@example.com');

# 5. View events in Kafka UI
open http://localhost:8080

# 6. Tear down when done
docker compose -f compose/docker-compose.yml down -v
```

Good for:
- Understanding real Debezium event shapes
- Demo'ing the pipeline in interviews
- Testing schema evolution scenarios

Requires ~4GB RAM. Port conflicts: MySQL 3306, Kafka 9092, Connect 8083, UI 8080.

## Testing

```bash
# Fast unit tests
make test-unit

# Lint + typecheck + security
make lint
make typecheck
make security

# Full local CI simulation
make all
```

## Common issues

### `java.lang.NoClassDefFoundError` on Spark startup
Ensure JAVA_HOME points to Java 17, not 21 (Spark 3.5 is incompatible with 21).

### Glue job fails locally with "module not found: awsglue"
Expected — the `awsglue` library is only available in the Glue runtime. Our code detects this with a try/import and falls back to pure PySpark locally.

### Docker: MySQL container keeps restarting
Check logs: `docker logs cdc-mysql`. Most common cause is insufficient RAM (needs ~1GB) or a port conflict on 3306.

### Kafka Connect: connector fails to register
Wait longer — Kafka Connect needs ~60s to be ready after container start. Use:
```bash
curl http://localhost:8083/connectors
```
to confirm the API is up.

### Simulator produces no events
Check `data/cdc_events/sales/`. Files should appear under `<table>/<hour>/events_*.json`.

## Editor setup

Same as Repo #1. VS Code with ruff + mypy extensions. PyCharm works too — mark `src` as sources root.

## Contributing workflow

```bash
git checkout -b feat/my-change
# code + test
make format
make lint
make typecheck
make test
git commit -m "feat: ..."
git push origin feat/my-change
# open PR
```

CI runs lint + security + terraform validate automatically. Tests run locally.
