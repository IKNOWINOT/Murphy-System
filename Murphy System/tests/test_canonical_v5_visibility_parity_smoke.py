from fastapi.testclient import TestClient

from src.murphy_core.app_v3_canonical_execution_surface_v5 import create_app


def test_canonical_v5_recent_outcome_visibility_surfaces_stay_in_parity():
    app = create_app()

    async def fake_execute(request, plan):
        return {
            'success': True,
            'status': 'fallback_completed',
            'fallback_route': 'legacy_adapter',
            'fallback_result': {'adapter': 'legacy_adapter', 'status': 'simulated'},
            'gate_enforcement_summary': {'blocking_gates': ['security']},
            'enforcement_summary': {'blocked': False},
        }

    app.state.services.executor.execute = fake_execute
    client = TestClient(app)

    execute_response = client.post('/api/execute', json={'task_description': 'fallback me'})
    assert execute_response.status_code == 200
    execute_payload = execute_response.json()
    assert execute_payload['execution_status'] == 'fallback_completed'

    operator_runtime = client.get('/api/operator/runtime').json()
    operator_summary = client.get('/api/operator/runtime-summary').json()
    ops_status = client.get('/api/ops/status').json()
    dashboard = client.get('/api/ui/runtime-dashboard').json()
    founder_summary = client.get('/api/founder/visibility-summary').json()
    founder_snapshot = client.get('/api/founder/visibility').json()

    assert operator_runtime['recent_execution_outcomes']['latest_status'] == 'fallback_completed'
    assert operator_summary['recent_execution_outcomes']['latest_status'] == 'fallback_completed'
    assert ops_status['recent_execution_outcomes']['latest_status'] == 'fallback_completed'
    assert dashboard['recent_execution_outcomes']['latest_status'] == 'fallback_completed'
    assert founder_summary['latest_execution_status'] == 'fallback_completed'
    assert founder_snapshot['recent_execution_outcomes']['latest_status'] == 'fallback_completed'

    assert operator_runtime['recent_execution_outcomes']['fallback_engaged'] >= 1
    assert operator_summary['recent_execution_outcomes']['fallback_engaged'] >= 1
    assert ops_status['recent_execution_outcomes']['fallback_engaged'] >= 1
    assert dashboard['recent_execution_outcomes']['fallback_engaged'] >= 1
    assert founder_summary['recent_fallback_engaged'] >= 1
    assert founder_snapshot['recent_execution_outcomes']['fallback_engaged'] >= 1
