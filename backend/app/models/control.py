import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Policy(Base):
    """
    An internal bank policy document.
    """
    __tablename__ = "policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    title = Column(String(512), nullable=False, index=True)
    description = Column(Text, nullable=True)
    owner = Column(String(256), nullable=True)
    file_reference = Column(String(1024), nullable=True)
    raw_text = Column(Text, nullable=True)                  # extracted plain text
    status = Column(String(32), nullable=False, default="active")
    # active | archived | draft | parsed | processing | processed | failed

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    controls = relationship("Control", back_populates="policy")


class Control(Base):
    """
    An internal control tied to a policy.
    Matches the schema from Section 8.5 of the implementation plan.
    """
    __tablename__ = "controls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    policy_id = Column(
        UUID(as_uuid=True),
        ForeignKey("policies.id"),
        nullable=True,
        index=True,
    )
    control_id_code = Column(String(64), nullable=True, index=True)  # e.g. "CTL-042"
    objective = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    owner = Column(String(256), nullable=True)
    frequency = Column(String(128), nullable=True)       # e.g. "daily", "quarterly"
    procedure = Column(Text, nullable=True)
    evidence_requirement = Column(Text, nullable=True)
    business_unit = Column(String(256), nullable=True)
    source_page = Column(String(32), nullable=True)
    source_section = Column(String(256), nullable=True)
    source_text_snippet = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="pending_review")
    # pending_review | approved | rejected | active | archived | draft | under_review

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    policy = relationship("Policy", back_populates="controls")
