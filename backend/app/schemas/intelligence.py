from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


# ── Cross-Regulation Intelligence Schemas ──────────────────────────

class CrossRegulationFinding(BaseModel):
    regulation_ids: List[str]
    obligation_ids: List[str]
    control_ids: List[str] = []
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    potential_effort_savings: str  # high, medium, low


class CrossRegulationResult(BaseModel):
    common_obligations: List[CrossRegulationFinding] = []
    overlapping_controls: List[CrossRegulationFinding] = []
    duplicate_requirements: List[CrossRegulationFinding] = []
    consolidation_opportunities: List[CrossRegulationFinding] = []


class CrossRegulationRunRequest(BaseModel):
    organization_id: UUID


class CrossRegulationRunResponse(BaseModel):
    job_id: str
    status: str
    message: str


# ── Contradiction Detection Schemas ────────────────────────────────

class ContradictionFinding(BaseModel):
    obligation_ids: List[str]
    contradiction_type: str  # direct, implicit, jurisdictional, hierarchical
    description: str
    severity: str  # critical, high, medium, low
    confidence: float = Field(ge=0.0, le=1.0)
    recommendation: str


class ContradictionResult(BaseModel):
    contradictions: List[ContradictionFinding] = []


class ContradictionRunRequest(BaseModel):
    organization_id: UUID


class ContradictionRunResponse(BaseModel):
    job_id: str
    status: str
    message: str