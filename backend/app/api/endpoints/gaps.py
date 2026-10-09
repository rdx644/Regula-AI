from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.services.governance import risk, audit
from app.services.compliance import assessment_revision
from app.core.rbac import Permission
from app.models.gap import Gap, RiskAssessment
from app.models.obligation import RegulatoryObligation
from app.models.control import Control
from app.models.user import User
from app.schemas.gap import (
    GapCreate,
    GapUpdate,
    GapResponse,
    GapRunRequest,
    GapRunResponse,
    RiskAssessmentBase,
    RiskAssessmentCreate,
    RiskAssessmentResponse,
)
from app.services.queue import get_queue, create_job, JobPriority

router = APIRouter()


@router.post("/", response_model=GapResponse, status_code=status.HTTP_201_CREATED)
def create_gap(
    *,
    db: Session = Depends(deps.get_db),
    payload: GapCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Record an identified compliance gap.
    """
    deps.verify_membership(
        db, current_user, payload.organization_id, required_permission=Permission.GAP_CREATE
    )

    if payload.obligation_id and not db.query(RegulatoryObligation.id).filter(
        RegulatoryObligation.id == payload.obligation_id,
        RegulatoryObligation.organization_id == payload.organization_id,
    ).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found")
    if payload.control_id and not db.query(Control.id).filter(
        Control.id == payload.control_id,
        Control.organization_id == payload.organization_id,
    ).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Control not found")

    gap = Gap(
        organization_id=payload.organization_id,
        obligation_id=payload.obligation_id,
        control_id=payload.control_id,
        gap_type=payload.gap_type,
        description=payload.description,
        severity=payload.severity or "medium",
        status=payload.status or "open",
    )
    db.add(gap)
    db.commit()
    db.refresh(gap)
    return gap


@router.get("/", response_model=List[GapResponse])
def list_gaps(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    gap_type: Optional[str] = None,
    severity: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List compliance gaps for an organization with optional filters.
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.GAP_READ
    )

    query = db.query(Gap).filter(Gap.organization_id == organization_id)
    if gap_type:
        query = query.filter(Gap.gap_type == gap_type)
    if severity:
        query = query.filter(Gap.severity == severity)
    if status_filter:
        query = query.filter(Gap.status == status_filter)

    return query.order_by(Gap.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{gap_id}", response_model=GapResponse)
def get_gap(
    *,
    db: Session = Depends(deps.get_db),
    gap_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get a single gap with its risk assessment.
    """
    gap = db.query(Gap).filter(Gap.id == gap_id).first()
    if not gap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gap not found")

    deps.verify_membership(
        db, current_user, gap.organization_id, required_permission=Permission.GAP_READ
    )
    return gap


@router.patch("/{gap_id}", response_model=GapResponse)
def update_gap(
    *,
    db: Session = Depends(deps.get_db),
    gap_id: UUID,
    payload: GapUpdate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update gap status or details.
    """
    gap = db.query(Gap).filter(Gap.id == gap_id).first()
    if not gap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gap not found")

    deps.verify_membership(
        db, current_user, gap.organization_id, required_permission=Permission.GAP_UPDATE
    )

    update_data = payload.model_dump(exclude_unset=True)
    if payload.status == 'closed':
        raise HTTPException(409, 'Close the gap through reviewed remediation and validation')
    for field, val in update_data.items():
        setattr(gap, field, val)

    db.commit()
    db.refresh(gap)
    return gap


@router.post("/run", response_model=GapRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_gap_identification(
    *,
    db: Session = Depends(deps.get_db),
    payload: GapRunRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Run AI gap identification for a specific obligation.
    Returns a job ID for async tracking.
    """
    from app.models.obligation import RegulatoryObligation
    
    obligation = db.query(RegulatoryObligation).filter(RegulatoryObligation.id == payload.obligation_id).first()
    if not obligation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found")

    deps.verify_membership(
        db, current_user, obligation.organization_id, required_permission=Permission.GAP_CREATE
    )

    job = create_job(
        job_type="gap_identification",
        payload={
            "obligation_id": str(payload.obligation_id),
        },
        organization_id=obligation.organization_id,
        user_id=current_user.id,
        priority=JobPriority.HIGH,
        idempotency_key=f"gap_identification_{payload.obligation_id}_{assessment_revision(db, obligation.organization_id, obligation_id=obligation.id)}",
        workflow_id=f"gap_analysis_{obligation.id}",
        step_order=1,
    )

    queue = await get_queue()
    job = await queue.enqueue(job)

    return GapRunResponse(
        job_id=job.id,
        status=job.status.value,
        message="Gap identification started. Use job ID to track progress."
    )


@router.post("/{gap_id}/risk-assessment", response_model=RiskAssessmentResponse, status_code=status.HTTP_201_CREATED)
def assess_gap_risk(
    *,
    db: Session = Depends(deps.get_db),
    gap_id: UUID,
    payload: RiskAssessmentBase,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Attach or update a deterministic risk assessment for a gap.
    """
    gap = db.query(Gap).filter(Gap.id == gap_id).first()
    if not gap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gap not found")

    deps.verify_membership(
        db, current_user, gap.organization_id, required_permission=Permission.GAP_UPDATE
    )

    likelihood, impact, risk_score, level = risk(payload.likelihood, payload.impact)
    if payload.risk_score is not None and payload.risk_score != risk_score:
        raise HTTPException(422, "Risk score must match the deterministic formula")
    if payload.risk_level is not None and payload.risk_level != level:
        raise HTTPException(422, "Risk level must match the deterministic thresholds")
    audit(db, gap.organization_id, current_user.id, "risk_assessed", "gap", gap.id, score=risk_score, level=level)

    assessment = db.query(RiskAssessment).filter(RiskAssessment.gap_id == gap_id).first()
    if not assessment:
        assessment = RiskAssessment(
            gap_id=gap_id,
            likelihood=likelihood,
            impact=impact,
            risk_score=risk_score,
            risk_level=level,
            reasoning=payload.reasoning,
        )
        db.add(assessment)
    else:
        assessment.likelihood = likelihood
        assessment.impact = impact
        assessment.risk_score = risk_score
        assessment.risk_level = level
        assessment.reasoning = payload.reasoning

    # Also update gap severity to match risk level
    gap.severity = level

    db.commit()
    db.refresh(assessment)
    return assessment
