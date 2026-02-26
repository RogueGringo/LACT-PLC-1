.PHONY: test test-fast coverage lint format run run-tui install-dev clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

test: ## Run full test suite
	python -m pytest tests/ -v --tb=short

test-fast: ## Run tests, stop on first failure
	python -m pytest tests/ -x -q

coverage: ## Run tests with coverage report (fail under 80%)
	python -m pytest tests/ --cov=plc --cov-report=term-missing --cov-fail-under=80

lint: ## Check code with ruff
	python -m ruff check plc/ tests/ console/

format: ## Auto-format code with ruff
	python -m ruff format plc/ tests/ console/

run: ## Run LACT simulator with CLI
	python main.py

run-tui: ## Run LACT simulator with TUI dashboard
	python main.py --tui

install-dev: ## Install package in dev mode with all tools
	pip install -e ".[dev]"

clean: ## Remove build artifacts and caches
	rm -rf __pycache__ .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
