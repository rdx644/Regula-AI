from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.services.governance import audit
from app.core.rbac import Permission
from app.models.gap import Gap, RemediationPlan
from app.models.user import User
from app.schemas.remediation import (
    RemediationPlanCreate,
    RemediationPlanUpdate,
    RemediationPlanResponse,
    RemediationRunRequest,
    RemediationRunResponse,
)
from app.services.queue import get_queue, create_job, JobPriority

router = APIRouter()


@router.post("/", response_model=RemediationPlanResponse, status_code=status.HTTP_201_CREATED)
def create_remediation_plan(
    *,
    db: Session = Depends(deps.get_db),
    payload: RemediationPlanCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Create a remediation action plan for a specific compliance gap.
    """
    deps.verify_membership(
        db, current_user, payload.organization_id, required_permission=Permission.REMEDIATION_CREATE
    )

    gap = db.query(Gap).filter(
        Gap.id == payload.gap_id,
        Gap.organization_id == payload.organization_id,
    ).first()
    if not gap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gap not found")

    existing = db.query(RemediationPlan).filter(RemediationPlan.gap_id == payload.gap_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A remediation plan already exists for this gap.",
        )

    plan = RemediationPlan(
        organization_id=payload.organization_id,
        gap_id=payload.gap_id,
        recommendation=payload.recommendation,
        priority=payload.priority or "medium_term",
        estimated_effort=payload.estimated_effort,
        assigned_to=payload.assigned_to,
        status="proposed",
        due_date=payload.due_date,
    )
    db.add(plan)
    
    # Mark gap as in_remediation if plan is created
    # Gap state changes only after explicit plan approval.
    
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/", response_model=List[RemediationPlanResponse])
def list_remediation_plans(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    priority: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List all remediation plans for an organization.
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.REMEDIATION_READ
    )

    query = db.query(RemediationPlan).filter(RemediationPlan.organization_id == organization_id)
    if priority:
        query = query.filter(RemediationPlan.priority == priority)
    if status_filter:
        query = query.filter(RemediationPlan.status == status_filter)

    return query.order_by(RemediationPlan.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{plan_id}", response_model=RemediationPlanResponse)
def get_remediation_plan(
    *,
    db: Session = Depends(deps.get_db),
    plan_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get a single remediation plan by ID.
    """
    plan = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Remediation plan not found")

    deps.verify_membership(
        db, current_user, plan.organization_id, required_permission=Permission.REMEDIATION_READ
    )
    return plan


@router.patch("/{plan_id}", response_model=RemediationPlanResponse)
def update_remediation_plan(
    *,
    db: Session = Depends(deps.get_db),
    plan_id: UUID,
    payload: RemediationPlanUpdate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update remediation plan status, assigned owner, or completion date.
    """
    plan = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Remediation plan not found")

    deps.verify_membership(
        db, current_user, plan.organization_id, required_permission=Permission.REMEDIATION_UPDATE
    )

    transitions = {"proposed": {"approved", "rejected"}, "approved": {"in_progress"}, "in_progress": {"completed"}, "completed": set(), "rejected": {"proposed"}}
    if payload.status and payload.status != plan.status:
        if payload.status not in transitions.get(plan.status, set()):
            raise HTTPException(409, "Invalid remediation transition")
        deps.verify_membership(db, current_user, plan.organization_id, allowed_roles=["Owner", "Admin", "Compliance Manager"])
        if payload.status == "completed":
            linked = db.query(Gap).filter(Gap.id == plan.gap_id, Gap.organization_id == plan.organization_id).first()
            from app.models.evidence_model import ControlTest
            latest = db.query(ControlTest).filter(ControlTest.organization_id == plan.organization_id, ControlTest.control_id == linked.control_id).order_by(ControlTest.created_at.desc()).first() if linked else None
            if not latest or latest.result != "pass" or latest.review_status != "approved" or (latest.effectiveness_score or 0) < 0.7 or latest.created_at < (plan.updated_at or plan.created_at):
                raise HTTPException(409, "A successful post-remediation validation test is required")
            from app.services.compliance import require_passing_evidence
            require_passing_evidence(db, plan.organization_id, linked.control_id, latest.effectiveness_score)
        audit(db, plan.organization_id, current_user.id, "remediation_reviewed", "remediation", plan.id, previous_state=plan.status, next_state=payload.status)
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(plan, field, val)

    if payload.status in {'approved', 'in_progress'}:
        linked_gap = db.query(Gap).filter(Gap.id == plan.gap_id, Gap.organization_id == plan.organization_id).first()
        if linked_gap:
            linked_gap.status = 'in_remediation'

    # If completed, check if associated gap can be closed
    if payload.status == "completed":
        gap = db.query(Gap).filter(Gap.id == plan.gap_id, Gap.organization_id == plan.organization_id).first()
        if gap:
            gap.status = "closed"

    db.commit()
    db.refresh(plan)
    return plan


@router.post("/run", response_model=RemediationRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_remediation(
    *,
    db: Session = Depends(deps.get_db),
    payload: RemediationRunRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Run AI remediation recommendation for a specific gap.
    Returns a job ID for async tracking.
    """
    gap = db.query(Gap).filter(Gap.id == payload.gap_id).first()
    if not gap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gap not found")

    deps.verify_membership(
        db, current_user, gap.organization_id, required_permission=Permission.REMEDIATION_CREATE
    )

    job = create_job(
        job_type="remediation",
        payload={
            "gap_id": str(payload.gap_id),
        },
        organization_id=gap.organization_id,
        user_id=current_user.id,
        priority=JobPriority.HIGH,
        idempotency_key=f"remediation_{payload.gap_id}",
        workflow_id=f"remediation_{gap.id}",
        step_order=1,
    )

    queue = await get_queue()
    job = await queue.enqueue(job)

    return RemediationRunResponse(
        job_id=job.id,
        status=job.status.value,
        message="Remediation recommendation started. Use job ID to track progress."
    )
