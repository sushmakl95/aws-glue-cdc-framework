# Contributing

Same conventions as our other data-eng repos. Briefly:

## Workflow

```bash
git checkout -b feat/my-change
# make changes
make format && make lint && make typecheck && make security && make test
git commit -m "feat: concise description"
git push origin feat/my-change
# open PR
```

## Code style

- `ruff format` + `ruff check` (configured in `pyproject.toml`)
- Type hints required on public functions
- Google-style docstrings
- No Python UDFs — use native Spark column expressions
- No hardcoded credentials — use Secrets Manager via `src/utils/secrets.py`
- No `print()` — use `get_logger(__name__)` from `src/utils/logging_config.py`

## PR requirements

- [ ] CI green (lint, security, terraform validate)
- [ ] New code covered by tests where possible
- [ ] Updated docs if behavior changed
- [ ] `make security` passes
- [ ] No secrets in diff

## Adding a new CDC table

1. Add entry to `TABLE_CONTRACTS` in `src/schemas/contracts.py`
2. Add the table to the Debezium connector's `table.include.list`
3. Add sink-specific DDL (Redshift `CREATE TABLE`, Postgres, OpenSearch mapping)
4. Snapshot the table once via Debezium snapshot mode
5. Test with the simulator locally first

## Adding a new sink

1. Implement `Sink` subclass in `src/sinks/`
2. Add it to `src/sinks/__init__.py`
3. Extend `build_sinks` in `src/glue_jobs/cdc_to_sinks.py`
4. Add a sink-specific config block in `config/<env>.yaml`
5. Write unit tests in `tests/unit/test_sinks.py`

## Questions?

Open a [discussion](https://github.com/sushmakl95/aws-glue-cdc-framework/discussions) or ping me on [LinkedIn](https://www.linkedin.com/in/sushmakl1995/).
