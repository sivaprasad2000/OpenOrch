# OpenOrch

LLM API token tracking and management platform. Monitor usage, enforce budgets, and manage access across your organization.

## Structure

```
apps/
  api/   FastAPI backend (Python 3.11)
  web/   Next.js 15 frontend (TypeScript)
```

## Getting started

Copy the root env file and fill in the values:

```bash
cp .env.example .env
```

**Run everything with Docker:**

```bash
make up
```

**Or run locally:**

```bash
make install   # install all dependencies
make dev       # start api + web concurrently
```

Individual app commands:

```bash
make api-run       # http://localhost:8000
make api-migrate   # run DB migrations
make api-test      # pytest
make api-check     # lint + types + tests

make web-run       # http://localhost:3000
make web-build     # production build
```

## Services (Docker Compose)

| Service    | Port  |
|------------|-------|
| api        | 8000  |
| web        | 3000  |
| postgres   | 5432  |
| rabbitmq   | 5672  |
| rabbitmq ui| 15672 |

## Docs

- `apps/api/README.md` — backend setup, migrations, testing
- `apps/web/README.md` — frontend setup, architecture
