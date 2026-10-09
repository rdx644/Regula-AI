import json
from pydantic import field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


# â”€â”€ Simulation Schemas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class SimulationBase(BaseModel):
    name: str = Field(..., max_length=256)
    scenario_description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    status: Optional[str] = "created"  # created, running, completed, failed


class SimulationCreate(SimulationBase):
    organization_id: UUID


class SimulationUpdate(BaseModel):
    name: Optional[str] = None
    scenario_description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class SimulationRunRequest(BaseModel):
    simulation_id: UUID


class SimulationRunResponse(BaseModel):
    job_id: str
    status: str
    message: str


class SimulationResponse(SimulationBase):
    id: UUID
    organization_id: UUID
    affected_obligations: Optional[List[UUID]] = None
    affected_controls: Optional[List[UUID]] = None
    projected_gaps: Optional[List[Dict[str, Any]]] = None
    results: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator('parameters', 'results', 'affected_obligations', 'affected_controls', 'projected_gaps', mode="before")
    @classmethod
    def parse_json_columns(cls, value):
        return json.loads(value) if isinstance(value, str) else value

    class Config:
        from_attributes = True