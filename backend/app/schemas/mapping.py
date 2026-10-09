from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class MappingBase(BaseModel):
    mapping_status: str = "mapped"  # mapped, partially_mapped, unmapped, conflicting, human_review
    confidence: Optional[float] = None
    reasoning: Optional[str] = None


class MappingCreate(MappingBase):
    organization_id: UUID
    obligation_id: UUID
    control_id: UUID


class MappingUpdate(BaseModel):
    mapping_status: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None


class MappingApprove(BaseModel):
    mapping_status: Optional[str] = "mapped"
    notes: Optional[str] = None


class MappingRunRequest(BaseModel):
    obligation_id: UUID


class MappingRunResponse(BaseModel):
    job_id: str
    status: str
    message: str


class MappingResponse(MappingBase):
    id: UUID
    organization_id: UUID
    obligation_id: UUID
    control_id: UUID
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
