from fastapi.testclient import TestClient

from src.murphy_core.app_v3_canonical_execution_surface_v5 import create_app


def test_canonical_v5_visibility_surfaces_show_founder_hitl_scope_for_platform_changes():
    client = TestClient(create_app())
    execute_response = client.post(
        '/api/execute',
        json={
            'task_description': 'change the platform runtime and add code to the repo',
            'context': {'target_scope': 'platform'},
        },
    )
    assert execute_response.status_code == 200
    execute_payload = execute_response.json()
    assert execute_payload['execution_status'] == 'hitl_required'
    assert execute_payload['recovery']['gate_enforcement_summary']['hitl_scope'] == 'founder'

    operator_runtime = client.get('/api/operator/runtime').json()
    dashboard = client.get('/api/ui/runtime-dashboard').json()
    founder_summary = client.get('/api/founder/visibility-summary').json()

    assert operator_runtime['recent_execution_outcomes']['latest_hitl_scope'] == 'founder'
    assert operator_runtime['recent_execution_outcomes']['hitl_scope_counts']['founder'] >= 1
    assert dashboard['recent_execution_outcomes']['latest_hitl_scope'] == 'founder'
    hitl_card = next(card for card in dashboard['cards'] if card['id'] == 'hitl-scope')
    assert hitl_card['value'] == 'founder'
    assert founder_summary['latest_hitl_scope'] == 'founder'
    assert founder_summary['founder_hitl_pending'] >= 1


def test_canonical_v5_visibility_surfaces_show_org_hitl_scope_for_org_changes():
    client = TestClient(create_app())
    execute_response = client.post(
        '/api/execute',
        json={
            'task_description': 'update organization workspace settings for the team',
            'context': {'target_scope': 'organization'},
        },
    )
    assert execute_response.status_code == 200
    execute_payload = execute_response.json()
    assert execute_payload['execution_status'] == 'hitl_required'
    assert execute_payload['recovery']['gate_enforcement_summary']['hitl_scope'] == 'organization'

    operator_summary = client.get('/api/operator/runtime-summary').json()
    ops_status = client.get('/api/ops/status').json()
    founder_snapshot = client.get('/api/founder/visibility').json()

    assert operator_summary['recent_execution_outcomes']['latest_hitl_scope'] == 'organization'
    assert operator_summary['recent_execution_outcomes']['hitl_scope_counts']['organization'] >= 1
    assert ops_status['recent_execution_outcomes']['latest_hitl_scope'] == 'organization'
    assert ops_status['recent_execution_outcomes']['hitl_scope_counts']['organization'] >= 1
    assert founder_snapshot['recent_execution_outcomes']['latest_hitl_scope'] == 'organization'
    assert founder_snapshot['recent_execution_outcomes']['hitl_scope_counts']['organization'] >= 1
