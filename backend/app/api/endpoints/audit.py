from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api import deps
from app.core.rbac import Permission
from app.models.audit_log import AuditLog, AgentRun, AgentStep, ToolCall
from app.models.user import User
from app.schemas.audit import (
    AuditLogResponse,
    AgentRunResponse,
    AgentStepResponse,
    ToolCallResponse,
)

router = APIRouter()


@router.get("/logs", response_model=List[AuditLogResponse])
def list_audit_logs(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List immutable audit logs for an organization.
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.AUDIT_READ
    )

    query = db.query(AuditLog).filter(AuditLog.organization_id == organization_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)

    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()


@router.get("/agent-runs", response_model=List[AgentRunResponse])
def list_agent_runs(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    workflow_type: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List agent workflow executions (agent runs).
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.AUDIT_READ
    )

    query = (
        db.query(AgentRun)
        .options(joinedload(AgentRun.steps).joinedload(AgentStep.tool_calls))
        .filter(AgentRun.organization_id == organization_id)
    )
    if workflow_type:
        query = query.filter(AgentRun.workflow_type == workflow_type)
    if status_filter:
        query = query.filter(AgentRun.status == status_filter)

    return query.order_by(AgentRun.started_at.desc()).limit(limit).all()


@router.get("/agent-runs/{run_id}", response_model=AgentRunResponse)
def get_agent_run(
    *,
    db: Session = Depends(deps.get_db),
    run_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get full execution trace of an agent run including steps and tool calls.
    """
    run = (
        db.query(AgentRun)
        .options(joinedload(AgentRun.steps).joinedload(AgentStep.tool_calls))
        .filter(AgentRun.id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")

    deps.verify_membership(
        db, current_user, run.organization_id, required_permission=Permission.AUDIT_READ
    )
    return run
