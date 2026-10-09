import json
from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.rbac import Permission
from app.models.change import Simulation
from app.models.user import User
from app.schemas.simulation import (
    SimulationCreate,
    SimulationUpdate,
    SimulationResponse,
    SimulationRunRequest,
    SimulationRunResponse,
)
from app.services.queue import get_queue, create_job, JobPriority
from app.services.governance import input_fingerprint
from app.services.compliance import assessment_revision

router = APIRouter()


@router.post("/", response_model=SimulationResponse, status_code=status.HTTP_201_CREATED)
def create_simulation(
    *,
    db: Session = Depends(deps.get_db),
    payload: SimulationCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Create a what-if simulation scenario.
    """
    deps.verify_membership(
        db, current_user, payload.organization_id, required_permission=Permission.REGULATION_UPDATE
    )

    simulation = Simulation(
        organization_id=payload.organization_id,
        name=payload.name,
        scenario_description=payload.scenario_description,
        parameters=json.dumps(payload.parameters) if payload.parameters else None,
        status="created",
    )
    db.add(simulation)
    db.commit()
    db.refresh(simulation)
    return simulation


@router.get("/", response_model=List[SimulationResponse])
def list_simulations(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List simulations for an organization.
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.REGULATION_READ
    )

    query = db.query(Simulation).filter(Simulation.organization_id == organization_id)
    if status_filter:
        query = query.filter(Simulation.status == status_filter)

    return query.order_by(Simulation.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{simulation_id}", response_model=SimulationResponse)
def get_simulation(
    *,
    db: Session = Depends(deps.get_db),
    simulation_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get a single simulation by ID with results.
    """
    simulation = db.query(Simulation).filter(Simulation.id == simulation_id).first()
    if not simulation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    deps.verify_membership(
        db, current_user, simulation.organization_id, required_permission=Permission.REGULATION_READ
    )
    return simulation


@router.patch("/{simulation_id}", response_model=SimulationResponse)
def update_simulation(
    *,
    db: Session = Depends(deps.get_db),
    simulation_id: UUID,
    payload: SimulationUpdate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update a simulation.
    """
    simulation = db.query(Simulation).filter(Simulation.id == simulation_id).first()
    if not simulation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    deps.verify_membership(
        db, current_user, simulation.organization_id, required_permission=Permission.REGULATION_UPDATE
    )

    if payload.status is not None:
        raise HTTPException(422, "Simulation state is managed by the worker")
    if simulation.status == "running":
        raise HTTPException(409, "Cannot edit a running simulation")
    update_data = payload.model_dump(exclude_unset=True)
    if "parameters" in update_data and update_data["parameters"] is not None:
        update_data["parameters"] = json.dumps(update_data["parameters"])
    
    for field, val in update_data.items():
        setattr(simulation, field, val)

    db.commit()
    db.refresh(simulation)
    return simulation


@router.post("/run", response_model=SimulationRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_simulation(
    *,
    db: Session = Depends(deps.get_db),
    payload: SimulationRunRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Run a what-if simulation scenario.
    Returns a job ID for async tracking.
    """
    simulation = db.query(Simulation).filter(Simulation.id == payload.simulation_id).first()
    if not simulation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    deps.verify_membership(
        db, current_user, simulation.organization_id, required_permission=Permission.REGULATION_UPDATE
    )

    job = create_job(
        job_type="simulation",
        payload={
            "simulation_id": str(payload.simulation_id),
        },
        organization_id=simulation.organization_id,
        user_id=current_user.id,
        priority=JobPriority.HIGH,
        idempotency_key=f"simulation_{payload.simulation_id}_{input_fingerprint(simulation.parameters, assessment_revision(db, simulation.organization_id))}",
        workflow_id=f"simulation_{simulation.id}",
        step_order=1,
    )

    queue = await get_queue()
    candidate_id = job.id
    job = await queue.enqueue(job)
    if candidate_id != job.id:
        return SimulationRunResponse(job_id=job.id, status=job.status.value, message="Existing simulation for this input revision")

    simulation.status = "running"
    db.commit()

    return SimulationRunResponse(
        job_id=job.id,
        status=job.status.value,
        message="Simulation started. Use job ID to track progress."
    )