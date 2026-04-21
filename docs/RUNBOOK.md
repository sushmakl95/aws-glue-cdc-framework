# Operations Runbook

## Daily health check

1. Check the **CloudWatch dashboard** (`cdc-glue-<env>`):
   - `CdcRowsUpserted` should be > 0 for each active sink in the last hour
   - Step Functions success rate should be 100% over 24h
2. Check **SNS alert email** for any overnight failures

## Common scenarios

### Scenario: A batch failed, alert received

1. Open Step Functions console → find failed execution
2. Click into the failed state (`RunCdcJob`) → view error
3. Look up the Glue job run by JobRunId in CloudWatch Logs
4. Determine root cause from logs:
   - Transient: re-run via `aws stepfunctions start-execution ...`
   - DQ failure: check quarantine S3 prefix
   - Sink unavailable: check target DB status, then restart Glue job

### Scenario: Need to reprocess a specific day

```bash
python scripts/backfill.py \
    --config config/prod.yaml \
    --start 2026-03-15 \
    --end 2026-03-15 \
    --tables sales.orders,sales.customers
```

The backfill script reads the same S3 raw prefix but writes with `replace_where` semantics — replaying is safe.

### Scenario: New table needs to be CDC'd

1. Add the table to `src/schemas/contracts.py`
2. Update Debezium connector `table.include.list` (requires connector restart)
3. Deploy via `bash scripts/deploy.sh prod`
4. Run an initial snapshot:
   ```bash
   curl -X PUT http://connect:8083/connectors/sales-mysql-connector/config \
        -H "Content-Type: application/json" \
        -d @compose/debezium-connector.json
   ```

### Scenario: Schema drift detected

Debezium emits `SCHEMA_CHANGE` events on the `schema-changes.sales` topic. The framework auto-handles:
- New column: propagates automatically
- Column type change: row is quarantined with `_schema_conflict` flag
- Table rename: requires explicit mapping rule in `contracts.py`

Check the quarantine S3 prefix (`cdc/errors/`) for schema-drift quarantined rows.

### Scenario: Redshift credentials rotated

1. Update the value in Secrets Manager:
   ```bash
   aws secretsmanager put-secret-value \
        --secret-id cdc-glue/prod/redshift \
        --secret-string '{"username":"...", "password":"..."}'
   ```
2. The Glue job's `@lru_cache` on `get_secret` is process-local — next job run will fetch fresh. No code deploy needed.

### Scenario: Paused Redshift overnight, need to resume

```bash
aws redshift resume-cluster --cluster-identifier cdc-glue-redshift-prod
# Wait ~5 min for resume
aws redshift describe-clusters --cluster-identifier cdc-glue-redshift-prod \
    --query 'Clusters[0].ClusterStatus'
```

### Scenario: Pipeline latency spike

1. Check Glue job runtime trend in CloudWatch
2. Common causes:
   - Kinesis shard throttling → switch to on-demand if provisioned
   - Glue autoscale lag → bump `number_of_workers`
   - Large batch after downtime → shorten `eventbridge_schedule` to backfill faster
3. Check target DB metrics — Redshift queries piling up cause Glue workers to wait

## SLA targets

| Metric | Target | Alarm threshold |
|---|---|---|
| End-to-end CDC latency (MySQL → Redshift) | < 5 min p95 | > 15 min for 3 consecutive batches |
| Batch success rate | > 99.5% | < 98% over 24h |
| DQ quarantine rate | < 0.1% | > 1% over 1h |

## Escalation

- P1 (data loss or widespread failure): page DE oncall; notify data-platform-leads Slack
- P2 (single-sink failure, non-blocking): ticket in data-platform-bugs
- P3 (schema drift, minor issues): monitor; fix at next sprint

## Useful commands

```bash
# Manually trigger a backfill via Step Functions
aws stepfunctions start-execution \
    --state-machine-arn arn:aws:states:... \
    --input '{"batch_id":"manual-xxx","raw_prefix":"cdc/raw/sales/orders/2026/04/21/","trigger":"manual"}'

# Tail Glue job logs
aws logs tail /aws-glue/jobs/cdc-glue-prod --follow

# Check idempotency table
aws dynamodb scan --table-name cdc-glue-idempotency-prod \
    --filter-expression "#s = :status" \
    --expression-attribute-names '{"#s":"status"}' \
    --expression-attribute-values '{":status":{"S":"FAILED"}}'

# Pause Redshift (cost savings outside business hours)
aws redshift pause-cluster --cluster-identifier cdc-glue-redshift-prod
```
