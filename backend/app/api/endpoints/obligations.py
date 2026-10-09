from typing import Any, List, Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.services.governance import audit
from app.core.rbac import Permission
from app.models.obligation import RegulatoryObligation
from app.models.regulation import RegulatoryVersion, RegulatoryDocument
from app.models.user import User
from app.schemas.obligation import (
    ObligationCreate,
    ObligationUpdate,
    ObligationResponse,
    ObligationApprove,
    ObligationBulkAction,
)

router = APIRouter()


@router.post("/", response_model=ObligationResponse, status_code=status.HTTP_201_CREATED)
def create_obligation(
    *,
    db: Session = Depends(deps.get_db),
    payload: ObligationCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Create a regulatory obligation (manual or extracted by agent).
    """
    deps.verify_membership(
        db, current_user, payload.organization_id, required_permission=Permission.OBLIGATION_CREATE
    )

    version = db.query(RegulatoryVersion).join(RegulatoryDocument).filter(
        RegulatoryVersion.id == payload.version_id,
        RegulatoryDocument.organization_id == payload.organization_id,
    ).first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regulatory version not found")

    obligation = RegulatoryObligation(
        organization_id=payload.organization_id,
        version_id=payload.version_id,
        obligation_text=payload.obligation_text,
        actor=payload.actor,
        requirement=payload.requirement,
        condition=payload.condition,
        frequency=payload.frequency,
        effective_date=payload.effective_date,
        source_section=payload.source_section,
        source_page=payload.source_page,
        source_text_snippet=payload.source_text_snippet,
        confidence=payload.confidence,
        extraction_model=payload.extraction_model,
        status="pending_review",
    )
    db.add(obligation)
    db.commit()
    db.refresh(obligation)
    return obligation


@router.get("/", response_model=List[ObligationResponse])
def list_obligations(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    version_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List obligations for an organization, optionally filtered by version or status.
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.OBLIGATION_READ
    )

    query = db.query(RegulatoryObligation).filter(
        RegulatoryObligation.organization_id == organization_id
    )
    if version_id:
        query = query.filter(RegulatoryObligation.version_id == version_id)
    if status_filter:
        query = query.filter(RegulatoryObligation.status == status_filter)

    return query.order_by(RegulatoryObligation.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{obligation_id}", response_model=ObligationResponse)
def get_obligation(
    *,
    db: Session = Depends(deps.get_db),
    obligation_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get a single obligation with source provenance and confidence metrics.
    """
    obligation = db.query(RegulatoryObligation).filter(RegulatoryObligation.id == obligation_id).first()
    if not obligation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found")

    deps.verify_membership(
        db, current_user, obligation.organization_id, required_permission=Permission.OBLIGATION_READ
    )
    return obligation


@router.patch("/{obligation_id}", response_model=ObligationResponse)
def update_obligation(
    *,
    db: Session = Depends(deps.get_db),
    obligation_id: UUID,
    payload: ObligationUpdate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update or review an obligation (e.g. approve/reject/modify extracted requirement).
    """
    obligation = db.query(RegulatoryObligation).filter(RegulatoryObligation.id == obligation_id).first()
    if not obligation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found")

    deps.verify_membership(
        db, current_user, obligation.organization_id, required_permission=Permission.OBLIGATION_UPDATE
    )

    if payload.status is not None:
        deps.verify_membership(db, current_user, obligation.organization_id, required_permission=Permission.OBLIGATION_APPROVE)
        if payload.status not in {"pending_review", "approved", "rejected"}:
            raise HTTPException(422, "Invalid obligation state")
    previous = obligation.status
    audit(db, obligation.organization_id, current_user.id, "obligation_updated", "obligation", obligation.id, previous_state=previous, next_state=payload.status or previous)
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(obligation, field, val)

    db.commit()
    db.refresh(obligation)
    return obligation


@router.post("/{obligation_id}/approve", response_model=ObligationResponse)
def approve_obligation(
    *,
    db: Session = Depends(deps.get_db),
    obligation_id: UUID,
    payload: ObligationApprove,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Human-in-the-loop (HITL) approval or rejection of an AI-extracted obligation.
    Only users with OBLIGATION_APPROVE permission can approve/reject.
    """
    obligation = db.query(RegulatoryObligation).filter(RegulatoryObligation.id == obligation_id).first()
    if not obligation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found")

    deps.verify_membership(
        db, current_user, obligation.organization_id, required_permission=Permission.OBLIGATION_APPROVE
    )

    if obligation.status not in ["pending_review", "rejected"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve obligation in status: {obligation.status}"
        )

    audit(db, obligation.organization_id, current_user.id, "obligation_reviewed", "obligation", obligation.id, previous_state=obligation.status, next_state=payload.status)
    obligation.applicability = payload.applicability
    obligation.status = payload.status
    if payload.notes:
        obligation.reasoning = (obligation.reasoning or "") + f"\n[HITL {payload.status.upper()}]: {payload.notes}"

    db.commit()
    db.refresh(obligation)
    return obligation


@router.post("/bulk-action", response_model=List[ObligationResponse])
def bulk_action_obligations(
    *,
    db: Session = Depends(deps.get_db),
    payload: ObligationBulkAction,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Bulk approve or reject multiple obligations (HITL).
    """
    if not payload.obligation_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No obligation IDs provided")

    obligations = db.query(RegulatoryObligation).filter(
        RegulatoryObligation.id.in_(payload.obligation_ids)
    ).all()

    if len(obligations) != len(payload.obligation_ids):
        found_ids = {o.id for o in obligations}
        missing = set(payload.obligation_ids) - found_ids
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Obligations not found: {missing}"
        )

    deps.verify_membership(
        db, current_user, obligations[0].organization_id, required_permission=Permission.OBLIGATION_APPROVE
    )

    for obl in obligations:
        if obl.organization_id != obligations[0].organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All obligations must belong to the same organization"
            )

        if obl.status not in ["pending_review", "rejected"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Obligation {obl.id} cannot be {payload.action}d in status: {obl.status}"
            )

        audit(db, obl.organization_id, current_user.id, "obligation_reviewed", "obligation", obl.id, next_state=payload.action)
        obl.status = "approved" if payload.action == "approve" else "rejected"
        if payload.notes:
            obl.reasoning = (obl.reasoning or "") + f"\n[BULK {payload.action.upper()}]: {payload.notes}"

    db.commit()
    for obl in obligations:
        db.refresh(obl)

    return obligations


@router.get("/{obligation_id}/source")
def obligation_source(obligation_id: UUID, db: Session = Depends(deps.get_db), current_user: User = Depends(deps.get_current_user)):
    import json
    obligation = db.query(RegulatoryObligation).filter(RegulatoryObligation.id == obligation_id).first()
    if not obligation:
        raise HTTPException(404, "Obligation not found")
    deps.verify_membership(db, current_user, obligation.organization_id, required_permission=Permission.OBLIGATION_READ)
    version = db.query(RegulatoryVersion).join(RegulatoryDocument).filter(RegulatoryVersion.id == obligation.version_id,
        RegulatoryDocument.organization_id == obligation.organization_id).first()
    pages = json.loads(version.source_pages) if version and version.source_pages else [version.raw_text or ""] if version else []
    page = obligation.source_page or 1
    return {"document_id": str(version.document_id) if version else None, "version_id": str(obligation.version_id),
        "page": page, "section": obligation.source_section, "citation": obligation.source_text_snippet,
        "text": pages[page-1] if 0 < page <= len(pages) else "", "page_count": len(pages)}
