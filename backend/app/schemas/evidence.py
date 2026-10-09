from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
import json
from pydantic import field_validator


# ── Evidence Schemas ────────────────────────────────────────────────

class EvidenceBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    description: Optional[str] = None
    file_reference: Optional[str] = None
    evidence_date: Optional[datetime] = None
    coverage_start: Optional[datetime] = None
    coverage_end: Optional[datetime] = None
    status: Optional[str] = "pending_review"


class EvidenceCreate(EvidenceBase):
    organization_id: UUID
    control_id: UUID


class EvidenceUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=512)
    description: Optional[str] = None
    file_reference: Optional[str] = None
    evidence_date: Optional[datetime] = None
    coverage_start: Optional[datetime] = None
    coverage_end: Optional[datetime] = None
    status: Optional[str] = None


class EvidenceValidateRequest(BaseModel):
    evidence_id: UUID


class EvidenceValidateResponse(BaseModel):
    job_id: str
    status: str
    message: str


class EvidenceResponse(EvidenceBase):
    review_notes: Optional[str] = None
    validation_result: Optional[dict] = None
    @field_validator('validation_result', mode='before')
    @classmethod
    def parse_validation(cls, value):
        return json.loads(value) if isinstance(value, str) else value
    id: UUID
    organization_id: UUID
    control_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Control Test Schemas ────────────────────────────────────────────

class ControlTestBase(BaseModel):
    test_type: Optional[str] = "automated"  # automated, manual, hybrid
    description: Optional[str] = None
    result: Optional[str] = Field("inconclusive", pattern="^(pass|fail|partial|inconclusive)$")
    effectiveness_score: Optional[float] = Field(None, ge=0, le=1)
    findings: Optional[str] = None
    tested_at: Optional[datetime] = None
    tester: Optional[str] = None


class ControlTestCreate(ControlTestBase):
    organization_id: UUID
    control_id: UUID


class ControlTestRunRequest(BaseModel):
    control_id: UUID


class ControlTestRunResponse(BaseModel):
    job_id: str
    status: str
    message: str


class ControlTestResponse(ControlTestBase):
    review_status: str = 'manual'
    proposed_result: Optional[dict] = None
    @field_validator('proposed_result', mode='before')
    @classmethod
    def parse_proposal(cls, value):
        return json.loads(value) if isinstance(value, str) else value
    id: UUID
    organization_id: UUID
    control_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EvidenceReview(BaseModel):
    status: str = Field(..., pattern='^(valid|invalid|insufficient)$')
    notes: str = Field(..., min_length=1, max_length=2000)


class TestReview(BaseModel):
    result: str = Field(..., pattern='^(pass|fail|partial|inconclusive)$')
    effectiveness_score: float = Field(..., ge=0, le=1)
    findings: str = Field(..., min_length=1, max_length=10000)
