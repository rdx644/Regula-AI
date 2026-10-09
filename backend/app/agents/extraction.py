import json
from typing import Any, Dict, List, Literal, TypedDict
from uuid import UUID

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.agents.schemas import (
    ObligationExtraction,
    ObligationExtractionBatch,
    AgentStepInput,
    AgentStepOutput,
)
from app.core.ai_provider import get_llm_chain, ModelConfig
from app.core.retrieval import HybridRetriever
from app.db import base as registered_models  # Ensure relationship targets are registered for agent-only runs.
from app.services.parser import ParsedDocument, DocumentChunk
from app.db.session import SessionLocal
from app.models.regulation import RegulatoryVersion
from app.models.obligation import RegulatoryObligation


class ExtractionState(TypedDict):
    version_id: UUID
    organization_id: UUID
    document_text: str
    chunks: List[DocumentChunk]
    extracted_obligations: List[ObligationExtraction]
    current_chunk_index: int
    errors: List[str]
    tokens_used: int
    model_used: str
    provider: str


EXTRACTION_PROMPT = """You are a regulatory compliance expert extracting structured obligations from regulatory documents.

Given a chunk of regulatory text, extract ALL discrete obligations. Each obligation must be a specific, actionable requirement.

For each obligation, provide:
1. obligation_text: The full obligation text as it appears (or close paraphrase)
2. actor: Who must comply (e.g., "bank", "financial institution", "covered entity")
3. requirement: What specific action is required
4. condition: Under what circumstances (if conditional)
5. frequency: How often (e.g., "quarterly", "annual", "ongoing", "within 30 days")
6. effective_date: When it takes effect (ISO format if mentioned)
7. source_section: Section/clause reference (e.g., "Section 4.2", "Article 12")
8. source_page: Page number if available
9. source_text_snippet: Exact quote from the text (max 500 chars)
10. confidence: Your confidence 0.0-1.0
11. reasoning: Brief explanation of why this is an obligation

Rules:
- Only extract explicit obligations, not guidance or best practices
- Each obligation must be independently testable
- Preserve exact regulatory language where possible
- If uncertain, set confidence < 0.7 and note in reasoning
- Return empty list if no obligations found in chunk

Document context: {document_context}

Text chunk (page {page}, section: {section}):
{chunk_text}

Return JSON matching the ObligationExtractionBatch schema."""


async def _complete_obligation_batch(
    chunk: DocumentChunk,
    document_context: str,
) -> Any:
    llm_chain, config = get_llm_chain("extraction")

    prompt = EXTRACTION_PROMPT.format(
        document_context=document_context,
        page=chunk.page_number,
        section=chunk.section or "unknown",
        chunk_text=chunk.text,
    )

    messages = [
        {"role": "system", "content": "You are a regulatory compliance expert. Extract obligations precisely."},
        {"role": "user", "content": prompt},
    ]

    return await llm_chain.complete(messages, ObligationExtractionBatch, config)


async def extract_obligations_from_chunk(
    chunk: DocumentChunk,
    document_context: str,
) -> List[ObligationExtraction]:
    response = await _complete_obligation_batch(chunk, document_context)
    return response.content.obligations


async def process_chunk(state: ExtractionState) -> ExtractionState:
    idx = state["current_chunk_index"]
    if idx >= len(state["chunks"]):
        return state

    chunk = state["chunks"][idx]
    document_context = f"Regulatory document version {state['version_id']}"

    try:
        response = await _complete_obligation_batch(chunk, document_context)
        obligations = response.content.obligations

        for obl in obligations:
            if not obl.source_text_snippet or obl.source_text_snippet not in chunk.text:
                raise ValueError("Extraction citation is not an exact source span")
            obl.source_page = chunk.page_number
            obl.source_section = chunk.section or obl.source_section

        state["extracted_obligations"].extend(obligations)
        state["tokens_used"] += getattr(response, "tokens_used", 0) or 0
        state["model_used"] = (
            getattr(response, "model_used", None)
            or getattr(response, "model", None)
            or state["model_used"]
        )
        provider = getattr(response, "provider", None)
        state["provider"] = getattr(provider, "value", provider) or state["provider"]

    except Exception as e:
        state["errors"].append(f"Chunk {idx} failed ({type(e).__name__})")

    state["current_chunk_index"] = idx + 1
    return state


async def persist_obligations(state: ExtractionState) -> ExtractionState:
    db = SessionLocal()
    try:
        version = db.query(RegulatoryVersion).filter(
            RegulatoryVersion.id == state["version_id"]
        ).first()

        if not version:
            state["errors"].append(f"Version {state['version_id']} not found")
            return state

        for obl_data in state["extracted_obligations"]:
            if db.query(RegulatoryObligation).filter(RegulatoryObligation.organization_id == state["organization_id"], RegulatoryObligation.version_id == state["version_id"], RegulatoryObligation.obligation_text == obl_data.obligation_text).first():
                continue
            obligation = RegulatoryObligation(
                organization_id=state["organization_id"],
                version_id=state["version_id"],
                obligation_text=obl_data.obligation_text,
                actor=obl_data.actor,
                requirement=obl_data.requirement,
                condition=obl_data.condition,
                frequency=obl_data.frequency,
                effective_date=obl_data.effective_date,
                source_section=obl_data.source_section,
                source_page=obl_data.source_page,
                source_text_snippet=obl_data.source_text_snippet,
                confidence=obl_data.confidence,
                extraction_model=state["model_used"],
                status="pending_review",
            )
            db.add(obligation)

        version.status = "processed"
        db.commit()

    except Exception as e:
        db.rollback()
        state["errors"].append(f"Persistence failed ({type(e).__name__})")
    finally:
        db.close()

    return state


def should_continue(state: ExtractionState) -> Literal["process_chunk", "persist_obligations"]:
    if state["current_chunk_index"] < len(state["chunks"]):
        return "process_chunk"
    return "persist_obligations"


def build_extraction_graph() -> StateGraph:
    workflow = StateGraph(ExtractionState)

    workflow.add_node("process_chunk", process_chunk)
    workflow.add_node("persist_obligations", persist_obligations)

    workflow.set_entry_point("process_chunk")

    workflow.add_conditional_edges(
        "process_chunk",
        should_continue,
        {
            "process_chunk": "process_chunk",
            "persist_obligations": "persist_obligations",
        },
    )

    workflow.add_edge("persist_obligations", END)

    return workflow.compile()


extraction_graph = build_extraction_graph()


async def run_obligation_extraction(
    version_id: UUID,
    organization_id: UUID,
    document_text: str,
    chunks: List[DocumentChunk],
) -> AgentStepOutput:
    initial_state = ExtractionState(
        version_id=version_id,
        organization_id=organization_id,
        document_text=document_text,
        chunks=chunks,
        extracted_obligations=[],
        current_chunk_index=0,
        errors=[],
        tokens_used=0,
        model_used="",
        provider="",
    )

    try:
        config = {"configurable": {"thread_id": f"extraction-{version_id}"}}
        final_state = await extraction_graph.ainvoke(initial_state, config)

        return AgentStepOutput(
            success=len(final_state["errors"]) == 0,
            result={
                "obligations_extracted": len(final_state["extracted_obligations"]),
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
