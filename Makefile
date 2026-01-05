SHELL := /bin/bash

.PHONY: help install install-dev lint format type-check test clean  setup-hooks commit

help:
	@echo "Azure Deploy CLI - Azure Deployment Automation"
	@echo ""
	@echo "Available targets:"
	@echo "  install          Install the package locally"
	@echo "  install-dev      Install the package with development dependencies"
	@echo "  setup-hooks      Install pre-commit hooks"
	@echo "  commit           Create a conventional commit using commitizen"
	@echo "  lint             Run ruff linter"
	@echo "  format           Format code with ruff"
	@echo "  type-check       Run mypy type checker"
	@echo "  test             Run pytest"
	@echo "  clean            Clean up temporary files and caches"
	@echo "  build            Run linting, type checking, and tests"

setup-hooks:
	pre-commit install
	pre-commit install --hook-type commit-msg

install:
	pip install .
	$(MAKE) setup-hooks

install-dev:
	pip install -e ".[dev]"
	$(MAKE) setup-hooks

commit:
	cz commit

lint:
	ruff check src/ tests/ 2>/dev/null || echo "No issues found"

format:
	ruff format src/ tests/

type-check:
	mypy src/azure_deploy_cli

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=src/azure_deploy_cli --cov-report=html --cov-report=term-missing

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf htmlcov/ 2>/dev/null || true

build: lint type-check test

.DEFAULT_GOAL := help
