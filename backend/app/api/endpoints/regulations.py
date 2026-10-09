from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.rbac import Permission
from app.models.regulation import DocumentStatus, RegulatoryDocument, RegulatoryVersion
from app.models.user import User
from app.schemas.regulation import (
    RegulationCreate,
    RegulationResponse,
    RegulationSummary,
    RegulationProcessRequest,
    RegulationProcessResponse,
    ObligationExtractionRequest,
    ObligationExtractionResponse,
    VersionCreate,
    VersionResponse,
)
from app.services.queue import get_queue, create_job, JobPriority
from app.services.governance import input_fingerprint
from app.services.storage import get_private_storage, validate_document
from app.core.config import settings

router = APIRouter()


@router.post("/", response_model=RegulationResponse, status_code=status.HTTP_201_CREATED)
def create_regulation(
    *,
    db: Session = Depends(deps.get_db),
    payload: RegulationCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Ingest a new regulatory document.
    Creates the document header and an initial version (v1) in UPLOADED status.
    """
    deps.verify_membership(
        db, current_user, payload.organization_id, required_permission=Permission.REGULATION_CREATE
    )

    doc = RegulatoryDocument(
        organization_id=payload.organization_id,
        title=payload.title,
        source=payload.source,
        jurisdiction=payload.jurisdiction,
        document_type=payload.document_type,
        description=payload.description,
        status=DocumentStatus.UPLOADED.value,
    )
    db.add(doc)
    db.flush()

    version = RegulatoryVersion(
        document_id=doc.id,
        version_number=1,
        status=DocumentStatus.UPLOADED.value,
    )
    db.add(version)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/", response_model=List[RegulationSummary])
def list_regulations(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List all regulatory documents for an organization.
    Enforces tenant scoping — users can only see regulations in orgs they belong to.
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.REGULATION_READ
    )

    docs = (
        db.query(RegulatoryDocument)
        .filter(RegulatoryDocument.organization_id == organization_id)
        .order_by(RegulatoryDocument.created_at.desc())
        .all()
    )
    return docs


@router.get("/{regulation_id}", response_model=RegulationResponse)
def get_regulation(
    *,
    db: Session = Depends(deps.get_db),
    regulation_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve a single regulatory document with all its versions.
    Enforces tenant scoping via organization membership check.
    """
    doc = db.query(RegulatoryDocument).filter(RegulatoryDocument.id == regulation_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regulation not found")

    deps.verify_membership(
        db, current_user, doc.organization_id, required_permission=Permission.REGULATION_READ
    )
    return doc


@router.post("/{regulation_id}/versions", response_model=VersionResponse, status_code=status.HTTP_201_CREATED)
def add_version(
    *,
    db: Session = Depends(deps.get_db),
    regulation_id: UUID,
    payload: VersionCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Add a new version to an existing regulatory document.
    Enforces RBAC and tenant scoping.
    """
    doc = db.query(RegulatoryDocument).filter(RegulatoryDocument.id == regulation_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regulation not found")

    deps.verify_membership(
        db, current_user, doc.organization_id, required_permission=Permission.REGULATION_UPDATE
    )

    max_version = (
        db.query(RegulatoryVersion.version_number)
        .filter(RegulatoryVersion.document_id == regulation_id)
        .order_by(RegulatoryVersion.version_number.desc())
        .first()
    )
    next_version = (max_version[0] + 1) if max_version else 1

    version = RegulatoryVersion(
        document_id=regulation_id,
        version_number=next_version,
        effective_date=payload.effective_date,
        file_reference=payload.file_reference,
        raw_text=payload.raw_text,
        status=DocumentStatus.UPLOADED.value,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


@router.post("/{regulation_id}/versions/{version_id}/file", response_model=VersionResponse)
async def upload_regulation_version(
    *,
    db: Session = Depends(deps.get_db),
    regulation_id: UUID,
    version_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Store a bounded, validated document privately for later asynchronous processing."""
    doc = db.query(RegulatoryDocument).filter(RegulatoryDocument.id == regulation_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regulation not found")
    deps.verify_membership(
        db, current_user, doc.organization_id, required_permission=Permission.REGULATION_UPDATE
    )
    version = db.query(RegulatoryVersion).filter(
        RegulatoryVersion.id == version_id,
        RegulatoryVersion.document_id == regulation_id,
    ).first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    if version.status not in {DocumentStatus.UPLOADED.value, DocumentStatus.FAILED.value}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This version cannot be replaced in its current state")

    content = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Document exceeds the upload size limit")
    suffix, _content_type = validate_document(content, file.filename)

    storage = get_private_storage()
    old_key = version.file_reference
    new_key = storage.save(doc.organization_id, version.id, suffix, content)
    try:
        version.file_reference = new_key
        version.status = DocumentStatus.UPLOADED.value
        db.commit()
        db.refresh(version)
    except Exception:
        db.rollback()
        storage.delete(new_key)
        raise
    if old_key and old_key.startswith(f"regulations/{doc.organization_id}/{version.id}/"):
        storage.delete(old_key)
    return version


@router.post("/{regulation_id}/process", response_model=RegulationProcessResponse, status_code=status.HTTP_202_ACCEPTED)
async def process_regulation(
    *,
    db: Session = Depends(deps.get_db),
    regulation_id: UUID,
    payload: RegulationProcessRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Process a regulatory document version: parse, extract text, and queue for obligation extraction.
    Returns a job ID for async tracking.
    """
    doc = db.query(RegulatoryDocument).filter(RegulatoryDocument.id == regulation_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regulation not found")

    deps.verify_membership(
        db, current_user, doc.organization_id, required_permission=Permission.REGULATION_UPDATE
    )

    version = db.query(RegulatoryVersion).filter(
        RegulatoryVersion.id == payload.version_id,
        RegulatoryVersion.document_id == regulation_id
    ).first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    if not version.file_reference and not version.raw_text:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Upload a source document or provide raw text before processing this version")

    job = create_job(
        job_type="regulation_process",
        payload={
            "version_id": str(payload.version_id),
        },
        organization_id=doc.organization_id,
        user_id=current_user.id,
        priority=JobPriority.HIGH,
        idempotency_key=f"process_{payload.version_id}_{input_fingerprint(version.file_reference or version.raw_text)}",
        workflow_id=f"regulation_ingestion_{doc.id}",
        step_order=1,
    )

    queue = await get_queue()
    candidate_id = job.id
    job = await queue.enqueue(job)
    if job.id != candidate_id:
        return RegulationProcessResponse(job_id=job.id, status=job.status.value, message="Existing job for this input revision")

    version.job_id = job.id
    version.status = DocumentStatus.PARSING.value
    doc.status = DocumentStatus.PARSING.value
    db.commit()

    return RegulationProcessResponse(
        job_id=job.id,
        status=job.status.value,
        message="Document processing started. Use job ID to track progress."
    )


@router.post("/{regulation_id}/extract-obligations", response_model=ObligationExtractionResponse, status_code=status.HTTP_202_ACCEPTED)
async def extract_obligations(
    *,
    db: Session = Depends(deps.get_db),
    regulation_id: UUID,
    payload: ObligationExtractionRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Extract structured obligations from a processed regulatory document version.
    Returns a job ID for async tracking.
    """
    doc = db.query(RegulatoryDocument).filter(RegulatoryDocument.id == regulation_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regulation not found")

    deps.verify_membership(
        db, current_user, doc.organization_id, required_permission=Permission.REGULATION_UPDATE
    )

    version = db.query(RegulatoryVersion).filter(
        RegulatoryVersion.id == payload.version_id,
        RegulatoryVersion.document_id == regulation_id
    ).first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    if version.status not in [DocumentStatus.PARSED.value, DocumentStatus.PROCESSED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version must be parsed or processed first. Current status: {version.status}"
        )

    job = create_job(
        job_type="obligation_extraction",
        payload={
            "version_id": str(payload.version_id),
        },
        organization_id=doc.organization_id,
        user_id=current_user.id,
        priority=JobPriority.HIGH,
        idempotency_key=f"extract_{payload.version_id}_{input_fingerprint(version.raw_text, version.source_pages)}",
        workflow_id=f"regulation_ingestion_{doc.id}",
        step_order=2,
    )

    queue = await get_queue()
    candidate_id = job.id
    job = await queue.enqueue(job)
    if job.id != candidate_id:
        return ObligationExtractionResponse(job_id=job.id, status=job.status.value, message="Existing job for this input revision")

    version.job_id = job.id
    version.status = DocumentStatus.PROCESSING.value
    doc.status = DocumentStatus.PROCESSING.value
    db.commit()

    return ObligationExtractionResponse(
        job_id=job.id,
        status=job.status.value,
        message="Obligation extraction started. Use job ID to track progress."
    )


@router.get("/{regulation_id}/versions/{version_id}/file")
def download_regulation(regulation_id: UUID, version_id: UUID, db: Session = Depends(deps.get_db), current_user: User = Depends(deps.get_current_user)):
    from fastapi.responses import Response
    document = db.query(RegulatoryDocument).filter(RegulatoryDocument.id == regulation_id).first()
    if not document:
        raise HTTPException(404, "Regulation not found")
    deps.verify_membership(db, current_user, document.organization_id, required_permission=Permission.REGULATION_READ)
    version = db.query(RegulatoryVersion).filter(RegulatoryVersion.id == version_id, RegulatoryVersion.document_id == regulation_id).first()
    if not version or not version.file_reference or not version.file_reference.startswith(f"regulations/{document.organization_id}/{version.id}/"):
        raise HTTPException(404, "Source not available")
    from app.services.storage import get_private_storage
    return Response(get_private_storage().read(version.file_reference), media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=regulation-source", "Cache-Control": "no-store"})
