# AnnexOps

**Evidence-Pack-as-Code** platform for EU AI Act compliance, focused on HR/Workforce AI use cases.

## Overview

AnnexOps helps HR-Tech providers and AI deployers build auditable evidence packs for high-risk AI systems under the EU AI Act (Annex III - Employment/Workers Management).

### Key Features

- **AI System Registry** - Track use cases, data, roles, and deployment configurations
- **Evidence Store** - Upload files, link URLs, git refs, tickets, and notes with checksums
- **Evidence Mapping** - Map artifacts to Annex-IV sections and requirements
- **Annex-IV Generator** - Export structured DOCX documentation with evidence references
- **Version Control** - Track changes with immutable snapshots and diff reports
- **Completeness Scoring** - Identify gaps before audit

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend API | FastAPI + SQLAlchemy + Alembic |
| Database | PostgreSQL |
| Object Storage | MinIO / S3 |
| Task Queue | Celery + Redis |
| Deployment | Docker Compose |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+

### Setup

```bash
# Clone repository
git clone https://github.com/aliuyar1234/AnnexOps.git
cd AnnexOps

# Configure environment (Docker Compose reads `.env` from repo root)
cp .env.example .env
# Fill required values in `.env` (POSTGRES_PASSWORD, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD, JWT_SECRET, BOOTSTRAP_TOKEN)

# Start services
docker compose up -d

# Run migrations (inside the API container)
docker compose exec api alembic upgrade head
```

### API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

### Frontend (Next.js)

```bash
cd frontend
# Optional (defaults to http://localhost:8000)
# echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" > .env.local
npm install
npm run dev
```

### Bootstrap (First Organization)

Creating the first organization requires a bootstrap token:
- Set `BOOTSTRAP_TOKEN`
- Call `POST /api/organizations` with header `X-Bootstrap-Token: <BOOTSTRAP_TOKEN>`

## Project Structure

```
AnnexOps/
├── backend/
│   ├── alembic/           # Database migrations
│   ├── src/
│   │   ├── api/           # FastAPI routes
│   │   ├── core/          # Config, security, utilities
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   └── services/      # Business logic
│   └── tests/             # pytest tests
├── docker-compose.yml
└── README.md
```

## Modules

### Module A - Organization & Auth
- Single-org multi-user with RBAC (admin/editor/reviewer/viewer)
- JWT authentication with refresh tokens
- Account lockout with exponential backoff
- Invitation system with 7-day expiry

### Module B - AI System Registry
- CRUD for AI systems with HR use case tracking
- High-risk assessment wizard with scoring
- File attachments with S3/MinIO storage

### Module C - System Versioning
- Draft → Review → Approved workflow
- Version diff comparison
- Deterministic snapshot hashing (SHA-256)

### Module D - Evidence Store
- Five evidence types: upload, url, git, ticket, note
- Many-to-many evidence-to-section mappings
- Full-text search and tag filtering
- SHA-256 checksums for uploads

### Module E - Annex-IV Generator
- 12 section structure per EU AI Act Annex IV
- Completeness scoring with weighted sections
- DOCX export with evidence pack ZIP containing:
  - AnnexIV.docx
  - SystemManifest.json
  - EvidenceIndex.json/csv
  - CompletenessReport.json
  - DiffReport.json (for version comparisons)

## Roadmap

See `ROADMAP.md` for the open-source v1+ task list.

## Contributing

See `CONTRIBUTING.md`.

## Security

See `SECURITY.md`.

## License

Apache-2.0 (see `LICENSE`).

## API Endpoints

### Auth
- `POST /api/auth/login` - Login
- `POST /api/auth/logout` - Logout
- `POST /api/auth/refresh` - Refresh token
- `POST /api/auth/invite` - Invite user (admin)
- `POST /api/auth/accept-invite` - Accept invitation

### Systems
- `GET /api/systems` - List systems
- `POST /api/systems` - Create system
- `GET /api/systems/{id}` - Get system
- `PATCH /api/systems/{id}` - Update system
- `DELETE /api/systems/{id}` - Delete system (admin)

### Versions
- `GET /api/systems/{id}/versions` - List versions
- `POST /api/systems/{id}/versions` - Create version
- `GET /api/systems/{id}/versions/{vid}` - Get version
- `PATCH /api/systems/{id}/versions/{vid}` - Update version
- `PATCH /api/systems/{id}/versions/{vid}/status` - Change status

### Evidence
- `GET /api/evidence` - List evidence
- `POST /api/evidence` - Create evidence
- `GET /api/evidence/{id}` - Get evidence
- `PATCH /api/evidence/{id}` - Update evidence
- `DELETE /api/evidence/{id}` - Delete evidence

### Sections
- `GET /api/systems/{id}/versions/{vid}/sections` - List sections
- `PATCH /api/systems/{id}/versions/{vid}/sections/{key}` - Update section
- `GET /api/systems/{id}/versions/{vid}/completeness` - Get completeness

### Exports
- `POST /api/systems/{id}/versions/{vid}/exports` - Generate export
- `GET /api/systems/{id}/versions/{vid}/exports` - List exports
- `GET /api/exports/{id}/download` - Download export

## Testing

```bash
cd backend
python -m pytest tests/ -v
```

## Code Quality

This repo uses `pre-commit` (Ruff lint + format, plus basic hygiene checks).

```bash
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Dev Quality (pre-commit)

```bash
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| ENVIRONMENT | Runtime mode (`development`/`production`) | `development` |
| API_DOCS_ENABLED | Force-enable API docs (optional) | - |
| BOOTSTRAP_TOKEN | Required for `POST /api/organizations` | - |
| DATABASE_URL | PostgreSQL connection string | - |
| JWT_SECRET | Secret for JWT signing | - |
| JWT_ALGORITHM | JWT algorithm | `HS256` |
| JWT_ACCESS_TOKEN_EXPIRE_MINUTES | Access token TTL (minutes) | `30` |
| JWT_REFRESH_TOKEN_EXPIRE_DAYS | Refresh token TTL (days) | `7` |
| MINIO_ENDPOINT | MinIO/S3 endpoint (`host:port`) | - |
| MINIO_ACCESS_KEY | MinIO access key | - |
| MINIO_SECRET_KEY | MinIO secret key | - |
| MINIO_BUCKET | Bucket name | `annexops-attachments` |
| MINIO_USE_SSL | Use SSL for MinIO | `false` |

## License

Proprietary - All rights reserved.
