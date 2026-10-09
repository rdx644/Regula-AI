import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, Float, Integer, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class AgentRun(Base):
    """
    A single execution run of an agentic workflow (Supervisor → agents → tools).
    """
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    triggered_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    workflow_type = Column(String(128), nullable=False)
    # obligation_extraction | mapping | gap_analysis | impact_analysis | simulation | investigation
    status = Column(String(32), nullable=False, default="running")
    # running | completed | failed | cancelled
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    organization = relationship("Organization")
    steps = relationship("AgentStep", back_populates="run", cascade="all, delete-orphan")


class AgentStep(Base):
    """
    A single step within an AgentRun (e.g. one agent invocation).
    """
    __tablename__ = "agent_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name = Column(String(128), nullable=False)
    step_order = Column(Integer, nullable=False)
    input_data = Column(Text, nullable=True)        # JSON
    output_data = Column(Text, nullable=True)       # JSON
    status = Column(String(32), nullable=False, default="running")
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    token_usage = Column(Integer, nullable=True)

    run = relationship("AgentRun", back_populates="steps")
    tool_calls = relationship("ToolCall", back_populates="step", cascade="all, delete-orphan")


class ToolCall(Base):
    """
    A single tool invocation within an AgentStep.
    """
    __tablename__ = "tool_calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    step_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_steps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name = Column(String(256), nullable=False)
    input_args = Column(Text, nullable=True)        # JSON
    output_result = Column(Text, nullable=True)     # JSON
    duration_ms = Column(Integer, nullable=True)

    step = relationship("AgentStep", back_populates="tool_calls")


class AuditLog(Base):
    """
    Immutable audit log for all significant platform actions.
    """
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(256), nullable=False, index=True)
    entity_type = Column(String(128), nullable=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(Text, nullable=True)           # JSON
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization")
