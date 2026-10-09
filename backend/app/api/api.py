from fastapi import APIRouter
from app.api.endpoints import (
    auth,
    users,
    organizations,
    regulations,
    obligations,
    controls,
    mappings,
    evidence,
    gaps,
    remediation,
    audit,
    change,
    simulation,
    intelligence,
    evaluation,
    jobs,
)

api_router = APIRouter()
from app.core.metrics import router as metrics_router
api_router.include_router(metrics_router)

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(regulations.router, prefix="/regulations", tags=["regulations"])
api_router.include_router(obligations.router, prefix="/obligations", tags=["obligations"])
api_router.include_router(controls.router, prefix="/controls", tags=["controls"])
api_router.include_router(mappings.router, prefix="/mappings", tags=["mappings"])
api_router.include_router(evidence.router, prefix="/evidence", tags=["evidence"])
api_router.include_router(gaps.router, prefix="/gaps", tags=["gaps"])
api_router.include_router(remediation.router, prefix="/remediation", tags=["remediation"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(change.router, prefix="/changes", tags=["changes"])
api_router.include_router(simulation.router, prefix="/simulations", tags=["simulations"])
api_router.include_router(intelligence.router, prefix="/intelligence", tags=["intelligence"])
api_router.include_router(evaluation.router, prefix="/evaluation", tags=["evaluation"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
