# AnnexOps Backend

FastAPI-based backend API for AnnexOps.

## Quick Start

### 1. Start Infrastructure

```bash
# From repository root
docker compose up -d postgres redis minio minio-init
```

### 2. Setup Python Environment

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and set JWT_SECRET to a secure random value
# If you want to bootstrap the first organization, also set BOOTSTRAP_TOKEN
```

### 4. Run Migrations

```bash
# After Phase 2 is complete
alembic upgrade head
```

### 5. Start Development Server

```bash
uvicorn src.main:app --reload --port 8000
```

## Development Commands

### Testing

```bash
# Run all tests
pytest

# Run specific test types
pytest tests/unit/
pytest tests/integration/
pytest tests/contract/

# Run with coverage
pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Linting
ruff check src/

# Auto-fix linting issues
ruff check --fix src/

# Type checking
mypy src/

# Formatting
black src/ tests/
```

### Database

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# Reset database
alembic downgrade base
alembic upgrade head
```

## Project Structure

```
backend/
├── src/
│   ├── models/          # SQLAlchemy models
│   ├── services/        # Business logic
│   ├── api/
│   │   └── routes/      # API endpoints
│   ├── core/            # Config, security, database
│   └── main.py          # FastAPI app entry
├── tests/
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── contract/        # API contract tests
├── alembic/
│   └── versions/        # Database migrations
└── requirements.txt
```

## API Documentation

When the server is running:

- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc
- OpenAPI JSON: http://localhost:8000/api/openapi.json

## Environment Variables

See `.env.example` for all available configuration options.

Required variables:
- `DATABASE_URL`: PostgreSQL connection string
- `JWT_SECRET`: Secret key for JWT signing (change in production!)
- `JWT_ALGORITHM`: Algorithm for JWT (HS256)

## Next Steps

After Phase 1 setup is complete:
1. Phase 2: Implement foundational models and core utilities
2. Phase 3: Implement organization creation (User Story 1)
3. Phase 4: Implement authentication (User Story 2)
4. Phase 5: Implement invitations (User Story 3)
5. Phase 6: Implement RBAC (User Story 4)

See `specs/001-org-auth/tasks.md` for detailed task list.
