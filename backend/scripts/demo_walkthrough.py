"""Create a small demo dataset and (optionally) generate a first export.

Intended for local/demo environments (Docker Compose). This script is safe to run
multiple times: it reuses existing records when possible.

Usage (inside the API container):
  DEMO_ADMIN_PASSWORD='YourStrongPassword123!' python scripts/demo_walkthrough.py
"""

import asyncio
import os
import sys
from pathlib import Path
from uuid import UUID

# Add backend/src to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select  # noqa: E402

from src.core.database import get_db  # noqa: E402
from src.core.security import (  # noqa: E402
    PasswordValidationError,
    hash_password,
    validate_password,
)
from src.models.ai_system import AISystem  # noqa: E402
from src.models.evidence_item import EvidenceItem  # noqa: E402
from src.models.enums import (  # noqa: E402
    DecisionInfluence,
    DeploymentType,
    EvidenceType,
    HRUseCaseType,
    MappingTargetType,
    UserRole,
)
from src.models.organization import Organization  # noqa: E402
from src.models.system_version import SystemVersion  # noqa: E402
from src.models.user import User  # noqa: E402
from src.schemas.ai_system import CreateSystemRequest  # noqa: E402
from src.schemas.evidence import CreateEvidenceRequest  # noqa: E402
from src.schemas.mapping import CreateMappingRequest  # noqa: E402
from src.schemas.version import CreateVersionRequest  # noqa: E402
from src.services.ai_system_service import AISystemService  # noqa: E402        
from src.services.evidence_service import EvidenceService  # noqa: E402
from src.services.export_service import ExportService  # noqa: E402
from src.services.mapping_service import MappingService  # noqa: E402
from src.services.section_service import SectionService  # noqa: E402
from src.services.version_service import VersionService  # noqa: E402


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


async def demo_walkthrough() -> None:
    org_name = os.environ.get("DEMO_ORG_NAME", "AnnexOps Demo")
    admin_email = os.environ.get("DEMO_ADMIN_EMAIL", "admin@annexops.local")
    admin_password = os.environ.get("DEMO_ADMIN_PASSWORD")
    system_name = os.environ.get("DEMO_SYSTEM_NAME", "Example HR Screening Model")
    version_label = os.environ.get("DEMO_VERSION_LABEL", "v0-demo")
    generate_export = _env_bool("DEMO_GENERATE_EXPORT", default=True)

    if not admin_password:
        print("Missing DEMO_ADMIN_PASSWORD environment variable.")
        print("Example: DEMO_ADMIN_PASSWORD='YourStrongPassword123!' python scripts/demo_walkthrough.py")
        return

    try:
        validate_password(admin_password)
    except PasswordValidationError as e:
        print(f"Password validation failed: {e}")
        return

    async for db in get_db():
        # Organization
        result = await db.execute(select(Organization).where(Organization.name == org_name))
        org = result.scalar_one_or_none()
        if not org:
            org = Organization(name=org_name, is_active=True)
            db.add(org)
            await db.flush()
            print(f"Created organization: {org.name} ({org.id})")
        else:
            print(f"Using existing organization: {org.name} ({org.id})")

        # Admin user
        result = await db.execute(select(User).where(User.email == admin_email))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(
                org_id=org.id,
                email=admin_email,
                password_hash=hash_password(admin_password),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            await db.flush()
            print(f"Created admin user: {admin.email}")
        else:
            print(f"Using existing admin user: {admin.email} ({admin.id})")

        # System
        result = await db.execute(
            select(AISystem).where(AISystem.org_id == org.id).where(AISystem.name == system_name)
        )
        system = result.scalar_one_or_none()
        if not system:
            system_request = CreateSystemRequest(
                name=system_name,
                description="Demo system created by scripts/demo_walkthrough.py",
                hr_use_case_type=HRUseCaseType.RECRUITMENT_SCREENING,
                intended_purpose="Screen and rank candidates for an interview shortlist.",
                deployment_type=DeploymentType.SAAS,
                decision_influence=DecisionInfluence.SEMI_AUTOMATED,
                contact_name="Compliance Team",
                contact_email=None,
            )
            system = await AISystemService(db).create(system_request, admin)
            await db.flush()
            print(f"Created system: {system.name} ({system.id})")
        else:
            print(f"Using existing system: {system.name} ({system.id})")

        # Version
        result = await db.execute(
            select(SystemVersion)
            .where(SystemVersion.ai_system_id == system.id)
            .where(SystemVersion.label == version_label)
        )
        version = result.scalar_one_or_none()
        if not version:
            version_request = CreateVersionRequest(label=version_label, notes="Demo version")
            version = await VersionService(db).create(system.id, version_request, admin)
            await db.flush()
            print(f"Created version: {version.label} ({version.id})")
        else:
            print(f"Using existing version: {version.label} ({version.id})")

        # Ensure Annex IV sections exist
        section_service = SectionService(db)
        await section_service.list_sections(version_id=version.id, org_id=org.id)

        # Evidence (NOTE + URL)
        evidence_service = EvidenceService(db)

        async def _get_or_create_evidence(
            title: str,
            ev_type: EvidenceType,
            type_metadata: dict,
        ) -> UUID:
            # Lightweight lookup by title within org (best-effort)
            existing_result = await db.execute(
                select(EvidenceItem)
                .where(EvidenceItem.org_id == org.id)
                .where(EvidenceItem.title == title)
            )
            existing_item = existing_result.scalar_one_or_none()
            if existing_item:
                return existing_item.id

            req = CreateEvidenceRequest(
                type=ev_type,
                title=title,
                description=None,
                tags=["demo"],
                type_metadata=type_metadata,
            )
            created, _duplicate = await evidence_service.create(req, admin)
            await db.flush()
            return created.id

        note_id = await _get_or_create_evidence(
            "Risk Assessment Notes",
            EvidenceType.NOTE,
            {"content": "Demo note evidence. Add real process notes here."},
        )
        url_id = await _get_or_create_evidence(
            "Public Policy Reference",
            EvidenceType.URL,
            {"url": "https://example.com/policy", "accessed_at": None},
        )

        # Map evidence to a section target
        mapping_service = MappingService(db)
        for evidence_id in (note_id, url_id):
            try:
                await mapping_service.create(
                    version_id=version.id,
                    request=CreateMappingRequest(
                        evidence_id=evidence_id,
                        target_type=MappingTargetType.SECTION,
                        target_key="ANNEX4.RISK_MANAGEMENT",
                        strength=None,
                        notes="Demo mapping created by script.",
                    ),
                    current_user=admin,
                )
            except Exception:
                # Ignore duplicates when rerunning
                pass

        # Populate a section with content and evidence refs
        await section_service.update_content(
            version_id=version.id,
            section_key="ANNEX4.RISK_MANAGEMENT",
            content={
                "risk_management_system_description": "This is demo content. Replace with your real risk management system description.",
                "identified_risks": ["Bias", "Data quality", "Security"],
            },
            evidence_refs=[note_id, url_id],
            expected_updated_at=None,
            force=True,
            current_user=admin,
        )

        if generate_export:
            export_service = ExportService(db)
            export = await export_service.generate_export(
                version_id=version.id,
                org_id=org.id,
                user=admin,
                include_diff=False,
                compare_version_id=None,
            )
            await db.flush()
            print(f"Generated export: {export.id} (snapshot_hash={export.snapshot_hash})")

        await db.commit()

    print("Done.")
    print(f"Login: {admin_email} / (password you set in DEMO_ADMIN_PASSWORD)")
    print("UI: open the frontend and explore the demo system/version.")


if __name__ == "__main__":
    asyncio.run(demo_walkthrough())
