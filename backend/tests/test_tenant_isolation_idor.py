import uuid
import pytest
from datetime import datetime, timezone
from starlette.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.core import security
from app.core.rbac import Role
from app.models.user import User
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.regulation import RegulatoryDocument, RegulatoryVersion, DocumentStatus
from app.models.obligation import RegulatoryObligation
from app.models.control import Policy, Control
from app.models.evidence_model import Evidence, ControlTest
from app.models.gap import Gap, RemediationPlan


@pytest.fixture(scope="module")
def tenant_fixture():
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]

    # Create User A and Org A
    user_a = User(
        email=f"user_a_{suffix}@test.bank",
        hashed_password=security.get_password_hash("password123"),
        full_name="Tenant A Officer",
        is_active=True,
    )
    db.add(user_a)
    org_a = Organization(name=f"Org A Bank {suffix}")
    db.add(org_a)
    db.flush()

    member_a = OrganizationMember(
        organization_id=org_a.id,
        user_id=user_a.id,
        role=Role.OWNER.value,
    )
    db.add(member_a)

    # Create User B and Org B
    user_b = User(
        email=f"user_b_{suffix}@test.bank",
        hashed_password=security.get_password_hash("password123"),
        full_name="Tenant B Officer",
        is_active=True,
    )
    db.add(user_b)
    org_b = Organization(name=f"Org B Bank {suffix}")
    db.add(org_b)
    db.flush()

    member_b = OrganizationMember(
        organization_id=org_b.id,
        user_id=user_b.id,
        role=Role.OWNER.value,
    )
    db.add(member_b)

    # Seed Org A Resources
    doc_a = RegulatoryDocument(
        organization_id=org_a.id,
        title="Basel Capital Accord",
        source="BCBS",
        jurisdiction="Global",
        document_type="standard",
        status=DocumentStatus.PROCESSED.value,
    )
    db.add(doc_a)
    db.flush()

    ver_a = RegulatoryVersion(
        document_id=doc_a.id,
        version_number=1,
        status=DocumentStatus.PROCESSED.value,
    )
    db.add(ver_a)
    db.flush()

    obl_a = RegulatoryObligation(
        organization_id=org_a.id,
        version_id=ver_a.id,
        obligation_text="Maintain CET1 ratio of 4.5%",
        actor="Bank",
        requirement="Capital ratio maintenance",
        status="approved",
        confidence=0.95,
    )
    db.add(obl_a)
    db.flush()

    pol_a = Policy(
        organization_id=org_a.id,
        title="Capital Management Policy",
        description="Internal policy for regulatory capital",
        status="active",
    )
    db.add(pol_a)
    db.flush()

    ctl_a = Control(
        organization_id=org_a.id,
        policy_id=pol_a.id,
        control_id_code="CTL-CAP-001",
        objective="Ensure daily compliance with minimum capital requirements",
        description="Daily CET1 Ratio Calculation",
        frequency="daily",
        status="active",
    )
    db.add(ctl_a)
    db.flush()

    ev_a = Evidence(
        organization_id=org_a.id,
        control_id=ctl_a.id,
        title="Q1 Capital Ratio Report",
        description="Daily report output for Q1",
        evidence_date=datetime.now(timezone.utc),
        status="valid",
    )
    db.add(ev_a)
    db.flush()

    test_a = ControlTest(
        organization_id=org_a.id,
        control_id=ctl_a.id,
        test_type="automated",
        result="pass",
        effectiveness_score=1.0,
    )
    db.add(test_a)
    db.flush()

    gap_a = Gap(
        organization_id=org_a.id,
        obligation_id=obl_a.id,
        control_id=ctl_a.id,
        gap_type="partial_control",
        description="Stress testing buffer gap - calculations need automation",
        severity="medium",
        status="open",
    )
    db.add(gap_a)
    db.flush()

    rem_a = RemediationPlan(
        organization_id=org_a.id,
        gap_id=gap_a.id,
        recommendation="Implement automated calculation engine",
        priority="immediate",
        status="proposed",
    )
    db.add(rem_a)
    db.commit()

    token_a = security.create_access_token(str(user_a.id))
    token_b = security.create_access_token(str(user_b.id))

    yield {
        "user_a": user_a,
        "user_b": user_b,
        "org_a": org_a,
        "org_b": org_b,
        "doc_a": doc_a,
        "obl_a": obl_a,
        "pol_a": pol_a,
        "ctl_a": ctl_a,
        "ev_a": ev_a,
        "gap_a": gap_a,
        "rem_a": rem_a,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
        "headers_b": {"Authorization": f"Bearer {token_b}"},
    }

    # Cleanup
    try:
        db.query(RemediationPlan).filter(RemediationPlan.organization_id == org_a.id).delete()
        db.query(Gap).filter(Gap.organization_id == org_a.id).delete()
        db.query(ControlTest).filter(ControlTest.organization_id == org_a.id).delete()
        db.query(Evidence).filter(Evidence.organization_id == org_a.id).delete()
        db.query(Control).filter(Control.organization_id == org_a.id).delete()
        db.query(Policy).filter(Policy.organization_id == org_a.id).delete()
        db.query(RegulatoryObligation).filter(RegulatoryObligation.organization_id == org_a.id).delete()
        db.query(RegulatoryVersion).filter(RegulatoryVersion.document_id == doc_a.id).delete()
        db.query(RegulatoryDocument).filter(RegulatoryDocument.organization_id == org_a.id).delete()
        db.query(OrganizationMember).filter(OrganizationMember.organization_id.in_([org_a.id, org_b.id])).delete()
        db.query(Organization).filter(Organization.id.in_([org_a.id, org_b.id])).delete()
        db.query(User).filter(User.id.in_([user_a.id, user_b.id])).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def test_unauthenticated_requests_are_denied(tenant_fixture):
    client = TestClient(app)
    # No auth header passed
    res = client.get(f"/api/regulations/{tenant_fixture['doc_a'].id}")
    assert res.status_code == 401

    res = client.get(f"/api/controls/{tenant_fixture['ctl_a'].id}")
    assert res.status_code == 401

    res = client.get(f"/api/evidence/{tenant_fixture['ev_a'].id}")
    assert res.status_code == 401


def test_tenant_isolation_regulations(tenant_fixture):
    client = TestClient(app)
    doc_id = tenant_fixture["doc_a"].id
    org_a_id = tenant_fixture["org_a"].id

    # User B attempting IDOR on Org A's regulation by ID -> 403
    res = client.get(f"/api/regulations/{doc_id}", headers=tenant_fixture["headers_b"])
    assert res.status_code == 403

    # User B listing regulations with Org A's ID -> 403
    res = client.get(f"/api/regulations/?organization_id={org_a_id}", headers=tenant_fixture["headers_b"])
    assert res.status_code == 403

    # User A authorized access -> 200
    res = client.get(f"/api/regulations/{doc_id}", headers=tenant_fixture["headers_a"])
    assert res.status_code == 200
    assert res.json()["id"] == str(doc_id)


def test_tenant_isolation_obligations(tenant_fixture):
    client = TestClient(app)
    obl_id = tenant_fixture["obl_a"].id
    org_a_id = tenant_fixture["org_a"].id

    # User B attempting IDOR on Org A's obligation -> 403
    res = client.get(f"/api/obligations/{obl_id}", headers=tenant_fixture["headers_b"])
    assert res.status_code == 403

    # User B attempting to mutate Org A's obligation -> 403
    res = client.patch(
        f"/api/obligations/{obl_id}",
        json={"status": "approved"},
        headers=tenant_fixture["headers_b"],
    )
    assert res.status_code == 403

    # User B listing obligations for Org A -> 403
    res = client.get(f"/api/obligations/?organization_id={org_a_id}", headers=tenant_fixture["headers_b"])
    assert res.status_code == 403

    # User A authorized read -> 200
    res = client.get(f"/api/obligations/{obl_id}", headers=tenant_fixture["headers_a"])
    assert res.status_code == 200


def test_tenant_isolation_controls_and_policies(tenant_fixture):
    client = TestClient(app)
    ctl_id = tenant_fixture["ctl_a"].id
    org_a_id = tenant_fixture["org_a"].id

    # User B accessing Org A's control -> 403
    res = client.get(f"/api/controls/{ctl_id}", headers=tenant_fixture["headers_b"])
    assert res.status_code == 403

    # User B updating Org A's control -> 403
    res = client.patch(
        f"/api/controls/{ctl_id}",
        json={"description": "Hacked Description"},
        headers=tenant_fixture["headers_b"],
    )
    assert res.status_code == 403

    # User B listing policies for Org A -> 403
    res = client.get(f"/api/controls/policies?organization_id={org_a_id}", headers=tenant_fixture["headers_b"])
    assert res.status_code == 403

    # User B listing controls for Org A -> 403
    res = client.get(f"/api/controls/?organization_id={org_a_id}", headers=tenant_fixture["headers_b"])
    assert res.status_code == 403

    # User A authorized reads -> 200
    res = client.get(f"/api/controls/{ctl_id}", headers=tenant_fixture["headers_a"])
    assert res.status_code == 200
    res_pol = client.get(f"/api/controls/policies?organization_id={org_a_id}", headers=tenant_fixture["headers_a"])
    assert res_pol.status_code == 200


def test_tenant_isolation_evidence(tenant_fixture):
    client = TestClient(app)
    ev_id = tenant_fixture["ev_a"].id
    org_a_id = tenant_fixture["org_a"].id

    # User B accessing Org A's evidence -> 403
    res = client.get(f"/api/evidence/{ev_id}", headers=tenant_fixture["headers_b"])
    assert res.status_code == 403

    # User B listing evidence for Org A -> 403
    res = client.get(f"/api/evidence/?organization_id={org_a_id}", headers=tenant_fixture["headers_b"])
    assert res.status_code == 403

    # User A authorized read -> 200
    res = client.get(f"/api/evidence/{ev_id}", headers=tenant_fixture["headers_a"])
    assert res.status_code == 200


def test_tenant_isolation_gaps_and_remediation(tenant_fixture):
    client = TestClient(app)
    gap_id = tenant_fixture["gap_a"].id
    rem_id = tenant_fixture["rem_a"].id
    org_a_id = tenant_fixture["org_a"].id

    # User B accessing Org A's gap -> 403
    res = client.get(f"/api/gaps/{gap_id}", headers=tenant_fixture["headers_b"])
    assert res.status_code == 403

    # User B listing gaps for Org A -> 403
    res = client.get(f"/api/gaps/?organization_id={org_a_id}", headers=tenant_fixture["headers_b"])
    assert res.status_code == 403

    # User B accessing Org A's remediation plan -> 403
    res = client.get(f"/api/remediation/{rem_id}", headers=tenant_fixture["headers_b"])
    assert res.status_code == 403

    # User A authorized read -> 200
    res = client.get(f"/api/gaps/{gap_id}", headers=tenant_fixture["headers_a"])
    assert res.status_code == 200
    res_rem = client.get(f"/api/remediation/{rem_id}", headers=tenant_fixture["headers_a"])
    assert res_rem.status_code == 200


def test_tenant_isolation_matrix_and_metrics(tenant_fixture):
    client = TestClient(app)
    org_a_id = tenant_fixture["org_a"].id

    # User B accessing Org A's matrix -> 403
    res = client.get(f"/api/evaluation/demo/compliance-matrix?organization_id={org_a_id}", headers=tenant_fixture["headers_b"])
    assert res.status_code == 403

    # User B accessing Org A's metrics -> 403
    res = client.get(f"/api/evaluation/metrics/evaluation?organization_id={org_a_id}", headers=tenant_fixture["headers_b"])
    assert res.status_code == 403

    # User A authorized reads -> 200
    res = client.get(f"/api/evaluation/demo/compliance-matrix?organization_id={org_a_id}", headers=tenant_fixture["headers_a"])
    assert res.status_code == 200
    res_metrics = client.get(f"/api/evaluation/metrics/evaluation?organization_id={org_a_id}", headers=tenant_fixture["headers_a"])
    assert res_metrics.status_code == 200


def test_organization_membership_and_listing_isolation(tenant_fixture):
    client = TestClient(app)
    org_a_id = tenant_fixture["org_a"].id
    org_b_id = tenant_fixture["org_b"].id

    # User B cannot view members of Org A -> 403
    res = client.get(f"/api/organizations/{org_a_id}/members", headers=tenant_fixture["headers_b"])
    assert res.status_code == 403

    # User A can view members of Org A -> 200
    res = client.get(f"/api/organizations/{org_a_id}/members", headers=tenant_fixture["headers_a"])
    assert res.status_code == 200
    assert any(m["user_id"] == str(tenant_fixture["user_a"].id) for m in res.json())

    # User A listing organizations sees only Org A
    res_orgs_a = client.get("/api/organizations/", headers=tenant_fixture["headers_a"])
    assert res_orgs_a.status_code == 200
    org_ids_a = [o["id"] for o in res_orgs_a.json()]
    assert str(org_a_id) in org_ids_a
    assert str(org_b_id) not in org_ids_a

    # User B listing organizations sees only Org B
    res_orgs_b = client.get("/api/organizations/", headers=tenant_fixture["headers_b"])
    assert res_orgs_b.status_code == 200
    org_ids_b = [o["id"] for o in res_orgs_b.json()]
    assert str(org_b_id) in org_ids_b
    assert str(org_a_id) not in org_ids_b
