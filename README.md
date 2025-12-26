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

# Start services
docker-compose up -d

# Run migrations
cd backend
cp .env.example .env
alembic upgrade head

# Start API server
uvicorn src.main:app --reload
```

### API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

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

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| DATABASE_URL | PostgreSQL connection string | - |
| JWT_SECRET | Secret for JWT signing | - |
| JWT_ALGORITHM | JWT algorithm | HS256 |
| ACCESS_TOKEN_EXPIRE_MINUTES | Access token TTL | 30 |
| REFRESH_TOKEN_EXPIRE_DAYS | Refresh token TTL | 7 |
| S3_ENDPOINT | MinIO/S3 endpoint | - |
| S3_ACCESS_KEY | S3 access key | - |
| S3_SECRET_KEY | S3 secret key | - |
| S3_BUCKET | S3 bucket name | annexops |

## License

Proprietary - All rights reserved.
