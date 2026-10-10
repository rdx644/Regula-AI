from typing import Any, List, Optional
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.models.regulation import RegulatoryDocument, RegulatoryVersion
from app.models.obligation import RegulatoryObligation
from app.models.control import Control, Policy
from app.services.governance import owned
from app.core.rbac import Permission
from app.models.change import RegulatoryChange, ImpactAssessment
from app.models.user import User
from app.schemas.change import (
    RegulatoryChangeCreate,
    RegulatoryChangeUpdate,
    RegulatoryChangeResponse,
    ImpactAssessmentBase,
    ImpactAssessmentCreate,
    ImpactAssessmentResponse,
    ChangeDetectionRequest,
    ChangeDetectionResponse,
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
)
from app.services.queue import get_queue, create_job, JobPriority
from app.schemas.workspace import TextComparisonResponse

router = APIRouter()


@router.post("/compare-text", response_model=TextComparisonResponse)
def compare_source_text(*, payload: ChangeDetectionRequest, db: Session = Depends(deps.get_db),
                        current_user: User = Depends(deps.get_current_user)):
    from app.services.workspace_review import compare_text
    document = db.query(RegulatoryDocument).filter(RegulatoryDocument.id == payload.document_id).first()
    if not document:
        raise HTTPException(404, "Document not found")
    deps.verify_membership(db, current_user, document.organization_id, required_permission=Permission.REGULATION_UPDATE)
    return TextComparisonResponse(**compare_text(db, document, payload.old_version_id, payload.new_version_id, current_user.id))


# â”€â”€ Regulatory Change Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/", response_model=RegulatoryChangeResponse, status_code=status.HTTP_201_CREATED)
def create_regulatory_change(
    *,
    db: Session = Depends(deps.get_db),
    payload: RegulatoryChangeCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Manually create a regulatory change record.
    """
    deps.verify_membership(
        db, current_user, payload.organization_id, required_permission=Permission.REGULATION_UPDATE
    )

    owned(db, RegulatoryDocument, payload.document_id, payload.organization_id)
    for version_id in [payload.old_version_id, payload.new_version_id]:
        if version_id and not db.query(RegulatoryVersion).filter(RegulatoryVersion.id == version_id, RegulatoryVersion.document_id == payload.document_id).first():
            raise HTTPException(404, "Version not found")
    for obligation_id in payload.affected_obligations or []:
        owned(db, RegulatoryObligation, obligation_id, payload.organization_id)
    change = RegulatoryChange(
        organization_id=payload.organization_id,
        document_id=payload.document_id,
        old_version_id=payload.old_version_id,
        new_version_id=payload.new_version_id,
        change_type=payload.change_type,
        summary=payload.summary,
        affected_obligations=json.dumps([str(o) for o in payload.affected_obligations]) if payload.affected_obligations else None,
        severity=payload.severity,
        status=payload.status,
    )
    db.add(change)
    db.commit()
    db.refresh(change)
    return change


@router.get("/", response_model=List[RegulatoryChangeResponse])
def list_regulatory_changes(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    document_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List regulatory changes for an organization.
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.REGULATION_READ
    )

    query = db.query(RegulatoryChange).filter(RegulatoryChange.organization_id == organization_id)
    if document_id:
        query = query.filter(RegulatoryChange.document_id == document_id)
    if status_filter:
        query = query.filter(RegulatoryChange.status == status_filter)

    return query.order_by(RegulatoryChange.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{change_id}", response_model=RegulatoryChangeResponse)
def get_regulatory_change(
    *,
    db: Session = Depends(deps.get_db),
    change_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get a single regulatory change by ID.
    """
    change = db.query(RegulatoryChange).filter(RegulatoryChange.id == change_id).first()
    if not change:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regulatory change not found")

    deps.verify_membership(
        db, current_user, change.organization_id, required_permission=Permission.REGULATION_READ
    )
    return change


@router.post("/detect", response_model=ChangeDetectionResponse, status_code=status.HTTP_202_ACCEPTED)
async def detect_changes(
    *,
    db: Session = Depends(deps.get_db),
    payload: ChangeDetectionRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Run AI change detection between two versions of a regulatory document.
    Returns a job ID for async tracking.
    """
    from app.models.regulation import RegulatoryDocument, RegulatoryVersion
    
    document = db.query(RegulatoryDocument).filter(RegulatoryDocument.id == payload.document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    deps.verify_membership(
        db, current_user, document.organization_id, required_permission=Permission.REGULATION_UPDATE
    )

    old_version = db.query(RegulatoryVersion).filter(RegulatoryVersion.id == payload.old_version_id, RegulatoryVersion.document_id == document.id).first()
    new_version = db.query(RegulatoryVersion).filter(RegulatoryVersion.id == payload.new_version_id, RegulatoryVersion.document_id == document.id).first()
    
    if not old_version or not new_version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    job = create_job(
        job_type="change_detection",
        payload={
            "document_id": str(payload.document_id),
            "old_version_id": str(payload.old_version_id),
            "new_version_id": str(payload.new_version_id),
        },
        organization_id=document.organization_id,
        user_id=current_user.id,
        priority=JobPriority.HIGH,
        idempotency_key=f"change_detection_{payload.old_version_id}_{payload.new_version_id}",
        workflow_id=f"change_intelligence_{document.id}",
        step_order=1,
    )

    queue = await get_queue()
    job = await queue.enqueue(job)

    return ChangeDetectionResponse(
        job_id=job.id,
        status="queued",
        message="Change detection started. Use job ID to track progress."
    )


# â”€â”€ Impact Assessment Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/impact", response_model=ImpactAssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_impact_assessment(
    *,
    db: Session = Depends(deps.get_db),
    payload: ImpactAssessmentCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Create an impact assessment for a regulatory change.
    """
    deps.verify_membership(
        db, current_user, payload.organization_id, required_permission=Permission.REGULATION_UPDATE
    )

    owned(db, RegulatoryChange, payload.change_id, payload.organization_id)
    for model, ids in [(Control, payload.affected_controls), (Policy, payload.affected_policies)]:
        for record_id in ids or []:
            owned(db, model, record_id, payload.organization_id)
    assessment = ImpactAssessment(
        organization_id=payload.organization_id,
        change_id=payload.change_id,
        affected_controls=json.dumps([str(c) for c in payload.affected_controls]) if payload.affected_controls else None,
        affected_policies=json.dumps([str(p) for p in payload.affected_policies]) if payload.affected_policies else None,
        new_gaps_identified=json.dumps(payload.new_gaps_identified) if payload.new_gaps_identified else None,
        risk_delta=payload.risk_delta,
        recommendation=payload.recommendation,
        confidence=payload.confidence,
        status=payload.status,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


@router.get("/impact", response_model=List[ImpactAssessmentResponse])
def list_impact_assessments(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    change_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List impact assessments for an organization.
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.REGULATION_READ
    )

    query = db.query(ImpactAssessment).filter(ImpactAssessment.organization_id == organization_id)
    if change_id:
        query = query.filter(ImpactAssessment.change_id == change_id)
    if status_filter:
        query = query.filter(ImpactAssessment.status == status_filter)

    return query.order_by(ImpactAssessment.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/impact/{assessment_id}", response_model=ImpactAssessmentResponse)
def get_impact_assessment(
    *,
    db: Session = Depends(deps.get_db),
    assessment_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get a single impact assessment by ID.
    """
    assessment = db.query(ImpactAssessment).filter(ImpactAssessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Impact assessment not found")

    deps.verify_membership(
        db, current_user, assessment.organization_id, required_permission=Permission.REGULATION_READ
    )
    return assessment


@router.post("/impact/analyze", response_model=ImpactAnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def analyze_impact(
    *,
    db: Session = Depends(deps.get_db),
    payload: ImpactAnalysisRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Run AI impact analysis for a regulatory change.
    Returns a job ID for async tracking.
    """
    from app.models.change import RegulatoryChange
    
    change = db.query(RegulatoryChange).filter(RegulatoryChange.id == payload.change_id).first()
    if not change:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regulatory change not found")

    deps.verify_membership(
        db, current_user, change.organization_id, required_permission=Permission.REGULATION_UPDATE
    )

    job = create_job(
        job_type="impact_analysis",
        payload={
            "change_id": str(payload.change_id),
        },
        organization_id=change.organization_id,
        user_id=current_user.id,
        priority=JobPriority.HIGH,
        idempotency_key=f"impact_analysis_{payload.change_id}",
        workflow_id=f"change_intelligence_{change.document_id}",
        step_order=2,
    )

    queue = await get_queue()
    job = await queue.enqueue(job)

    return ImpactAnalysisResponse(
        job_id=job.id,
        status="queued",
        message="Impact analysis started. Use job ID to track progress."
    )
# Literal /impact must precede the UUID detail route.
router.routes.sort(key=lambda route: "{" in route.path)
