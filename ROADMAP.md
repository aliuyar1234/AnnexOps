# AnnexOps Roadmap (Open Source)

This is a living task list for turning AnnexOps into a proud-to-publish, ship-ready open-source product (not just an API MVP).

Legend:
- **P0** = required for a solid OSS v1 release
- **P1** = strongly recommended (v1+)
- **P2** = differentiators / standout

---

## Up Next

- [ ] M4.3 Add end-to-end smoke test (docker compose + basic API+UI checks)
- [ ] M4.5 Add release artifacts (built images + checksums)

---

## Milestone M0 - OSS Project Hygiene (P0)

- [x] M0.1 Add `LICENSE` (choose: Apache-2.0 or MIT)
- [x] M0.2 Add `CONTRIBUTING.md` (dev setup, style, PR rules)
- [x] M0.3 Add `CODE_OF_CONDUCT.md`
- [x] M0.4 Add `SECURITY.md` (vuln reporting + supported versions)
- [x] M0.5 Add GitHub issue + PR templates (`.github/ISSUE_TEMPLATE/*`, `.github/pull_request_template.md`)
- [x] M0.6 Add `ROADMAP.md` sections for "Up Next" and "Help Wanted" labels
- [x] M0.7 Add `CHANGELOG.md` and a release process (tagging, notes)

---

## Milestone M1 - Complete Product Flow in UI (P0)

### M1A: App Shell + Auth
- [x] M1A.1 Frontend layout: navigation, responsive shell, error boundary
- [x] M1A.2 Login screen (JWT flow) + logout
- [x] M1A.3 Session handling: refresh + "expired session" UX
- [x] M1A.4 RBAC-aware navigation (hide/disable forbidden actions)

### M1B: Organization + Users
- [x] M1B.1 Organization settings page (name, bootstrap hints)
- [x] M1B.2 User management UI (list, invite, revoke, role change)
- [x] M1B.3 Invitation acceptance UI

### M1C: AI Systems
- [x] M1C.1 Systems list + search/filter
- [x] M1C.2 Create/edit system forms (all required fields)
- [x] M1C.3 System detail page: metadata, attachments
- [x] M1C.4 High-risk assessment wizard UI + result view

### M1D: Versions
- [x] M1D.1 Versions list per system + create version
- [x] M1D.2 Version detail page: status, notes, release date
- [x] M1D.3 Workflow actions: draft -> review -> approved (role-gated)
- [x] M1D.4 Version compare UI (diff report rendering)

### M1E: Annex IV Sections Editor
- [x] M1E.1 Sections list with completion indicators
- [x] M1E.2 Section editor: schema-driven form UI per section
- [x] M1E.3 Autosave + conflict handling (optimistic concurrency)
- [x] M1E.4 Section "review" UX (comments + decision log link)

### M1F: Evidence Store + Mapping
- [x] M1F.1 Evidence list + filters (type, tags, classification)
- [x] M1F.2 Create evidence UI for all types (upload/url/git/ticket/note)
- [x] M1F.3 Upload UX: progress, checksum display, file preview (where safe)
- [x] M1F.4 Evidence detail page + edit metadata/tags
- [x] M1F.5 Mapping UI: map evidence -> section fields/targets + strength/notes
- [x] M1F.6 Mapping overview per version (coverage heatmap)

### M1G: Completeness + Export
- [x] M1G.1 Completeness dashboard UI (scores + prioritized gaps)
- [x] M1G.2 Export UI: create full export / diff export
- [x] M1G.3 Exports list + download links
- [x] M1G.4 Offline viewer UX polishing (search, section drill-down)

---

## Milestone M2 - Security & Safe Defaults (P0)

- [x] M2.1 Add security headers (CSP, HSTS where applicable, XFO, XCTO, referrer-policy)
- [x] M2.2 Add rate limiting for auth + write endpoints
- [x] M2.3 Review cookie/session settings (secure/httponly/samesite)
- [x] M2.4 Harden CORS (explicit origins, no wildcards in prod)
- [x] M2.5 Input validation pass for all endpoints (including file metadata)
- [x] M2.6 Audit log UI + admin filters (who did what/when)
- [x] M2.7 Data retention job (configurable) + docs (privacy/GDPR basics)

---

## Milestone M3 - "Works Everywhere" Deployment (P0)

- [x] M3.1 Production `docker-compose.prod.yml` (no dev defaults, no test secrets)
- [x] M3.2 Separate `frontend` container + reverse proxy (Caddy/Traefik/Nginx)
- [x] M3.3 Health checks for API, DB, MinIO, worker
- [x] M3.4 Upgrade guide: migrations, backwards compatibility notes
- [x] M3.5 Seed/demo dataset + scripted walkthrough for first export

---

## Milestone M4 - Quality Bar (P0)

- [x] M4.1 Add frontend CI job (lint + build) (already started; keep green)
- [x] M4.2 Add backend + frontend dependency update policy (pinning, renovate config)
- [ ] M4.3 Add end-to-end smoke test (docker compose + basic API+UI checks)
- [x] M4.4 Add SAST (e.g., CodeQL) + container scan (Trivy) (P1 if time)
- [ ] M4.5 Add release artifacts (built images + checksums)

---

## Milestone M5 - Verifiable Exports (P2, standout)

- [ ] M5.1 Add per-evidence checksum verification report inside export ZIP
- [ ] M5.2 Sign export ZIP (minisign/cosign) and include signature + public key
- [ ] M5.3 Offline verifier page: verify signature + snapshot hash + evidence checksums
- [ ] M5.4 Provenance capture: evidence source, timestamps, "last verified"

---

## Milestone M6 - Connectors & Automation (P2, standout)

- [ ] M6.1 GitHub connector: import issues/PRs/files as evidence
- [ ] M6.2 Scheduled sync (Celery beat) + drift detection alerts
- [ ] M6.3 Plugin-ish connector interface (so others can add Jira/Confluence/etc.)
- [ ] M6.4 Webhook support for near-real-time updates (where feasible)

---

## Milestone M7 - LLM Assist (P1/P2)

Core "no hallucination" is already implemented; next steps focus on UX + safe usefulness:
- [x] M7.1 Frontend UI for draft generation per section with evidence selection
- [x] M7.2 Frontend UI for gap suggestions + disclaimers
- [x] M7.3 "Citations only" rendering: show cited evidence and block uncited claims
- [x] M7.4 Admin controls: provider config, disable/enable, usage reporting

---

## Milestone M8 - Observability & Performance (P1)

- [x] M8.1 Structured logs with correlation IDs across API + worker
- [x] M8.2 Metrics endpoint (Prometheus) + basic dashboards
- [x] M8.3 Trace export generation time + slow queries
- [ ] M8.4 Large-evidence handling: pagination, streaming downloads, background jobs

---

## "Help Wanted" (Good OSS Contributions)

- [ ] Add translations/i18n for UI
- [ ] Improve offline viewer UX (filters, drill-down, export summary pages)
- [ ] Add more evidence type adapters (GitLab, Azure DevOps, Linear, etc.)
- [ ] Improve Annex-IV section schema/forms coverage
