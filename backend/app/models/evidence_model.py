import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, Float, ForeignKey, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Evidence(Base):
    """
    Evidence uploaded or linked to a specific control.
    Follows Section 8.7 validation requirements.
    """
    __tablename__ = "evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    control_id = Column(
        UUID(as_uuid=True),
        ForeignKey("controls.id"),
        nullable=False,
        index=True,
    )
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    file_reference = Column(String(1024), nullable=True)
    evidence_date = Column(DateTime(timezone=True), nullable=True)
    coverage_start = Column(DateTime(timezone=True), nullable=True)
    coverage_end = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="pending_review")
    validation_result = Column(Text, nullable=True)
    review_notes = Column(Text, nullable=True)
    # pending_review | valid | invalid | expired | insufficient

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    control = relationship("Control")


class ControlTest(Base):
    """
    A test executed against a control to assess its effectiveness.
    """
    __tablename__ = "control_tests"

    execution_id = Column(String(64), nullable=True)
    proposed_result = Column(Text, nullable=True)
    review_status = Column(String(32), nullable=False, default="manual", server_default="manual")
    __table_args__ = (UniqueConstraint("execution_id", name="uq_control_tests_execution_id"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    control_id = Column(
        UUID(as_uuid=True),
        ForeignKey("controls.id"),
        nullable=False,
        index=True,
    )
    test_type = Column(String(64), nullable=True)       # automated | manual | hybrid
    description = Column(Text, nullable=True)
    result = Column(String(32), nullable=True)           # pass | fail | partial | inconclusive
    effectiveness_score = Column(Float, nullable=True)   # 0.0 â€“ 1.0
    findings = Column(Text, nullable=True)
    tested_at = Column(DateTime(timezone=True), nullable=True)
    tester = Column(String(256), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    control = relationship("Control")
