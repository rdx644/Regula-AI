from typing import Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.rbac import Role
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationMemberCreate,
    OrganizationMemberResponse,
)

router = APIRouter()


@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    *,
    db: Session = Depends(deps.get_db),
    org_in: OrganizationCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Create a new organization and assign the creator as the Owner.
    """
    org = Organization(name=org_in.name)
    db.add(org)
    db.commit()
    db.refresh(org)

    # Assign creator as Owner
    member = OrganizationMember(
        organization_id=org.id,
        user_id=current_user.id,
        role=Role.OWNER.value,
    )
    db.add(member)
    db.commit()

    return org


@router.get("/", response_model=List[OrganizationResponse])
def read_organizations(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve organizations the current user belongs to (tenant-scoped).
    """
    orgs = (
        db.query(Organization)
        .join(OrganizationMember)
        .filter(OrganizationMember.user_id == current_user.id)
        .all()
    )
    return orgs


@router.get("/{organization_id}/members", response_model=List[OrganizationMemberResponse])
def list_organization_members(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List members belonging to an organization.
    """
    deps.verify_membership(db, current_user, organization_id)
    return (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == organization_id)
        .all()
    )


@router.post("/{organization_id}/members", response_model=OrganizationMemberResponse, status_code=status.HTTP_201_CREATED)
def add_organization_member(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    member_in: OrganizationMemberCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Add a member to an organization (requires Owner or Admin role).
    """
    deps.verify_membership(
        db, current_user, organization_id, allowed_roles=[Role.OWNER.value, Role.ADMIN.value]
    )

    existing = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == member_in.user_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this organization.",
        )

    member = OrganizationMember(
        organization_id=organization_id,
        user_id=member_in.user_id,
        role=member_in.role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member
