from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ExtractionStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    MERGED = "merged"


class ObligationExtraction(BaseModel):
    obligation_text: str = Field(..., description="The full obligation text as extracted")
    actor: Optional[str] = Field(None, description="Who must comply (e.g., 'bank', 'financial institution')")
    requirement: Optional[str] = Field(None, description="What must be done")
    condition: Optional[str] = Field(None, description="Under what circumstances")
    frequency: Optional[str] = Field(None, description="Frequency (e.g., 'quarterly', 'ongoing', 'annual')")
    effective_date: Optional[datetime] = Field(None, description="When the obligation takes effect")
    source_section: Optional[str] = Field(None, description="Section reference in source document")
    source_page: Optional[int] = Field(None, description="Page number in source document")
    source_text_snippet: Optional[str] = Field(None, description="Exact quoted text from source")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    reasoning: Optional[str] = Field(None, description="Extraction reasoning trace")

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return round(v, 2)


class ObligationExtractionBatch(BaseModel):
    # An empty extraction is a valid result when a chunk contains guidance only.
    obligations: List[ObligationExtraction] = Field(default_factory=list)
    document_summary: Optional[str] = Field(None, description="Brief summary of the document")


class ControlExtraction(BaseModel):
    control_id_code: str = Field(..., description="Unique control identifier (e.g., CTL-CAP-001)")
    objective: Optional[str] = Field(None, description="What the control aims to achieve")
    description: Optional[str] = Field(None, description="Detailed description of the control activity")
    owner: Optional[str] = Field(None, description="Responsible role/team")
    frequency: Optional[str] = Field(None, description="Frequency (e.g., 'daily', 'monthly', 'quarterly')")
    procedure: Optional[str] = Field(None, description="Step-by-step procedure")
    evidence_requirement: Optional[str] = Field(None, description="What evidence demonstrates control execution")
    business_unit: Optional[str] = Field(None, description="Business unit where control operates")
    source_section: Optional[str] = Field(None, description="Section reference in source document")
    source_page: Optional[int] = Field(None, description="Page number in source document")
    source_text_snippet: Optional[str] = Field(None, description="Exact quoted text from source")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    reasoning: Optional[str] = Field(None, description="Extraction reasoning trace")

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return round(v, 2)


class ControlExtractionBatch(BaseModel):
    controls: List[ControlExtraction]
    document_summary: Optional[str] = Field(None, description="Brief summary of the document")


class MappingCandidate(BaseModel):
    control_id: UUID
    control_code: str
    control_objective: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    reasoning: str


class MappingDecision(BaseModel):
    obligation_id: UUID
    control_id: Optional[UUID] = None
    mapping_status: str = Field(..., pattern="^(mapped|partially_mapped|unmapped|conflicting|human_review)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    alternative_controls: List[MappingCandidate] = Field(default_factory=list)


class EvidenceValidation(BaseModel):
    evidence_id: UUID
    is_valid: bool
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    coverage_score: float = Field(..., ge=0.0, le=1.0)
    completeness_score: float = Field(..., ge=0.0, le=1.0)
    issues: List[str] = Field(default_factory=list)
    reasoning: str


class ControlTestResult(BaseModel):
    control_id: UUID
    test_type: str
    result: str = Field(..., pattern="^(pass|fail|partial|inconclusive)$")
    effectiveness_score: float = Field(..., ge=0.0, le=1.0)
    findings: str
    evidence_reviewed: List[UUID] = Field(default_factory=list)


class GapIdentification(BaseModel):
    obligation_id: Optional[UUID] = None
    control_id: Optional[UUID] = None
    gap_type: str = Field(..., pattern="^(no_control|partial_control|no_evidence|stale_evidence|test_failure|unmapped)$")
    description: str
    severity: str = Field(..., pattern="^(critical|high|medium|low)$")
    reasoning: str


class RiskAssessmentOutput(BaseModel):
    gap_id: UUID
    likelihood: float = Field(..., ge=0.0, le=1.0)
    impact: float = Field(..., ge=0.0, le=1.0)
    risk_score: float = Field(..., ge=0.0, le=100.0)
    risk_level: str = Field(..., pattern="^(critical|high|medium|low)$")
    reasoning: str


class RemediationRecommendation(BaseModel):
    gap_id: UUID
    root_cause: str
    recommended_action: str
    control_change: Optional[str] = None
    owner_recommendation: Optional[str] = None
    priority: str = Field(..., pattern="^(immediate|short_term|medium_term|long_term)$")
    target_date: Optional[datetime] = None
    evidence_required: List[str] = Field(default_factory=list)
    validation_test: Optional[str] = None
    expected_residual_risk: str = Field(..., pattern="^(critical|high|medium|low)$")
    reasoning: str


class ImpactAnalysisOutput(BaseModel):
    change_id: UUID
    affected_obligations: List[UUID] = Field(default_factory=list)
    affected_controls: List[UUID] = Field(default_factory=list)
    affected_evidence: List[UUID] = Field(default_factory=list)
    new_gaps: List[GapIdentification] = Field(default_factory=list)
    risk_delta: float
    recommendation: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class SimulationOutput(BaseModel):
    simulation_id: UUID
    baseline_state: dict
    scenario_state: dict
    changed_obligations: List[UUID] = Field(default_factory=list)
    affected_controls: List[UUID] = Field(default_factory=list)
    new_gaps: List[GapIdentification] = Field(default_factory=list)
    risk_delta: float
    remediation_delta: List[RemediationRecommendation] = Field(default_factory=list)


class AgentStepInput(BaseModel):
    organization_id: UUID
    workflow_type: str
    payload: dict


class AgentStepOutput(BaseModel):
    success: bool
    result: Optional[dict] = None
    error: Optional[str] = None
    tokens_used: int = 0
    model_used: str
    provider: str
