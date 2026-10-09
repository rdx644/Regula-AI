from typing import Any, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.rbac import Permission
from app.models.user import User
from app.schemas.intelligence import (
    CrossRegulationRunRequest,
    CrossRegulationRunResponse,
    ContradictionRunRequest,
    ContradictionRunResponse,
)
from app.services.queue import get_queue, create_job, JobPriority
from app.services.compliance import assessment_revision

router = APIRouter()


@router.post("/cross-regulation", response_model=CrossRegulationRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_cross_regulation(
    *,
    db: Session = Depends(deps.get_db),
    payload: CrossRegulationRunRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Run cross-regulation intelligence analysis.
    Identifies common obligations, overlapping controls, duplicates, and consolidation opportunities.
    """
    deps.verify_membership(
        db, current_user, payload.organization_id, required_permission=Permission.REGULATION_READ
    )

    job = create_job(
        job_type="cross_regulation",
        payload={
            "organization_id": str(payload.organization_id),
        },
        organization_id=payload.organization_id,
        user_id=current_user.id,
        priority=JobPriority.NORMAL,
        idempotency_key=f"cross_regulation_{payload.organization_id}_{assessment_revision(db, payload.organization_id)}",
        workflow_id=f"advanced_intelligence_{payload.organization_id}",
        step_order=1,
    )

    queue = await get_queue()
    job = await queue.enqueue(job)

    return CrossRegulationRunResponse(
        job_id=job.id,
        status=job.status.value,
        message="Cross-regulation analysis started. Use job ID to track progress."
    )


@router.post("/contradiction", response_model=ContradictionRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_contradiction_detection(
    *,
    db: Session = Depends(deps.get_db),
    payload: ContradictionRunRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Run contradiction detection across approved obligations.
    Identifies potential regulatory contradictions.
    """
    deps.verify_membership(
        db, current_user, payload.organization_id, required_permission=Permission.REGULATION_READ
    )

    job = create_job(
        job_type="contradiction",
        payload={
            "organization_id": str(payload.organization_id),
        },
        organization_id=payload.organization_id,
        user_id=current_user.id,
        priority=JobPriority.NORMAL,
        idempotency_key=f"contradiction_{payload.organization_id}_{assessment_revision(db, payload.organization_id)}",
        workflow_id=f"advanced_intelligence_{payload.organization_id}",
        step_order=2,
    )

    queue = await get_queue()
    job = await queue.enqueue(job)

    return ContradictionRunResponse(
        job_id=job.id,
        status=job.status.value,
        message="Contradiction detection started. Use job ID to track progress."
    )