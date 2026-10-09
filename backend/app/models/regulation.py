import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, Integer, ForeignKey, Enum, Index, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from pgvector.sqlalchemy import Vector
import enum


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class RegulatoryDocument(Base):
    """
    A top-level regulatory document (e.g. Basel III, GDPR, RBI Master Direction).
    Every document is scoped to an organization for multi-tenancy.
    """
    __tablename__ = "regulatory_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    title = Column(String(512), nullable=False, index=True)
    source = Column(String(512), nullable=True)          # e.g. "RBI", "SEBI", "OCC"
    jurisdiction = Column(String(128), nullable=True)     # e.g. "IN", "US", "EU"
    document_type = Column(String(128), nullable=True)    # e.g. "Circular", "Guideline"
    description = Column(Text, nullable=True)
    status = Column(
        String(32),
        nullable=False,
        default=DocumentStatus.UPLOADED.value,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization")
    versions = relationship(
        "RegulatoryVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="RegulatoryVersion.version_number.desc()",
    )


class RegulatoryVersion(Base):
    """
    A specific version / amendment of a regulatory document.
    Tracks the file reference, effective date, and processing status independently
    so that regulatory-change diffing (Phase 11) can compare versions.
    """
    __tablename__ = "regulatory_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_documents.id"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False, default=1)
    effective_date = Column(DateTime(timezone=True), nullable=True)
    file_reference = Column(String(1024), nullable=True)   # path / URL / S3 key
    source_pages = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)                  # extracted plain text
    embedding = Column(Vector(1536), nullable=True)         # pgvector for semantic search
    job_id = Column(String(64), nullable=True)              # async job tracking
    status = Column(
        String(32),
        nullable=False,
        default=DocumentStatus.UPLOADED.value,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    document = relationship("RegulatoryDocument", back_populates="versions")


Index(
    "ix_regulatory_versions_embedding",
    RegulatoryVersion.embedding,
    postgresql_using="hnsw",
    postgresql_ops={"embedding": "vector_cosine_ops"},
    postgresql_with={"m": 16, "ef_construction": 64},
)
