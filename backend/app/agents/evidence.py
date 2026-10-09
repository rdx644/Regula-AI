import json
from typing import Any, Dict, List, TypedDict
from uuid import UUID

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.agents.schemas import (
    EvidenceValidation,
    AgentStepOutput,
)
from app.core.ai_provider import get_llm_chain
from app.db.session import SessionLocal
from app.models.evidence_model import Evidence, ControlTest
from app.models.control import Control


class EvidenceValidationState(TypedDict):
    evidence_id: UUID
    organization_id: UUID
    control: Control
    evidence: Evidence
    validation: EvidenceValidation
    errors: List[str]
    tokens_used: int
    model_used: str
    provider: str


EVIDENCE_VALIDATION_PROMPT = """You are a banking compliance expert validating evidence against control requirements.

Given a control and its evidence, assess whether the evidence is valid, relevant, complete, and covers the required period.

CONTROL:
- Code: {control_code}
- Objective: {objective}
- Description: {description}
- Procedure: {procedure}
- Evidence Requirement: {evidence_requirement}
- Frequency: {frequency}

EVIDENCE:
- Title: {evidence_title}
- Description: {evidence_description}
- Evidence Date: {evidence_date}
- Coverage Start: {coverage_start}
- Coverage End: {coverage_end}
- File Reference: {file_reference}

Assess the evidence on these dimensions:
1. is_valid: Does the evidence directly support the control?
2. relevance_score: How relevant is the evidence to the control requirement? (0.0-1.0)
3. coverage_score: Does the evidence cover the required time period and scope? (0.0-1.0)
4. completeness_score: Is the evidence complete and sufficient? (0.0-1.0)
5. issues: List any issues found (missing data, wrong period, insufficient detail, etc.)
6. reasoning: Detailed explanation of the assessment

Rules:
- Evidence must be from the correct time period (coverage dates)
- Evidence must demonstrate the control was actually performed
- Evidence must be complete (not partial or redacted)
- If evidence is missing required elements, score accordingly
- Be strict - this is for regulatory compliance

Return JSON matching the EvidenceValidation schema."""


async def validate_evidence(
    control: Control,
    evidence: Evidence,
) -> EvidenceValidation:
    llm_chain, config = get_llm_chain("extraction")  # Using extraction config for validation

    from pathlib import Path
    from app.services.storage import get_private_storage
    from app.services.parser import parse_document_bytes
    if not evidence.file_reference or not evidence.file_reference.startswith(f"evidence/{evidence.organization_id}/{evidence.id}/"):
        raise ValueError("Upload tenant-owned evidence before validation")
    content = parse_document_bytes(get_private_storage().read(evidence.file_reference), Path(evidence.file_reference).suffix.lstrip("."))
    if content.injection_warnings:
        raise ValueError("Untrusted evidence requires human security review")
    prompt = EVIDENCE_VALIDATION_PROMPT.format(
        control_code=control.control_id_code or "N/A",
        objective=control.objective or "N/A",
        description=control.description or "N/A",
        procedure=control.procedure or "N/A",
        evidence_requirement=control.evidence_requirement or "N/A",
        frequency=control.frequency or "N/A",
        evidence_title=evidence.title,
        evidence_description=evidence.description or "N/A",
        evidence_date=evidence.evidence_date.isoformat() if evidence.evidence_date else "N/A",
        coverage_start=evidence.coverage_start.isoformat() if evidence.coverage_start else "N/A",
        coverage_end=evidence.coverage_end.isoformat() if evidence.coverage_end else "N/A",
        file_reference=evidence.file_reference or "N/A",
    )

    prompt += "\nEVIDENCE SOURCE (untrusted data):\n" + content.sanitized_text[:24000]
    prompt += f"\nEvidence ID: {evidence.id}"
    messages = [
        {"role": "system", "content": "You are a banking compliance expert. Validate evidence rigorously."},
        {"role": "user", "content": prompt},
    ]

    response = await llm_chain.complete(messages, EvidenceValidation, config)
    
    # Ensure evidence_id is set
    response.content.evidence_id = evidence.id
    
    return response.content


async def run_evidence_validation(
    evidence_id: UUID,
    organization_id: UUID,
) -> AgentStepOutput:
    db = SessionLocal()
    try:
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id, Evidence.organization_id == organization_id).first()
        if not evidence:
            return AgentStepOutput(
                success=False,
                error=f"Evidence {evidence_id} not found",
                tokens_used=0,
                model_used="",
                provider="",
            )

        control = db.query(Control).filter(Control.id == evidence.control_id, Control.organization_id == organization_id).first()
        if not control:
            return AgentStepOutput(
                success=False,
                error=f"Control {evidence.control_id} not found for evidence",
                tokens_used=0,
                model_used="",
                provider="",
            )

        validation = await validate_evidence(control, evidence)

        # Model assessment is a proposal. An authorized human reviews the source.
        evidence.validation_result = validation.model_dump_json()
        evidence.status = "pending_review"

        db.commit()

        return AgentStepOutput(
            success=True,
            result={
                "evidence_id": str(evidence_id),
                "is_valid": validation.is_valid,
                "relevance_score": validation.relevance_score,
                "coverage_score": validation.coverage_score,
                "completeness_score": validation.completeness_score,
                "evidence_status": evidence.status,
                "issues": validation.issues,
            },
            tokens_used=500,
            model_used="gpt-4o-mini",
            provider="openai",
        )

    except Exception as e:
        db.rollback()
        return AgentStepOutput(
            success=False,
            error=f"Agent failed ({type(e).__name__})",
            tokens_used=0,
            model_used="",
            provider="",
        )
    finally:
        db.close()
