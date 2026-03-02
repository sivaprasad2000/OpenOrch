.PHONY: help install dev up down logs \
        api-install api-run api-migrate api-lint api-format api-test api-check \
        web-install web-run web-lint web-build

help:
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Root"
	@echo "  install        Install dependencies for both apps"
	@echo "  dev            Start both apps in development mode"
	@echo "  up             Start all services via Docker Compose"
	@echo "  down           Stop Docker Compose services"
	@echo "  logs           Tail Docker Compose logs"
	@echo ""
	@echo "API (apps/api)"
	@echo "  api-install    Install Python dependencies"
	@echo "  api-run        Start API dev server"
	@echo "  api-migrate    Run database migrations"
	@echo "  api-lint       Lint and type-check"
	@echo "  api-format     Auto-format code"
	@echo "  api-test       Run tests"
	@echo "  api-check      Run all checks (lint + types + tests)"
	@echo ""
	@echo "Web (apps/web)"
	@echo "  web-install    Install Node dependencies"
	@echo "  web-run        Start web dev server"
	@echo "  web-lint       Run ESLint"
	@echo "  web-build      Build for production"
	@echo ""

# Root targets

install: api-install web-install

dev:
	@make -j2 api-run web-run

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

# API targets

api-install:
	cd apps/api && pip install -r requirements.txt

api-run:
	cd apps/api && python -m app.main

api-migrate:
	cd apps/api && alembic upgrade head

api-lint:
	cd apps/api && ruff check app tests scripts && ruff format --check app tests scripts && mypy app

api-format:
	cd apps/api && ruff check --fix app tests scripts && ruff format app tests scripts

api-test:
	cd apps/api && pytest tests/ -v

api-check: api-lint api-test
	@echo "All API checks passed."

# Web targets

web-install:
	cd apps/web && npm install

web-run:
	cd apps/web && npm run dev

web-lint:
	cd apps/web && npm run lint

web-build:
	cd apps/web && npm run build
