"""Shared tenant ownership, review transitions, deterministic risk and audit rules."""
import json
import hashlib
from uuid import UUID

from fastapi import HTTPException
from app.models.audit_log import AuditLog


def owned(db, model, record_id, organization_id):
    record = db.query(model).filter(model.id == record_id, model.organization_id == organization_id).first()
    if not record:
        raise HTTPException(404, "Resource not found")
    return record


def audit(db, organization_id, user_id, action, entity_type, entity_id, **details):
    # Keep source text, credentials and prompts out of the audit stream.
    db.add(AuditLog(organization_id=organization_id, user_id=user_id, action=action,
                    entity_type=entity_type, entity_id=entity_id,
                    details=json.dumps(details, default=str)))


def risk(likelihood, impact):
    likelihood = 0.5 if likelihood is None else likelihood
    impact = 0.5 if impact is None else impact
    score = round(likelihood * impact * 100, 2)
    level = "critical" if score >= 80 else "high" if score >= 45 else "medium" if score >= 20 else "low"
    return likelihood, impact, score, level


def input_fingerprint(*values):
    """Stable input revision for queue deduplication; never includes outputs."""
    return hashlib.sha256(json.dumps(values, default=str, sort_keys=True).encode()).hexdigest()
