"""Real PostgreSQL review checks; no provider execution or expected-answer copying."""
import json
import uuid
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.regulation import RegulatoryVersion
from app.models.change import RegulatoryChange, ImpactAssessment
from app.models.audit_log import AuditLog
from app.models.obligation import RegulatoryObligation
from app.services.workspace_review import literal_diff
from test_tenant_isolation_idor import tenant_fixture


@pytest.fixture()
def review_fixture(tenant_fixture):
    fixture = tenant_fixture
    with SessionLocal() as db:
        old = db.query(RegulatoryVersion).filter(RegulatoryVersion.document_id == fixture["doc_a"].id).first()
        old.raw_text = "Synthetic rule\nReview every quarter.\n"
        old.status = "processed"
        obligation = db.get(RegulatoryObligation, fixture["obl_a"].id)
        obligation.source_text_snippet = "Review every quarter."
        new = RegulatoryVersion(document_id=fixture["doc_a"].id, version_number=2, status="parsed",
                                raw_text="Synthetic rule\nReview every month.\n")
        db.add(new)
        db.commit()
        payload = {"document_id": str(fixture["doc_a"].id), "old_version_id": str(old.id), "new_version_id": str(new.id)}
    yield fixture, payload
    with SessionLocal() as db:
        db.query(ImpactAssessment).filter(ImpactAssessment.organization_id == fixture["org_a"].id).delete()
        db.query(RegulatoryChange).filter(RegulatoryChange.organization_id == fixture["org_a"].id).delete()
        db.query(AuditLog).filter(AuditLog.organization_id == fixture["org_a"].id).delete()
        db.query(RegulatoryVersion).filter(RegulatoryVersion.id == uuid.UUID(payload["new_version_id"])).delete()
        db.commit()


def test_literal_diff_preserves_exact_source_and_bounds():
    assert literal_diff("Same\n", "Same\n") == []
    assert literal_diff("Quarterly\n", "Monthly\n") == [{"kind": "modified", "old_line_start": 1,
        "new_line_start": 1, "before": "Quarterly\n", "after": "Monthly\n"}]
    assert literal_diff("Same\n", "Same")[0]["after"] == "Same"
    for text in ["x" * 50_001, "a\n" * 501]:
        with pytest.raises(HTTPException) as error:
            literal_diff(text, "Small")
        assert error.value.status_code == 413


def test_comparison_persists_draft_and_deduplicates_without_baseline_mutation(review_fixture):
    fixture, payload = review_fixture
    client = TestClient(app)
    response = client.post("/api/changes/compare-text", headers=fixture["headers_a"], json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["changed"] and result["report"]["method"] == "literal_text_diff"
    assert result["report"]["hunks"][0]["after"] == "Review every month.\n"
    assert result["report"]["candidate_obligation_ids"] == [str(fixture["obl_a"].id)]
    repeated = client.post("/api/changes/compare-text", headers=fixture["headers_a"], json=payload)
    assert repeated.json()["change_id"] == result["change_id"]
    impacts = client.get(f"/api/changes/impact?organization_id={fixture['org_a'].id}", headers=fixture["headers_a"])
    assert impacts.status_code == 200
    assert len(impacts.json()) == 1
    assert impacts.json()[0]["status"] == "draft"
    assert impacts.json()[0]["confidence"] is None and impacts.json()[0]["risk_delta"] is None
    with SessionLocal() as db:
        assert db.get(RegulatoryObligation, fixture["obl_a"].id).status == "approved"
        trace = db.query(AuditLog).filter(AuditLog.action == "text_change_compared", AuditLog.organization_id == fixture["org_a"].id).one()
        assert "Review every" not in trace.details


def test_comparison_denies_foreign_tenant_versions_and_unparsed_sources(review_fixture):
    fixture, payload = review_fixture
    client = TestClient(app)
    assert client.post("/api/changes/compare-text", headers=fixture["headers_b"], json=payload).status_code == 403
    assert client.post("/api/changes/compare-text", json=payload).status_code == 401
    assert client.post("/api/changes/compare-text", headers=fixture["headers_a"], json={**payload, "new_version_id": str(uuid.uuid4())}).status_code == 404
    assert client.post("/api/changes/compare-text", headers=fixture["headers_a"], json={**payload, "new_version_id": payload["old_version_id"]}).status_code == 422
    with SessionLocal() as db:
        db.get(RegulatoryVersion, uuid.UUID(payload["new_version_id"])).status = "uploaded"
        db.commit()
    assert client.post("/api/changes/compare-text", headers=fixture["headers_a"], json=payload).status_code == 409


def test_guided_investigation_returns_recorded_citations_and_audit(review_fixture):
    fixture, _ = review_fixture
    client = TestClient(app)
    payload = {"organization_id": str(fixture["org_a"].id), "question": "open_gaps"}
    result = client.post("/api/intelligence/investigate", headers=fixture["headers_a"], json=payload)
    assert result.status_code == 200, result.text
    answer = result.json()
    assert answer["total"] == 1
    assert answer["findings"][0]["obligation"]["source_text_snippet"] == "Review every quarter."
    assert answer["findings"][0]["gaps"][0]["id"] == str(fixture["gap_a"].id)
    with SessionLocal() as db:
        trace = db.get(AuditLog, uuid.UUID(answer["audit_id"]))
        assert trace.organization_id == fixture["org_a"].id
        assert json.loads(trace.details)["method"] == "structured_workspace_lookup"
        assert "Review every" not in trace.details
    assert client.post("/api/intelligence/investigate", headers=fixture["headers_b"], json=payload).status_code == 403
    assert client.post("/api/intelligence/investigate", headers=fixture["headers_a"], json={**payload, "question": "arbitrary_prompt"}).status_code == 422
