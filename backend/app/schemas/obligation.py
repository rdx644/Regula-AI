from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ObligationBase(BaseModel):
    obligation_text: str = Field(..., min_length=1)
    actor: Optional[str] = None
    requirement: Optional[str] = None
    condition: Optional[str] = None
    frequency: Optional[str] = None
    effective_date: Optional[datetime] = None
    source_section: Optional[str] = None
    source_page: Optional[int] = None
    source_text_snippet: Optional[str] = None
    confidence: Optional[float] = Field(0.0, ge=0, le=1)
    extraction_model: Optional[str] = None
    status: Optional[str] = "pending_review"


class ObligationCreate(ObligationBase):
    organization_id: UUID
    version_id: UUID


class ObligationUpdate(BaseModel):
    obligation_text: Optional[str] = None
    actor: Optional[str] = None
    requirement: Optional[str] = None
    condition: Optional[str] = None
    frequency: Optional[str] = None
    effective_date: Optional[datetime] = None
    source_section: Optional[str] = None
    source_page: Optional[int] = None
    source_text_snippet: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)
    extraction_model: Optional[str] = None
    status: Optional[str] = None


class ObligationApprove(BaseModel):
    applicability: str = Field(default="applicable", pattern="^(applicable|not_applicable|conditional|uncertain)$")
    status: str = Field(..., pattern="^(approved|rejected)$")
    notes: Optional[str] = None
    reviewer_id: Optional[UUID] = None


class ObligationBulkAction(BaseModel):
    obligation_ids: list[UUID]
    action: str = Field(..., pattern="^(approve|reject)$")
    notes: Optional[str] = None


class ObligationResponse(ObligationBase):
    applicability: str = "uncertain"
    id: UUID
    organization_id: UUID
    version_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
