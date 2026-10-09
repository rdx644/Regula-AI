from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.core.rbac import Permission
from app.models.user import User
from app.services.queue import get_queue, create_job, JobStatus

router = APIRouter()


class JobStatusResponse(BaseModel):
    id: str
    type: str
    status: str
    result: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    *,
    job_id: str,
    organization_id: UUID = Query(...),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Return status only to members of the tenant that owns the queued job."""
    if not job_id or len(job_id) > 64 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.ORG_READ
    )
    queue = await get_queue()
    job = await queue.get_job(job_id)
    if not job or job.organization_id != str(organization_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return JobStatusResponse(
        id=job.id,
        type=job.type,
        status=job.status.value,
        result=job.result,
        created_at=job.created_at,
        updated_at=job.updated_at,
        finished_at=job.finished_at,
        error=job.error,
        retry_count=job.retry_count,
        next_retry_at=job.next_retry_at,
    )


@router.post("/{job_id}/retry", status_code=202)
async def retry_job(job_id: UUID, organization_id: UUID, db: Session = Depends(deps.get_db), current_user: User = Depends(deps.get_current_user)):
    from app.services.execution import job_permission
    from app.services.governance import audit
    deps.verify_membership(db, current_user, organization_id, required_permission=Permission.ORG_READ)
    queue = await get_queue()
    previous = await queue.get_job(str(job_id))
    if not previous or previous.organization_id != str(organization_id):
        raise HTTPException(404, "Job not found")
    deps.verify_membership(db, current_user, organization_id, required_permission=job_permission(previous.type))
    if previous.status != JobStatus.FAILED:
        raise HTTPException(409, "Only terminally failed jobs can be retried")
    job = await queue.enqueue(create_job(previous.type, previous.payload, organization_id, current_user.id,
        priority=previous.priority, idempotency_key=f"manual_retry:{previous.id}", workflow_id=previous.workflow_id))
    audit(db, organization_id, current_user.id, "job_retry_requested", "job", job_id, replacement_job_id=job.id)
    db.commit()
    return {"job_id": job.id, "status": job.status.value}
