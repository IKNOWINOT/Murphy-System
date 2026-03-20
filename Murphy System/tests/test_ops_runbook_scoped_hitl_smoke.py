from fastapi.testclient import TestClient

from src.murphy_core.app_v3_canonical_execution_surface_v5 import create_app


def test_ops_runbook_mentions_scoped_hitl_verification():
    client = TestClient(create_app())
    response = client.get('/api/ops/runbook')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    scoped_step = next(step for step in payload['runbook'] if step['step'] == 'verify-scoped-hitl')
    assert 'founder vs organization HITL routing' in scoped_step['title']
    assert 'latest_hitl_scope' in scoped_step['command']
