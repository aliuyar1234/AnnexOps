# Contributing

Thanks for your interest in contributing to AnnexOps.

## Code of Conduct

By participating, you agree to abide by `CODE_OF_CONDUCT.md`.

## Development Setup

### Prerequisites

- Git
- Docker + Docker Compose
- Python 3.11+
- Node.js 20+ (for `frontend/`)

### Backend

```bash
cp .env.example .env
docker compose up -d
docker compose exec api alembic upgrade head
```

Run tests:

```bash
cd backend
python -m pytest
```

### Frontend

```bash
cd frontend
npm ci
npm run lint
npm run build
```

## Pre-commit (Required)

This repo uses `pre-commit` for linting/formatting and basic hygiene checks.

```bash
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Branching & PRs

- Create a feature branch (the repo uses numbered branches like `007-llm-assist`).
- Keep PRs focused and include tests for behavioral changes.
- CI must be green (backend tests + frontend lint/build + security scans).

## Reporting Bugs / Requesting Features

Please use GitHub Issues:
- Bug reports: include steps to reproduce, expected vs actual behavior, and logs.
- Feature requests: explain the user problem and desired workflow.

