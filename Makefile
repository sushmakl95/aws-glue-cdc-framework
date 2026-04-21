.PHONY: help install install-dev test test-unit lint format typecheck security clean simulate-cdc run-glue-job seed-mysql register-debezium-connector

PYTHON := python3.11
VENV := .venv
VENV_BIN := $(VENV)/bin

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip setuptools wheel

install: $(VENV)/bin/activate  ## Install runtime deps
	$(VENV_BIN)/pip install -e .

install-dev: $(VENV)/bin/activate  ## Install dev + test deps
	$(VENV_BIN)/pip install -e ".[dev]"
	$(VENV_BIN)/pre-commit install

test: test-unit  ## Run full test suite

test-unit:  ## Run unit tests
	$(VENV_BIN)/pytest tests/unit -v -m unit

lint:  ## Run ruff linter
	$(VENV_BIN)/ruff check src tests

format:  ## Auto-format
	$(VENV_BIN)/ruff format src tests
	$(VENV_BIN)/ruff check --fix src tests

typecheck:  ## Run mypy
	$(VENV_BIN)/mypy src --ignore-missing-imports --exclude "src/glue_jobs/"

security:  ## Run bandit
	$(VENV_BIN)/bandit -c pyproject.toml -r src -lll -x src/glue_jobs,tests

simulate-cdc:  ## Generate synthetic Debezium events (no Docker needed)
	$(VENV_BIN)/cdc-glue simulate --output-dir data/cdc_events --events 10000

run-glue-job:  ## Run the Glue CDC job locally against simulated events
	$(VENV_BIN)/cdc-glue run --raw-path data/cdc_events --config config/local.yaml

seed-mysql:  ## Seed MySQL (requires compose stack running)
	docker exec -i cdc-mysql mysql -u root -pdebezium sales < compose/mysql-init/01-schema.sql

register-debezium-connector:  ## Register Debezium connector with Kafka Connect
	curl -X POST -H "Content-Type: application/json" \
		--data @compose/debezium-connector.json \
		http://localhost:8083/connectors

clean:  ## Clean generated artifacts
	rm -rf build/ dist/ *.egg-info .pytest_cache .coverage htmlcov/
	rm -rf spark-warehouse/ metastore_db/ derby.log
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-data:  ## Clean generated data (destructive)
	rm -rf data/cdc_events

all: install-dev lint typecheck security test  ## Full CI simulation
