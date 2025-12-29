# Upgrade Guide

This guide covers upgrading an existing AnnexOps deployment between releases.

## Before You Upgrade

- Back up your Postgres data volume (or take a database snapshot).
- Review `CHANGELOG.md` for breaking changes and new environment variables.
- If you run behind a reverse proxy, verify your public URL and cookie settings.

## Docker Compose Upgrade (Recommended)

1. Pull new code / images and update config:
   - `git pull` (if you deploy from source), or pull the new image tags.
   - Update your `.env` to match `.env.example` (add new variables as needed).
2. Recreate containers:
   - `docker compose -f docker-compose.prod.yml up -d --build`
3. Run database migrations (if not already handled by your deployment):
   - `docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head`
4. Verify:
   - `GET /api/health` returns `{"status":"ok"}`.
   - Login works and refresh cookies are being set as expected.

## Notes

- Database migrations are managed via Alembic and are assumed to be forward-only.
- If you run `ENVIRONMENT=production`, `JWT_SECRET` must be strong and MinIO credentials must not use defaults.
- Input validation is strict; malformed payloads now return `422` rather than being partially accepted.

## Rollback

Rollback is safest by restoring the database backup/snapshot and redeploying the previous version tag/images.

