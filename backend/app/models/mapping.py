import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, Float, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class RegulationControlMapping(Base):
    """
    Maps a regulatory obligation to an internal control.
    Tracks semantic similarity, LLM reasoning confidence, and approval state
    as specified in Section 8.6 of the implementation plan.
    """
    __tablename__ = "regulation_control_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    obligation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_obligations.id"),
        nullable=False,
        index=True,
    )
    control_id = Column(
        UUID(as_uuid=True),
        ForeignKey("controls.id"),
        nullable=False,
        index=True,
    )
    mapping_status = Column(String(32), nullable=False, default="mapped")
    # mapped | partially_mapped | unmapped | conflicting | human_review
    confidence = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)        # LLM reasoning trace
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    obligation = relationship("RegulatoryObligation")
    control = relationship("Control")
