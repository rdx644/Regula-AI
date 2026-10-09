import json
from pydantic import field_validator
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


# â”€â”€ Regulatory Change Schemas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class RegulatoryChangeBase(BaseModel):
    change_type: str = Field(..., max_length=64)  # added, removed, modified, clarification, tightening, relaxation
    summary: Optional[str] = None
    affected_obligations: Optional[List[UUID]] = None
    severity: Optional[str] = "medium"  # critical, high, medium, low
    status: Optional[str] = "detected"  # detected, analyzed, reviewed, acknowledged


class RegulatoryChangeCreate(RegulatoryChangeBase):
    organization_id: UUID
    document_id: UUID
    old_version_id: Optional[UUID] = None
    new_version_id: UUID


class RegulatoryChangeUpdate(BaseModel):
    change_type: Optional[str] = None
    summary: Optional[str] = None
    affected_obligations: Optional[List[UUID]] = None
    severity: Optional[str] = None
    status: Optional[str] = None


class RegulatoryChangeResponse(RegulatoryChangeBase):
    id: UUID
    organization_id: UUID
    document_id: UUID
    old_version_id: Optional[UUID] = None
    new_version_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator('affected_obligations', mode="before")
    @classmethod
    def parse_json_columns(cls, value):
        return json.loads(value) if isinstance(value, str) else value

    class Config:
        from_attributes = True


# â”€â”€ Impact Assessment Schemas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ImpactAssessmentBase(BaseModel):
    affected_controls: Optional[List[UUID]] = None
    affected_policies: Optional[List[UUID]] = None
    new_gaps_identified: Optional[List[dict]] = None
    risk_delta: Optional[float] = None
    recommendation: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    status: Optional[str] = "draft"  # draft, reviewed, approved


class ImpactAssessmentCreate(ImpactAssessmentBase):
    organization_id: UUID
    change_id: UUID


class ImpactAssessmentResponse(ImpactAssessmentBase):
    id: UUID
    organization_id: UUID
    change_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator('affected_controls', 'affected_policies', 'new_gaps_identified', mode="before")
    @classmethod
    def parse_json_columns(cls, value):
        return json.loads(value) if isinstance(value, str) else value

    class Config:
        from_attributes = True


# â”€â”€ Change Intelligence Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ChangeDetectionRequest(BaseModel):
    document_id: UUID
    old_version_id: UUID
    new_version_id: UUID


class ChangeDetectionResponse(BaseModel):
    job_id: str
    status: str
    message: str


class ImpactAnalysisRequest(BaseModel):
    change_id: UUID


class ImpactAnalysisResponse(BaseModel):
    job_id: str
    status: str
    message: str


class RegulationCompareRequest(BaseModel):
    document_id: UUID
    version_a_id: UUID
    version_b_id: UUID


class RegulationCompareResponse(BaseModel):
    changes: List[dict]
    summary: dict