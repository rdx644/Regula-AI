import json
from typing import Any, Dict, List, TypedDict
from uuid import UUID
from collections import defaultdict

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.agents.schemas import (
    AgentStepOutput,
)
from app.core.ai_provider import get_llm_chain
from app.core.retrieval import HybridRetriever
from app.db.session import SessionLocal
from app.models.obligation import RegulatoryObligation
from app.models.control import Control
from app.models.mapping import RegulationControlMapping
from app.models.gap import Gap
from app.models.change import RegulatoryChange
from app.models.regulation import RegulatoryVersion, RegulatoryDocument


class CrossRegulationState(TypedDict):
    organization_id: UUID
    obligations_by_regulation: Dict[str, List[RegulatoryObligation]]
    common_obligations: List[Dict[str, Any]]
    overlapping_controls: List[Dict[str, Any]]
    duplicate_requirements: List[Dict[str, Any]]
    consolidation_opportunities: List[Dict[str, Any]]
    errors: List[str]
    tokens_used: int
    model_used: str
    provider: str


CROSS_REGULATION_PROMPT = """You are a banking compliance expert analyzing cross-regulation intelligence.

Given obligations from multiple regulations, identify:
1. Common obligations across regulations
2. Overlapping controls that serve multiple regulations
3. Duplicate or redundant requirements
4. Consolidation opportunities

REGULATIONS AND OBLIGATIONS:
{regulations_data}

ANALYSIS REQUIRED:
1. common_obligations: Obligations that appear in multiple regulations (same actor, similar requirement)
2. overlapping_controls: Controls that map to obligations from multiple regulations
3. duplicate_requirements: Requirements that are essentially the same across regulations
4. consolidation_opportunities: Where banks can use single control/evidence for multiple regulations

For each finding, provide:
- regulation_ids: List of regulation document IDs involved
- obligation_ids: List of obligation IDs involved
- control_ids: List of control IDs involved (if applicable)
- description: Human-readable explanation
- confidence: 0.0-1.0
- potential_effort_savings: "high", "medium", "low"

Return JSON with lists for each category."""


async def analyze_cross_regulation(
    organization_id: UUID,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        # Get all obligations grouped by regulation document
        obligations = db.query(RegulatoryObligation).filter(
            RegulatoryObligation.organization_id == organization_id
        ).all()
        
        # Group by regulation document (via version -> document)
        regulations_data = {}
        for obl in obligations:
            version = db.query(RegulatoryVersion).filter(
                RegulatoryVersion.id == obl.version_id
            ).first()
            if version:
                doc = db.query(RegulatoryDocument).filter(
                    RegulatoryDocument.id == version.document_id
                ).first()
                if doc:
                    key = f"{doc.title} (v{version.version_number})"
                    if key not in regulations_data:
                        regulations_data[key] = {
                            "document_id": str(doc.id),
                            "version_id": str(version.id),
                            "title": doc.title,
                            "source": doc.source,
                            "jurisdiction": doc.jurisdiction,
                            "obligations": []
                        }
                    regulations_data[key]["obligations"].append({
                        "id": str(obl.id),
                        "text": obl.obligation_text,
                        "actor": obl.actor,
                        "requirement": obl.requirement,
                        "condition": obl.condition,
                        "frequency": obl.frequency,
                    })
        
        if len(regulations_data) < 2:
            return {
                "common_obligations": [],
                "overlapping_controls": [],
                "duplicate_requirements": [],
                "consolidation_opportunities": [],
            }
        
        llm_chain, config = get_llm_chain("reasoning")
        
        prompt = CROSS_REGULATION_PROMPT.format(
            regulations_data=json.dumps(regulations_data, indent=2),
        )
        
        messages = [
            {"role": "system", "content": "You are a banking compliance expert. Analyze cross-regulation intelligence."},
            {"role": "user", "content": prompt},
        ]
        
        from pydantic import BaseModel
        from typing import List
        
        class CrossRegulationFinding(BaseModel):
            regulation_ids: List[str]
            obligation_ids: List[str]
            control_ids: List[str] = []
            description: str
            confidence: float
            potential_effort_savings: str
        
        class CrossRegulationResult(BaseModel):
            common_obligations: List[CrossRegulationFinding]
            overlapping_controls: List[CrossRegulationFinding]
            duplicate_requirements: List[CrossRegulationFinding]
            consolidation_opportunities: List[CrossRegulationFinding]
        
        response = await llm_chain.complete(messages, CrossRegulationResult, config)
        
        result = response.content.model_dump()
        allowed_documents = {item['document_id'] for item in regulations_data.values()}
        allowed_obligations = {str(o.id) for o in obligations}
        allowed_controls = {str(c.id) for c in db.query(Control).filter(Control.organization_id == organization_id).all()}
        for findings in result.values():
            for finding in findings:
                if not set(finding['regulation_ids']) <= allowed_documents or not set(finding['obligation_ids']) <= allowed_obligations or not set(finding['control_ids']) <= allowed_controls:
                    raise ValueError('Analysis references an unknown resource')
        return result
        
    except Exception as e:
        return {"error": f"Analysis failed ({type(e).__name__})"}
    finally:
        db.close()


async def run_cross_regulation_analysis(
    organization_id: UUID,
) -> AgentStepOutput:
    result = await analyze_cross_regulation(organization_id)
    
    if "error" in result:
        return AgentStepOutput(
            success=False,
            error=result["error"],
            tokens_used=0,
            model_used="",
            provider="",
        )
    
    return AgentStepOutput(
        success=True,
        result={
            **result,
            "review_status": "pending_review",
        },
        tokens_used=0,
        model_used="",
        provider="",
    )


class ContradictionState(TypedDict):
    organization_id: UUID
    obligations: List[RegulatoryObligation]
    contradictions: List[Dict[str, Any]]
    errors: List[str]
    tokens_used: int
    model_used: str
    provider: str


CONTRADICTION_PROMPT = """You are a banking compliance expert detecting potential regulatory contradictions.

Given a set of regulatory obligations, identify potential contradictions or conflicts.

OBLIGATIONS:
{obligations_data}

DETECT:
1. Direct contradictions: Obligations that explicitly require opposite actions
2. Implicit conflicts: Obligations that create practical conflicts (e.g., different deadlines, incompatible frequencies, mutually exclusive conditions)
3. Jurisdictional conflicts: Requirements from different jurisdictions that conflict
4. Hierarchical conflicts: Higher-level requirements that contradict lower-level ones

For each potential contradiction, provide:
- obligation_ids: The conflicting obligations
- contradiction_type: "direct", "implicit", "jurisdictional", "hierarchical"
- description: Clear explanation of the conflict
- severity: "critical", "high", "medium", "low"
- confidence: 0.0-1.0
- recommendation: How to resolve or escalate

IMPORTANT: Only flag "Potential contradiction" unless verified by legal/compliance review.
Be conservative - false positives are costly.

Return JSON with a "contradictions" list."""


async def detect_contradictions(
    organization_id: UUID,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        obligations = db.query(RegulatoryObligation).filter(
            RegulatoryObligation.organization_id == organization_id,
            RegulatoryObligation.status == "approved",
        ).all()
        
        if len(obligations) < 2:
            return {"contradictions": []}
        
        obligations_data = [{
            "id": str(obl.id),
            "text": obl.obligation_text,
            "actor": obl.actor,
            "requirement": obl.requirement,
            "condition": obl.condition,
            "frequency": obl.frequency,
            "source_section": obl.source_section,
        } for obl in obligations]
        
        llm_chain, config = get_llm_chain("reasoning")
        
        prompt = CONTRADICTION_PROMPT.format(
            obligations_data=json.dumps(obligations_data, indent=2),
        )
        
        messages = [
            {"role": "system", "content": "You are a banking compliance expert. Detect potential contradictions conservatively."},
            {"role": "user", "content": prompt},
        ]
        
        from pydantic import BaseModel
        from typing import List
        
        class ContradictionFinding(BaseModel):
            obligation_ids: List[str]
            contradiction_type: str
            description: str
            severity: str
            confidence: float
            recommendation: str
        
        class ContradictionResult(BaseModel):
            contradictions: List[ContradictionFinding]
        
        response = await llm_chain.complete(messages, ContradictionResult, config)
        
        result = response.content.model_dump()
        for finding in result['contradictions']:
            if not set(finding['obligation_ids']) <= {str(o.id) for o in obligations}:
                raise ValueError('Contradiction references an unknown obligation')
        return result
        
    except Exception as e:
        return {"error": f"Analysis failed ({type(e).__name__})"}
    finally:
        db.close()


async def run_contradiction_detection(
    organization_id: UUID,
) -> AgentStepOutput:
    result = await detect_contradictions(organization_id)
    
    if "error" in result:
        return AgentStepOutput(
            success=False,
            error=result["error"],
            tokens_used=0,
            model_used="",
            provider="",
        )
    
    contradictions = result.get("contradictions", [])
    
    # Filter to only high-confidence findings
    high_confidence = [c for c in contradictions if c.get("confidence", 0) >= 0.7]
    
    return AgentStepOutput(
        success=True,
        result={
            "total_contradictions": len(contradictions),
            "high_confidence": len(high_confidence),
            "contradictions": contradictions,
        },
        tokens_used=0,
        model_used="",
        provider="",
    )
