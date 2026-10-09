import json
from typing import Any, Dict, List, TypedDict
from uuid import UUID
from datetime import datetime

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.agents.schemas import (
    ImpactAnalysisOutput,
    AgentStepOutput,
)
from app.core.ai_provider import get_llm_chain
from app.db.session import SessionLocal
from app.models.regulation import RegulatoryVersion, RegulatoryDocument
from app.models.obligation import RegulatoryObligation
from app.models.control import Control
from app.models.mapping import RegulationControlMapping
from app.models.evidence_model import Evidence
from app.models.change import RegulatoryChange, ImpactAssessment


class ChangeDetectionState(TypedDict):
    document_id: UUID
    organization_id: UUID
    old_version_id: UUID
    new_version_id: UUID
    old_text: str
    new_text: str
    changes: List[Dict[str, Any]]
    affected_obligations: List[UUID]
    errors: List[str]
    tokens_used: int
    model_used: str
    provider: str


CHANGE_DETECTION_PROMPT = """You are a regulatory compliance expert analyzing changes between two versions of a regulatory document.

Given the old and new versions of a regulatory document, identify all changes at the clause/obligation level.

OLD VERSION TEXT:
{old_text}

NEW VERSION TEXT:
{new_text}

Identify changes:
1. For each change, provide:
   - change_type: "added", "removed", "modified", "clarification", "tightening", "relaxation"
   - old_text: The original text (for removed/modified)
   - new_text: The new text (for added/modified)
   - section: Section reference if identifiable
   - description: Human-readable description of the change
   - severity: "critical", "high", "medium", "low" based on compliance impact
   - affected_obligations: List of obligation IDs from old version that are affected

2. Categorize changes:
   - Added: New requirements/obligations
   - Removed: Requirements that no longer apply
   - Modified: Changed wording that affects meaning
   - Clarification: Wording changes that clarify without changing requirements
   - Tightening: Requirements made more stringent
   - Relaxation: Requirements made less stringent

Return JSON with a "changes" list."""


async def detect_changes(
    old_text: str,
    new_text: str,
    old_version_id: UUID,
    new_version_id: UUID,
) -> List[Dict[str, Any]]:
    llm_chain, config = get_llm_chain("reasoning")

    # Truncate texts if too long
    max_len = 15000
    if len(old_text) > max_len:
        old_text = old_text[:max_len] + "... [truncated]"
    if len(new_text) > max_len:
        new_text = new_text[:max_len] + "... [truncated]"

    prompt = CHANGE_DETECTION_PROMPT.format(
        old_text=old_text,
        new_text=new_text,
    )

    messages = [
        {"role": "system", "content": "You are a regulatory compliance expert. Detect changes precisely."},
        {"role": "user", "content": prompt},
    ]

    from pydantic import BaseModel
    from typing import List
    
    class ChangeItem(BaseModel):
        change_type: str
        old_text: str
        new_text: str
        section: str
        description: str
        severity: str
        affected_obligations: List[str] = []
    
    class ChangeDetectionResult(BaseModel):
        changes: List[ChangeItem]

    response = await llm_chain.complete(messages, ChangeDetectionResult, config)
    
    return [change.model_dump() for change in response.content.changes]


async def run_change_detection(
    document_id: UUID,
    organization_id: UUID,
    old_version_id: UUID,
    new_version_id: UUID,
) -> AgentStepOutput:
    db = SessionLocal()
    try:
        document = db.query(RegulatoryDocument).filter(RegulatoryDocument.id == document_id, RegulatoryDocument.organization_id == organization_id).first()
        if not document:
            raise ValueError("Document not found")
        old_version = db.query(RegulatoryVersion).filter(RegulatoryVersion.id == old_version_id, RegulatoryVersion.document_id == document_id).first()
        new_version = db.query(RegulatoryVersion).filter(RegulatoryVersion.id == new_version_id, RegulatoryVersion.document_id == document_id).first()
        
        if not old_version or not new_version:
            return AgentStepOutput(
                success=False,
                error="Version not found",
                tokens_used=0,
                model_used="",
                provider="",
            )

        if not old_version.raw_text or not new_version.raw_text:
            return AgentStepOutput(
                success=False,
                error="Versions must have parsed text. Run process first.",
                tokens_used=0,
                model_used="",
                provider="",
            )

        changes = await detect_changes(
            old_version.raw_text,
            new_version.raw_text,
            old_version_id,
            new_version_id,
        )

        # Persist changes
        allowed_obligations = {str(o.id) for o in db.query(RegulatoryObligation).filter(RegulatoryObligation.organization_id == organization_id, RegulatoryObligation.version_id == old_version_id).all()}
        for change_data in changes:
            if (change_data["old_text"] and change_data["old_text"] not in old_version.raw_text) or (change_data["new_text"] and change_data["new_text"] not in new_version.raw_text):
                raise ValueError("Change quote is not an exact source span")
            if not set(change_data.get("affected_obligations", [])) <= allowed_obligations:
                raise ValueError("Change output refers to an unknown obligation")
            if db.query(RegulatoryChange).filter_by(organization_id=organization_id, old_version_id=old_version_id, new_version_id=new_version_id, summary=change_data["description"]).first():
                continue
            change = RegulatoryChange(
                organization_id=organization_id,
                document_id=document_id,
                old_version_id=old_version_id,
                new_version_id=new_version_id,
                change_type=change_data["change_type"],
                summary=change_data["description"],
                affected_obligations=json.dumps(change_data.get("affected_obligations", [])),
                severity=change_data["severity"],
                status="detected",
            )
            db.add(change)

        db.commit()

        return AgentStepOutput(
            success=True,
            result={
                "changes_detected": len(changes),
                "change_types": [c["change_type"] for c in changes],
            },
            tokens_used=0,
            model_used="",
            provider="",
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


class ImpactAnalysisState(TypedDict):
    change_id: UUID
    organization_id: UUID
    change: RegulatoryChange
    affected_obligations: List[RegulatoryObligation]
    affected_controls: List[Control]
    affected_evidence: List[Evidence]
    new_gaps: List[Dict[str, Any]]
    risk_delta: float
    errors: List[str]
    tokens_used: int
    model_used: str
    provider: str


IMPACT_ANALYSIS_PROMPT = """You are a banking compliance expert analyzing the impact of a regulatory change.

Given a regulatory change and the current compliance landscape, analyze the impact.

CHANGE:
- Type: {change_type}
- Summary: {summary}
- Severity: {severity}
- Affected Obligations: {affected_obligation_ids}

CURRENT STATE:
- Affected Obligations: {obligation_count}
- Affected Controls: {control_count}
- Current Gaps: {current_gap_count}

For the impact analysis, provide:
1. affected_controls: List of control IDs that need review/update
2. affected_policies: List of policy IDs that need review/update
3. new_gaps: List of new gaps identified (with gap_type, description, severity)
4. risk_delta: Change in overall risk score (-100 to 100)
5. recommendation: Specific actions to take
6. confidence: 0.0-1.0

Rules:
- Risk delta positive = increased risk, negative = decreased risk
- Consider obligation frequency changes, new requirements, removed requirements
- Be specific about which controls/policies need updates
- Confidence should reflect certainty of analysis

Return JSON matching the ImpactAnalysisOutput schema."""


async def analyze_impact(
    change: RegulatoryChange,
    affected_obligations: List[RegulatoryObligation],
    affected_controls: List[Control],
    affected_evidence: List[Evidence],
    current_gaps: List[Dict[str, Any]],
) -> ImpactAnalysisOutput:
    llm_chain, config = get_llm_chain("reasoning")

    prompt = IMPACT_ANALYSIS_PROMPT.format(
        change_type=change.change_type,
        summary=change.summary or "N/A",
        severity=change.severity or "medium",
        affected_obligation_ids=", ".join([str(o.id) for o in affected_obligations]),
        obligation_count=len(affected_obligations),
        control_count=len(affected_controls),
        current_gap_count=len(current_gaps),
    )

    messages = [
        {"role": "system", "content": "You are a banking compliance expert. Analyze regulatory change impact precisely."},
        {"role": "user", "content": prompt},
    ]

    response = await llm_chain.complete(messages, ImpactAnalysisOutput, config)
    
    response.content.change_id = change.id
    
    return response.content


async def run_impact_analysis(
    change_id: UUID,
    organization_id: UUID,
) -> AgentStepOutput:
    db = SessionLocal()
    try:
        change = db.query(RegulatoryChange).filter(RegulatoryChange.id == change_id, RegulatoryChange.organization_id == organization_id).first()
        if not change:
            return AgentStepOutput(
                success=False,
                error=f"Change {change_id} not found",
                tokens_used=0,
                model_used="",
                provider="",
            )

        # Get affected obligations
        affected_obligation_ids = json.loads(change.affected_obligations) if change.affected_obligations else []
        affected_obligations = db.query(RegulatoryObligation).filter(
            RegulatoryObligation.id.in_(affected_obligation_ids), RegulatoryObligation.organization_id == organization_id
        ).all() if affected_obligation_ids else []

        # Get affected controls via mappings
        control_ids = []
        for obl in affected_obligations:
            mappings = db.query(RegulationControlMapping).filter(
                RegulationControlMapping.obligation_id == obl.id, RegulationControlMapping.organization_id == organization_id
            ).all()
            control_ids.extend([m.control_id for m in mappings])
        
        affected_controls = db.query(Control).filter(
            Control.id.in_(control_ids), Control.organization_id == organization_id
        ).all() if control_ids else []

        # Get evidence for affected controls
        affected_evidence = db.query(Evidence).filter(
            Evidence.control_id.in_(control_ids), Evidence.organization_id == organization_id
        ).all() if control_ids else []

        # Get current gaps
        from app.models.gap import Gap
        current_gaps = db.query(Gap).filter(
            Gap.organization_id == organization_id,
            Gap.obligation_id.in_(affected_obligation_ids)
        ).all() if affected_obligation_ids else []

        # Run AI impact analysis
        impact = await analyze_impact(
            change, affected_obligations, affected_controls, affected_evidence,
            [{"id": str(g.id), "type": g.gap_type, "severity": g.severity} for g in current_gaps]
        )

        if not set(impact.affected_controls) <= {c.id for c in affected_controls} or not set(impact.affected_obligations) <= {o.id for o in affected_obligations} or not set(impact.affected_evidence) <= {e.id for e in affected_evidence}:
            raise ValueError("Impact output refers to an unknown resource")
        # Persist impact assessment
        assessment = db.query(ImpactAssessment).filter(ImpactAssessment.change_id == change_id, ImpactAssessment.organization_id == organization_id).first()
        if assessment:
            return AgentStepOutput(success=True, result={"assessment_id": str(assessment.id)}, tokens_used=0, model_used="", provider="")
        assessment = ImpactAssessment(
            organization_id=organization_id,
            change_id=change_id,
            affected_controls=json.dumps([str(c.id) for c in affected_controls]),
            affected_policies=json.dumps([str(c.policy_id) for c in affected_controls if c.policy_id]),
            new_gaps_identified=json.dumps([gap.model_dump(mode="json") for gap in impact.new_gaps]),
            risk_delta=impact.risk_delta,
            recommendation=impact.recommendation,
            confidence=impact.confidence,
            status="draft",
        )
        db.add(assessment)

        change.status = "analyzed"
        db.commit()

        return AgentStepOutput(
            success=True,
            result={
                "change_id": str(change_id),
                "affected_controls": len(affected_controls),
                "risk_delta": impact.risk_delta,
                "new_gaps": len(impact.new_gaps),
                "confidence": impact.confidence,
            },
            tokens_used=0,
            model_used="",
            provider="",
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
