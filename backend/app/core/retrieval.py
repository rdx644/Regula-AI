from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from app.models.regulation import RegulatoryVersion
from app.models.obligation import RegulatoryObligation
from app.models.control import Control
from app.models.evidence_model import Evidence
from app.core.ai_provider import get_llm_chain, ModelConfig


@dataclass
class RetrievalResult:
    id: UUID
    content: str
    source_type: str
    source_id: UUID
    metadata: dict
    score: float


@dataclass
class RetrievalContext:
    results: List[RetrievalResult]
    query: str
    organization_id: UUID


class BaseRetriever(ABC):
    @abstractmethod
    def retrieve(
        self,
        query: str,
        organization_id: UUID,
        limit: int = 10,
        filters: Optional[dict] = None,
    ) -> List[RetrievalResult]:
        pass


class VectorRetriever(BaseRetriever):
    def __init__(self, db: Session, embedding_model: str = "text-embedding-3-small"):
        self.db = db
        self.embedding_model = embedding_model
        self._embed_cache = {}

    def _get_embedding(self, text: str) -> List[float]:
        from app.core.config import settings
        if not settings.MODEL_EXECUTION_ENABLED:
            raise RuntimeError('Model execution is disabled pending owner budget approval')
        if text in self._embed_cache:
            return self._embed_cache[text]

        from openai import OpenAI
        with OpenAI(api_key=settings.OPENAI_API_KEY) as client:
            response = client.embeddings.create(model=self.embedding_model, input=text)
        embedding = response.data[0].embedding
        self._embed_cache[text] = embedding
        return embedding

    def retrieve(
        self,
        query: str,
        organization_id: UUID,
        limit: int = 10,
        filters: Optional[dict] = None,
    ) -> List[RetrievalResult]:
        # Embeddings currently belong to whole versions, not obligations. Do not
        # spend on a query when this tenant has no embedded source versions.
        from app.core.config import settings
        if not settings.MODEL_EXECUTION_ENABLED:
            return []
        if not self.db.query(RegulatoryObligation.id).join(RegulatoryVersion).filter(
            RegulatoryObligation.organization_id == organization_id, RegulatoryVersion.embedding.is_not(None)).first():
            return []
        query_embedding = self._get_embedding(query)

        stmt = (
            select(
                RegulatoryObligation.id,
                RegulatoryObligation.obligation_text,
                RegulatoryObligation.source_section,
                RegulatoryObligation.source_page,
                RegulatoryObligation.confidence,
                RegulatoryObligation.version_id,
                (RegulatoryVersion.embedding.cosine_distance(query_embedding)).label("distance"),
            )
            .join(RegulatoryVersion, RegulatoryVersion.id == RegulatoryObligation.version_id)
            .where(RegulatoryObligation.organization_id == organization_id)
            .where(RegulatoryVersion.embedding.is_not(None))
        )

        if filters:
            if "version_id" in filters:
                stmt = stmt.where(RegulatoryObligation.version_id == filters["version_id"])
            if "status" in filters:
                stmt = stmt.where(RegulatoryObligation.status == filters["status"])

        stmt = stmt.order_by(text("distance")).limit(limit)

        results = self.db.execute(stmt).fetchall()

        return [
            RetrievalResult(
                id=row.id,
                content=row.obligation_text,
                source_type="obligation",
                source_id=row.id,
                metadata={
                    "source_section": row.source_section,
                    "source_page": row.source_page,
                    "confidence": row.confidence,
                    "version_id": str(row.version_id),
                },
                score=1.0 - row.distance,
            )
            for row in results
        ]


class KeywordRetriever(BaseRetriever):
    def __init__(self, db: Session):
        self.db = db

    def retrieve(
        self,
        query: str,
        organization_id: UUID,
        limit: int = 10,
        filters: Optional[dict] = None,
    ) -> List[RetrievalResult]:
        terms = query.lower().split()

        conditions = []
        for term in terms:
            conditions.append(
                func.to_tsvector("english", RegulatoryObligation.obligation_text).match(term)
            )

        stmt = (
            select(
                RegulatoryObligation.id,
                RegulatoryObligation.obligation_text,
                RegulatoryObligation.source_section,
                RegulatoryObligation.source_page,
                RegulatoryObligation.confidence,
                RegulatoryObligation.version_id,
            )
            .where(RegulatoryObligation.organization_id == organization_id)
            .where(func.to_tsvector("english", RegulatoryObligation.obligation_text).op('@@')(func.plainto_tsquery('english', query)))
        )

        if filters:
            if "version_id" in filters:
                stmt = stmt.where(RegulatoryObligation.version_id == filters["version_id"])
            if "status" in filters:
                stmt = stmt.where(RegulatoryObligation.status == filters["status"])

        stmt = stmt.limit(limit)

        results = self.db.execute(stmt).fetchall()

        return [
            RetrievalResult(
                id=row.id,
                content=row.obligation_text,
                source_type="obligation",
                source_id=row.id,
                metadata={
                    "source_section": row.source_section,
                    "source_page": row.source_page,
                    "confidence": row.confidence,
                    "version_id": str(row.version_id),
                },
                score=1.0,
            )
            for row in results
        ]


class MetadataRetriever(BaseRetriever):
    def __init__(self, db: Session):
        self.db = db

    def retrieve(
        self,
        query: str,
        organization_id: UUID,
        limit: int = 10,
        filters: Optional[dict] = None,
    ) -> List[RetrievalResult]:
        stmt = (
            select(
                RegulatoryObligation.id,
                RegulatoryObligation.obligation_text,
                RegulatoryObligation.source_section,
                RegulatoryObligation.source_page,
                RegulatoryObligation.confidence,
                RegulatoryObligation.version_id,
            )
            .where(RegulatoryObligation.organization_id == organization_id)
        )

        if filters:
            if "version_id" in filters:
                stmt = stmt.where(RegulatoryObligation.version_id == filters["version_id"])
            if "status" in filters:
                stmt = stmt.where(RegulatoryObligation.status == filters["status"])
            if "actor" in filters:
                stmt = stmt.where(RegulatoryObligation.actor.ilike(f"%{filters['actor']}%"))

        stmt = stmt.order_by(RegulatoryObligation.created_at.desc()).limit(limit)

        results = self.db.execute(stmt).fetchall()

        return [
            RetrievalResult(
                id=row.id,
                content=row.obligation_text,
                source_type="obligation",
                source_id=row.id,
                metadata={
                    "source_section": row.source_section,
                    "source_page": row.source_page,
                    "confidence": row.confidence,
                    "version_id": str(row.version_id),
                },
                score=0.5,
            )
            for row in results
        ]


class RelationshipRetriever(BaseRetriever):
    def __init__(self, db: Session):
        self.db = db

    def retrieve(
        self,
        query: str,
        organization_id: UUID,
        limit: int = 10,
        filters: Optional[dict] = None,
    ) -> List[RetrievalResult]:
        from app.models.mapping import RegulationControlMapping
        from app.models.control import Control

        stmt = (
            select(
                RegulatoryObligation.id,
                RegulatoryObligation.obligation_text,
                RegulatoryObligation.source_section,
                RegulatoryObligation.source_page,
                RegulatoryObligation.confidence,
                RegulatoryObligation.version_id,
                Control.id.label("control_id"),
                Control.control_id_code,
                Control.objective,
            )
            .join(RegulationControlMapping, RegulationControlMapping.obligation_id == RegulatoryObligation.id)
            .join(Control, Control.id == RegulationControlMapping.control_id)
            .where(RegulatoryObligation.organization_id == organization_id)
            .where(Control.organization_id == organization_id)
        )

        if filters:
            if "version_id" in filters:
                stmt = stmt.where(RegulatoryObligation.version_id == filters["version_id"])
            if "control_id" in filters:
                stmt = stmt.where(Control.id == filters["control_id"])

        stmt = stmt.limit(limit)

        results = self.db.execute(stmt).fetchall()

        return [
            RetrievalResult(
                id=row.id,
                content=row.obligation_text,
                source_type="obligation_with_control",
                source_id=row.id,
                metadata={
                    "source_section": row.source_section,
                    "source_page": row.source_page,
                    "confidence": row.confidence,
                    "version_id": str(row.version_id),
                    "control_id": str(row.control_id),
                    "control_code": row.control_id_code,
                    "control_objective": row.objective,
                },
                score=0.8,
            )
            for row in results
        ]


class Reranker:
    def __init__(self):
        pass

    def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int = 10,
    ) -> List[RetrievalResult]:
        return sorted(results, key=lambda r: r.score, reverse=True)[:top_k]


class HybridRetriever:
    def __init__(self, db: Session):
        self.db = db
        self.vector_retriever = VectorRetriever(db)
        self.keyword_retriever = KeywordRetriever(db)
        self.metadata_retriever = MetadataRetriever(db)
        self.relationship_retriever = RelationshipRetriever(db)
        self.reranker = Reranker()

    def retrieve(
        self,
        query: str,
        organization_id: UUID,
        limit: int = 10,
        filters: Optional[dict] = None,
    ) -> RetrievalContext:
        all_results = []

        vector_results = self.vector_retriever.retrieve(query, organization_id, limit, filters)
        all_results.extend(vector_results)

        keyword_results = self.keyword_retriever.retrieve(query, organization_id, limit, filters)
        all_results.extend(keyword_results)

        metadata_results = self.metadata_retriever.retrieve(query, organization_id, limit, filters)
        all_results.extend(metadata_results)

        relationship_results = self.relationship_retriever.retrieve(query, organization_id, limit, filters)
        all_results.extend(relationship_results)

        seen = set()
        deduped = []
        for r in all_results:
            key = (r.source_type, r.source_id)
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        reranked = self.reranker.rerank(query, deduped, top_k=limit)

        return RetrievalContext(
            results=reranked,
            query=query,
            organization_id=organization_id,
        )

    def retrieve_obligations_for_mapping(
        self,
        control: Control,
        organization_id: UUID,
        limit: int = 20,
    ) -> RetrievalContext:
        query = f"{control.objective} {control.description} {control.evidence_requirement}"
        filters = {"status": "approved"}
        return self.retrieve(query, organization_id, limit, filters)

    def retrieve_controls_for_obligation(
        self,
        obligation: RegulatoryObligation,
        organization_id: UUID,
        limit: int = 20,
    ) -> RetrievalContext:
        query = f"{obligation.actor} {obligation.requirement} {obligation.condition}"
        filters = {"status": "active"}
        return self.retrieve(query, organization_id, limit, filters)
