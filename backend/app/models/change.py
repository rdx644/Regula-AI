import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, Float, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class RegulatoryChange(Base):
    """
    A detected change between two versions of a regulatory document (Phase 11).
    """
    __tablename__ = "regulatory_changes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_documents.id"),
        nullable=False,
        index=True,
    )
    old_version_id = Column(UUID(as_uuid=True), ForeignKey("regulatory_versions.id"), nullable=True)
    new_version_id = Column(UUID(as_uuid=True), ForeignKey("regulatory_versions.id"), nullable=False)
    change_type = Column(String(64), nullable=False)
    # added | modified | removed | clarification | tightening | relaxation
    summary = Column(Text, nullable=True)
    affected_obligations = Column(Text, nullable=True)   # JSON list of obligation IDs
    severity = Column(String(32), nullable=True)          # critical | high | medium | low
    status = Column(String(32), nullable=False, default="detected")
    # detected | analyzed | reviewed | acknowledged

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    document = relationship("RegulatoryDocument")


class ImpactAssessment(Base):
    """
    Autonomous impact assessment of a regulatory change on the bank (Phase 12).
    """
    __tablename__ = "impact_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    change_id = Column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_changes.id"),
        nullable=False,
        index=True,
    )
    affected_controls = Column(Text, nullable=True)     # JSON list
    affected_policies = Column(Text, nullable=True)     # JSON list
    new_gaps_identified = Column(Text, nullable=True)   # JSON list
    risk_delta = Column(Float, nullable=True)
    recommendation = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    status = Column(String(32), nullable=False, default="draft")
    # draft | reviewed | approved

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    change = relationship("RegulatoryChange")


class Simulation(Base):
    """
    What-if simulation for regulatory scenarios (Phase 13).
    """
    __tablename__ = "simulations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    name = Column(String(256), nullable=False)
    scenario_description = Column(Text, nullable=True)
    parameters = Column(Text, nullable=True)             # JSON
    results = Column(Text, nullable=True)                 # JSON
    affected_obligations = Column(Text, nullable=True)    # JSON
    affected_controls = Column(Text, nullable=True)       # JSON
    projected_gaps = Column(Text, nullable=True)          # JSON
    status = Column(String(32), nullable=False, default="created")
    # created | running | completed | failed

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
