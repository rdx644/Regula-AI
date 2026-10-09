from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


# ── Risk Assessment Schemas ─────────────────────────────────────────

class RiskAssessmentBase(BaseModel):
    likelihood: Optional[float] = Field(None, ge=0, le=1)
    impact: Optional[float] = Field(None, ge=0, le=1)
    risk_score: Optional[float] = Field(None, ge=0, le=100)
    risk_level: Optional[str] = None  # critical, high, medium, low
    reasoning: Optional[str] = None


class RiskAssessmentCreate(RiskAssessmentBase):
    gap_id: UUID


class RiskAssessmentResponse(RiskAssessmentBase):
    id: UUID
    gap_id: UUID
    assessed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Gap Schemas ─────────────────────────────────────────────────────

class GapBase(BaseModel):
    gap_type: str = Field(..., max_length=64)  # no_control, partial_control, no_evidence, stale_evidence, test_failure, unmapped
    description: Optional[str] = None
    severity: Optional[str] = "medium"  # critical, high, medium, low
    status: Optional[str] = "open"  # open, in_remediation, closed, accepted, deferred


class GapCreate(GapBase):
    organization_id: UUID
    obligation_id: Optional[UUID] = None
    control_id: Optional[UUID] = None


class GapUpdate(BaseModel):
    gap_type: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None


class GapRunRequest(BaseModel):
    obligation_id: UUID


class GapRunResponse(BaseModel):
    job_id: str
    status: str
    message: str


class GapResponse(GapBase):
    id: UUID
    organization_id: UUID
    obligation_id: Optional[UUID] = None
    control_id: Optional[UUID] = None
    risk_assessment: Optional[RiskAssessmentResponse] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
