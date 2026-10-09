from typing import Any, List, Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api import deps
from app.services.governance import owned, audit
from app.core.rbac import Permission
from app.models.control import Policy, Control
from app.models.user import User
from app.schemas.control import (
    PolicyCreate,
    PolicyUpdate,
    PolicyResponse,
    PolicyProcessResponse,
    ControlExtractionRequest,
    ControlExtractionResponse,
    ControlCreate,
    ControlUpdate,
    ControlResponse,
    ControlApprove,
    ControlBulkAction,
)
from app.services.queue import get_queue, create_job, JobPriority
from app.services.governance import input_fingerprint
from app.services.storage import get_private_storage, validate_document
from app.core.config import settings

router = APIRouter()


# â”€â”€ Policy Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/policies", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
def create_policy(
    *,
    db: Session = Depends(deps.get_db),
    payload: PolicyCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Create a bank internal policy document.
    """
    deps.verify_membership(
        db, current_user, payload.organization_id, required_permission=Permission.CONTROL_CREATE
    )

    policy = Policy(
        organization_id=payload.organization_id,
        title=payload.title,
        description=payload.description,
        owner=payload.owner,
        status="active",
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.get("/policies", response_model=List[PolicyResponse])
def list_policies(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List policies for an organization.
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.CONTROL_READ
    )

    query = db.query(Policy).filter(Policy.organization_id == organization_id)
    if status_filter:
        query = query.filter(Policy.status == status_filter)

    return query.order_by(Policy.created_at.desc()).offset(offset).limit(limit).all()


@router.get('/policies/{policy_id}', response_model=PolicyResponse)
def get_policy(policy_id: UUID, db: Session = Depends(deps.get_db), current_user: User = Depends(deps.get_current_user)):
    policy = db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(404, 'Policy not found')
    deps.verify_membership(db, current_user, policy.organization_id, required_permission=Permission.CONTROL_READ)
    return policy


@router.patch('/policies/{policy_id}', response_model=PolicyResponse)
def update_policy(policy_id: UUID, payload: PolicyUpdate, db: Session = Depends(deps.get_db), current_user: User = Depends(deps.get_current_user)):
    policy = db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(404, 'Policy not found')
    deps.verify_membership(db, current_user, policy.organization_id, required_permission=Permission.CONTROL_UPDATE)
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(policy, name, value)
    audit(db, policy.organization_id, current_user.id, 'policy_updated', 'policy', policy.id)
    db.commit()
    db.refresh(policy)
    return policy


@router.get('/policies/{policy_id}/file')
def download_policy(policy_id: UUID, db: Session = Depends(deps.get_db), current_user: User = Depends(deps.get_current_user)):
    from fastapi.responses import Response
    policy = get_policy(policy_id, db, current_user)
    if not policy.file_reference or not policy.file_reference.startswith(f'policies/{policy.organization_id}/{policy.id}/'):
        raise HTTPException(404, 'Source not available')
    return Response(get_private_storage().read(policy.file_reference), media_type='application/octet-stream',
        headers={'Content-Disposition': 'attachment; filename=policy-source', 'Cache-Control': 'no-store'})


@router.post("/policies/{policy_id}/process", response_model=PolicyProcessResponse, status_code=status.HTTP_202_ACCEPTED)
async def process_policy(
    *,
    db: Session = Depends(deps.get_db),
    policy_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Process a policy document: parse, extract text, and queue for control extraction.
    Returns a job ID for async tracking.
    """
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")

    deps.verify_membership(
        db, current_user, policy.organization_id, required_permission=Permission.CONTROL_UPDATE
    )

    if not policy.file_reference:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Upload a policy document before processing it")

    job = create_job(
        job_type="policy_process",
        payload={
            "policy_id": str(policy.id),
        },
        organization_id=policy.organization_id,
        user_id=current_user.id,
        priority=JobPriority.HIGH,
        idempotency_key=f"process_policy_{policy.id}_{input_fingerprint(policy.file_reference)}",
        workflow_id=f"control_framework_{policy.id}",
        step_order=1,
    )

    queue = await get_queue()
    candidate_id = job.id
    job = await queue.enqueue(job)
    if candidate_id != job.id:
        return PolicyProcessResponse(job_id=job.id, status=job.status.value, message="Existing job for this source")

    policy.status = "processing"
    db.commit()
    return PolicyProcessResponse(
        job_id=job.id,
        status=job.status.value,
        message="Policy document processing started. Use job ID to track progress."
    )


@router.post("/policies/{policy_id}/file", response_model=PolicyResponse)
async def upload_policy_file(
    *,
    db: Session = Depends(deps.get_db),
    policy_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Store a validated internal policy privately for asynchronous parsing."""
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    deps.verify_membership(
        db, current_user, policy.organization_id, required_permission=Permission.CONTROL_UPDATE
    )
    if policy.status in {"processing", "processed"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This policy cannot be replaced in its current state")

    content = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Document exceeds the upload size limit")
    suffix, _content_type = validate_document(content, file.filename)
    storage = get_private_storage()
    new_key = storage.save(policy.organization_id, policy.id, suffix, content, category="policies")
    old_key = policy.file_reference
    try:
        policy.file_reference = new_key
        policy.status = "uploaded"
        db.commit()
        db.refresh(policy)
    except Exception:
        db.rollback()
        storage.delete(new_key)
        raise
    if old_key and old_key.startswith(f"policies/{policy.organization_id}/{policy.id}/"):
        storage.delete(old_key)
    return policy


@router.post("/policies/{policy_id}/extract-controls", response_model=ControlExtractionResponse, status_code=status.HTTP_202_ACCEPTED)
async def extract_controls(
    *,
    db: Session = Depends(deps.get_db),
    policy_id: UUID,
    payload: ControlExtractionRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Extract structured controls from a processed policy document.
    Returns a job ID for async tracking.
    """
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")

    deps.verify_membership(
        db, current_user, policy.organization_id, required_permission=Permission.CONTROL_UPDATE
    )

    if payload.policy_id != policy.id:
        raise HTTPException(404, "Policy not found")
    if not policy.raw_text:
        raise HTTPException(409, "Process the uploaded policy before extracting controls")
    job = create_job(
        job_type="control_extraction",
        payload={
            "policy_id": str(payload.policy_id),
        },
        organization_id=policy.organization_id,
        user_id=current_user.id,
        priority=JobPriority.HIGH,
        idempotency_key=f"extract_controls_{payload.policy_id}_{input_fingerprint(policy.raw_text)}",
        workflow_id=f"control_framework_{policy.id}",
        step_order=2,
    )

    queue = await get_queue()
    job = await queue.enqueue(job)

    return ControlExtractionResponse(
        job_id=job.id,
        status=job.status.value,
        message="Control extraction started. Use job ID to track progress."
    )


# â”€â”€ Control Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/", response_model=ControlResponse, status_code=status.HTTP_201_CREATED)
def create_control(
    *,
    db: Session = Depends(deps.get_db),
    payload: ControlCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Create an internal compliance control (e.g. CTL-042).
    """
    deps.verify_membership(
        db, current_user, payload.organization_id, required_permission=Permission.CONTROL_CREATE
    )

    if payload.policy_id:
        owned(db, Policy, payload.policy_id, payload.organization_id)

    control = Control(
        organization_id=payload.organization_id,
        policy_id=payload.policy_id,
        control_id_code=payload.control_id_code,
        objective=payload.objective,
        description=payload.description,
        owner=payload.owner,
        frequency=payload.frequency,
        procedure=payload.procedure,
        evidence_requirement=payload.evidence_requirement,
        business_unit=payload.business_unit,
        status="pending_review",
    )
    db.add(control)
    db.commit()
    db.refresh(control)
    return control


@router.get("/", response_model=List[ControlResponse])
def list_controls(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    policy_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List controls for an organization, optionally filtered by policy or status.
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.CONTROL_READ
    )

    query = db.query(Control).filter(Control.organization_id == organization_id)
    if policy_id:
        query = query.filter(Control.policy_id == policy_id)
    if status_filter:
        query = query.filter(Control.status == status_filter)

    return query.order_by(Control.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{control_id}", response_model=ControlResponse)
def get_control(
    *,
    db: Session = Depends(deps.get_db),
    control_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get a single control by ID.
    """
    control = db.query(Control).filter(Control.id == control_id).first()
    if not control:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Control not found")

    deps.verify_membership(
        db, current_user, control.organization_id, required_permission=Permission.CONTROL_READ
    )
    return control


@router.patch("/{control_id}", response_model=ControlResponse)
def update_control(
    *,
    db: Session = Depends(deps.get_db),
    control_id: UUID,
    payload: ControlUpdate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update a control.
    """
    control = db.query(Control).filter(Control.id == control_id).first()
    if not control:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Control not found")

    deps.verify_membership(
        db, current_user, control.organization_id, required_permission=Permission.CONTROL_UPDATE
    )

    if payload.policy_id:
        owned(db, Policy, payload.policy_id, control.organization_id)
    if payload.status in {"approved", "active"}:
        raise HTTPException(403, "Use the review endpoint to activate a proposed control")
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(control, field, val)

    db.commit()
    db.refresh(control)
    return control


@router.post("/{control_id}/approve", response_model=ControlResponse)
def approve_control(
    *,
    db: Session = Depends(deps.get_db),
    control_id: UUID,
    payload: ControlApprove,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Human-in-the-loop (HITL) approval or rejection of an AI-extracted control.
    Only users with CONTROL_UPDATE permission can approve/reject.
    """
    control = db.query(Control).filter(Control.id == control_id).first()
    if not control:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Control not found")

    deps.verify_membership(
        db, current_user, control.organization_id, required_permission=Permission.CONTROL_APPROVE
    )

    if control.status not in ["pending_review", "rejected"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve control in status: {control.status}"
        )

    audit(db, control.organization_id, current_user.id, "control_reviewed", "control", control.id, next_state=payload.status)
    control.status = payload.status
    if payload.notes:
        control.description = (control.description or "") + f"\n[HITL {payload.status.upper()}]: {payload.notes}"

    db.commit()
    db.refresh(control)
    return control


@router.post("/bulk-action", response_model=List[ControlResponse])
def bulk_action_controls(
    *,
    db: Session = Depends(deps.get_db),
    payload: ControlBulkAction,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Bulk approve or reject multiple controls (HITL).
    """
    if not payload.control_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No control IDs provided")

    controls = db.query(Control).filter(Control.id.in_(payload.control_ids)).all()

    if len(controls) != len(payload.control_ids):
        found_ids = {c.id for c in controls}
        missing = set(payload.control_ids) - found_ids
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Controls not found: {missing}"
        )

    deps.verify_membership(
        db, current_user, controls[0].organization_id, required_permission=Permission.CONTROL_APPROVE
    )

    for ctrl in controls:
        if ctrl.organization_id != controls[0].organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All controls must belong to the same organization"
            )

        if ctrl.status not in ["pending_review", "rejected"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Control {ctrl.id} cannot be {payload.action}d in status: {ctrl.status}"
            )

        ctrl.status = "approved" if payload.action == "approve" else "rejected"
        audit(db, ctrl.organization_id, current_user.id, "control_reviewed", "control", ctrl.id, next_state=ctrl.status)
        if payload.notes:
            ctrl.description = (ctrl.description or "") + f"\n[BULK {payload.action.upper()}]: {payload.notes}"

    db.commit()
    for ctrl in controls:
        db.refresh(ctrl)

    return controls
