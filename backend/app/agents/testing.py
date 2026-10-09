import json
from datetime import datetime, timezone
from typing import Any, Dict, List, TypedDict
from uuid import UUID

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.agents.schemas import (
    ControlTestResult,
    AgentStepOutput,
)
from app.core.ai_provider import get_llm_chain
from app.core.retrieval import HybridRetriever
from app.db.session import SessionLocal
from app.models.evidence_model import Evidence, ControlTest
from app.models.control import Control
from app.models.gap import Gap


class ControlTestingState(TypedDict):
    control_id: UUID
    organization_id: UUID
    control: Control
    evidence_list: List[Evidence]
    test_results: List[ControlTestResult]
    errors: List[str]
    tokens_used: int
    model_used: str
    provider: str


CONTROL_TEST_PROMPT = """You are a banking compliance expert executing control tests.

Given a control and its associated evidence, execute the control test and determine effectiveness.

CONTROL:
- Code: {control_code}
- Objective: {objective}
- Description: {description}
- Procedure: {procedure}
- Frequency: {frequency}
- Evidence Requirement: {evidence_requirement}

AVAILABLE EVIDENCE:
{evidence_summary}

Execute the test by:
1. Checking if evidence covers all required elements from the procedure
2. Verifying evidence dates align with control frequency
3. Assessing if evidence demonstrates the control was actually performed
4. Determining test result: pass, fail, partial, inconclusive
5. Calculating effectiveness score (0.0-1.0)
6. Documenting findings

Rules:
- "pass": All procedure steps evidenced, dates align, complete
- "fail": Critical evidence missing, dates don't align, control not performed
- "partial": Some evidence present but gaps exist
- "inconclusive": Insufficient evidence to determine
- Be strict - this is for regulatory compliance

Return JSON matching the ControlTestResult schema."""


async def test_control(
    control: Control,
    evidence_list: List[Evidence],
) -> ControlTestResult:
    llm_chain, config = get_llm_chain("extraction")

    evidence_summary = "\n\n".join([
        f"Evidence: {e.title}\n"
        f"Date: {e.evidence_date.isoformat() if e.evidence_date else 'N/A'}\n"
        f"Coverage: {e.coverage_start.isoformat() if e.coverage_start else 'N/A'} to {e.coverage_end.isoformat() if e.coverage_end else 'N/A'}\n"
        f"Description: {e.description or 'N/A'}\n"
        f"Status: {e.status}"
        for e in evidence_list
    ]) or "No evidence available"
    from pathlib import Path
    from app.services.storage import get_private_storage
    from app.services.parser import parse_document_bytes
    for evidence in evidence_list:
        if not evidence.file_reference or not evidence.file_reference.startswith(f"evidence/{evidence.organization_id}/{evidence.id}/"):
            continue
        parsed = parse_document_bytes(get_private_storage().read(evidence.file_reference), Path(evidence.file_reference).suffix.lstrip('.'))
        if parsed.injection_warnings:
            raise ValueError("Evidence requires human security review")
        evidence_summary += f"\nEvidence ID: {evidence.id}\nSOURCE (untrusted):\n{parsed.sanitized_text[:12000]}"

    prompt = CONTROL_TEST_PROMPT.format(
        control_code=control.control_id_code or "N/A",
        objective=control.objective or "N/A",
        description=control.description or "N/A",
        procedure=control.procedure or "N/A",
        frequency=control.frequency or "N/A",
        evidence_requirement=control.evidence_requirement or "N/A",
        evidence_summary=evidence_summary,
    )
    prompt += f"\nControl ID: {control.id}"

    messages = [
        {"role": "system", "content": "You are a banking compliance expert. Test controls rigorously."},
        {"role": "user", "content": prompt},
    ]

    response = await llm_chain.complete(messages, ControlTestResult, config)
    
    response.content.control_id = control.id
    if not set(response.content.evidence_reviewed) <= {e.id for e in evidence_list}:
        raise ValueError("Test refers to unknown evidence")
    if response.content.result == "pass" and not any(e.file_reference and e.status == "valid" for e in evidence_list):
        raise ValueError("A passing test requires validated source evidence")
    
    return response.content


async def run_control_testing(
    control_id: UUID,
    organization_id: UUID,
) -> AgentStepOutput:
    db = SessionLocal()
    try:
        control = db.query(Control).filter(Control.id == control_id, Control.organization_id == organization_id).first()
        if not control:
            return AgentStepOutput(
                success=False,
                error=f"Control {control_id} not found",
                tokens_used=0,
                model_used="",
                provider="",
            )

        evidence_list = db.query(Evidence).filter(
            Evidence.control_id == control_id,
            Evidence.organization_id == organization_id,
        ).all()

        from app.services.execution import job_context
        execution_id = job_context.get()
        existing = db.query(ControlTest).filter(ControlTest.execution_id == execution_id).first() if execution_id else None
        if existing:
            return AgentStepOutput(success=True, result={"test_result": existing.result}, model_used="", provider="deterministic")
        test_result = await test_control(control, evidence_list)

        # Persist test result
        test_record = ControlTest(
            execution_id=execution_id,
            organization_id=organization_id,
            control_id=control_id,
            test_type="ai_assisted",
            description=f"AI-assisted test of control {control.control_id_code}",
            result="inconclusive",
            effectiveness_score=None,
            review_status="pending_review",
            proposed_result=test_result.model_dump_json(),
            findings=test_result.findings,
            tested_at=datetime.now(timezone.utc),
            tester="AI Agent",
        )
        db.add(test_record)
        db.commit()

        return AgentStepOutput(
            success=True,
            result={
                "control_id": str(control_id),
                "test_result": "inconclusive",
                "proposed_result": test_result.result,
                "review_status": "pending_review",
                "effectiveness_score": test_result.effectiveness_score,
                "findings": test_result.findings,
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
