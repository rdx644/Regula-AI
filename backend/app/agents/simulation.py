"""An isolated scenario calculation; only the Simulation result is persisted."""
import json
from uuid import UUID
from app.db.session import SessionLocal
from app.models.change import Simulation
from app.agents.schemas import AgentStepOutput
from app.services.compliance import compliance_matrix, simulate_rows


async def run_simulation_analysis(simulation_id: UUID, organization_id: UUID) -> AgentStepOutput:
    db = SessionLocal()
    try:
        simulation = db.query(Simulation).filter(Simulation.id == simulation_id,
            Simulation.organization_id == organization_id).first()
        if simulation is None:
            raise ValueError("Scenario not found")
        parameters = json.loads(simulation.parameters) if simulation.parameters else {}
        result = simulate_rows(compliance_matrix(db, organization_id), parameters)
        simulation.results = json.dumps(result)
        simulation.affected_obligations = json.dumps(result["changed_obligations"])
        simulation.affected_controls = json.dumps(result["affected_controls"])
        simulation.projected_gaps = json.dumps(result["new_gaps"])
        simulation.status = "completed"
        db.commit()
        return AgentStepOutput(success=True, result={"simulation_id": str(simulation_id),
            "changed_obligations": len(result["changed_obligations"]), "affected_controls": len(result["affected_controls"]),
            "new_gaps": len(result["new_gaps"]), "risk_delta": result["risk_delta"]}, model_used="", provider="deterministic")
    except Exception as exc:
        db.rollback()
        return AgentStepOutput(success=False, error=f"Scenario failed ({type(exc).__name__})", model_used="", provider="deterministic")
    finally:
        db.close()
