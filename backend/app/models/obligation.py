import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, Float, Integer, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class RegulatoryObligation(Base):
    """
    A single regulatory obligation extracted from a RegulatoryVersion.
    Preserves full source provenance (document, section, page, confidence).
    """
    __tablename__ = "regulatory_obligations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_versions.id"),
        nullable=False,
        index=True,
    )
    applicability = Column(String(32), nullable=False, server_default="uncertain")
    obligation_text = Column(Text, nullable=False)
    actor = Column(String(256), nullable=True)          # who must comply
    requirement = Column(Text, nullable=True)            # what must be done
    condition = Column(Text, nullable=True)              # under what circumstances
    frequency = Column(String(128), nullable=True)       # e.g. "quarterly", "ongoing"
    effective_date = Column(DateTime(timezone=True), nullable=True)

    # Source provenance (critical for D2 reliability)
    source_section = Column(String(256), nullable=True)
    source_page = Column(Integer, nullable=True)
    source_text_snippet = Column(Text, nullable=True)    # exact quoted text

    # AI metadata
    confidence = Column(Float, nullable=True, default=0.0)
    extraction_model = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="pending_review")
    # pending_review | approved | rejected | merged

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization")
    version = relationship("RegulatoryVersion")
