"""Pytest fixtures for testing."""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from uuid import UUID

import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("BOOTSTRAP_TOKEN", "test-bootstrap-token")

from src.core.database import get_db
from src.core.security import hash_password
from src.main import app
from src.models.ai_system import AISystem
from src.models.annex_section import AnnexSection
from src.models.base import Base
from src.models.enums import (
    AnnexSectionKey,
    Classification,
    DecisionInfluence,
    DeploymentType,
    EvidenceType,
    HRUseCaseType,
    MappingStrength,
    MappingTargetType,
    UserRole,
    VersionStatus,
)
from src.models.evidence_item import EvidenceItem
from src.models.evidence_mapping import EvidenceMapping
from src.models.export import Export
from src.models.llm_interaction import LlmInteraction
from src.models.log_api_key import LogApiKey
from src.models.organization import Organization
from src.models.system_version import SystemVersion
from src.models.user import User

# Test database URL (using port 5433 to avoid conflict with local postgres)
TEST_DATABASE_URL = "postgresql+asyncpg://annexops:annexops@localhost:5433/annexops_test"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

# Create test session factory
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
def bootstrap_headers() -> dict[str, str]:
    return {"X-Bootstrap-Token": os.environ["BOOTSTRAP_TOKEN"]}


@pytest_asyncio.fixture(scope="function")
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Create test database session.

    Creates all tables before each test and drops them after.
    Drops everything first to ensure clean slate even if previous test crashed.
    """
    # First, drop all tables and types to ensure clean state
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(sa.text("DROP TYPE IF EXISTS user_role CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS audit_action CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS hr_use_case_type CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS deployment_type CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS decision_influence CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS assessment_result CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS version_status CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS evidence_type CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS classification CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS mapping_target_type CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS mapping_strength CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS annex_section_key CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS export_type CASCADE"))

    # Create enum types (must exist before tables reference them)
    async with test_engine.begin() as conn:
        await conn.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.execute(
            sa.text("CREATE TYPE user_role AS ENUM ('admin', 'editor', 'reviewer', 'viewer')")
        )
        await conn.execute(
            sa.text(
                "CREATE TYPE audit_action AS ENUM ('organization.create', 'organization.update', 'user.create', 'user.update', 'user.delete', 'user.role_change', 'user.login', 'user.logout', 'user.lockout', 'invitation.create', 'invitation.accept', 'invitation.expire', 'invitation.revoke', 'ai_system.create', 'ai_system.update', 'ai_system.delete', 'assessment.create', 'attachment.upload', 'attachment.delete', 'version.create', 'version.update', 'version.delete', 'version.status_change', 'evidence.create', 'evidence.update', 'evidence.delete', 'mapping.create', 'mapping.delete', 'section.update', 'export.create')"
            )
        )
        await conn.execute(
            sa.text(
                "CREATE TYPE hr_use_case_type AS ENUM ('recruitment_screening', 'application_filtering', 'candidate_matching', 'performance_evaluation', 'employee_monitoring', 'task_allocation', 'promotion_termination', 'other_hr')"
            )
        )
        await conn.execute(
            sa.text("CREATE TYPE deployment_type AS ENUM ('saas', 'onprem', 'hybrid')")
        )
        await conn.execute(
            sa.text(
                "CREATE TYPE decision_influence AS ENUM ('assistive', 'semi_automated', 'automated')"
            )
        )
        await conn.execute(
            sa.text(
                "CREATE TYPE assessment_result AS ENUM ('likely_high_risk', 'unclear', 'likely_not')"
            )
        )
        await conn.execute(
            sa.text("CREATE TYPE version_status AS ENUM ('draft', 'review', 'approved')")
        )
        await conn.execute(
            sa.text("CREATE TYPE evidence_type AS ENUM ('upload', 'url', 'git', 'ticket', 'note')")
        )
        await conn.execute(
            sa.text("CREATE TYPE classification AS ENUM ('public', 'internal', 'confidential')")
        )
        await conn.execute(
            sa.text("CREATE TYPE mapping_target_type AS ENUM ('section', 'field', 'requirement')")
        )
        await conn.execute(
            sa.text("CREATE TYPE mapping_strength AS ENUM ('weak', 'medium', 'strong')")
        )

    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async with TestSessionLocal() as session:
        try:
            yield session
        finally:
            # Always rollback to clean up - we're dropping all tables anyway
            # This also handles the case where a test triggered an IntegrityError
            try:
                await session.rollback()
            except Exception:
                pass
            await session.close()

    # Drop all tables and enum types
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        # Also drop enum types to ensure clean state
        await conn.execute(sa.text("DROP TYPE IF EXISTS user_role CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS audit_action CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS hr_use_case_type CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS deployment_type CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS decision_influence CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS assessment_result CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS version_status CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS evidence_type CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS classification CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS mapping_target_type CASCADE"))
        await conn.execute(sa.text("DROP TYPE IF EXISTS mapping_strength CASCADE"))


@pytest_asyncio.fixture(scope="function")
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database dependency override.

    Args:
        db: Test database session

    Yields:
        AsyncClient configured for testing
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_org(db: AsyncSession) -> Organization:
    """Create a test organization.

    Args:
        db: Database session

    Returns:
        Test Organization instance
    """
    org = Organization(name="Test Organization")
    db.add(org)
    await db.flush()
    return org


@pytest_asyncio.fixture
async def test_admin_user(db: AsyncSession, test_org: Organization) -> User:
    """Create a test admin user.

    Args:
        db: Database session
        test_org: Test organization

    Returns:
        Test User instance with ADMIN role
    """
    user = User(
        org_id=test_org.id,
        email="admin@test.com",
        password_hash=hash_password("TestPass123!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def test_editor_user(db: AsyncSession, test_org: Organization) -> User:
    """Create a test editor user.

    Args:
        db: Database session
        test_org: Test organization

    Returns:
        Test User instance with EDITOR role
    """
    user = User(
        org_id=test_org.id,
        email="editor@test.com",
        password_hash=hash_password("TestPass123!"),
        role=UserRole.EDITOR,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def test_viewer_user(db: AsyncSession, test_org: Organization) -> User:
    """Create a test viewer user.

    Args:
        db: Database session
        test_org: Test organization

    Returns:
        Test User instance with VIEWER role
    """
    user = User(
        org_id=test_org.id,
        email="viewer@test.com",
        password_hash=hash_password("TestPass123!"),
        role=UserRole.VIEWER,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def create_user(
    db: AsyncSession,
    org_id: str,
    email: str,
    password: str = "TestPass123!",
    role: UserRole = UserRole.VIEWER,
    is_active: bool = True,
) -> User:
    """User factory for creating test users.

    Args:
        db: Database session
        org_id: Organization ID
        email: User email
        password: User password (default: TestPass123!)
        role: User role (default: VIEWER)
        is_active: Account active status (default: True)

    Returns:
        Created User instance
    """
    user = User(
        org_id=org_id,
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def test_ai_system(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
) -> AISystem:
    """Create a test AI system.

    Args:
        db: Database session
        test_org: Test organization
        test_editor_user: Test editor user as owner

    Returns:
        Test AISystem instance
    """
    system = AISystem(
        org_id=test_org.id,
        name="Test CV Screening System",
        description="AI-powered resume screening for initial candidate filtering",
        hr_use_case_type=HRUseCaseType.RECRUITMENT_SCREENING,
        intended_purpose="Assist recruiters by pre-filtering applications",
        deployment_type=DeploymentType.SAAS,
        decision_influence=DecisionInfluence.ASSISTIVE,
        owner_user_id=test_editor_user.id,
        contact_name="Test Contact",
        contact_email="contact@test.com",
    )
    db.add(system)
    await db.flush()
    return system


async def create_ai_system(
    db: AsyncSession,
    org_id: UUID,
    name: str,
    owner_user_id: UUID | None = None,
    hr_use_case_type: HRUseCaseType = HRUseCaseType.RECRUITMENT_SCREENING,
    deployment_type: DeploymentType = DeploymentType.SAAS,
    decision_influence: DecisionInfluence = DecisionInfluence.ASSISTIVE,
) -> AISystem:
    """AI System factory for creating test systems.

    Args:
        db: Database session
        org_id: Organization ID
        name: System name
        owner_user_id: Owner user ID
        hr_use_case_type: HR use case type
        deployment_type: Deployment type
        decision_influence: Decision influence level

    Returns:
        Created AISystem instance
    """
    system = AISystem(
        org_id=org_id,
        name=name,
        description=f"Description for {name}",
        hr_use_case_type=hr_use_case_type,
        intended_purpose=f"Purpose for {name}",
        deployment_type=deployment_type,
        decision_influence=decision_influence,
        owner_user_id=owner_user_id,
    )
    db.add(system)
    await db.flush()
    return system


@pytest_asyncio.fixture
async def test_version(
    db: AsyncSession,
    test_ai_system: AISystem,
    test_editor_user: User,
) -> SystemVersion:
    """Create a test system version.

    Args:
        db: Database session
        test_ai_system: Test AI system
        test_editor_user: Test editor user as creator

    Returns:
        Test SystemVersion instance
    """
    version = SystemVersion(
        ai_system_id=test_ai_system.id,
        label="1.0.0",
        status=VersionStatus.DRAFT,
        notes="Initial version for testing",
        created_by=test_editor_user.id,
    )
    db.add(version)
    await db.flush()
    return version


async def create_version(
    db: AsyncSession,
    ai_system_id: UUID,
    label: str,
    created_by: UUID,
    status: VersionStatus = VersionStatus.DRAFT,
    notes: str | None = None,
) -> SystemVersion:
    """System Version factory for creating test versions.

    Args:
        db: Database session
        ai_system_id: AI System ID
        label: Version label (e.g., "1.0.0")
        created_by: Creator user ID
        status: Version status (default: DRAFT)
        notes: Optional version notes

    Returns:
        Created SystemVersion instance
    """
    version = SystemVersion(
        ai_system_id=ai_system_id,
        label=label,
        status=status,
        notes=notes,
        created_by=created_by,
    )
    db.add(version)
    await db.flush()
    return version


@pytest_asyncio.fixture
async def test_log_api_key(
    db: AsyncSession, test_version: SystemVersion, test_editor_user: User
) -> dict:
    """Create a test log API key (returns both model and plaintext key)."""
    import hashlib
    import uuid

    api_key = f"ak_test_{uuid.uuid4().hex}"
    key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    key = LogApiKey(
        version_id=test_version.id,
        key_hash=key_hash,
        name="Test Ingest Key",
        created_by=test_editor_user.id,
    )
    db.add(key)
    await db.flush()

    return {"api_key": api_key, "key": key}


async def create_log_api_key(
    db: AsyncSession,
    version_id: UUID,
    created_by: UUID,
    name: str = "Test Key",
    api_key: str | None = None,
    revoked_at=None,
) -> dict:
    """LogApiKey factory for creating test keys (returns both model and plaintext)."""
    import hashlib
    import uuid

    if api_key is None:
        api_key = f"ak_test_{uuid.uuid4().hex}"

    key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    key = LogApiKey(
        version_id=version_id,
        key_hash=key_hash,
        name=name,
        created_by=created_by,
        revoked_at=revoked_at,
    )
    db.add(key)
    await db.flush()
    return {"api_key": api_key, "key": key}


@pytest.fixture
def sample_decision_event() -> dict:
    """Sample decision event payload for ingestion tests."""
    return {
        "event_id": "evt_123456",
        "event_time": "2025-12-25T10:00:00Z",
        "actor": "hiring-assistant",
        "subject": {
            "subject_type": "candidate",
            "subject_id_hash": "sha256:abc123",
        },
        "model": {
            "model_id": "gpt-4",
            "model_version": "0613",
            "prompt_version": "v1",
        },
        "input": {
            "input_hash": "sha256:def456",
            "features_summary": {"education": "bachelor", "experience_years": 3},
        },
        "output": {
            "decision": "recommend",
            "score": 0.85,
            "output_hash": "sha256:ghi789",
        },
        "human": {
            "reviewer_id": "user_1",
            "override": False,
        },
        "trace": {
            "request_id": "req_123",
            "latency_ms": 123,
            "error": None,
        },
    }


@pytest_asyncio.fixture
async def test_evidence_item(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
) -> EvidenceItem:
    """Create a test evidence item.

    Args:
        db: Database session
        test_org: Test organization
        test_editor_user: Test editor user as creator

    Returns:
        Test EvidenceItem instance
    """
    evidence = EvidenceItem(
        org_id=test_org.id,
        type=EvidenceType.NOTE,
        title="Test Evidence Note",
        description="A test note documenting compliance requirements",
        tags=["compliance", "test"],
        classification=Classification.INTERNAL,
        type_metadata={"content": "This is a test note content"},
        created_by=test_editor_user.id,
    )
    db.add(evidence)
    await db.flush()
    return evidence


async def create_evidence_item(
    db: AsyncSession,
    org_id: UUID,
    type: EvidenceType,
    title: str,
    created_by: UUID | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    classification: Classification = Classification.INTERNAL,
    type_metadata: dict | None = None,
) -> EvidenceItem:
    """Evidence Item factory for creating test evidence.

    Args:
        db: Database session
        org_id: Organization ID
        type: Evidence type
        title: Evidence title
        created_by: Creator user ID
        description: Optional description
        tags: Optional list of tags
        classification: Classification level (default: INTERNAL)
        type_metadata: Type-specific metadata

    Returns:
        Created EvidenceItem instance
    """
    if type_metadata is None:
        type_metadata = {}
    if tags is None:
        tags = []

    evidence = EvidenceItem(
        org_id=org_id,
        type=type,
        title=title,
        description=description,
        tags=tags,
        classification=classification,
        type_metadata=type_metadata,
        created_by=created_by,
    )
    db.add(evidence)
    await db.flush()
    return evidence


@pytest_asyncio.fixture
async def test_evidence_mapping(
    db: AsyncSession,
    test_evidence_item: EvidenceItem,
    test_version: SystemVersion,
    test_editor_user: User,
) -> EvidenceMapping:
    """Create a test evidence mapping.

    Args:
        db: Database session
        test_evidence_item: Test evidence item
        test_version: Test system version
        test_editor_user: Test editor user as creator

    Returns:
        Test EvidenceMapping instance
    """
    mapping = EvidenceMapping(
        evidence_id=test_evidence_item.id,
        version_id=test_version.id,
        target_type=MappingTargetType.SECTION,
        target_key="ANNEX4.RISK_MANAGEMENT",
        strength=MappingStrength.MEDIUM,
        notes="Test mapping for risk management section",
        created_by=test_editor_user.id,
    )
    db.add(mapping)
    await db.flush()
    return mapping


async def create_evidence_mapping(
    db: AsyncSession,
    evidence_id: UUID,
    version_id: UUID,
    target_type: MappingTargetType,
    target_key: str,
    created_by: UUID | None = None,
    strength: MappingStrength | None = None,
    notes: str | None = None,
) -> EvidenceMapping:
    """Evidence Mapping factory for creating test mappings.

    Args:
        db: Database session
        evidence_id: Evidence item ID
        version_id: System version ID
        target_type: Target type (section/field/requirement)
        target_key: Target key identifier
        created_by: Creator user ID
        strength: Optional mapping strength
        notes: Optional notes

    Returns:
        Created EvidenceMapping instance
    """
    mapping = EvidenceMapping(
        evidence_id=evidence_id,
        version_id=version_id,
        target_type=target_type,
        target_key=target_key,
        strength=strength,
        notes=notes,
        created_by=created_by,
    )
    db.add(mapping)
    await db.flush()
    return mapping


@pytest_asyncio.fixture
async def test_annex_section(
    db: AsyncSession,
    test_version: SystemVersion,
    test_editor_user: User,
) -> AnnexSection:
    """Create a test annex section.

    Args:
        db: Database session
        test_version: Test system version
        test_editor_user: Test editor user as last editor

    Returns:
        Test AnnexSection instance
    """
    from decimal import Decimal

    section = AnnexSection(
        version_id=test_version.id,
        section_key=AnnexSectionKey.GENERAL.value,
        content={
            "provider_name": "Test Provider Ltd.",
            "provider_address": "123 Test Street, Test City",
            "system_name": "Test CV Screening System",
            "system_version": "1.0.0",
        },
        completeness_score=Decimal("80.00"),
        evidence_refs=[],
        llm_assisted=False,
        last_edited_by=test_editor_user.id,
    )
    db.add(section)
    await db.flush()
    return section


async def create_annex_section(
    db: AsyncSession,
    version_id: UUID,
    section_key: str,
    content: dict | None = None,
    completeness_score: float = 0.0,
    evidence_refs: list[UUID] | None = None,
    llm_assisted: bool = False,
    last_edited_by: UUID | None = None,
) -> AnnexSection:
    """Annex Section factory for creating test sections.

    Args:
        db: Database session
        version_id: System version ID
        section_key: Section key (e.g., "ANNEX4.GENERAL")
        content: Section content as dictionary
        completeness_score: Completeness score (0-100)
        evidence_refs: List of evidence item UUIDs
        llm_assisted: Whether section was LLM-assisted
        last_edited_by: Last editor user ID

    Returns:
        Created AnnexSection instance
    """
    from decimal import Decimal

    if content is None:
        content = {}
    if evidence_refs is None:
        evidence_refs = []

    section = AnnexSection(
        version_id=version_id,
        section_key=section_key,
        content=content,
        completeness_score=Decimal(str(completeness_score)),
        evidence_refs=evidence_refs,
        llm_assisted=llm_assisted,
        last_edited_by=last_edited_by,
    )
    db.add(section)
    await db.flush()
    return section


@pytest_asyncio.fixture
async def test_export(
    db: AsyncSession,
    test_version: SystemVersion,
    test_editor_user: User,
) -> Export:
    """Create a test export.

    Args:
        db: Database session
        test_version: Test system version
        test_editor_user: Test editor user as creator

    Returns:
        Test Export instance
    """
    from decimal import Decimal

    export = Export(
        version_id=test_version.id,
        export_type="full",
        snapshot_hash="abc123def456",
        storage_uri="s3://annexops-exports/test-export.pdf",
        file_size=1024000,
        include_diff=False,
        compare_version_id=None,
        completeness_score=Decimal("85.50"),
        created_by=test_editor_user.id,
    )
    db.add(export)
    await db.flush()
    return export


async def create_export(
    db: AsyncSession,
    version_id: UUID,
    created_by: UUID,
    export_type: str = "full",
    snapshot_hash: str = "test_hash",
    storage_uri: str = "s3://test/export.pdf",
    file_size: int = 1024000,
    include_diff: bool = False,
    compare_version_id: UUID | None = None,
    completeness_score: float = 0.0,
) -> Export:
    """Export factory for creating test exports.

    Args:
        db: Database session
        version_id: System version ID
        created_by: Creator user ID
        export_type: Export type (full/diff)
        snapshot_hash: Snapshot hash
        storage_uri: Storage URI
        file_size: File size in bytes
        include_diff: Whether to include diff
        compare_version_id: Compare version ID for diffs
        completeness_score: Completeness score (0-100)

    Returns:
        Created Export instance
    """
    from decimal import Decimal

    export = Export(
        version_id=version_id,
        export_type=export_type,
        snapshot_hash=snapshot_hash,
        storage_uri=storage_uri,
        file_size=file_size,
        include_diff=include_diff,
        compare_version_id=compare_version_id,
        completeness_score=Decimal(str(completeness_score)),
        created_by=created_by,
    )
    db.add(export)
    await db.flush()
    return export


@pytest_asyncio.fixture
async def test_llm_interaction(
    db: AsyncSession,
    test_version: SystemVersion,
    test_editor_user: User,
) -> LlmInteraction:
    """Create a test LLM interaction record."""
    interaction = LlmInteraction(
        version_id=test_version.id,
        section_key="ANNEX4.GENERAL",
        user_id=test_editor_user.id,
        selected_evidence_ids=[],
        prompt="Test prompt",
        response="Test response [Evidence: 00000000-0000-0000-0000-000000000000]",
        cited_evidence_ids=[],
        model="claude-3-sonnet-20240229",
        input_tokens=10,
        output_tokens=20,
        strict_mode=False,
        duration_ms=5,
    )
    db.add(interaction)
    await db.flush()
    return interaction


async def create_llm_interaction(
    db: AsyncSession,
    *,
    version_id: UUID,
    section_key: str,
    user_id: UUID,
    selected_evidence_ids: list[UUID] | None = None,
    prompt: str = "Test prompt",
    response: str = "Test response",
    cited_evidence_ids: list[UUID] | None = None,
    model: str = "claude-3-sonnet-20240229",
    input_tokens: int = 0,
    output_tokens: int = 0,
    strict_mode: bool = False,
    duration_ms: int = 0,
) -> LlmInteraction:
    """LLM Interaction factory for creating test interactions."""
    if selected_evidence_ids is None:
        selected_evidence_ids = []
    if cited_evidence_ids is None:
        cited_evidence_ids = []

    interaction = LlmInteraction(
        version_id=version_id,
        section_key=section_key,
        user_id=user_id,
        selected_evidence_ids=selected_evidence_ids,
        prompt=prompt,
        response=response,
        cited_evidence_ids=cited_evidence_ids,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        strict_mode=strict_mode,
        duration_ms=duration_ms,
    )
    db.add(interaction)
    await db.flush()
    return interaction


@pytest.fixture
def mock_llm_generate_success():
    """Mock LLM generation to avoid real provider calls."""
    from unittest.mock import AsyncMock, patch

    from src.services.llm_service import LlmCompletion

    with patch(
        "src.services.llm_service.LlmService.generate", new_callable=AsyncMock
    ) as mock_generate:
        mock_generate.return_value = LlmCompletion(
            text="## Draft\n\nExample text [Evidence: 00000000-0000-0000-0000-000000000000]",
            model="claude-3-sonnet-20240229",
            input_tokens=100,
            output_tokens=50,
            duration_ms=10,
        )
        yield mock_generate
