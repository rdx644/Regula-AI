from enum import Enum
from typing import Set, Dict, List


class Role(str, Enum):
    OWNER = "Owner"
    ADMIN = "Admin"
    COMPLIANCE_MANAGER = "Compliance Manager"
    ANALYST = "Analyst"
    CONTROL_OWNER = "Control Owner"
    VIEWER = "Viewer"


class Permission(str, Enum):
    # Org
    ORG_READ = "org:read"
    ORG_UPDATE = "org:update"
    ORG_DELETE = "org:delete"
    ORG_MANAGE_MEMBERS = "org:manage_members"

    # Regulations
    REGULATION_READ = "regulation:read"
    REGULATION_CREATE = "regulation:create"
    REGULATION_UPDATE = "regulation:update"
    REGULATION_DELETE = "regulation:delete"

    # Obligations
    OBLIGATION_READ = "obligation:read"
    OBLIGATION_CREATE = "obligation:create"
    OBLIGATION_UPDATE = "obligation:update"
    OBLIGATION_APPROVE = "obligation:approve"

    # Controls & Policies
    CONTROL_READ = "control:read"
    CONTROL_CREATE = "control:create"
    CONTROL_UPDATE = "control:update"
    CONTROL_APPROVE = "control:approve"
    CONTROL_DELETE = "control:delete"

    # Mappings
    MAPPING_READ = "mapping:read"
    MAPPING_CREATE = "mapping:create"
    MAPPING_UPDATE = "mapping:update"
    MAPPING_APPROVE = "mapping:approve"

    # Evidence & Tests
    EVIDENCE_READ = "evidence:read"
    EVIDENCE_CREATE = "evidence:create"
    EVIDENCE_UPDATE = "evidence:update"
    EVIDENCE_VALIDATE = "evidence:validate"

    # Gaps & Risk
    GAP_READ = "gap:read"
    GAP_CREATE = "gap:create"
    GAP_UPDATE = "gap:update"

    # Remediation
    REMEDIATION_READ = "remediation:read"
    REMEDIATION_CREATE = "remediation:create"
    REMEDIATION_UPDATE = "remediation:update"

    # Audit & Agents
    AUDIT_READ = "audit:read"
    AGENT_RUN = "agent:run"


# Define permissions by role
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    Role.OWNER.value: {p.value for p in Permission},
    
    Role.ADMIN.value: {
        p.value for p in Permission if p != Permission.ORG_DELETE
    },
    
    Role.COMPLIANCE_MANAGER.value: {
        Permission.ORG_READ.value,
        Permission.REGULATION_READ.value,
        Permission.REGULATION_CREATE.value,
        Permission.REGULATION_UPDATE.value,
        Permission.OBLIGATION_READ.value,
        Permission.OBLIGATION_CREATE.value,
        Permission.OBLIGATION_UPDATE.value,
        Permission.OBLIGATION_APPROVE.value,
        Permission.CONTROL_READ.value,
        Permission.CONTROL_CREATE.value,
        Permission.CONTROL_UPDATE.value,
        Permission.CONTROL_APPROVE.value,
        Permission.MAPPING_READ.value,
        Permission.MAPPING_CREATE.value,
        Permission.MAPPING_UPDATE.value,
        Permission.MAPPING_APPROVE.value,
        Permission.EVIDENCE_READ.value,
        Permission.EVIDENCE_CREATE.value,
        Permission.EVIDENCE_UPDATE.value,
        Permission.EVIDENCE_VALIDATE.value,
        Permission.GAP_READ.value,
        Permission.GAP_CREATE.value,
        Permission.GAP_UPDATE.value,
        Permission.REMEDIATION_READ.value,
        Permission.REMEDIATION_CREATE.value,
        Permission.REMEDIATION_UPDATE.value,
        Permission.AUDIT_READ.value,
        Permission.AGENT_RUN.value,
    },
    
    Role.ANALYST.value: {
        Permission.ORG_READ.value,
        Permission.REGULATION_READ.value,
        Permission.REGULATION_CREATE.value,
        Permission.OBLIGATION_READ.value,
        Permission.OBLIGATION_CREATE.value,
        Permission.OBLIGATION_UPDATE.value,
        Permission.CONTROL_READ.value,
        Permission.MAPPING_READ.value,
        Permission.MAPPING_CREATE.value,
        Permission.EVIDENCE_READ.value,
        Permission.GAP_READ.value,
        Permission.REMEDIATION_READ.value,
        Permission.AUDIT_READ.value,
        Permission.AGENT_RUN.value,
    },
    
    Role.CONTROL_OWNER.value: {
        Permission.ORG_READ.value,
        Permission.REGULATION_READ.value,
        Permission.OBLIGATION_READ.value,
        Permission.CONTROL_READ.value,
        Permission.CONTROL_CREATE.value,
        Permission.CONTROL_UPDATE.value,
        Permission.MAPPING_READ.value,
        Permission.EVIDENCE_READ.value,
        Permission.EVIDENCE_CREATE.value,
        Permission.EVIDENCE_UPDATE.value,
        Permission.GAP_READ.value,
        Permission.REMEDIATION_READ.value,
        Permission.REMEDIATION_UPDATE.value,
        Permission.AUDIT_READ.value,
    },
    
    Role.VIEWER.value: {
        Permission.ORG_READ.value,
        Permission.REGULATION_READ.value,
        Permission.OBLIGATION_READ.value,
        Permission.CONTROL_READ.value,
        Permission.MAPPING_READ.value,
        Permission.EVIDENCE_READ.value,
        Permission.GAP_READ.value,
        Permission.REMEDIATION_READ.value,
        Permission.AUDIT_READ.value,
    },
}


def has_permission(role: str, permission: Permission | str) -> bool:
    perm_val = permission.value if isinstance(permission, Permission) else permission
    role_perms = ROLE_PERMISSIONS.get(role, set())
    return perm_val in role_perms


def is_role_allowed(user_role: str, allowed_roles: List[str]) -> bool:
    if user_role == Role.OWNER.value:
        return True
    return user_role in allowed_roles
