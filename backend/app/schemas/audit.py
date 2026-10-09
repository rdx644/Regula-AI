from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel


class ToolCallResponse(BaseModel):
    id: UUID
    step_id: UUID
    tool_name: str
    input_args: Optional[str] = None
    output_result: Optional[str] = None
    duration_ms: Optional[int] = None

    class Config:
        from_attributes = True


class AgentStepResponse(BaseModel):
    id: UUID
    run_id: UUID
    agent_name: str
    step_order: int
    input_data: Optional[str] = None
    output_data: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    token_usage: Optional[int] = None
    tool_calls: List[ToolCallResponse] = []

    class Config:
        from_attributes = True


class AgentRunResponse(BaseModel):
    id: UUID
    organization_id: UUID
    triggered_by: Optional[UUID] = None
    workflow_type: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    steps: List[AgentStepResponse] = []

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: UUID
    organization_id: UUID
    user_id: Optional[UUID] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
