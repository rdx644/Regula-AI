from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile
from sqlalchemy.orm import Session

from app.api import deps
from app.core.rbac import Permission
from app.models.evidence_model import Evidence, ControlTest
from app.models.control import Control
from app.models.user import User
from app.schemas.evidence import (
    EvidenceCreate,
    EvidenceUpdate,
    EvidenceResponse,
    EvidenceValidateRequest,
    EvidenceValidateResponse,
    ControlTestCreate,
    ControlTestResponse,
    ControlTestRunRequest,
    ControlTestRunResponse,
    EvidenceReview,
    TestReview,
)
from app.services.queue import get_queue, create_job, JobPriority
from app.services.governance import input_fingerprint
from app.services.compliance import assessment_revision, require_passing_evidence

router = APIRouter()


# ── Evidence Endpoints ──────────────────────────────────────────────

@router.post("/", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
def create_evidence(
    *,
    db: Session = Depends(deps.get_db),
    payload: EvidenceCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Upload or link an evidence record to a control.
    """
    deps.verify_membership(
        db, current_user, payload.organization_id, required_permission=Permission.EVIDENCE_CREATE
    )

    control = db.query(Control).filter(
        Control.id == payload.control_id,
        Control.organization_id == payload.organization_id,
    ).first()
    if not control:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Control not found")

    if payload.file_reference:
        raise HTTPException(422, "Use the private evidence upload endpoint")
    evidence = Evidence(
        organization_id=payload.organization_id,
        control_id=payload.control_id,
        title=payload.title,
        description=payload.description,
        file_reference=None,
        evidence_date=payload.evidence_date,
        coverage_start=payload.coverage_start,
        coverage_end=payload.coverage_end,
        # Evidence stays pending until the validation workflow or an authorized reviewer approves it.
        status="pending_review",
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


@router.get("/", response_model=List[EvidenceResponse])
def list_evidence(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    control_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List evidence records for an organization.
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.EVIDENCE_READ
    )

    query = db.query(Evidence).filter(Evidence.organization_id == organization_id)
    if control_id:
        query = query.filter(Evidence.control_id == control_id)
    if status_filter:
        query = query.filter(Evidence.status == status_filter)

    return query.order_by(Evidence.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(
    *,
    db: Session = Depends(deps.get_db),
    evidence_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get a single evidence record by ID.
    """
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")

    deps.verify_membership(
        db, current_user, evidence.organization_id, required_permission=Permission.EVIDENCE_READ
    )
    return evidence


@router.post("/validate", response_model=EvidenceValidateResponse, status_code=status.HTTP_202_ACCEPTED)
async def validate_evidence(
    *,
    db: Session = Depends(deps.get_db),
    payload: EvidenceValidateRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Run AI evidence validation for a specific evidence record.
    Returns a job ID for async tracking.
    """
    evidence = db.query(Evidence).filter(Evidence.id == payload.evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")

    deps.verify_membership(
        db, current_user, evidence.organization_id, required_permission=Permission.EVIDENCE_VALIDATE
    )

    job = create_job(
        job_type="evidence_validation",
        payload={
            "evidence_id": str(payload.evidence_id),
        },
        organization_id=evidence.organization_id,
        user_id=current_user.id,
        priority=JobPriority.HIGH,
        idempotency_key=f"validate_evidence_{payload.evidence_id}_{input_fingerprint(evidence.file_reference, evidence.updated_at)}",
        workflow_id=f"evidence_validation_{evidence.id}",
        step_order=1,
    )

    queue = await get_queue()
    job = await queue.enqueue(job)

    return EvidenceValidateResponse(
        job_id=job.id,
        status=job.status.value,
        message="Evidence validation started. Use job ID to track progress."
    )


# ── Control Test Endpoints ──────────────────────────────────────────

@router.post("/tests", response_model=ControlTestResponse, status_code=status.HTTP_201_CREATED)
def create_control_test(
    *,
    db: Session = Depends(deps.get_db),
    payload: ControlTestCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Record an execution test result for a control.
    """
    deps.verify_membership(
        db, current_user, payload.organization_id, required_permission=Permission.EVIDENCE_VALIDATE
    )

    control = db.query(Control).filter(
        Control.id == payload.control_id,
        Control.organization_id == payload.organization_id,
    ).first()
    if not control:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Control not found")

    if payload.result == "pass":
        require_passing_evidence(db, payload.organization_id, payload.control_id, payload.effectiveness_score)
    test = ControlTest(
        organization_id=payload.organization_id,
        control_id=payload.control_id,
        test_type=payload.test_type,
        description=payload.description,
        result=payload.result,
        effectiveness_score=payload.effectiveness_score,
        findings=payload.findings,
        tested_at=payload.tested_at,
        tester=current_user.full_name,
        review_status="approved",
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


@router.get("/tests", response_model=List[ControlTestResponse])
def list_control_tests(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    control_id: Optional[UUID] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List control tests for an organization.
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.EVIDENCE_READ
    )

    query = db.query(ControlTest).filter(ControlTest.organization_id == organization_id)
    if control_id:
        query = query.filter(ControlTest.control_id == control_id)

    return query.order_by(ControlTest.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/tests/run", response_model=ControlTestRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_control_test(
    *,
    db: Session = Depends(deps.get_db),
    payload: ControlTestRunRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Run AI-assisted control test for a specific control.
    Returns a job ID for async tracking.
    """
    from app.models.control import Control
    
    control = db.query(Control).filter(Control.id == payload.control_id).first()
    if not control:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Control not found")

    deps.verify_membership(
        db, current_user, control.organization_id, required_permission=Permission.EVIDENCE_VALIDATE
    )

    job = create_job(
        job_type="control_testing",
        payload={
            "control_id": str(payload.control_id),
        },
        organization_id=control.organization_id,
        user_id=current_user.id,
        priority=JobPriority.HIGH,
        idempotency_key=f"test_control_{payload.control_id}_{assessment_revision(db, control.organization_id, control_id=control.id)}",
        workflow_id=f"control_testing_{control.id}",
        step_order=1,
    )

    queue = await get_queue()
    job = await queue.enqueue(job)

    return ControlTestRunResponse(
        job_id=job.id,
        status=job.status.value,
        message="Control testing started. Use job ID to track progress."
    )


@router.post("/{evidence_id}/file", response_model=EvidenceResponse)
async def upload_evidence_file(evidence_id: UUID, file: UploadFile = File(...), db: Session = Depends(deps.get_db), current_user: User = Depends(deps.get_current_user)):
    from app.services.storage import get_private_storage, validate_document
    from app.core.config import settings
    from app.services.governance import audit
    record = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not record:
        raise HTTPException(404, "Evidence not found")
    deps.verify_membership(db, current_user, record.organization_id, required_permission=Permission.EVIDENCE_UPDATE)
    if record.status == "valid":
        raise HTTPException(409, "Create new evidence to replace an approved artifact")
    content = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Document exceeds the upload size limit")
    suffix, _ = validate_document(content, file.filename)
    storage = get_private_storage()
    key = storage.save(record.organization_id, record.id, suffix, content, category="evidence")
    try:
        record.file_reference = key
        record.status = "pending_review"
        audit(db, record.organization_id, current_user.id, "evidence_uploaded", "evidence", record.id, bytes=len(content))
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    db.refresh(record)
    return record


@router.get("/{evidence_id}/file")
def download_evidence_file(evidence_id: UUID, db: Session = Depends(deps.get_db), current_user: User = Depends(deps.get_current_user)):
    from fastapi.responses import Response
    from app.services.storage import get_private_storage
    record = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not record:
        raise HTTPException(404, "Evidence not found")
    deps.verify_membership(db, current_user, record.organization_id, required_permission=Permission.EVIDENCE_READ)
    if not record.file_reference or not record.file_reference.startswith(f"evidence/{record.organization_id}/{record.id}/"):
        raise HTTPException(404, "Source not available")
    return Response(get_private_storage().read(record.file_reference), media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=evidence-source", "Cache-Control": "no-store"})

@router.post("/{evidence_id}/approve", response_model=EvidenceResponse)
def review_evidence(evidence_id: UUID, payload: EvidenceReview, db: Session = Depends(deps.get_db), current_user: User = Depends(deps.get_current_user)):
    from app.services.governance import audit
    record = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not record:
        raise HTTPException(404, "Evidence not found")
    deps.verify_membership(db, current_user, record.organization_id, required_permission=Permission.EVIDENCE_VALIDATE)
    if not record.file_reference or not record.file_reference.startswith(f"evidence/{record.organization_id}/{record.id}/"):
        raise HTTPException(409, "Review a privately uploaded source before approval")
    record.status = payload.status
    record.review_notes = payload.notes
    audit(db, record.organization_id, current_user.id, "evidence_reviewed", "evidence", record.id, next_state=payload.status)
    db.commit()
    db.refresh(record)
    return record


@router.post("/tests/{test_id}/approve", response_model=ControlTestResponse)
def review_test(test_id: UUID, payload: TestReview, db: Session = Depends(deps.get_db), current_user: User = Depends(deps.get_current_user)):
    from app.services.governance import audit
    record = db.query(ControlTest).filter(ControlTest.id == test_id).first()
    if not record:
        raise HTTPException(404, "Test not found")
    deps.verify_membership(db, current_user, record.organization_id, required_permission=Permission.EVIDENCE_VALIDATE)
    if payload.result == "pass":
        require_passing_evidence(db, record.organization_id, record.control_id, payload.effectiveness_score)
    record.result = payload.result
    record.effectiveness_score = payload.effectiveness_score
    record.findings = payload.findings
    record.review_status = 'approved'
    audit(db, record.organization_id, current_user.id, "control_test_reviewed", "control_test", record.id, next_state=payload.result)
    db.commit()
    db.refresh(record)
    return record


# Literal /tests must precede the UUID detail route.
router.routes.sort(key=lambda route: "{" in route.path)
