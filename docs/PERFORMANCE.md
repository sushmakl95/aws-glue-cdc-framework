# Performance Tuning

Benchmarks from scaling the CDC pipeline from a 5-minute average batch to under 30 seconds. Each optimization is explained by *why* it works.

## Baseline

| Metric | Value |
|---|---|
| Dataset | 10M CDC events (1 week of a mid-volume MySQL DB) |
| Configuration | 5 × G.1X DPUs, no tuning |
| Query | Full pipeline: parse → flatten → dedup → route → 3 sinks |

**Baseline runtime: 38 minutes. Cost: $2.85/run.**

---

## Optimization 1 — Partition pruning on raw S3

**Change:** Structured raw S3 prefix as `/cdc/raw/<db>/<table>/<yyyy>/<MM>/<dd>/<HH>/`

**Why:** Glue's partition pruning only works if the directory structure matches the predicate. Filtering by `table = 'orders'` skips every other table's files entirely.

**Impact:** 38 min → 24 min (1.6x). Cost: $2.85 → $1.80.

**Gotcha:** Firehose dynamic partitioning costs extra. But skipping 90% of files dwarfs the partitioning cost.

---

## Optimization 2 — Executor tuning

**Change:**
- 5 × G.1X → 10 × G.1X workers
- `spark.sql.shuffle.partitions = 60` (was default 200)
- `spark.default.parallelism = 40`

**Why:**
- Glue autoscale doesn't kick in fast enough for 10-min batches
- Default shuffle partitions = 200 → many tiny tasks → scheduler overhead dominates
- For a ~2GB batch, 60 partitions × ~30MB each is the sweet spot

**Impact:** 24 min → 14 min (1.7x). Cost: $1.80 → $1.05.

---

## Optimization 3 — Glue Job Bookmarks

**Change:** `enable-glue-datacatalog=true` and `transformation_ctx` on every read.

**Why:** Without bookmarks, every Glue run re-reads all S3 data back to the beginning of time. Bookmarks track "what did we process last" and read only new files.

**Impact:** 14 min → 6 min (2.3x). Cost: $1.05 → $0.45.

**Gotcha:** Bookmarks are per-job-per-source. Renaming sources invalidates them.

---

## Optimization 4 — DynamicFrame → DataFrame conversion + broadcast dim join

**Change:**
```python
# Before: Glue DynamicFrame with optional resolveChoice
events_dyf.resolveChoice(specs=[...]).toDF()

# After: explicit schema + broadcast dim join
events_df = events_dyf.toDF()
enriched = events_df.join(F.broadcast(device_dim_df), ...)
```

**Why:**
- DynamicFrame's per-row null-safe operations are Python-interpreted → slow
- Direct DataFrame with typed schema stays in the JVM
- `F.broadcast()` avoids a full shuffle for small-table joins (dim is ~100k rows, fact is millions)

**Impact:** 6 min → 3 min (2x). Cost: $0.45 → $0.22.

---

## Cumulative results

| Stage | Runtime | Cost/Run | Speedup |
|---|---|---|---|
| Baseline | 38 min | $2.85 | 1.0x |
| + Partition pruning | 24 min | $1.80 | 1.6x |
| + Executor tuning | 14 min | $1.05 | 2.7x |
| + Glue Bookmarks | 6 min | $0.45 | 6.3x |
| + DataFrame + broadcast | 3 min | $0.22 | 12.7x |

**Net: 12.7× faster, 13× cheaper vs baseline.**

## Runbook: Benchmarking your own change

1. Run on a representative dataset 3x (discard first run — cold start)
2. Record wall time + DPU hours from Glue console
3. Change one thing
4. Re-run 3x
5. Compare

**Do not** eyeball single runs. Glue cold starts and S3 list throttling add 2-3x variance on short jobs.

## Sink-specific tuning

### Redshift
- **Use S3 COPY instead of INSERT**: `COPY ... FROM 's3://...' IAM_ROLE ...` is 50-500x faster on batches > 1000 rows
- **MERGE pattern**: DELETE-then-INSERT with a temp table. Native MERGE is slower on small batches.
- **Staging buckets should be in the same region**: cross-region COPY is 5-10x slower and incurs data transfer.

### Postgres
- **`execute_values` not `executemany`**: 10-50x faster on batch inserts
- **Batch size = 1000-5000**: larger batches hit Postgres parameter limits
- **`ON CONFLICT DO UPDATE` with `WHERE target.updated_at < EXCLUDED.updated_at`**: prevents stale-write races in multi-writer scenarios

### OpenSearch
- **Bulk chunk size = 500 docs**: OpenSearch's default bulk limit is 100MB; 500 docs is typically ~5-10MB
- **`refresh=false` during bulk**: refresh per-batch on a schedule; refreshing on every bulk destroys indexing throughput
