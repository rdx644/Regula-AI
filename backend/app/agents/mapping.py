import json
from typing import Any, Dict, List, Literal, TypedDict
from uuid import UUID

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.agents.schemas import (
    MappingDecision,
    MappingCandidate,
    AgentStepOutput,
)
from app.core.ai_provider import get_llm_chain, ModelConfig
from app.core.retrieval import HybridRetriever
from app.db.session import SessionLocal
from app.models.obligation import RegulatoryObligation
from app.models.control import Control
from app.models.mapping import RegulationControlMapping


class MappingState(TypedDict):
    obligation_id: UUID
    organization_id: UUID
    candidate_controls: List[Control]
    mapping_decision: MappingDecision
    errors: List[str]
    tokens_used: int
    model_used: str
    provider: str


MAPPING_PROMPT = """You are a banking compliance expert mapping regulatory obligations to internal controls.

Given a regulatory obligation and a list of candidate internal controls, determine the best mapping.

OBLIGATION:
- Text: {obligation_text}
- Actor: {actor}
- Requirement: {requirement}
- Condition: {condition}
- Frequency: {frequency}

CANDIDATE CONTROLS:
{candidates}

For the mapping decision, provide:
1. mapping_status: One of "mapped", "partially_mapped", "unmapped", "conflicting", "human_review"
2. confidence: 0.0-1.0
3. reasoning: Detailed explanation of the mapping decision
4. alternative_controls: List of other relevant controls with similarity scores

Rules:
- "mapped": Control directly and fully addresses the obligation
- "partially_mapped": Control addresses part of the obligation
- "unmapped": No suitable control found
- "conflicting": Control contradicts the obligation
- "human_review": Uncertain, requires human judgment
- Only map to controls that are testable and have clear procedures
- Consider frequency alignment (e.g., quarterly obligation → quarterly control)

Return JSON matching the MappingDecision schema."""


async def find_candidate_controls(
    obligation: RegulatoryObligation,
    organization_id: UUID,
    limit: int = 10,
) -> List[Control]:
    db = SessionLocal()
    try:
        # Retrieve controls directly. New tenants have no mapping graph yet.
        import re
        words = set(re.findall(r"[a-z]{3,}", obligation.obligation_text.lower()))
        controls = db.query(Control).filter(Control.organization_id == organization_id,
            Control.status.in_(["active", "approved"])).all()
        controls.sort(key=lambda c: len(words & set(re.findall(r"[a-z]{3,}", f"{c.objective} {c.description} {c.procedure}".lower()))), reverse=True)
        controls = controls[:limit]
        return controls
    finally:
        db.close()


async def map_obligation_to_controls(
    obligation: RegulatoryObligation,
    candidates: List[Control],
) -> MappingDecision:
    llm_chain, config = get_llm_chain("mapping")

    candidate_text = "\n\n".join([
        f"Control ID: {c.id}\nControl: {c.control_id_code}\n"
        f"Objective: {c.objective}\n"
        f"Description: {c.description}\n"
        f"Procedure: {c.procedure}\n"
        f"Frequency: {c.frequency}\n"
        f"Business Unit: {c.business_unit}"
        for c in candidates
    ])

    prompt = MAPPING_PROMPT.format(
        obligation_text=obligation.obligation_text,
        actor=obligation.actor or "N/A",
        requirement=obligation.requirement or "N/A",
        condition=obligation.condition or "N/A",
        frequency=obligation.frequency or "N/A",
        candidates=candidate_text or "No candidates found",
    )
    prompt += f"\nObligation ID: {obligation.id}"

    messages = [
        {"role": "system", "content": "You are a banking compliance expert. Map obligations to controls precisely."},
        {"role": "user", "content": prompt},
    ]

    response = await llm_chain.complete(messages, MappingDecision, config)
    
    # Ensure the obligation_id is set
    response.content.obligation_id = obligation.id
    if response.content.control_id is not None and response.content.control_id not in {c.id for c in candidates}:
        raise ValueError("Mapping refers to a control outside the approved candidates")
    if any(alternative.control_id not in {c.id for c in candidates} for alternative in response.content.alternative_controls):
        raise ValueError("Alternative mapping refers to an unknown control")
    if response.content.confidence < 0.7:
        response.content.mapping_status = "human_review"
    
    return response.content


async def persist_mapping(state: MappingState) -> MappingState:
    db = SessionLocal()
    try:
        decision = state["mapping_decision"]
        
        if decision.control_id is None or decision.mapping_status == "unmapped":
            return state
        # Check if mapping already exists
        existing = db.query(RegulationControlMapping).filter(
            RegulationControlMapping.obligation_id == decision.obligation_id,
            RegulationControlMapping.control_id == decision.control_id,
            RegulationControlMapping.organization_id == state["organization_id"]
        ).first()
        
        if existing and existing.approved_by:
            state["errors"].append("Approved mapping requires a human review before replacement")
            return state
        if existing:
            existing.mapping_status = decision.mapping_status
            existing.confidence = decision.confidence
            existing.reasoning = decision.reasoning
        else:
            mapping = RegulationControlMapping(
                organization_id=state["organization_id"],
                obligation_id=decision.obligation_id,
                control_id=decision.control_id,
                mapping_status=decision.mapping_status,
                confidence=decision.confidence,
                reasoning=decision.reasoning,
            )
            db.add(mapping)
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        state["errors"].append(f"Persistence failed ({type(e).__name__})")
    finally:
        db.close()
    
    return state


def build_mapping_graph() -> StateGraph:
    workflow = StateGraph(MappingState)
    
    # Single node that does retrieval + mapping + persistence
    async def run_mapping(state: MappingState) -> MappingState:
        db = SessionLocal()
        try:
            obligation = db.query(RegulatoryObligation).filter(
                RegulatoryObligation.id == state["obligation_id"],
                RegulatoryObligation.organization_id == state["organization_id"]
            ).first()
            
            if not obligation:
                state["errors"].append(f"Obligation {state['obligation_id']} not found")
                return state
            
            if obligation.status != "approved" or obligation.applicability not in {"applicable", "conditional"}:
                state["errors"].append("Approve obligation and applicability before mapping")
                return state
            # Find candidate controls
            candidates = await find_candidate_controls(obligation, state["organization_id"])
            state["candidate_controls"] = candidates
            
            if not candidates:
                state["mapping_decision"] = MappingDecision(
                    obligation_id=obligation.id,
                    control_id=None,
                    mapping_status="unmapped",
                    confidence=0.0,
                    reasoning="No candidate controls found",
                    alternative_controls=[],
                )
            else:
                # Generate mapping decision
                decision = await map_obligation_to_controls(obligation, candidates)
                state["mapping_decision"] = decision
            
            # Persist
            state = await persist_mapping(state)
            
        except Exception as e:
            state["errors"].append(f"Mapping failed ({type(e).__name__})")
        finally:
            db.close()
        
        return state
    
    workflow.add_node("run_mapping", run_mapping)
    workflow.set_entry_point("run_mapping")
    workflow.add_edge("run_mapping", END)
    
    return workflow.compile()


mapping_graph = build_mapping_graph()


async def run_mapping(
    obligation_id: UUID,
    organization_id: UUID,
) -> AgentStepOutput:
    initial_state = MappingState(
        obligation_id=obligation_id,
        organization_id=organization_id,
        candidate_controls=[],
        mapping_decision=None,
        errors=[],
        tokens_used=0,
        model_used="",
        provider="",
    )

    try:
        config = {"configurable": {"thread_id": f"mapping-{obligation_id}"}}
        final_state = await mapping_graph.ainvoke(initial_state, config)

        return AgentStepOutput(
            success=len(final_state["errors"]) == 0,
            result={
                "mapping_status": final_state["mapping_decision"].mapping_status if final_state["mapping_decision"] else "error",
                "confidence": final_state["mapping_decision"].confidence if final_state["mapping_decision"] else 0.0,
                "errors": final_state["errors"],
            },
            error="; ".join(final_state["errors"]) if final_state["errors"] else None,
            tokens_used=final_state["tokens_used"],
            model_used=final_state["model_used"],
            provider=final_state["provider"],
        )
    except Exception as e:
        return AgentStepOutput(
            success=False,
            error=f"Agent failed ({type(e).__name__})",
            tokens_used=0,
            model_used="",
            provider="",
        )
