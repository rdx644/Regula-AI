"""Deterministic gaps from reviewed controls, dated evidence and latest tests."""
from uuid import UUID
from app.db.session import SessionLocal
from app.models.obligation import RegulatoryObligation
from app.models.control import Control
from app.models.mapping import RegulationControlMapping
from app.models.evidence_model import Evidence, ControlTest
from app.models.gap import Gap, RiskAssessment
from app.agents.schemas import AgentStepOutput
from app.services.compliance import landscape_gap
from app.services.governance import risk


async def run_gap_identification(obligation_id: UUID, organization_id: UUID, as_of=None) -> AgentStepOutput:
    db = SessionLocal()
    try:
        obligation = db.query(RegulatoryObligation).filter(RegulatoryObligation.id == obligation_id,
            RegulatoryObligation.organization_id == organization_id).first()
        if not obligation or obligation.status != "approved":
            raise ValueError("Approve the obligation before assessment")
        if obligation.applicability == "not_applicable":
            return AgentStepOutput(success=True, result={"gap_created": False}, model_used="", provider="deterministic")
        if obligation.applicability not in {"applicable", "conditional"}:
            raise ValueError("Record applicability before assessment")
        mapping = db.query(RegulationControlMapping).filter(RegulationControlMapping.obligation_id == obligation_id,
            RegulationControlMapping.organization_id == organization_id).order_by(RegulationControlMapping.approved_at.desc().nullslast()).first()
        control = db.query(Control).filter(Control.id == mapping.control_id, Control.organization_id == organization_id).first() if mapping else None
        evidence = db.query(Evidence).filter(Evidence.control_id == control.id, Evidence.organization_id == organization_id).all() if control else []
        tests = db.query(ControlTest).filter(ControlTest.control_id == control.id, ControlTest.organization_id == organization_id).all() if control else []
        finding = landscape_gap(mapping, control, evidence, tests, as_of)
        if finding is None:
            return AgentStepOutput(success=True, result={"gap_created": False}, model_used="", provider="deterministic")
        gap = db.query(Gap).filter(Gap.organization_id == organization_id, Gap.obligation_id == obligation_id,
            Gap.gap_type == finding["gap_type"], Gap.status == "open").first()
        if gap is None:
            gap = Gap(organization_id=organization_id, obligation_id=obligation_id,
                      control_id=control.id if control else None, status="open", **finding)
            db.add(gap)
            db.flush()
        if gap.risk_assessment is None:
            likelihood, impact, score, level = risk(0.8, 0.9) if finding["severity"] == "high" else risk(0.5, 0.6)
            db.add(RiskAssessment(gap_id=gap.id, likelihood=likelihood, impact=impact, risk_score=score,
                risk_level=level, reasoning="Deterministic landscape assessment; review assumptions before authoritative use"))
        db.commit()
        return AgentStepOutput(success=True, result={"gap_created": True, "gap_id": str(gap.id), **finding},
                               model_used="", provider="deterministic")
    except Exception as exc:
        db.rollback()
        return AgentStepOutput(success=False, error=f"Gap assessment failed ({type(exc).__name__})",
                               model_used="", provider="deterministic")
    finally:
        db.close()
