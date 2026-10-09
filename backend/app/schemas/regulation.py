from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class VersionBase(BaseModel):
    effective_date: Optional[datetime] = None


class VersionCreate(VersionBase):
    file_reference: Optional[str] = None
    raw_text: Optional[str] = None


class VersionResponse(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    effective_date: Optional[datetime] = None
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RegulationBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    source: Optional[str] = None
    jurisdiction: Optional[str] = None
    document_type: Optional[str] = None
    description: Optional[str] = None


class RegulationCreate(RegulationBase):
    organization_id: UUID


class RegulationUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=512)
    source: Optional[str] = None
    jurisdiction: Optional[str] = None
    document_type: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class RegulationResponse(RegulationBase):
    id: UUID
    organization_id: UUID
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    versions: List[VersionResponse] = []

    class Config:
        from_attributes = True


class RegulationSummary(BaseModel):
    id: UUID
    title: str
    source: Optional[str] = None
    jurisdiction: Optional[str] = None
    document_type: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RegulationProcessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: UUID


class RegulationProcessResponse(BaseModel):
    job_id: str
    status: str
    message: str


class ObligationExtractionRequest(BaseModel):
    version_id: UUID


class ObligationExtractionResponse(BaseModel):
    job_id: str
    status: str
    message: str
