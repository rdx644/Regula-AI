import json
from typing import Any, Dict, List, TypedDict
from uuid import UUID

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.agents.schemas import (
    RemediationRecommendation,
    AgentStepOutput,
)
from app.core.ai_provider import get_llm_chain
from app.db.session import SessionLocal
from app.models.gap import Gap, RemediationPlan, RiskAssessment
from app.models.obligation import RegulatoryObligation
from app.models.control import Control


class RemediationState(TypedDict):
    gap_id: UUID
    organization_id: UUID
    gap: Gap
    risk_assessment: RiskAssessment
    obligation: RegulatoryObligation
    control: Control
    recommendation: RemediationRecommendation
    errors: List[str]
    tokens_used: int
    model_used: str
    provider: str


REMEDIATION_PROMPT = """You are a banking compliance expert recommending remediation for compliance gaps.

Given a gap with its risk assessment, recommend a structured remediation plan.

GAP:
- Type: {gap_type}
- Description: {gap_description}
- Severity: {gap_severity}

RISK ASSESSMENT:
- Likelihood: {likelihood}
- Impact: {impact}
- Risk Score: {risk_score}
- Risk Level: {risk_level}
- Reasoning: {risk_reasoning}

OBLIGATION:
- Text: {obligation_text}
- Actor: {actor}
- Requirement: {requirement}
- Frequency: {frequency}

CONTROL (if exists):
- Code: {control_code}
- Objective: {control_objective}
- Description: {control_description}
- Current Procedure: {control_procedure}

Recommend a remediation plan with:
1. root_cause: Why the gap exists
2. recommended_action: Specific action to close the gap
3. control_change: How the control should change (new/modified/removed)
4. owner_recommendation: Who should own the remediation
5. priority: "immediate", "short_term", "medium_term", "long_term"
6. target_date: When to complete (ISO format)
7. evidence_required: What evidence will demonstrate closure
8. validation_test: How to verify remediation worked
9. expected_residual_risk: "critical", "high", "medium", "low"
10. reasoning: Explanation of the recommendation

Rules:
- Priority based on risk_level: critical→immediate, high→short_term, medium→medium_term, low→long_term
- Root cause must be specific and actionable
- Recommended action must be testable
- Control change must be specific (new control, modify existing, remove)
- Owner should be a role/team, not a person
- Evidence required must be concrete
- Validation test must be measurable

Return JSON matching the RemediationRecommendation schema."""


async def generate_remediation(
    gap: Gap,
    risk_assessment: RiskAssessment,
    obligation: RegulatoryObligation,
    control: Control,
) -> RemediationRecommendation:
    llm_chain, config = get_llm_chain("reasoning")

    prompt = REMEDIATION_PROMPT.format(
        gap_type=gap.gap_type,
        gap_description=gap.description or "N/A",
        gap_severity=gap.severity,
        likelihood=risk_assessment.likelihood or 0.5,
        impact=risk_assessment.impact or 0.5,
        risk_score=risk_assessment.risk_score or 0.0,
        risk_level=risk_assessment.risk_level or "medium",
        risk_reasoning=risk_assessment.reasoning or "N/A",
        obligation_text=obligation.obligation_text,
        actor=obligation.actor or "N/A",
        requirement=obligation.requirement or "N/A",
        frequency=obligation.frequency or "N/A",
        control_code=control.control_id_code if control else "N/A",
        control_objective=control.objective if control else "N/A",
        control_description=control.description if control else "N/A",
        control_procedure=control.procedure if control else "N/A",
    )

    prompt += f"\nGap ID: {gap.id}"
    messages = [
        {"role": "system", "content": "You are a banking compliance expert. Recommend precise, actionable remediation."},
        {"role": "user", "content": prompt},
    ]

    response = await llm_chain.complete(messages, RemediationRecommendation, config)
    
    response.content.gap_id = gap.id
    
    return response.content


async def run_remediation(
    gap_id: UUID,
    organization_id: UUID,
) -> AgentStepOutput:
    db = SessionLocal()
    try:
        gap = db.query(Gap).filter(Gap.id == gap_id, Gap.organization_id == organization_id).first()
        if not gap:
            return AgentStepOutput(
                success=False,
                error=f"Gap {gap_id} not found",
                tokens_used=0,
                model_used="",
                provider="",
            )

        risk_assessment = gap.risk_assessment
        if not risk_assessment:
            return AgentStepOutput(
                success=False,
                error=f"Gap {gap_id} has no risk assessment",
                tokens_used=0,
                model_used="",
                provider="",
            )

        obligation = db.query(RegulatoryObligation).filter(RegulatoryObligation.id == gap.obligation_id).first() if gap.obligation_id else None
        control = db.query(Control).filter(Control.id == gap.control_id).first() if gap.control_id else None

        if not obligation:
            return AgentStepOutput(
                success=False,
                error=f"Obligation not found for gap",
                tokens_used=0,
                model_used="",
                provider="",
            )

        existing = db.query(RemediationPlan).filter(RemediationPlan.organization_id == organization_id, RemediationPlan.gap_id == gap_id).first()
        if existing:
            return AgentStepOutput(success=True, result={"plan_id": str(existing.id)}, model_used="", provider="deterministic")
        recommendation = await generate_remediation(gap, risk_assessment, obligation, control)

        # Create remediation plan
        from datetime import datetime, timedelta
        
        plan = RemediationPlan(
            organization_id=organization_id,
            gap_id=gap_id,
            recommendation=recommendation.recommended_action,
            priority=recommendation.priority,
            estimated_effort="TBD",
            assigned_to=recommendation.owner_recommendation,
            status="proposed",
            due_date=recommendation.target_date or datetime.utcnow() + timedelta(days=30),
        )
        db.add(plan)

        # Proposed recommendations do not change authoritative gap state.
        
        db.commit()

        return AgentStepOutput(
            success=True,
            result={
                "gap_id": str(gap_id),
                "plan_id": str(plan.id),
                "priority": recommendation.priority,
                "owner": recommendation.owner_recommendation,
                "target_date": recommendation.target_date.isoformat() if recommendation.target_date else None,
            },
            tokens_used=500,
            model_used="gpt-4o",
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
