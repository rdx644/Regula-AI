import json
from typing import Any, Dict, List, Literal, TypedDict
from uuid import UUID

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.agents.schemas import (
    ControlExtraction,
    ControlExtractionBatch,
    AgentStepOutput,
)
from app.core.ai_provider import get_llm_chain, ModelConfig
from app.services.parser import DocumentChunk
from app.db.session import SessionLocal
from app.models.control import Policy, Control


class ControlExtractionState(TypedDict):
    policy_id: UUID
    organization_id: UUID
    document_text: str
    chunks: List[DocumentChunk]
    extracted_controls: List[ControlExtraction]
    current_chunk_index: int
    errors: List[str]
    tokens_used: int
    model_used: str
    provider: str


CONTROL_EXTRACTION_PROMPT = """You are a banking compliance expert extracting structured internal controls from policy documents.

Given a chunk of policy text, extract ALL discrete controls. Each control must be a specific, testable control activity.

For each control, provide:
1. control_id_code: Unique control identifier (e.g., "CTL-CAP-001", "CTL-RISK-042")
2. objective: What the control aims to achieve
3. description: Detailed description of the control activity
4. owner: Responsible role/team (e.g., "CRO", "Treasury", "Internal Audit")
5. frequency: How often performed (e.g., "daily", "weekly", "monthly", "quarterly", "annual", "continuous")
6. procedure: Step-by-step procedure
7. evidence_requirement: What evidence demonstrates control execution
8. business_unit: Business unit where control operates
9. source_section: Section reference in source document
10. source_page: Page number if available
11. source_text_snippet: Exact quote from text (max 500 chars)
12. confidence: Your confidence 0.0-1.0
13. reasoning: Brief explanation of why this is a control

Rules:
- Only extract explicit controls, not general policy statements
- Each control must be independently testable
- Look for: procedures, checklists, reconciliations, approvals, monitoring, reviews
- If uncertain, set confidence < 0.7 and note in reasoning
- Return empty list if no controls found in chunk

Document context: {document_context}

Text chunk (page {page}, section: {section}):
{chunk_text}

Return JSON matching the ControlExtractionBatch schema."""


async def extract_controls_from_chunk(
    chunk: DocumentChunk,
    document_context: str,
) -> List[ControlExtraction]:
    llm_chain, config = get_llm_chain("extraction")

    prompt = CONTROL_EXTRACTION_PROMPT.format(
        document_context=document_context,
        page=chunk.page_number,
        section=chunk.section or "unknown",
        chunk_text=chunk.text,
    )

    messages = [
        {"role": "system", "content": "You are a banking compliance expert. Extract controls precisely."},
        {"role": "user", "content": prompt},
    ]

    response = await llm_chain.complete(messages, ControlExtractionBatch, config)

    return response.content.controls


async def process_control_chunk(state: ControlExtractionState) -> ControlExtractionState:
    idx = state["current_chunk_index"]
    if idx >= len(state["chunks"]):
        return state

    chunk = state["chunks"][idx]
    document_context = f"Internal policy document for policy {state['policy_id']}"

    try:
        controls = await extract_controls_from_chunk(chunk, document_context)

        for ctrl in controls:
            if not ctrl.source_text_snippet or ctrl.source_text_snippet not in chunk.text:
                raise ValueError("Control citation is not an exact source span")
            ctrl.source_page = chunk.page_number
            ctrl.source_section = chunk.section

        state["extracted_controls"].extend(controls)

    except Exception as e:
        state["errors"].append(f"Chunk {idx} failed ({type(e).__name__})")

    state["current_chunk_index"] = idx + 1
    return state


async def persist_controls(state: ControlExtractionState) -> ControlExtractionState:
    db = SessionLocal()
    try:
        policy = db.query(Policy).filter(Policy.id == state["policy_id"], Policy.organization_id == state["organization_id"]).first()
        if not policy:
            state["errors"].append(f"Policy {state['policy_id']} not found")
            return state

        for ctrl_data in state["extracted_controls"]:
            if db.query(Control).filter(Control.organization_id == state["organization_id"],
                Control.policy_id == state["policy_id"], Control.control_id_code == ctrl_data.control_id_code,
                Control.description == ctrl_data.description).first():
                continue
            control = Control(
                organization_id=state["organization_id"],
                policy_id=state["policy_id"],
                control_id_code=ctrl_data.control_id_code,
                objective=ctrl_data.objective,
                description=ctrl_data.description,
                owner=ctrl_data.owner,
                frequency=ctrl_data.frequency,
                procedure=ctrl_data.procedure,
                evidence_requirement=ctrl_data.evidence_requirement,
                business_unit=ctrl_data.business_unit,
                source_page=str(ctrl_data.source_page) if ctrl_data.source_page else None,
                source_section=ctrl_data.source_section,
                source_text_snippet=ctrl_data.source_text_snippet,
                status="pending_review",
            )
            db.add(control)

        db.commit()

    except Exception as e:
        db.rollback()
        state["errors"].append(f"Persistence failed ({type(e).__name__})")
    finally:
        db.close()

    return state


def should_continue_controls(state: ControlExtractionState) -> Literal["process_chunk", "persist_controls"]:
    if state["current_chunk_index"] < len(state["chunks"]):
        return "process_chunk"
    return "persist_controls"


def build_control_extraction_graph() -> StateGraph:
    workflow = StateGraph(ControlExtractionState)

    workflow.add_node("process_chunk", process_control_chunk)
    workflow.add_node("persist_controls", persist_controls)

    workflow.set_entry_point("process_chunk")

    workflow.add_conditional_edges(
        "process_chunk",
        should_continue_controls,
        {
            "process_chunk": "process_chunk",
            "persist_controls": "persist_controls",
        },
    )

    workflow.add_edge("persist_controls", END)

    return workflow.compile()


control_extraction_graph = build_control_extraction_graph()


async def run_control_extraction(
    policy_id: UUID,
    organization_id: UUID,
    document_text: str,
    chunks: List[DocumentChunk],
) -> AgentStepOutput:
    initial_state = ControlExtractionState(
        policy_id=policy_id,
        organization_id=organization_id,
        document_text=document_text,
        chunks=chunks,
        extracted_controls=[],
        current_chunk_index=0,
        errors=[],
        tokens_used=0,
        model_used="",
        provider="",
    )

    try:
        config = {"configurable": {"thread_id": f"control-extraction-{policy_id}"}}
        final_state = await control_extraction_graph.ainvoke(initial_state, config)

        return AgentStepOutput(
            success=len(final_state["errors"]) == 0,
            result={
                "controls_extracted": len(final_state["extracted_controls"]),
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
