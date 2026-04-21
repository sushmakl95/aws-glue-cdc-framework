# Cost Analysis

## ⚠️ Read this before running `terraform apply`

Full cloud deployment costs approximately **~$720/month** at moderate volume. Development and testing of this framework is designed to run **entirely on your laptop for $0** using the included Debezium simulator (`make simulate-cdc`) or the Docker Compose stack.

The Terraform in `infra/terraform/` is **reference IaC** demonstrating the full architecture. It is not a "deploy me" button — you can showcase it to recruiters and use it as a template, but running `terraform apply` creates billed resources.

## Monthly estimate (prod, 10M CDC events/day)

| Component | Monthly cost (USD) | Notes |
|---|---|---|
| Glue Job DPU-hours | $320 | ~15 min/batch × 4 batches/hr × 24h × 30d × G.1X |
| Redshift dc2.large × 1 | $190 | Single-node cluster, 24/7 |
| RDS Postgres db.t4g.micro | $12 | Operational mirror |
| OpenSearch t3.small.search | $28 | Optional — disable via `enable_opensearch=false` |
| Kinesis on-demand | $55 | 10M events/day, ~1KB each |
| Firehose | $22 | Dynamic partitioning + GZIP |
| Lambda invocations | $3 | S3 triggers + SFN notifier |
| Step Functions | $12 | ~3000 transitions/day |
| DynamoDB (idempotency) | $2 | Pay-per-request, ~3k writes/day |
| S3 storage (raw + staging) | $25 | ~800GB with lifecycle |
| S3 requests | $18 | Firehose writes + Glue reads |
| NAT Gateway | $32 | VPC egress for Glue → OpenSearch etc. |
| VPC endpoints (S3 gateway) | $0 | Free gateway endpoint cuts NAT costs |
| CloudWatch logs (14d retention) | $8 | Glue + Lambda |
| SNS | <$1 | Alert emails |
| **Total** | **~$728** | |

## Cost optimization checklist (already applied)

- [x] S3 gateway endpoint — cuts NAT egress costs by ~30% for S3 traffic
- [x] Kinesis on-demand mode — no shard management, scales to zero if idle
- [x] Glue auto-scaling — spin up only when needed
- [x] Glue job bookmarks — process only new files, not the entire history
- [x] S3 lifecycle: raw events expire after 90 days, staging after 14 days
- [x] Abort incomplete multipart uploads after 7 days
- [x] Firehose GZIP compression — ~75% storage saving vs raw JSON
- [x] DynamoDB TTL on idempotency records (30 days)
- [x] CloudWatch retention 14 days (not default indefinite)
- [x] Redshift `single-node` + `dc2.large` (smallest practical prod cluster)
- [x] RDS Postgres burstable instance (db.t4g.micro)

## Cost vs volume scaling

| CDC events/day | Estimated monthly cost |
|---|---|
| 1M | $450 |
| 10M | $728 |
| 100M | $1,650 |
| 1B | $8,400 |

Scaling is sublinear because the fixed costs (Redshift, RDS, OpenSearch, NAT) don't grow. The variable costs (Glue DPU-hours, Kinesis, S3) scale roughly linearly with volume.

## How to cut costs if running in dev

1. **Skip OpenSearch**: set `enable_opensearch = false` in tfvars. Saves $28/mo.
2. **Pause Redshift overnight**: Add a scheduled Lambda that calls `pause-cluster` / `resume-cluster`. Saves ~50% of Redshift cost.
3. **Delete RDS Postgres** if you don't need the operational mirror: saves $12/mo.
4. **Disable EventBridge schedule**: set `eventbridge_schedule = "rate(60 minutes)"` instead of 15. Saves ~75% of Glue DPU-hours.
5. **`terraform destroy` aggressively**: spin up only when demonstrating; tear down immediately. Average hourly cost is ~$1 — showing the full stack for an hour costs ~$1.

## How to demonstrate this repo to recruiters at $0 cost

1. **Do not `terraform apply`** — the Terraform code is the artifact, not the deployment.
2. **Run the local Docker Compose stack** (free):
   ```bash
   docker compose -f compose/docker-compose.yml up -d
   make seed-mysql
   make register-debezium-connector
   ```
   This gives you a fully functional local CDC environment.
3. **Run the simulator** (even simpler):
   ```bash
   make simulate-cdc
   make run-glue-job
   ```
4. **Reference the IaC and docs in interviews**: "Here's my Terraform for the full AWS stack — I designed it so a clone can be provisioned with `terraform apply` after setting credentials in Secrets Manager."

## Recruiter talking points about cost-awareness

This repo demonstrates specific cost-consciousness:
- VPC gateway endpoints for S3 (free, saves NAT costs)
- Glue job bookmarks (read only new data)
- Kinesis on-demand (no idle cost)
- S3 lifecycle rules (cap storage growth)
- Tight CloudWatch retention (not default 2-year retention)
- DynamoDB TTL (no unbounded table growth)
- GZIP compression in Firehose

These are the discussion points senior data engineering interviewers want to hear — not "I just made it work", but "I made it work and I know where the money goes".
