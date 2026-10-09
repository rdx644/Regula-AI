"""Regression gates using PostgreSQL, actual API authorization and domain services."""
import asyncio
import copy
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette.testclient import TestClient
from test_tenant_isolation_idor import tenant_fixture
from app.main import app
from app.core import security
from app.db.session import SessionLocal
from app.models.organization_member import OrganizationMember
from app.models.session import RevokedSession
from app.models.regulation import RegulatoryVersion
from app.models.control import Control
from app.services.compliance import landscape_gap, simulate_rows
from app.services.governance import risk
from app.agents.mapping import find_candidate_controls


def test_control_policy_cross_tenant_link_denied(tenant_fixture):
    f = tenant_fixture
    client = TestClient(app)
    response = client.post('/api/controls/', headers=f['headers_b'], json={
        'organization_id': str(f['org_b'].id), 'policy_id': str(f['pol_a'].id),
        'control_id_code': 'INJECTED', 'objective': 'Unauthorized linked policy'})
    assert response.status_code == 404
    response = client.patch(f"/api/controls/{f['ctl_a'].id}", headers=f['headers_b'], json={'policy_id': str(f['pol_a'].id)})
    assert response.status_code == 403


def test_change_cross_tenant_document_denied(tenant_fixture):
    f = tenant_fixture
    response = TestClient(app).post('/api/changes/', headers=f['headers_b'], json={
        'organization_id': str(f['org_b'].id), 'document_id': str(f['doc_a'].id),
        'new_version_id': str(f['obl_a'].version_id),
        'change_type': 'modified', 'summary': 'Untrusted cross-tenant reference'})
    assert response.status_code == 404


def test_analyst_cannot_approve_obligation_via_patch(tenant_fixture):
    f = tenant_fixture
    db = SessionLocal()
    member = db.query(OrganizationMember).filter_by(user_id=f['user_a'].id, organization_id=f['org_a'].id).one()
    original_role = member.role
    try:
        member.role = 'Analyst'
        db.commit()
        response = TestClient(app).patch(f"/api/obligations/{f['obl_a'].id}", headers=f['headers_a'], json={'status': 'approved'})
        assert response.status_code == 403
    finally:
        member.role = original_role
        db.commit()
        db.close()


def test_control_owner_cannot_self_approve(tenant_fixture):
    f = tenant_fixture
    db = SessionLocal()
    member = db.query(OrganizationMember).filter_by(user_id=f['user_a'].id, organization_id=f['org_a'].id).one()
    original_role = member.role
    try:
        member.role = 'Control Owner'
        db.commit()
        response = TestClient(app).post(f"/api/controls/{f['ctl_a'].id}/approve", headers=f['headers_a'], json={'status': 'approved'})
        assert response.status_code == 403
    finally:
        member.role = original_role
        db.commit()
        db.close()


def test_bootstrap_candidates_do_not_require_existing_mapping(tenant_fixture):
    f = tenant_fixture
    candidates = asyncio.run(find_candidate_controls(f['obl_a'], f['org_a'].id))
    assert f['ctl_a'].id in {c.id for c in candidates}
    assert all(c.organization_id == f['org_a'].id for c in candidates)
    assert asyncio.run(find_candidate_controls(f['obl_a'], f['org_b'].id)) == []


def test_pending_and_unmapped_obligations_remain_visible(tenant_fixture):
    f = tenant_fixture
    response = TestClient(app).get(f"/api/evaluation/demo/compliance-matrix?organization_id={f['org_a'].id}", headers=f['headers_a'])
    assert response.status_code == 200
    row = next(r for r in response.json()['matrix'] if r['obligation']['id'] == str(f['obl_a'].id))
    assert row['mapping']['status'] == 'unmapped'
    assert row['applicability'] == 'uncertain'


def test_source_read_is_authenticated_and_tenant_scoped(tenant_fixture):
    f = tenant_fixture
    db = SessionLocal()
    version = db.get(RegulatoryVersion, f['obl_a'].version_id)
    previous = version.source_pages
    try:
        version.source_pages = json.dumps(['Synthetic regulation source'])
        db.commit()
        client = TestClient(app)
        endpoint = f"/api/obligations/{f['obl_a'].id}/source"
        assert client.get(endpoint).status_code == 401
        assert client.get(endpoint, headers=f['headers_b']).status_code == 403
        response = client.get(endpoint, headers=f['headers_a'])
        assert response.status_code == 200
        assert response.json()['text'] == 'Synthetic regulation source'
    finally:
        version.source_pages = previous
        db.commit()
        db.close()


def test_private_evidence_download_is_authorized_before_storage(tenant_fixture):
    f = tenant_fixture
    client = TestClient(app)
    endpoint = f"/api/evidence/{f['ev_a'].id}/file"
    assert client.get(endpoint).status_code == 401
    assert client.get(endpoint, headers=f['headers_b']).status_code == 403
    assert client.get(endpoint, headers=f['headers_a']).status_code == 404
    assert client.post(endpoint, headers=f['headers_b'], files={'file': ('source.txt', b'Synthetic evidence', 'text/plain')}).status_code == 403


def test_logout_revokes_previously_valid_bearer_token(tenant_fixture):
    f = tenant_fixture
    token = security.create_access_token(str(f['user_a'].id))
    headers = {'Authorization': f'Bearer {token}'}
    client = TestClient(app)
    assert client.get('/api/users/me', headers=headers).status_code == 200
    assert client.post('/api/auth/logout', headers=headers).status_code == 200
    assert client.get('/api/users/me', headers=headers).status_code == 401
    db = SessionLocal()
    db.query(RevokedSession).filter_by(user_id=f['user_a'].id).delete()
    db.commit()
    db.close()


def test_risk_zero_and_bounds():
    assert risk(0, 1)[2:] == (0.0, 'low')
    assert risk(.8, .9)[2:] == (72.0, 'high')
    assert risk(1, 1)[2:] == (100.0, 'critical')


def test_no_gap_is_valid_and_stale_evidence_is_detected():
    now = datetime.now(timezone.utc)
    mapping = SimpleNamespace(mapping_status='mapped', approved_by=uuid4())
    evidence = SimpleNamespace(status='valid', coverage_end=None)
    test = SimpleNamespace(result='pass', effectiveness_score=.95, tested_at=now, created_at=now)
    assert landscape_gap(mapping, object(), [evidence], [test], now) is None
    evidence.coverage_end = datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert landscape_gap(mapping, object(), [evidence], [test], now)['gap_type'] == 'stale_evidence'


def test_simulation_snapshot_isolation_and_foreign_ids():
    rows = [{'obligation': {'id': 'obl'}, 'control': {'id': 'ctl', 'status': 'approved'}, 'evidence': [], 'gaps': []}]
    original = copy.deepcopy(rows)
    result = simulate_rows(rows, {'disable_control_ids': ['ctl']})
    assert rows == original
    assert result['scenario_state'][0]['control']['status'] == 'disabled_in_scenario'
    assert result['risk_delta'] == 66
    with pytest.raises(ValueError, match='tenant snapshot'):
        simulate_rows(rows, {'disable_control_ids': ['foreign']})
    with pytest.raises(ValueError):
        simulate_rows(rows, {'likelihood_multiplier': 3})
