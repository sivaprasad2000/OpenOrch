.PHONY: help install dev-install lint format type-check test test-cov clean run migrate

# Default target
help:
	@echo "Available commands:"
	@echo "  make install       - Install production dependencies"
	@echo "  make dev-install   - Install all dependencies including dev tools"
	@echo "  make lint          - Run linting checks"
	@echo "  make format        - Auto-format code"
	@echo "  make type-check    - Run type checking with mypy"
	@echo "  make test          - Run tests"
	@echo "  make test-cov      - Run tests with coverage report"
	@echo "  make clean         - Clean up cache files"
	@echo "  make run           - Run the development server"
	@echo "  make migrate       - Run database migrations"

# Install dependencies
install:
	pip install -r requirements.txt

dev-install:
	pip install -r requirements.txt
	pip install pre-commit
	pre-commit install

# Linting
lint:
	@echo "Running Ruff linter..."
	ruff check app tests scripts
	@echo "Checking formatting..."
	ruff format --check app tests scripts

# Format code
format:
	@echo "Formatting code with Ruff..."
	ruff check --fix app tests scripts
	ruff format app tests scripts

# Type checking
type-check:
	@echo "Running MyPy type checker..."
	mypy app

# Testing
test:
	@echo "Running tests..."
	pytest tests/ -v

test-cov:
	@echo "Running tests with coverage..."
	pytest tests/ -v --cov=app --cov-report=term --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

# Clean cache files
clean:
	@echo "Cleaning cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov/ .coverage coverage.xml

# Run development server
run:
	@echo "Starting development server..."
	python -m app.main

# Database migrations
migrate:
	@echo "Running database migrations..."
	alembic upgrade head

# Run all quality checks (lint + type-check + test)
check: lint type-check test
	@echo "All checks passed!"
