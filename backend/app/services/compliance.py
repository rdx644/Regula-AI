"""Traceable tenant views and deterministic assessment/scenario calculations."""
from copy import deepcopy
from datetime import datetime, timezone

from app.models.obligation import RegulatoryObligation
from app.models.control import Control
from app.models.mapping import RegulationControlMapping
from app.models.evidence_model import Evidence, ControlTest
from app.models.gap import Gap, RemediationPlan
from app.services.governance import risk


def assessment_revision(db, organization_id, obligation_id=None, control_id=None):
    from app.services.governance import input_fingerprint
    models = [RegulatoryObligation, Control, RegulationControlMapping, Evidence, ControlTest]
    state = []
    for model in models:
        records = db.query(model).filter(model.organization_id == organization_id).order_by(model.id).all()
        state.append([{column.name: getattr(record, column.name) for column in model.__table__.columns}
                      for record in records])
    return input_fingerprint(organization_id, obligation_id, control_id, state)


def utc(value):
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def require_passing_evidence(db, organization_id, control_id, score):
    from fastapi import HTTPException
    if score is None or score < 0.7:
        raise HTTPException(409, "A passing test requires effectiveness of at least 0.7")
    now = datetime.now(timezone.utc)
    records = db.query(Evidence).filter(Evidence.organization_id == organization_id,
        Evidence.control_id == control_id, Evidence.status == 'valid').all()
    if not any(e.file_reference and e.file_reference.startswith(f'evidence/{organization_id}/{e.id}/')
        and (e.coverage_start is None or utc(e.coverage_start) <= now)
        and (e.coverage_end is None or utc(e.coverage_end) >= now) for e in records):
        raise HTTPException(409, "A passing test requires current, privately uploaded and reviewed evidence")


def compliance_matrix(db, organization_id):
    obligations = db.query(RegulatoryObligation).filter(RegulatoryObligation.organization_id == organization_id).order_by(RegulatoryObligation.created_at).all()
    controls = {c.id: c for c in db.query(Control).filter(Control.organization_id == organization_id).all()}
    mappings = db.query(RegulationControlMapping).filter(RegulationControlMapping.organization_id == organization_id).all()
    evidence = db.query(Evidence).filter(Evidence.organization_id == organization_id).all()
    tests = db.query(ControlTest).filter(ControlTest.organization_id == organization_id).all()
    gaps = db.query(Gap).filter(Gap.organization_id == organization_id).all()
    plans = db.query(RemediationPlan).filter(RemediationPlan.organization_id == organization_id).all()
    rows = []
    for obligation in obligations:
        for mapping in [m for m in mappings if m.obligation_id == obligation.id] or [None]:
            control = controls.get(mapping.control_id) if mapping else None
            linked_gaps = [g for g in gaps if g.obligation_id == obligation.id]
            plan = next((p for p in plans if p.gap_id in {g.id for g in linked_gaps}), None)
            rows.append({
                "obligation": {"id": str(obligation.id), "text": obligation.obligation_text,
                    "frequency": obligation.frequency, "confidence": obligation.confidence,
                    "source_section": obligation.source_section, "source_page": obligation.source_page,
                    "source_text_snippet": obligation.source_text_snippet, "version_id": str(obligation.version_id),
                    "status": obligation.status},
                "applicability": obligation.applicability,
                "control": {"id": str(control.id) if control else None, "code": control.control_id_code if control else "UNMAPPED",
                    "objective": control.objective if control else None, "status": control.status if control else None},
                "mapping": {"id": str(mapping.id) if mapping else None, "status": mapping.mapping_status if mapping else "unmapped",
                    "confidence": mapping.confidence if mapping else None, "approved": bool(mapping and mapping.approved_by)},
                "evidence": [{"id": str(e.id), "title": e.title, "status": e.status} for e in evidence if control and e.control_id == control.id],
                "tests": [{"id": str(t.id), "result": t.result, "effectiveness": t.effectiveness_score} for t in tests if control and t.control_id == control.id],
                "gaps": [{"id": str(g.id), "type": g.gap_type, "severity": g.severity, "status": g.status} for g in linked_gaps],
                "remediation": {"id": str(plan.id), "recommendation": plan.recommendation, "priority": plan.priority, "status": plan.status} if plan else None,
            })
    return rows


def landscape_gap(mapping, control, evidence, tests, as_of=None):
    """Return a gap or None. A healthy landscape is a valid no-gap result."""
    as_of = as_of or datetime.now(timezone.utc)
    if mapping is None:
        return {"gap_type": "unmapped", "severity": "high", "description": "No reviewed control mapping exists"}
    if control is None:
        return {"gap_type": "no_control", "severity": "high", "description": "No control exists"}
    if mapping.mapping_status != "mapped" or not mapping.approved_by:
        return {"gap_type": "partial_control", "severity": "medium", "description": "Control mapping requires review or only partially addresses the obligation"}
    valid = [e for e in evidence if e.status == "valid"]
    if not valid:
        return {"gap_type": "no_evidence", "severity": "high", "description": "No validated evidence supports this control"}
    current = [e for e in valid if (getattr(e, 'coverage_start', None) is None or utc(e.coverage_start) <= utc(as_of)) and (e.coverage_end is None or utc(e.coverage_end) >= utc(as_of))]
    if not current:
        return {"gap_type": "stale_evidence", "severity": "high", "description": "Evidence does not cover the assessment date"}
    latest = sorted(tests, key=lambda t: utc(t.tested_at or t.created_at or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    if not latest or latest[0].result != "pass" or (latest[0].effectiveness_score or 0) < 0.7:
        return {"gap_type": "test_failure", "severity": "high", "description": "The latest test is missing, ineffective or failed"}
    return None


def simulate_rows(rows, parameters):
    """Clone explicit records, apply bounded assumptions and recalculate risk."""
    allowed = {"disable_control_ids", "invalidate_evidence_ids", "likelihood_multiplier", "impact_multiplier"}
    if set(parameters) - allowed:
        raise ValueError("Unsupported scenario parameter")
    scenario = deepcopy(rows)
    controls = {r["control"]["id"] for r in rows if r["control"]["id"]}
    evidence = {e["id"] for r in rows for e in r["evidence"]}
    if not set(parameters.get("disable_control_ids", [])) <= controls or not set(parameters.get("invalidate_evidence_ids", [])) <= evidence:
        raise ValueError("Scenario reference is outside this tenant snapshot")
    multipliers = [float(parameters.get(name, 1)) for name in ["likelihood_multiplier", "impact_multiplier"]]
    if any(not 0 <= value <= 2 for value in multipliers):
        raise ValueError("Risk multipliers must be between 0 and 2")
    base_scores, next_scores, changed, affected, new_gaps = [], [], set(), set(), []
    for baseline, row in zip(rows, scenario):
        has_gap = bool([g for g in baseline["gaps"] if g["status"] == "open"])
        likelihood, impact = (0.8, 0.9) if has_gap else (0.2, 0.3)
        base_scores.append(risk(likelihood, impact)[2])
        if row["control"]["id"] in parameters.get("disable_control_ids", []):
            affected.add(row["control"]["id"])
            changed.add(row["obligation"]["id"])
            row["control"]["status"] = "disabled_in_scenario"
            new_gaps.append({"obligation_id": row["obligation"]["id"], "gap_type": "no_control", "severity": "high"})
            likelihood, impact = 0.8, 0.9
        for item in row["evidence"]:
            if item["id"] in parameters.get("invalidate_evidence_ids", []):
                item["status"] = "invalid_in_scenario"
                changed.add(row["obligation"]["id"])
                new_gaps.append({"obligation_id": row["obligation"]["id"], "gap_type": "no_evidence", "severity": "high"})
                likelihood, impact = 0.8, 0.9
        next_scores.append(risk(min(1, likelihood*multipliers[0]), min(1, impact*multipliers[1]))[2])
    return {"baseline_state": rows, "scenario_state": scenario, "changed_obligations": sorted(changed),
            "affected_controls": sorted(affected), "new_gaps": new_gaps,
            "risk_delta": round(sum(next_scores)-sum(base_scores), 2), "remediation_delta": [],
            "method": "deterministic snapshot; likelihood/impact assumptions documented in docs/ai-evaluation.md"}
