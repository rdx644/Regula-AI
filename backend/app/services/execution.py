"""Durable job traces and a tenant scope for all agent database sessions."""
import contextvars
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.orm import Session, with_loader_criteria

tenant_context = contextvars.ContextVar("agent_tenant", default=None)
actor_context = contextvars.ContextVar("actor", default=None)
job_context = contextvars.ContextVar("job", default=None)
step_context = contextvars.ContextVar("step", default=None)
usage_context = contextvars.ContextVar("model_usage", default=None)


def job_permission(job_type):
    from app.core.rbac import Permission
    return {
        "regulation_process": Permission.REGULATION_UPDATE,
        "obligation_extraction": Permission.OBLIGATION_CREATE,
        "policy_process": Permission.CONTROL_UPDATE,
        "control_extraction": Permission.CONTROL_CREATE,
        "mapping": Permission.MAPPING_CREATE,
        "evidence_validation": Permission.EVIDENCE_VALIDATE,
        "control_testing": Permission.EVIDENCE_VALIDATE,
        "gap_identification": Permission.GAP_CREATE,
        "remediation": Permission.REMEDIATION_CREATE,
        "change_detection": Permission.REGULATION_UPDATE,
        "impact_analysis": Permission.REGULATION_UPDATE,
        "simulation": Permission.REGULATION_UPDATE,
    }.get(job_type, Permission.AGENT_RUN)


@event.listens_for(Session, "do_orm_execute")
def scope_agent_queries(state):
    tenant = tenant_context.get()
    if tenant is None or not state.is_select:
        return
    from app.db.base_class import Base
    for mapper in Base.registry.mappers:
        model = mapper.class_
        if hasattr(model, "organization_id"):
            state.statement = state.statement.options(
                with_loader_criteria(model, model.organization_id == tenant, include_aliases=True)
            )


async def execute_job(handler, job):
    from app.db.session import SessionLocal
    from app.models.audit_log import AgentRun, AgentStep, AuditLog
    from app.models.organization_member import OrganizationMember
    from app.core.rbac import has_permission, Permission
    tenant = tenant_context.set(UUID(job.organization_id))
    actor = actor_context.set(UUID(job.user_id) if job.user_id else None)
    current_job = job_context.set(job.id)
    db = SessionLocal()
    lock_connection = None
    try:
        # Only PostgreSQL holds this distributed execution lock. Never replace
        # production integration with a process-local lock.
        lock_connection = db.get_bind().connect()
        locked = lock_connection.execute(text("SELECT pg_try_advisory_lock(hashtextextended(:key, 0))"), {"key": job.id}).scalar()
        if not locked:
            raise RuntimeError("Another worker owns this execution")
        if job.user_id:
            member = db.query(OrganizationMember).filter(
                OrganizationMember.organization_id == UUID(job.organization_id),
                OrganizationMember.user_id == UUID(job.user_id),
            ).first()
            if not member or not has_permission(member.role, job_permission(job.type)):
                raise PermissionError("Job actor no longer has execution permission")
        run = db.get(AgentRun, UUID(job.id))
        if run and run.status == "completed":
            step = db.query(AgentStep).filter(AgentStep.run_id == run.id).order_by(AgentStep.step_order.desc()).first()
            return json.loads(step.output_data)
        if run is None:
            run = AgentRun(id=UUID(job.id), organization_id=UUID(job.organization_id),
                           triggered_by=UUID(job.user_id) if job.user_id else None, workflow_type=job.type)
            db.add(run)
        run.status = "running"
        step = AgentStep(run_id=run.id, agent_name=job.type, step_order=job.retry_count + 1,
                         input_data=json.dumps({"job_id": job.id, "prompt_version": "2026-10-v2"}))
        db.add(step)
        db.commit()
        current_step = step_context.set(step.id)
        usage = []
        current_usage = usage_context.set(usage)
        try:
            result = await handler.handle(job)
            if usage:
                result["tokens_used"] = sum(call["tokens"] for call in usage)
                result["model_calls"] = usage
            success = result.get("status") not in {"failed", "error"}
            run.status = "completed" if success else "failed"
            step.status = run.status
            step.output_data = json.dumps(result, default=str)
            step.token_usage = result.get("tokens_used", 0)
            run.finished_at = step.finished_at = datetime.now(timezone.utc)
            db.add(AuditLog(organization_id=UUID(job.organization_id), user_id=run.triggered_by,
                            action="agent_" + run.status, entity_type="agent_run", entity_id=run.id,
                            details=json.dumps({"job_id": job.id, "operation": job.type, "attempt": step.step_order})))
            db.commit()
            return result
        except BaseException as exc:
            db.rollback()
            run.status = step.status = "failed"
            run.error_message = type(exc).__name__
            run.finished_at = step.finished_at = datetime.now(timezone.utc)
            db.commit()
            raise
        finally:
            usage_context.reset(current_usage)
            step_context.reset(current_step)
    finally:
        if lock_connection is not None:
            lock_connection.execute(text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"), {"key": job.id})
            lock_connection.close()
        db.close()
        tenant_context.reset(tenant)
        actor_context.reset(actor)
        job_context.reset(current_job)
