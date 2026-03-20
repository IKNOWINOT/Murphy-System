from fastapi.testclient import TestClient

from src.murphy_core.app_v3_canonical_execution_surface_v5 import create_app


client = TestClient(create_app())


def test_canonical_execution_surface_v5_health_identity():
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['service'] == 'murphy_core_v3_canonical_execution_surface_v5'


def test_canonical_execution_surface_v5_execute_includes_family_selection():
    response = client.post('/api/execute', json={'task_description': 'run a swarm task'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert 'subsystem_family_selection' in payload
    assert 'selected_families' in payload['subsystem_family_selection']


def test_canonical_execution_surface_v5_readiness_flags_founder_overlay():
    response = client.get('/api/readiness')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ready'
    assert payload['founder_visibility_overlay']['enabled'] is True


def test_canonical_execution_surface_v5_execute_exposes_execution_status_and_recovery():
    response = client.post('/api/execute', json={'task_description': 'run a deterministic task'})
    assert response.status_code == 200
    payload = response.json()
    assert 'execution_status' in payload
    assert 'recovery' in payload
    assert payload['recovery']['plan_route'] == payload['route']
    assert 'fallback_policy' in payload['recovery']


def test_canonical_execution_surface_v5_trace_persists_recovery_state():
    response = client.post('/api/execute', json={'task_description': 'run a deterministic task'})
    assert response.status_code == 200
    payload = response.json()
    trace_id = payload['trace_id']

    trace_response = client.get(f'/api/traces/{trace_id}')
    assert trace_response.status_code == 200
    trace_payload = trace_response.json()['trace']
    assert trace_payload['execution_status'] == payload['execution_status']
    assert trace_payload['recovery']['plan_route'] == payload['route']
    assert 'final_status' in trace_payload['recovery']


def test_canonical_execution_surface_v5_reports_approval_pending_for_review():
    app = create_app()

    async def fake_execute(request, plan):
        return {
            'success': False,
            'status': 'review_required',
            'gate_enforcement_summary': {'requires_review': True},
            'enforcement_summary': {'blocked': False},
        }

    app.state.services.executor.execute = fake_execute
    local_client = TestClient(app)
    response = local_client.post('/api/execute', json={'task_description': 'review me'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['execution_status'] == 'review_required'
    assert payload['approval_pending'] is True
    assert payload['fallback_engaged'] is False
    assert payload['blocked'] is False


def test_canonical_execution_surface_v5_reports_fallback_engaged():
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
    local_client = TestClient(app)
    response = local_client.post('/api/execute', json={'task_description': 'fallback me'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['execution_status'] == 'fallback_completed'
    assert payload['approval_pending'] is False
    assert payload['fallback_engaged'] is True
    assert payload['blocked'] is False


def test_canonical_execution_surface_v5_reports_blocked_state():
    app = create_app()

    async def fake_execute(request, plan):
        return {
            'success': False,
            'status': 'blocked',
            'gate_enforcement_summary': {'blocking_gates': ['security']},
            'enforcement_summary': {'blocked': True},
        }

    app.state.services.executor.execute = fake_execute
    local_client = TestClient(app)
    response = local_client.post('/api/execute', json={'task_description': 'block me'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['execution_status'] == 'blocked'
    assert payload['approval_pending'] is False
    assert payload['fallback_engaged'] is False
    assert payload['blocked'] is True
