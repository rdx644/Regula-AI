from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class RemediationPlanBase(BaseModel):
    recommendation: Optional[str] = None
    priority: Optional[str] = "medium_term"  # immediate, short_term, medium_term, long_term
    estimated_effort: Optional[str] = None
    assigned_to: Optional[str] = None
    status: Optional[str] = "proposed"  # proposed, approved, in_progress, completed, rejected
    due_date: Optional[datetime] = None


class RemediationPlanCreate(RemediationPlanBase):
    organization_id: UUID
    gap_id: UUID


class RemediationPlanUpdate(BaseModel):
    recommendation: Optional[str] = None
    priority: Optional[str] = None
    estimated_effort: Optional[str] = None
    assigned_to: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[datetime] = None


class RemediationRunRequest(BaseModel):
    gap_id: UUID


class RemediationRunResponse(BaseModel):
    job_id: str
    status: str
    message: str


class RemediationPlanResponse(RemediationPlanBase):
    id: UUID
    organization_id: UUID
    gap_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
