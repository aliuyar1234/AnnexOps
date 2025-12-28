"""Enumerations for user roles and audit actions."""

from enum import Enum


class UserRole(str, Enum):
    """User role enumeration with hierarchy.

    Hierarchy (higher can do everything lower can do):
    1. ADMIN (all permissions + user management)
    2. EDITOR (CRUD on systems, versions, evidence)
    3. REVIEWER (read + comment)
    4. VIEWER (read-only)
    """

    ADMIN = "admin"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"

    @classmethod
    def get_hierarchy_level(cls, role: "UserRole") -> int:
        """Get numeric hierarchy level for role comparison.

        Args:
            role: UserRole to get level for

        Returns:
            Integer level (higher = more permissions)
        """
        levels = {
            cls.VIEWER: 1,
            cls.REVIEWER: 2,
            cls.EDITOR: 3,
            cls.ADMIN: 4,
        }
        return levels.get(role, 0)

    def has_permission(self, required_role: "UserRole") -> bool:
        """Check if this role has permission for action requiring another role.

        Args:
            required_role: Minimum role required

        Returns:
            True if this role has sufficient permissions
        """
        return self.get_hierarchy_level(self) >= self.get_hierarchy_level(required_role)


class AuditAction(str, Enum):
    """Audit action enumeration for tracking administrative actions."""

    # Organization
    ORG_CREATE = "organization.create"
    ORG_UPDATE = "organization.update"

    # User
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_ROLE_CHANGE = "user.role_change"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_LOCKOUT = "user.lockout"

    # Invitation
    INVITATION_CREATE = "invitation.create"
    INVITATION_ACCEPT = "invitation.accept"
    INVITATION_EXPIRE = "invitation.expire"
    INVITATION_REVOKE = "invitation.revoke"

    # AI System
    AI_SYSTEM_CREATE = "ai_system.create"
    AI_SYSTEM_UPDATE = "ai_system.update"
    AI_SYSTEM_DELETE = "ai_system.delete"

    # Assessment
    ASSESSMENT_CREATE = "assessment.create"

    # Attachment
    ATTACHMENT_UPLOAD = "attachment.upload"
    ATTACHMENT_DELETE = "attachment.delete"

    # Version
    VERSION_CREATE = "version.create"
    VERSION_UPDATE = "version.update"
    VERSION_DELETE = "version.delete"
    VERSION_STATUS_CHANGE = "version.status_change"

    # Evidence
    EVIDENCE_CREATE = "evidence.create"
    EVIDENCE_UPDATE = "evidence.update"
    EVIDENCE_DELETE = "evidence.delete"
    MAPPING_CREATE = "mapping.create"
    MAPPING_DELETE = "mapping.delete"

    # Annex Section
    SECTION_UPDATE = "section.update"

    # Export
    EXPORT_CREATE = "export.create"


class HRUseCaseType(str, Enum):
    """HR use case types per EU AI Act Annex III."""

    RECRUITMENT_SCREENING = "recruitment_screening"
    APPLICATION_FILTERING = "application_filtering"
    CANDIDATE_MATCHING = "candidate_matching"
    PERFORMANCE_EVALUATION = "performance_evaluation"
    EMPLOYEE_MONITORING = "employee_monitoring"
    TASK_ALLOCATION = "task_allocation"
    PROMOTION_TERMINATION = "promotion_termination"
    OTHER_HR = "other_hr"


class DeploymentType(str, Enum):
    """Deployment type for AI systems."""

    SAAS = "saas"
    ON_PREM = "onprem"
    HYBRID = "hybrid"


class DecisionInfluence(str, Enum):
    """Level of decision influence for AI systems."""

    ASSISTIVE = "assistive"  # Provides recommendations only
    SEMI_AUTOMATED = "semi_automated"  # Decisions with human review
    AUTOMATED = "automated"  # Autonomous decisions


class AssessmentResult(str, Enum):
    """High-risk assessment result labels."""

    LIKELY_HIGH_RISK = "likely_high_risk"
    UNCLEAR = "unclear"
    LIKELY_NOT_HIGH_RISK = "likely_not"


class VersionStatus(str, Enum):
    """Version status enumeration for system versioning lifecycle.

    Workflow:
    - DRAFT: In progress, editable
    - REVIEW: Ready for approval
    - APPROVED: Signed off, immutable if exported
    """

    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"


class EvidenceType(str, Enum):
    """Evidence type enumeration for evidence storage."""

    UPLOAD = "upload"
    URL = "url"
    GIT = "git"
    TICKET = "ticket"
    NOTE = "note"


class Classification(str, Enum):
    """Classification level for evidence items."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


class MappingTargetType(str, Enum):
    """Target type for evidence mappings."""

    SECTION = "section"
    FIELD = "field"
    REQUIREMENT = "requirement"


class MappingStrength(str, Enum):
    """Strength level for evidence mappings."""

    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"


class AnnexSectionKey(str, Enum):
    """Annex IV section keys for technical documentation."""

    GENERAL = "ANNEX4.GENERAL"
    INTENDED_PURPOSE = "ANNEX4.INTENDED_PURPOSE"
    SYSTEM_DESCRIPTION = "ANNEX4.SYSTEM_DESCRIPTION"
    RISK_MANAGEMENT = "ANNEX4.RISK_MANAGEMENT"
    DATA_GOVERNANCE = "ANNEX4.DATA_GOVERNANCE"
    MODEL_TECHNICAL = "ANNEX4.MODEL_TECHNICAL"
    PERFORMANCE = "ANNEX4.PERFORMANCE"
    HUMAN_OVERSIGHT = "ANNEX4.HUMAN_OVERSIGHT"
    LOGGING = "ANNEX4.LOGGING"
    ACCURACY_ROBUSTNESS_CYBERSEC = "ANNEX4.ACCURACY_ROBUSTNESS_CYBERSEC"
    POST_MARKET_MONITORING = "ANNEX4.POST_MARKET_MONITORING"
    CHANGE_MANAGEMENT = "ANNEX4.CHANGE_MANAGEMENT"


class ExportType(str, Enum):
    """Export type for Annex IV documentation exports."""

    FULL = "full"
    DIFF = "diff"
