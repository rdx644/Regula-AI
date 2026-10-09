from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.services.governance import audit
from app.core.rbac import Permission
from app.models.mapping import RegulationControlMapping
from app.models.obligation import RegulatoryObligation
from app.models.control import Control
from app.models.user import User
from app.schemas.mapping import (
    MappingCreate,
    MappingUpdate,
    MappingApprove,
    MappingResponse,
    MappingRunRequest,
    MappingRunResponse,
)
from app.services.queue import get_queue, create_job, JobPriority
from app.services.compliance import assessment_revision

router = APIRouter()


@router.post("/", response_model=MappingResponse, status_code=status.HTTP_201_CREATED)
def create_mapping(
    *,
    db: Session = Depends(deps.get_db),
    payload: MappingCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Map a regulatory obligation to an internal control.
    """
    deps.verify_membership(
        db, current_user, payload.organization_id, required_permission=Permission.MAPPING_CREATE
    )

    obligation = db.query(RegulatoryObligation).filter(
        RegulatoryObligation.id == payload.obligation_id,
        RegulatoryObligation.organization_id == payload.organization_id,
    ).first()
    control = db.query(Control).filter(
        Control.id == payload.control_id,
        Control.organization_id == payload.organization_id,
    ).first()
    if not obligation or not control:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obligation or control not found")

    mapping = RegulationControlMapping(
        organization_id=payload.organization_id,
        obligation_id=payload.obligation_id,
        control_id=payload.control_id,
        mapping_status="human_review",
        confidence=payload.confidence,
        reasoning=payload.reasoning,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


@router.get("/", response_model=List[MappingResponse])
def list_mappings(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    obligation_id: Optional[UUID] = None,
    control_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List obligation-control mappings for an organization with optional filters.
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.MAPPING_READ
    )

    query = db.query(RegulationControlMapping).filter(
        RegulationControlMapping.organization_id == organization_id
    )
    if obligation_id:
        query = query.filter(RegulationControlMapping.obligation_id == obligation_id)
    if control_id:
        query = query.filter(RegulationControlMapping.control_id == control_id)
    if status_filter:
        query = query.filter(RegulationControlMapping.mapping_status == status_filter)

    return query.order_by(RegulationControlMapping.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{mapping_id}", response_model=MappingResponse)
def get_mapping(
    *,
    db: Session = Depends(deps.get_db),
    mapping_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get a single mapping by ID.
    """
    mapping = db.query(RegulationControlMapping).filter(RegulationControlMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")

    deps.verify_membership(
        db, current_user, mapping.organization_id, required_permission=Permission.MAPPING_READ
    )
    return mapping


@router.post("/{mapping_id}/approve", response_model=MappingResponse)
def approve_mapping(
    *,
    db: Session = Depends(deps.get_db),
    mapping_id: UUID,
    payload: MappingApprove,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Human-in-the-loop (HITL) approval of an AI-generated or proposed mapping.
    """
    mapping = db.query(RegulationControlMapping).filter(RegulationControlMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")

    deps.verify_membership(
        db, current_user, mapping.organization_id, required_permission=Permission.MAPPING_APPROVE
    )

    audit(db, mapping.organization_id, current_user.id, "mapping_reviewed", "mapping", mapping.id, next_state=payload.mapping_status)
    mapping.approved_by = current_user.id
    mapping.approved_at = datetime.now(timezone.utc)
    if payload.mapping_status:
        mapping.mapping_status = payload.mapping_status
    if payload.notes:
        mapping.reasoning = (mapping.reasoning or "") + f"\n[Approval Note]: {payload.notes}"

    db.commit()
    db.refresh(mapping)
    return mapping


@router.post("/run", response_model=MappingRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_mapping(
    *,
    db: Session = Depends(deps.get_db),
    payload: MappingRunRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Run the AI mapping agent for a specific obligation.
    Returns a job ID for async tracking.
    """
    from app.models.obligation import RegulatoryObligation
    
    obligation = db.query(RegulatoryObligation).filter(RegulatoryObligation.id == payload.obligation_id).first()
    if not obligation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found")

    deps.verify_membership(
        db, current_user, obligation.organization_id, required_permission=Permission.MAPPING_CREATE
    )

    job = create_job(
        job_type="mapping",
        payload={
            "obligation_id": str(payload.obligation_id),
        },
        organization_id=obligation.organization_id,
        user_id=current_user.id,
        priority=JobPriority.HIGH,
        idempotency_key=f"mapping_{payload.obligation_id}_{assessment_revision(db, obligation.organization_id, obligation_id=obligation.id)}",
        workflow_id=f"mapping_{obligation.id}",
        step_order=1,
    )

    queue = await get_queue()
    job = await queue.enqueue(job)

    return MappingRunResponse(
        job_id=job.id,
        status=job.status.value,
        message="Mapping started. Use job ID to track progress."
    )
