import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.rbac import Permission
from app.models.user import User
from app.models.organization import Organization
from app.models.regulation import RegulatoryDocument, RegulatoryVersion
from app.models.obligation import RegulatoryObligation
from app.models.control import Policy, Control
from app.models.mapping import RegulationControlMapping
from app.models.evidence_model import Evidence, ControlTest
from app.models.gap import Gap, RiskAssessment, RemediationPlan
from app.models.change import RegulatoryChange, ImpactAssessment, Simulation

router = APIRouter()


@router.post("/demo/seed", status_code=status.HTTP_201_CREATED)
def seed_demo_data(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Seed deterministic demo data for hackathon demonstration.
    Creates a complete compliance scenario with regulations, obligations, controls, evidence, gaps, and remediation.
    """
    # Keep the demo tenant private to its creator. A shared "Demo Bank" would
    # let one user seed or view another user's compliance data.
    demo_org_name = f"Demo Bank {current_user.id}"
    org = db.query(Organization).filter(Organization.name == demo_org_name).first()
    from app.models.organization_member import OrganizationMember
    from app.core.rbac import Role
    if org:
        deps.verify_membership(
            db, current_user, org.id, required_permission=Permission.REGULATION_CREATE
        )
        existing_regulation = db.query(RegulatoryDocument).filter(
            RegulatoryDocument.organization_id == org.id,
            RegulatoryDocument.title == "Basel III: Capital Requirements",
        ).first()
        if existing_regulation:
            return {
                "message": "Demo data already exists",
                "already_seeded": True,
                "organization_id": str(org.id),
                "regulation": str(existing_regulation.id),
            }
    else:
        org = Organization(name=demo_org_name)
        db.add(org)
        db.flush()
        member = OrganizationMember(
            organization_id=org.id,
            user_id=current_user.id,
            role=Role.OWNER.value,
        )
        db.add(member)
        db.flush()
    
    org_id = org.id
    user_id = current_user.id
    
    # 1. Create Regulation Document (Basel III)
    regulation = RegulatoryDocument(
        organization_id=org_id,
        title="Basel III: Capital Requirements",
        source="BCBS",
        jurisdiction="International",
        document_type="Standard",
        description="International regulatory framework for bank capital adequacy, stress testing, and market liquidity risk",
        status="processed",
    )
    db.add(regulation)
    db.flush()
    
    version = RegulatoryVersion(
        document_id=regulation.id,
        version_number=1,
        effective_date=datetime(2023, 1, 1),
        raw_text="""
Section 49: Banks shall maintain a minimum Common Equity Tier 1 capital ratio of 4.5% at all times.

Section 50: Banks shall maintain a Tier 1 capital ratio of at least 6% at all times.

Section 51: Banks shall maintain a Total Capital ratio of at least 8% at all times.

Section 52: Where a bank's leverage ratio falls below 3%, the bank shall submit a capital restoration plan to the regulator within 30 calendar days.

Section 53: Banks shall maintain a liquidity coverage ratio (LCR) of at least 100% on an ongoing basis.

Section 54: Banks shall monitor and report large exposures exceeding 10% of eligible capital to the supervisory authority quarterly.

Section 55: Banks shall maintain a net stable funding ratio (NSFR) of at least 100% on an ongoing basis.

Section 56: Banks shall conduct stress testing at least annually and report results to the supervisory authority.
""",
        status="processed",
    )
    db.add(version)
    db.flush()
    
    # 2. Create Obligations
    obligations_data = [
        {
            "text": "Banks shall maintain a minimum Common Equity Tier 1 capital ratio of 4.5% at all times.",
            "actor": "Banks",
            "requirement": "maintain a minimum Common Equity Tier 1 capital ratio of 4.5%",
            "condition": "at all times",
            "frequency": "ongoing",
            "source_section": "Section 49",
            "source_page": 12,
        },
        {
            "text": "Banks shall maintain a Tier 1 capital ratio of at least 6% at all times.",
            "actor": "Banks",
            "requirement": "maintain a Tier 1 capital ratio of at least 6%",
            "condition": "at all times",
            "frequency": "ongoing",
            "source_section": "Section 50",
            "source_page": 12,
        },
        {
            "text": "Banks shall maintain a Total Capital ratio of at least 8% at all times.",
            "actor": "Banks",
            "requirement": "maintain a Total Capital ratio of at least 8%",
            "condition": "at all times",
            "frequency": "ongoing",
            "source_section": "Section 51",
            "source_page": 13,
        },
        {
            "text": "Where a bank's leverage ratio falls below 3%, the bank shall submit a capital restoration plan to the regulator within 30 calendar days.",
            "actor": "bank",
            "requirement": "submit a capital restoration plan to the regulator",
            "condition": "leverage ratio falls below 3%",
            "frequency": "one-time (triggered)",
            "source_section": "Section 52",
            "source_page": 14,
        },
        {
            "text": "Banks shall maintain a liquidity coverage ratio (LCR) of at least 100% on an ongoing basis.",
            "actor": "Banks",
            "requirement": "maintain a liquidity coverage ratio (LCR) of at least 100%",
            "condition": "on an ongoing basis",
            "frequency": "ongoing",
            "source_section": "Section 53",
            "source_page": 15,
        },
        {
            "text": "Banks shall monitor and report large exposures exceeding 10% of eligible capital to the supervisory authority quarterly.",
            "actor": "Banks",
            "requirement": "monitor and report large exposures exceeding 10% of eligible capital",
            "condition": "quarterly",
            "frequency": "quarterly",
            "source_section": "Section 54",
            "source_page": 16,
        },
        {
            "text": "Banks shall maintain a net stable funding ratio (NSFR) of at least 100% on an ongoing basis.",
            "actor": "Banks",
            "requirement": "maintain a net stable funding ratio (NSFR) of at least 100%",
            "condition": "on an ongoing basis",
            "frequency": "ongoing",
            "source_section": "Section 55",
            "source_page": 17,
        },
        {
            "text": "Banks shall conduct stress testing at least annually and report results to the supervisory authority.",
            "actor": "Banks",
            "requirement": "conduct stress testing and report results",
            "condition": "at least annually",
            "frequency": "annual",
            "source_section": "Section 56",
            "source_page": 18,
        },
    ]
    
    obligation_objects = []
    for obl_data in obligations_data:
        obl = RegulatoryObligation(
            organization_id=org_id,
            version_id=version.id,
            obligation_text=obl_data["text"],
            actor=obl_data["actor"],
            requirement=obl_data["requirement"],
            condition=obl_data["condition"],
            frequency=obl_data["frequency"],
            source_section=obl_data["source_section"],
            source_page=obl_data["source_page"],
            source_text_snippet=obl_data["text"],
            confidence=0.95,
            extraction_model="gpt-4o-mini",
            status="approved",
        )
        db.add(obl)
        obligation_objects.append(obl)
    db.flush()
    
    # 3. Create Policy
    policy = Policy(
        organization_id=org_id,
        title="Capital Adequacy Policy",
        description="Internal policy governing capital adequacy management and reporting",
        owner="CRO",
        status="active",
    )
    db.add(policy)
    db.flush()
    
    # 4. Create Controls
    controls_data = [
        {
            "code": "CTL-CAP-001",
            "objective": "Monitor and maintain CET1 capital ratio above regulatory minimum",
            "description": "Daily calculation and monitoring of CET1 ratio against 4.5% minimum with automated alerts",
            "owner": "Treasury",
            "frequency": "daily",
            "procedure": "1. Extract capital data from core banking system\n2. Calculate CET1 ratio\n3. Compare against 4.5% threshold\n4. Alert if below 5% (buffer)\n5. Document in daily capital report",
            "evidence_requirement": "Daily CET1 ratio calculation report with timestamp",
            "business_unit": "Treasury",
        },
        {
            "code": "CTL-CAP-002",
            "objective": "Monitor and maintain Tier 1 and Total Capital ratios",
            "description": "Weekly calculation of Tier 1 and Total Capital ratios with regulatory reporting",
            "owner": "Treasury",
            "frequency": "weekly",
            "procedure": "1. Calculate Tier 1 capital\n2. Calculate Total Capital\n3. Compute ratios\n4. Compare against 6% and 8% minimums\n5. Submit to regulatory reporting system",
            "evidence_requirement": "Weekly capital adequacy report",
            "business_unit": "Treasury",
        },
        {
            "code": "CTL-CAP-003",
            "objective": "Monitor leverage ratio and trigger restoration plan if needed",
            "description": "Monthly leverage ratio monitoring with automated trigger for restoration plan",
            "owner": "Risk Management",
            "frequency": "monthly",
            "procedure": "1. Calculate leverage ratio\n2. Compare against 3% threshold\n3. If below threshold, initiate restoration plan workflow\n4. Submit plan to regulator within 30 days",
            "evidence_requirement": "Monthly leverage ratio report and restoration plan (if triggered)",
            "business_unit": "Risk Management",
        },
        {
            "code": "CTL-LIQ-001",
            "objective": "Monitor and maintain LCR above 100%",
            "description": "Daily LCR calculation and monitoring with high-quality liquid asset tracking",
            "owner": "Treasury",
            "frequency": "daily",
            "procedure": "1. Calculate high-quality liquid assets (HQLA)\n2. Calculate net cash outflows over 30 days\n3. Compute LCR = HQLA / Net cash outflows\n3. Alert if below 110% (buffer)\n4. Document in daily liquidity report",
            "evidence_requirement": "Daily LCR calculation report with HQLA breakdown",
            "business_unit": "Treasury",
        },
        {
            "code": "CTL-LIQ-002",
            "objective": "Monitor and maintain NSFR above 100%",
            "description": "Quarterly NSFR calculation with stable funding assessment",
            "owner": "Treasury",
            "frequency": "quarterly",
            "procedure": "1. Calculate available stable funding (ASF)\n2. Calculate required stable funding (RSF)\n3. Compute NSFR = ASF / RSF\n4. Alert if below 105% (buffer)\n5. Document in quarterly funding report",
            "evidence_requirement": "Quarterly NSFR calculation report",
            "business_unit": "Treasury",
        },
        {
            "code": "CTL-RPT-001",
            "objective": "Large exposure monitoring and quarterly regulatory reporting",
            "description": "Automated identification and reporting of exposures > 10% eligible capital",
            "owner": "Risk Management",
            "frequency": "quarterly",
            "procedure": "1. Identify all counterparty exposures\n2. Calculate as percentage of eligible capital\n3. Filter exposures > 10%\n4. Prepare regulatory report\n5. Submit to supervisory authority",
            "evidence_requirement": "Quarterly large exposure report submitted to regulator",
            "business_unit": "Risk Management",
        },
        {
            "code": "CTL-STR-001",
            "objective": "Annual stress testing and regulatory reporting",
            "description": "Comprehensive stress testing program with scenario analysis and regulatory submission",
            "owner": "Risk Management",
            "frequency": "annual",
            "procedure": "1. Define stress scenarios (baseline, adverse, severely adverse)\n2. Project capital ratios under each scenario\n3. Document methodology and assumptions\n5. Submit results to supervisory authority",
            "evidence_requirement": "Annual stress test report submitted to regulator",
            "business_unit": "Risk Management",
        },
    ]
    
    control_objects = []
    for ctrl_data in controls_data:
        ctrl = Control(
            organization_id=org_id,
            policy_id=policy.id,
            control_id_code=ctrl_data["code"],
            objective=ctrl_data["objective"],
            description=ctrl_data["description"],
            owner=ctrl_data["owner"],
            frequency=ctrl_data["frequency"],
            procedure=ctrl_data["procedure"],
            evidence_requirement=ctrl_data["evidence_requirement"],
            business_unit=ctrl_data["business_unit"],
            status="approved",
        )
        db.add(ctrl)
        control_objects.append(ctrl)
    db.flush()
    
    # 5. Create Mappings
    mapping_pairs = [
        (obligation_objects[0], control_objects[0]),  # CET1 4.5% -> CTL-CAP-001
        (obligation_objects[1], control_objects[1]),  # Tier 1 6% -> CTL-CAP-002
        (obligation_objects[2], control_objects[1]),  # Total Capital 8% -> CTL-CAP-002
        (obligation_objects[3], control_objects[2]),  # Leverage ratio -> CTL-CAP-003
        (obligation_objects[4], control_objects[3]),  # LCR -> CTL-LIQ-001
        (obligation_objects[5], control_objects[5]),  # Large exposures -> CTL-RPT-001
        (obligation_objects[6], control_objects[4]),  # NSFR -> CTL-LIQ-002
        (obligation_objects[7], control_objects[6]),  # Stress testing -> CTL-STR-001
    ]
    
    for obl, ctrl in mapping_pairs:
        mapping = RegulationControlMapping(
            organization_id=org_id,
            obligation_id=obl.id,
            control_id=ctrl.id,
            mapping_status="mapped",
            confidence=0.92,
            reasoning=f"Control {ctrl.control_id_code} directly addresses {obl.source_section}",
            approved_by=user_id,
            approved_at=datetime.utcnow(),
        )
        db.add(mapping)
    
    # 6. Create Evidence
    evidence_data = [
        {
            "control": control_objects[0],
            "title": "Daily CET1 Ratio Report - 2024-01-15",
            "description": "Automated daily CET1 ratio calculation showing 12.3% (well above 4.5% minimum)",
            "evidence_date": datetime(2024, 1, 15),
            "coverage_start": datetime(2024, 1, 15),
            "coverage_end": datetime(2024, 1, 15),
            "status": "valid",
        },
        {
            "control": control_objects[1],
            "title": "Weekly Capital Adequacy Report - Week 3 2024",
            "description": "Tier 1 ratio 14.2%, Total Capital ratio 16.8% - both above minimums",
            "evidence_date": datetime(2024, 1, 19),
            "coverage_start": datetime(2024, 1, 15),
            "coverage_end": datetime(2024, 1, 19),
            "status": "valid",
        },
        {
            "control": control_objects[2],
            "title": "Monthly Leverage Ratio Report - Jan 2024",
            "description": "Leverage ratio 5.2% - above 3% threshold, no restoration plan needed",
            "evidence_date": datetime(2024, 1, 31),
            "coverage_start": datetime(2024, 1, 1),
            "coverage_end": datetime(2024, 1, 31),
            "status": "valid",
        },
        {
            "control": control_objects[3],
            "title": "Daily LCR Report - 2024-01-15",
            "description": "LCR 142% with HQLA of $45B and net cash outflows of $31.7B",
            "evidence_date": datetime(2024, 1, 15),
            "coverage_start": datetime(2024, 1, 15),
            "coverage_end": datetime(2024, 1, 15),
            "status": "valid",
        },
        {
            "control": control_objects[4],
            "title": "Quarterly NSFR Report - Q4 2023",
            "description": "NSFR 118% with ASF of $180B and RSF of $152.5B",
            "evidence_date": datetime(2024, 1, 10),
            "coverage_start": datetime(2023, 10, 1),
            "coverage_end": datetime(2023, 12, 31),
            "status": "valid",
        },
        {
            "control": control_objects[5],
            "title": "Quarterly Large Exposure Report - Q4 2023",
            "description": "3 exposures identified > 10% eligible capital, all reported to regulator",
            "evidence_date": datetime(2024, 1, 12),
            "coverage_start": datetime(2023, 10, 1),
            "coverage_end": datetime(2023, 12, 31),
            "status": "valid",
        },
        {
            "control": control_objects[6],
            "title": "Annual Stress Test Report - 2023",
            "description": "Severely adverse scenario: CET1 minimum 8.1% (above 4.5% minimum). Report submitted to regulator.",
            "evidence_date": datetime(2024, 3, 31),
            "coverage_start": datetime(2023, 1, 1),
            "coverage_end": datetime(2023, 12, 31),
            "status": "valid",
        },
    ]
    
    for ev_data in evidence_data:
        evidence = Evidence(
            organization_id=org_id,
            control_id=ev_data["control"].id,
            title=ev_data["title"],
            description=ev_data["description"],
            evidence_date=ev_data["evidence_date"],
            coverage_start=ev_data["coverage_start"],
            coverage_end=ev_data["coverage_end"],
            status=ev_data["status"],
        )
        db.add(evidence)
    
    # 7. Create Control Tests
    for ctrl in control_objects:
        test = ControlTest(
            organization_id=org_id,
            control_id=ctrl.id,
            test_type="automated",
            description=f"Automated test of {ctrl.control_id_code}",
            result="pass",
            effectiveness_score=0.95,
            findings=f"Control {ctrl.control_id_code} operating effectively. All automated checks passed.",
            tested_at=datetime(2024, 1, 20),
            tester="Automated Testing System",
        )
        db.add(test)
    
    # 8. Create Gap (one intentional gap for demo)
    gap = Gap(
        organization_id=org_id,
        obligation_id=obligation_objects[5].id,  # Large exposure reporting
        control_id=control_objects[5].id,
        gap_type="stale_evidence",
        description="Q1 2024 large exposure report not yet available (due mid-April 2024)",
        severity="medium",
        status="open",
    )
    db.add(gap)
    db.flush()
    
    # 9. Risk Assessment for gap
    risk = RiskAssessment(
        gap_id=gap.id,
        likelihood=0.4,
        impact=0.6,
        risk_score=24.0,
        risk_level="medium",
        reasoning="Regulatory deadline missed but exposure monitoring continues; low immediate risk",
        assessed_at=datetime.utcnow(),
    )
    db.add(risk)
    
    # 10. Remediation Plan for gap
    remediation = RemediationPlan(
        organization_id=org_id,
        gap_id=gap.id,
        recommendation="Expedite Q1 2024 large exposure report preparation; implement automated report generation",
        priority="short_term",
        estimated_effort="2 weeks",
        assigned_to="Risk Management Team Lead",
        status="proposed",
        due_date=datetime(2024, 4, 30),
    )
    db.add(remediation)
    
    db.commit()
    
    return {
        "message": "Demo data seeded successfully",
        "organization_id": str(org_id),
        "regulation": str(regulation.id),
        "obligations_created": len(obligation_objects),
        "controls_created": len(control_objects),
        "mappings_created": len(mapping_pairs),
        "evidence_created": len(evidence_data),
        "gaps_created": 1,
        "remediation_plans_created": 1,
    }


@router.get("/demo/compliance-matrix")
def get_compliance_matrix(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get the compliance matrix view: Obligation -> Control -> Evidence -> Test -> Gap -> Remediation
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.REGULATION_READ
    )
    
    from app.services.compliance import compliance_matrix
    rows = compliance_matrix(db, organization_id)
    return {"matrix": rows, "count": len(rows)}


@router.get("/metrics/evaluation")
def get_evaluation_metrics(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get evaluation metrics for the organization's compliance data.
    """
    deps.verify_membership(
        db, current_user, organization_id, required_permission=Permission.AUDIT_READ
    )
    
    # Count entities
    obligations = db.query(RegulatoryObligation).filter(
        RegulatoryObligation.organization_id == organization_id
    ).count()
    
    approved_obligations = db.query(RegulatoryObligation).filter(
        RegulatoryObligation.organization_id == organization_id,
        RegulatoryObligation.status == "approved"
    ).count()
    
    controls = db.query(Control).filter(
        Control.organization_id == organization_id
    ).count()
    
    approved_controls = db.query(Control).filter(
        Control.organization_id == organization_id,
        Control.status == "approved"
    ).count()
    
    mappings = db.query(RegulationControlMapping).filter(
        RegulationControlMapping.organization_id == organization_id
    ).count()
    
    approved_mappings = db.query(RegulationControlMapping).filter(
        RegulationControlMapping.organization_id == organization_id,
        RegulationControlMapping.mapping_status == "mapped"
    ).count()
    
    evidence = db.query(Evidence).filter(
        Evidence.organization_id == organization_id
    ).count()
    
    valid_evidence = db.query(Evidence).filter(
        Evidence.organization_id == organization_id,
        Evidence.status == "valid"
    ).count()
    
    tests = db.query(ControlTest).filter(
        ControlTest.organization_id == organization_id
    ).count()
    
    passed_tests = db.query(ControlTest).filter(
        ControlTest.organization_id == organization_id,
        ControlTest.result == "pass"
    ).count()
    
    gaps = db.query(Gap).filter(
        Gap.organization_id == organization_id
    ).count()
    
    open_gaps = db.query(Gap).filter(
        Gap.organization_id == organization_id,
        Gap.status == "open"
    ).count()
    
    remediation_plans = db.query(RemediationPlan).filter(
        RemediationPlan.organization_id == organization_id
    ).count()
    
    completed_remediation = db.query(RemediationPlan).filter(
        RemediationPlan.organization_id == organization_id,
        RemediationPlan.status == "completed"
    ).count()
    
    return {
        "obligations": {
            "total": obligations,
            "approved": approved_obligations,
            "approval_rate": round(approved_obligations / obligations * 100, 1) if obligations > 0 else 0,
        },
        "controls": {
            "total": controls,
            "approved": approved_controls,
            "approval_rate": round(approved_controls / controls * 100, 1) if controls > 0 else 0,
        },
        "mappings": {
            "total": mappings,
            "approved": approved_mappings,
            "approval_rate": round(approved_mappings / mappings * 100, 1) if mappings > 0 else 0,
        },
        "evidence": {
            "total": evidence,
            "valid": valid_evidence,
            "validation_rate": round(valid_evidence / evidence * 100, 1) if evidence > 0 else 0,
        },
        "tests": {
            "total": tests,
            "passed": passed_tests,
            "pass_rate": round(passed_tests / tests * 100, 1) if tests > 0 else 0,
        },
        "gaps": {
            "total": gaps,
            "open": open_gaps,
            "closure_rate": round((gaps - open_gaps) / gaps * 100, 1) if gaps > 0 else 100,
        },
        "remediation": {
            "total": remediation_plans,
            "completed": completed_remediation,
            "completion_rate": round(completed_remediation / remediation_plans * 100, 1) if remediation_plans > 0 else 0,
        },
        "overall_compliance_score": round(
            (
                (approved_obligations / obligations * 0.2 if obligations else 0) +
                (approved_controls / controls * 0.2 if controls else 0) +
                (approved_mappings / mappings * 0.2 if mappings else 0) +
                (valid_evidence / evidence * 0.2 if evidence else 0) +
                (passed_tests / tests * 0.2 if tests else 0)
            ) * 100, 1
        ),
    }
