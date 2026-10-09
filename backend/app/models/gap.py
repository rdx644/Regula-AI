import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, Float, Integer, ForeignKey, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Gap(Base):
    """
    A compliance gap identified between an obligation and its controls/evidence.
    """
    __tablename__ = "gaps"

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
        nullable=True,
        index=True,
    )
    control_id = Column(
        UUID(as_uuid=True),
        ForeignKey("controls.id"),
        nullable=True,
        index=True,
    )
    gap_type = Column(String(64), nullable=False)
    # no_control | partial_control | no_evidence | stale_evidence | test_failure | unmapped
    description = Column(Text, nullable=True)
    severity = Column(String(32), nullable=True)      # critical | high | medium | low
    status = Column(String(32), nullable=False, default="open")
    # open | in_remediation | closed | accepted | deferred

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    obligation = relationship("RegulatoryObligation")
    control = relationship("Control")
    risk_assessment = relationship("RiskAssessment", back_populates="gap", uselist=False)
    remediation_plan = relationship("RemediationPlan", back_populates="gap", uselist=False)


class RiskAssessment(Base):
    """
    Deterministic risk score for a gap (Section 8.8 of the implementation plan).
    """
    __tablename__ = "risk_assessments"
    __table_args__ = (UniqueConstraint("gap_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gap_id = Column(
        UUID(as_uuid=True),
        ForeignKey("gaps.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    likelihood = Column(Float, nullable=True)          # 0.0 – 1.0
    impact = Column(Float, nullable=True)              # 0.0 – 1.0
    risk_score = Column(Float, nullable=True)           # composite
    risk_level = Column(String(32), nullable=True, index=True)  # critical | high | medium | low
    reasoning = Column(Text, nullable=True)
    assessed_at = Column(DateTime(timezone=True), server_default=func.now())

    gap = relationship("Gap", back_populates="risk_assessment")


class RemediationPlan(Base):
    """
    Recommended remediation actions for a gap.
    """
    __tablename__ = "remediation_plans"
    __table_args__ = (UniqueConstraint("gap_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    gap_id = Column(
        UUID(as_uuid=True),
        ForeignKey("gaps.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    recommendation = Column(Text, nullable=True)
    priority = Column(String(32), nullable=True)        # immediate | short_term | medium_term | long_term
    estimated_effort = Column(String(128), nullable=True)
    assigned_to = Column(String(256), nullable=True)
    status = Column(String(32), nullable=False, default="proposed")
    # proposed | approved | in_progress | completed | rejected
    due_date = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    gap = relationship("Gap", back_populates="remediation_plan")
