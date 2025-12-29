"""Service layer for export operations."""

import csv
import io
import json
import logging
import time
import zipfile
from html import escape as html_escape
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.storage import get_storage_client
from src.core.structured_logging import log_json
from src.models.ai_system import AISystem
from src.models.annex_section import AnnexSection
from src.models.enums import AuditAction
from src.models.evidence_mapping import EvidenceMapping
from src.models.export import Export
from src.models.high_risk_assessment import HighRiskAssessment
from src.models.organization import Organization
from src.models.system_version import SystemVersion
from src.models.user import User
from src.services.audit_service import AuditService
from src.services.completeness_service import get_completeness_report
from src.services.docx_generator import generate_annex_iv_document
from src.services.snapshot_service import SnapshotService
from src.services.storage_service import get_storage_service

logger = logging.getLogger(__name__)


class ExportService:
    """Service for export operations."""

    def __init__(self, db: AsyncSession):
        """Initialize export service.

        Args:
            db: Database session
        """
        self.db = db
        self.audit_service = AuditService(db)

    async def list_exports(
        self,
        version_id: UUID,
        org_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Export], int]:
        """List exports for a system version.

        Args:
            version_id: System version ID
            org_id: Organization ID (for authorization check)
            limit: Maximum items to return
            offset: Number of items to skip

        Returns:
            Tuple of (exports list, total count)

        Raises:
            HTTPException: 404 if version not found or doesn't belong to org
        """
        # Verify version exists and belongs to org
        version_query = (
            select(SystemVersion)
            .join(AISystem, SystemVersion.ai_system_id == AISystem.id)
            .where(
                SystemVersion.id == version_id,
                AISystem.org_id == org_id,
            )
        )
        result = await self.db.execute(version_query)
        version = result.scalar_one_or_none()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Version not found",
            )

        # Get total count
        count_query = (
            select(func.count()).select_from(Export).where(Export.version_id == version_id)
        )
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        # Get exports
        exports_query = (
            select(Export)
            .where(Export.version_id == version_id)
            .order_by(Export.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(exports_query)
        exports = result.scalars().all()

        return list(exports), total

    async def get_download_url(
        self,
        export_id: UUID,
        org_id: UUID,
    ) -> str:
        """Get presigned download URL for an export.

        Args:
            export_id: Export ID
            org_id: Organization ID (for authorization check)

        Returns:
            Presigned download URL (valid for 1 hour)

        Raises:
            HTTPException: 404 if export not found or doesn't belong to org
        """
        # Get export with version join for org check
        query = (
            select(Export)
            .join(SystemVersion, Export.version_id == SystemVersion.id)
            .join(AISystem, SystemVersion.ai_system_id == AISystem.id)
            .where(
                Export.id == export_id,
                AISystem.org_id == org_id,
            )
        )
        result = await self.db.execute(query)
        export = result.scalar_one_or_none()

        if not export:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Export not found",
            )

        # Generate presigned download URL
        storage_service = get_storage_service()
        download_url = storage_service.generate_download_url(
            export.storage_uri,
            expires_in=3600,
        )

        return download_url

    async def generate_export(
        self,
        version_id: UUID,
        org_id: UUID,
        user: User,
        include_diff: bool = False,
        compare_version_id: UUID | None = None,
    ) -> Export:
        """Generate an export package for a system version.

        Creates a ZIP file containing:
        - AnnexIV.docx: The main document
        - SystemManifest.json: Version metadata with snapshot hash
        - EvidenceIndex.json: All evidence items (sorted)
        - EvidenceIndex.csv: Evidence items in CSV format
        - CompletenessReport.json: Completeness scores and gaps
        - DiffReport.json: (optional) Changes from compare version

        Args:
            version_id: System version ID
            org_id: Organization ID
            user: User generating the export
            include_diff: Whether to include diff report
            compare_version_id: Version to compare against (if include_diff)

        Returns:
            Created Export record

        Raises:
            HTTPException: 404 if version not found
            HTTPException: 400 if include_diff but no compare_version_id        
        """
        started = time.perf_counter()
        log_json(
            logger,
            logging.INFO,
            "export_generate_start",
            version_id=version_id,
            org_id=org_id,
            include_diff=include_diff,
            compare_version_id=compare_version_id,
        )

        # Validate diff params
        if include_diff and not compare_version_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="compare_version_id required when include_diff is true",
            )

        # Get version with system
        version_query = (
            select(SystemVersion)
            .join(AISystem, SystemVersion.ai_system_id == AISystem.id)
            .options(selectinload(SystemVersion.ai_system))
            .where(
                SystemVersion.id == version_id,
                AISystem.org_id == org_id,
            )
        )
        result = await self.db.execute(version_query)
        version = result.scalar_one_or_none()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Version not found",
            )

        ai_system = version.ai_system

        # Get all sections for this version
        sections_query = (
            select(AnnexSection)
            .where(AnnexSection.version_id == version_id)
            .order_by(AnnexSection.section_key)
        )
        sections_result = await self.db.execute(sections_query)
        sections = list(sections_result.scalars().all())

        # Get evidence items mapped to this version
        mappings_query = (
            select(EvidenceMapping)
            .options(selectinload(EvidenceMapping.evidence_item))
            .where(EvidenceMapping.version_id == version_id)
        )
        mappings_result = await self.db.execute(mappings_query)
        mappings = list(mappings_result.scalars().all())

        # Extract unique evidence items (sorted by ID for determinism)
        evidence_map = {}
        for mapping in mappings:
            if mapping.evidence_item:
                evidence_map[str(mapping.evidence_item.id)] = mapping.evidence_item
        evidence_items = sorted(evidence_map.values(), key=lambda e: str(e.id))

        # Get completeness report
        completeness = await get_completeness_report(self.db, version_id) 

        # Load org + optional assessment for canonical manifest (SSOT)
        org_result = await self.db.execute(select(Organization).where(Organization.id == org_id))
        org = org_result.scalar_one_or_none()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )

        assessment_result = await self.db.execute(
            select(HighRiskAssessment)
            .where(HighRiskAssessment.ai_system_id == ai_system.id)
            .order_by(HighRiskAssessment.created_at.desc())
            .limit(1)
        )
        assessment = assessment_result.scalar_one_or_none()

        snapshot_service = SnapshotService()
        manifest = snapshot_service.generate_manifest(
            org=org,
            version=version,
            ai_system=ai_system,
            sections=sections,
            evidence_items=evidence_items,
            mappings=mappings,
            assessment=assessment,
        )
        manifest = snapshot_service.finalize_manifest(manifest)
        snapshot_hash = manifest.snapshot_hash or snapshot_service.compute_hash_from_manifest(manifest)

        # Prepare data for DOCX
        system_info = {
            "id": str(ai_system.id),
            "name": ai_system.name,
            "hr_use_case_type": ai_system.hr_use_case_type.value,
            "intended_purpose": ai_system.intended_purpose,
            "org_name": "",  # Could be populated if org relationship exists
        }
        version_info = {
            "id": str(version.id),
            "label": version.label,
            "status": version.status.value,
            "release_date": version.release_date.isoformat() if version.release_date else None,
        }
        sections_data = [
            {
                "section_key": s.section_key,
                "content": s.content or {},
                "evidence_refs": s.evidence_refs or [],
            }
            for s in sections
        ]
        evidence_data = [
            {
                "id": str(e.id),
                "title": e.title,
                "type": e.type.value,
            }
            for e in evidence_items
        ]

        # Generate DOCX
        docx_buffer = generate_annex_iv_document(
            system_info=system_info,
            version_info=version_info,
            sections=sections_data,
            evidence_items=evidence_data,
        )

        # Generate EvidenceIndex.json (sorted)
        manifest_checksums = {item.id: item.checksum for item in manifest.evidence_index.values()}
        evidence_index = [
            {
                "id": str(e.id),
                "title": e.title,
                "type": e.type.value,
                "description": e.description,
                "classification": e.classification.value,
                "tags": sorted({t for t in (e.tags or []) if t}),
                "type_metadata": e.type_metadata or {},
                "checksum": manifest_checksums.get(str(e.id), ""),
            }
            for e in evidence_items
        ]
        evidence_json = json.dumps(
            evidence_index, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )

        # Generate EvidenceIndex.csv
        csv_buffer = io.StringIO()
        csv_writer = csv.DictWriter(
            csv_buffer,
            fieldnames=["id", "title", "type", "description", "classification", "tags"],
        )
        csv_writer.writeheader()
        for e in evidence_items:
            csv_writer.writerow(
                {
                    "id": str(e.id),
                    "title": e.title,
                    "type": e.type.value,
                    "description": e.description or "",
                    "classification": e.classification.value,
                    "tags": ",".join(sorted({t for t in (e.tags or []) if t})),
                }
            )
        evidence_csv = csv_buffer.getvalue()

        # Generate CompletenessReport.json
        completeness_data = {
            "version_id": str(version_id),
            "overall_score": float(completeness.overall_score),
            "generated_at": datetime.now(UTC).isoformat() + "Z",
            "sections": [
                {
                    "section_key": s.section_key,
                    "title": s.title,
                    "score": float(s.score),
                    "evidence_count": s.evidence_count,
                    "field_completion": s.field_completion,
                    "gaps": s.gaps,
                }
                for s in completeness.sections
            ],
            "gaps": [
                {
                    "section_key": g.section_key,
                    "gap_type": g.gap_type,
                    "description": g.description,
                }
                for g in completeness.gaps
            ],
        }
        completeness_json = json.dumps(
            completeness_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )

        # Generate SystemManifest.json
        manifest_json = json.dumps(
            manifest.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )

        # Create ZIP package (sorted entries for determinism)
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:      
            # Add files in sorted order for determinism
            files_to_add = [
                ("AnnexIV.docx", docx_buffer.getvalue()),
                ("CompletenessReport.json", completeness_json.encode("utf-8")), 
                ("EvidenceIndex.csv", evidence_csv.encode("utf-8")),
                ("EvidenceIndex.json", evidence_json.encode("utf-8")),
                ("SystemManifest.json", manifest_json.encode("utf-8")),
            ]

            # Add diff report if requested
            if include_diff and compare_version_id:
                diff_data = await self._generate_diff_report(version_id, compare_version_id, org_id)
                diff_json = json.dumps(
                    diff_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                )
                files_to_add.append(("DiffReport.json", diff_json.encode("utf-8")))

            # Add offline viewer (self-contained HTML; no network fetch)
            viewer_html = self._generate_export_viewer_html(
                manifest_json=manifest_json,
                evidence_json=evidence_json,
                completeness_json=completeness_json,
                diff_json=diff_json if include_diff and compare_version_id else None,
            )
            files_to_add.append(("viewer/index.html", viewer_html.encode("utf-8")))

            files_to_add.sort(key=lambda x: x[0])

            for filename, content in files_to_add:
                zf.writestr(filename, content)

        zip_buffer.seek(0)
        zip_content = zip_buffer.getvalue()
        file_size = len(zip_content)

        # Upload to MinIO
        storage_client = get_storage_client()
        export_id = uuid4()
        storage_uri = f"exports/{org_id}/{ai_system.id}/{version_id}/{export_id}.zip"

        storage_client._client.put_object(
            Bucket=storage_client._bucket,
            Key=storage_uri,
            Body=zip_content,
            ContentType="application/zip",
            Metadata={
                "snapshot-hash": snapshot_hash,
            },
        )

        # Create Export record
        export_record = Export(
            id=export_id,
            version_id=version_id,
            export_type="diff" if include_diff else "full",
            snapshot_hash=snapshot_hash,
            storage_uri=storage_uri,
            file_size=file_size,
            include_diff=include_diff,
            compare_version_id=compare_version_id,
            completeness_score=Decimal(str(completeness.overall_score)),
            created_by=user.id,
        )
        self.db.add(export_record)
        await self.db.flush()
        await self.db.refresh(export_record)

        # Audit logging
        await self.audit_service.log(
            org_id=org_id,
            user_id=user.id,
            action=AuditAction.EXPORT_CREATE,
            entity_type="export",
            entity_id=export_record.id,
            diff_json={
                "version_id": str(version_id),
                "export_type": export_record.export_type,
                "snapshot_hash": snapshot_hash,
                "file_size": file_size,
                "include_diff": include_diff,
                "compare_version_id": str(compare_version_id) if compare_version_id else None,
            },
        )

        duration_ms = (time.perf_counter() - started) * 1000
        log_json(
            logger,
            logging.INFO,
            "export_generate_done",
            export_id=export_record.id,
            version_id=version_id,
            org_id=org_id,
            include_diff=include_diff,
            compare_version_id=compare_version_id,
            file_size=file_size,
            snapshot_hash=snapshot_hash,
            duration_ms=round(duration_ms, 2),
        )

        return export_record

    def _generate_export_viewer_html(
        self,
        *,
        manifest_json: str,
        evidence_json: str,
        completeness_json: str,
        diff_json: str | None,
    ) -> str:
        def _safe_script_json(raw: str) -> str:
            # Prevent accidental </script> termination and keep output readable.
            return raw.replace("</", "<\\/")

        manifest_json_safe = _safe_script_json(manifest_json)
        evidence_json_safe = _safe_script_json(evidence_json)
        completeness_json_safe = _safe_script_json(completeness_json)
        diff_json_safe = _safe_script_json(diff_json) if diff_json else "null"

        manifest_html = html_escape(manifest_json_safe)
        evidence_html = html_escape(evidence_json_safe)
        completeness_html = html_escape(completeness_json_safe)
        diff_html = html_escape(diff_json_safe)

        # Basic, dependency-free viewer (works offline; data is embedded).
        template = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AnnexOps Evidence Pack Viewer</title>
    <style>
      :root {{
        --bg: #0b1020;
        --panel: #121a33;
        --muted: #9aa7c7;
        --text: #eef2ff;
        --border: rgba(255,255,255,0.10);
        --accent: #7c3aed;
        --good: #22c55e;
        --warn: #f59e0b;
      }}
      body {{
        margin: 0;
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        background: radial-gradient(1200px 800px at 15% 0%, rgba(124, 58, 237, 0.35), transparent 60%),
                    radial-gradient(900px 700px at 95% 15%, rgba(34, 197, 94, 0.18), transparent 55%),
                    var(--bg);
        color: var(--text);
      }}
      a {{ color: #a78bfa; }}
      .wrap {{ max-width: 1100px; margin: 0 auto; padding: 28px 18px 60px; }}
      .title {{
        display: flex; gap: 14px; align-items: baseline; flex-wrap: wrap;
      }}
      .title h1 {{ margin: 0; font-size: 22px; letter-spacing: 0.2px; }}
      .badge {{
        display: inline-flex; align-items: center; gap: 8px;
        font-size: 12px; color: var(--muted);
        border: 1px solid var(--border); border-radius: 999px;
        padding: 6px 10px; background: rgba(255,255,255,0.04);
      }}
      .grid {{ display: grid; grid-template-columns: 1fr; gap: 14px; margin-top: 16px; }}
      @media (min-width: 960px) {{ .grid {{ grid-template-columns: 1fr 1fr; }} }}
      .card {{
        border: 1px solid var(--border);
        background: rgba(18, 26, 51, 0.75);
        backdrop-filter: blur(6px);
        border-radius: 14px;
        padding: 14px 14px 12px;
      }}
      .card h2 {{ margin: 0 0 10px; font-size: 14px; color: var(--muted); font-weight: 600; }}
      .kv {{ display: grid; grid-template-columns: 170px 1fr; gap: 6px 12px; font-size: 13px; }}
      .k {{ color: var(--muted); }}
      .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
      .search {{
        width: 100%; padding: 10px 12px; border-radius: 10px;
        border: 1px solid var(--border); background: rgba(0,0,0,0.25);
        color: var(--text);
      }}
      table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
      th, td {{ padding: 10px 8px; border-top: 1px solid var(--border); vertical-align: top; }}
      th {{ text-align: left; color: var(--muted); font-weight: 600; }}
      .pill {{
        display: inline-flex; padding: 2px 8px; border-radius: 999px;
        border: 1px solid var(--border); background: rgba(255,255,255,0.04);
        color: var(--muted); font-size: 12px;
      }}
      .score {{
        display: inline-flex; align-items: center; gap: 8px;
      }}
      .dot {{
        width: 10px; height: 10px; border-radius: 999px; display: inline-block;
      }}
      .dot.good {{ background: var(--good); }}
      .dot.warn {{ background: var(--warn); }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="title">
        <h1>Evidence Pack Viewer</h1>
        <span class="badge">AnnexOps export (offline)</span>
      </div>

      <div class="grid">
        <div class="card">
          <h2>System</h2>
          <div class="kv" id="system-kv"></div>
        </div>
        <div class="card">
          <h2>Completeness</h2>
          <div class="kv" id="completeness-kv"></div>
        </div>
      </div>

      <div class="card" style="margin-top: 14px;">
        <h2>Sections</h2>
        <div id="sections"></div>
      </div>

      <div class="card" style="margin-top: 14px;">
        <h2>Evidence</h2>
        <input id="evidence-search" class="search" placeholder="Search title/type/tags…" />
        <div style="height: 10px;"></div>
        <div style="overflow:auto;">
          <table>
            <thead>
              <tr>
                <th style="width: 220px;">Title</th>
                <th style="width: 90px;">Type</th>
                <th style="width: 120px;">Classification</th>
                <th>Tags</th>
              </tr>
            </thead>
            <tbody id="evidence-rows"></tbody>
          </table>
        </div>
      </div>

      <div class="card" style="margin-top: 14px;">
        <h2>Diff</h2>
        <div id="diff"></div>
      </div>
    </div>

    <script id="annexops-manifest" type="application/json">__ANNEXOPS_MANIFEST__</script>
    <script id="annexops-evidence" type="application/json">__ANNEXOPS_EVIDENCE__</script>
    <script id="annexops-completeness" type="application/json">__ANNEXOPS_COMPLETENESS__</script>
    <script id="annexops-diff" type="application/json">__ANNEXOPS_DIFF__</script>
    <script>
      const manifest = JSON.parse(document.getElementById('annexops-manifest').textContent);
      const evidence = JSON.parse(document.getElementById('annexops-evidence').textContent);
      const completeness = JSON.parse(document.getElementById('annexops-completeness').textContent);
      const diff = JSON.parse(document.getElementById('annexops-diff').textContent);

      const systemKv = document.getElementById('system-kv');
      const completenessKv = document.getElementById('completeness-kv');

      const row = (k, v, mono=false) => `
        <div class="k">${k}</div>
        <div class="${mono ? 'mono' : ''}">${v ?? ''}</div>
      `;

      systemKv.innerHTML = [
        row('Organization', manifest.org?.name),
        row('System', manifest.ai_system?.name),
        row('Version', manifest.system_version?.label),
        row('Status', manifest.system_version?.status),
        row('Snapshot Hash', `<span class="mono">${manifest.snapshot_hash || ''}</span>`),
      ].join('');

      const score = Number(completeness?.overall_score ?? 0);
      const dotClass = score >= 0.8 ? 'good' : 'warn';
      completenessKv.innerHTML = [
        row('Overall Score', `<span class="score"><span class="dot ${dotClass}"></span>${Math.round(score * 100)}%</span>`),
        row('Generated At', `<span class="mono">${completeness?.generated_at || ''}</span>`),
      ].join('');

      // Sections list
      const sectionsRoot = document.getElementById('sections');
      const sections = manifest.annex_sections || {};
      const keys = Object.keys(sections).sort();
      sectionsRoot.innerHTML = `
        <table>
          <thead>
            <tr><th style="width:240px;">Key</th><th>Evidence Refs</th></tr>
          </thead>
          <tbody>
            ${keys.map(k => {
              const refs = (sections[k].evidence_refs || []).slice().sort();
              return `<tr>
                <td class="mono">${k}</td>
                <td>${refs.length ? refs.map(r => `<span class="pill mono" title="${r}">${r.slice(0, 8)}…</span>`).join(' ') : '<span class="pill">none</span>'}</td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
      `;

      // Evidence table with search
      const rowsEl = document.getElementById('evidence-rows');
      const searchEl = document.getElementById('evidence-search');
      const renderEvidence = (q) => {
        const query = (q || '').trim().toLowerCase();
        const filtered = evidence.filter(e => {
          if (!query) return true;
          const hay = [
            e.title, e.type, e.classification,
            ...(e.tags || []),
          ].join(' ').toLowerCase();
          return hay.includes(query);
        });

        rowsEl.innerHTML = filtered.map(e => {
          const tags = (e.tags || []).slice().sort();
          return `<tr>
            <td>
              <div>${e.title || ''}</div>
              <div class="mono" style="color: var(--muted); margin-top: 4px;">${e.id}</div>
            </td>
            <td><span class="pill">${e.type}</span></td>
            <td><span class="pill">${e.classification}</span></td>
            <td>${tags.length ? tags.map(t => `<span class="pill">${t}</span>`).join(' ') : '<span class="pill">—</span>'}</td>
          </tr>`;
        }).join('');
      };
      renderEvidence('');
      searchEl.addEventListener('input', (ev) => renderEvidence(ev.target.value));

      // Diff
      const diffEl = document.getElementById('diff');
      if (!diff || !diff.section_changes) {
        diffEl.innerHTML = '<span class="pill">No diff included in this export.</span>';
      } else {
        const changes = diff.section_changes || [];
        diffEl.innerHTML = `
          <div style="color: var(--muted); font-size: 13px; margin-bottom: 10px;">
            ${changes.length} section change(s)
          </div>
          <div style="overflow:auto;">
            <table>
              <thead><tr><th style="width:240px;">Section</th><th style="width:120px;">Type</th><th>Details</th></tr></thead>
              <tbody>
                ${changes.map(c => `<tr>
                  <td class="mono">${c.section_key}</td>
                  <td><span class="pill">${c.change_type}</span></td>
                  <td class="mono" style="color: var(--muted);">Keys: current=${Object.keys(c.current_content||{}).length}, prev=${Object.keys(c.previous_content||{}).length}</td>
                </tr>`).join('')}
              </tbody>
            </table>
          </div>
        `;
      }
    </script>
  </body>
</html>
"""

        template = template.replace("{{", "{").replace("}}", "}")
        return (
            template.replace("__ANNEXOPS_MANIFEST__", manifest_html)
            .replace("__ANNEXOPS_EVIDENCE__", evidence_html)
            .replace("__ANNEXOPS_COMPLETENESS__", completeness_html)
            .replace("__ANNEXOPS_DIFF__", diff_html)
        )

    async def _generate_diff_report(
        self,
        version_id: UUID,
        compare_version_id: UUID,
        org_id: UUID,
    ) -> dict:
        """Generate diff report between two versions.

        Args:
            version_id: Current version ID
            compare_version_id: Version to compare against
            org_id: Organization ID

        Returns:
            Dict with section and evidence changes
        """
        # Get both versions' sections
        current_sections = await self._get_sections_map(version_id)
        compare_sections = await self._get_sections_map(compare_version_id)

        # Get both versions' evidence mappings
        current_evidence = await self._get_evidence_ids(version_id)
        compare_evidence = await self._get_evidence_ids(compare_version_id)

        # Calculate changes
        section_changes = []
        all_keys = set(current_sections.keys()) | set(compare_sections.keys())

        for key in sorted(all_keys):
            current = current_sections.get(key, {})
            compare = compare_sections.get(key, {})

            if current != compare:
                section_changes.append(
                    {
                        "section_key": key,
                        "change_type": "modified"
                        if key in current_sections and key in compare_sections
                        else ("added" if key in current_sections else "removed"),
                        "current_content": current,
                        "previous_content": compare,
                    }
                )

        # Evidence changes
        added_evidence = list(current_evidence - compare_evidence)
        removed_evidence = list(compare_evidence - current_evidence)

        return {
            "version_id": str(version_id),
            "compare_version_id": str(compare_version_id),
            "generated_at": datetime.now(UTC).isoformat() + "Z",
            "section_changes": section_changes,
            "evidence_changes": {
                "added": sorted(added_evidence),
                "removed": sorted(removed_evidence),
            },
        }

    async def _get_sections_map(self, version_id: UUID) -> dict:
        """Get sections as a map keyed by section_key."""
        query = select(AnnexSection).where(AnnexSection.version_id == version_id)
        result = await self.db.execute(query)
        sections = result.scalars().all()
        return {s.section_key: s.content or {} for s in sections}

    async def _get_evidence_ids(self, version_id: UUID) -> set:
        """Get set of evidence IDs mapped to a version."""
        query = select(EvidenceMapping.evidence_id).where(EvidenceMapping.version_id == version_id)
        result = await self.db.execute(query)
        return {str(row[0]) for row in result.fetchall()}
