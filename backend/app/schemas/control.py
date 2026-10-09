from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


# ── Policy Schemas ──────────────────────────────────────────────────

class PolicyCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    description: Optional[str] = None
    owner: Optional[str] = None
    organization_id: UUID


class PolicyUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=512)
    description: Optional[str] = None
    owner: Optional[str] = None


class PolicyResponse(BaseModel):
    id: UUID
    organization_id: UUID
    title: str
    description: Optional[str] = None
    owner: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PolicyProcessResponse(BaseModel):
    job_id: str
    status: str
    message: str


class ControlExtractionRequest(BaseModel):
    policy_id: UUID


class ControlExtractionResponse(BaseModel):
    job_id: str
    status: str
    message: str


# ── Control Schemas ─────────────────────────────────────────────────

class ControlBase(BaseModel):
    policy_id: Optional[UUID] = None
    control_id_code: Optional[str] = Field(None, max_length=64)
    objective: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    frequency: Optional[str] = None
    procedure: Optional[str] = None
    evidence_requirement: Optional[str] = None
    business_unit: Optional[str] = None
    status: Optional[str] = "active"


class ControlCreate(ControlBase):
    organization_id: UUID


class ControlUpdate(BaseModel):
    policy_id: Optional[UUID] = None
    control_id_code: Optional[str] = None
    objective: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    frequency: Optional[str] = None
    procedure: Optional[str] = None
    evidence_requirement: Optional[str] = None
    business_unit: Optional[str] = None
    status: Optional[str] = None


class ControlApprove(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected)$")
    notes: Optional[str] = None
    reviewer_id: Optional[UUID] = None


class ControlBulkAction(BaseModel):
    control_ids: list[UUID]
    action: str = Field(..., pattern="^(approve|reject)$")
    notes: Optional[str] = None


class ControlResponse(ControlBase):
    source_page: Optional[str] = None
    source_section: Optional[str] = None
    source_text_snippet: Optional[str] = None
    id: UUID
    organization_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
