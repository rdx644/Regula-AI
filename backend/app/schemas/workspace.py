"""Bounded, unpaid workspace review contracts. No model inference is implied."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel


class InvestigationRequest(BaseModel):
    organization_id: UUID
    question: Literal["open_gaps", "unmapped_obligations", "evidence_review", "control_coverage"]


class TextComparisonResponse(BaseModel):
    changed: bool
    report: dict
    change_id: UUID | None = None
    impact_id: UUID | None = None


class InvestigationResponse(BaseModel):
    method: str
    question: str
    summary: str
    total: int
    truncated: bool
    findings: list[dict]
    audit_id: UUID
