from fastapi.testclient import TestClient

from src.murphy_core.app_v3_canonical_execution_surface_v5 import create_app


def _exercise_surfaces(fake_result: dict, task_description: str = 'test task'):
    app = create_app()

    async def fake_execute(request, plan):
        return fake_result

    app.state.services.executor.execute = fake_execute
    client = TestClient(app)

    execute_response = client.post('/api/execute', json={'task_description': task_description})
    assert execute_response.status_code == 200
    execute_payload = execute_response.json()

    return {
        'execute': execute_payload,
        'operator_runtime': client.get('/api/operator/runtime').json(),
        'operator_summary': client.get('/api/operator/runtime-summary').json(),
        'ops_status': client.get('/api/ops/status').json(),
        'dashboard': client.get('/api/ui/runtime-dashboard').json(),
        'founder_summary': client.get('/api/founder/visibility-summary').json(),
        'founder_snapshot': client.get('/api/founder/visibility').json(),
    }


def test_canonical_v5_recent_outcome_visibility_surfaces_stay_in_parity_for_fallback():
    payloads = _exercise_surfaces(
        {
            'success': True,
            'status': 'fallback_completed',
            'fallback_route': 'legacy_adapter',
            'fallback_result': {'adapter': 'legacy_adapter', 'status': 'simulated'},
            'gate_enforcement_summary': {'blocking_gates': ['security']},
            'enforcement_summary': {'blocked': False},
        },
        task_description='fallback me',
    )

    assert payloads['execute']['execution_status'] == 'fallback_completed'
    assert payloads['operator_runtime']['recent_execution_outcomes']['latest_status'] == 'fallback_completed'
    assert payloads['operator_summary']['recent_execution_outcomes']['latest_status'] == 'fallback_completed'
    assert payloads['ops_status']['recent_execution_outcomes']['latest_status'] == 'fallback_completed'
    assert payloads['dashboard']['recent_execution_outcomes']['latest_status'] == 'fallback_completed'
    assert payloads['founder_summary']['latest_execution_status'] == 'fallback_completed'
    assert payloads['founder_snapshot']['recent_execution_outcomes']['latest_status'] == 'fallback_completed'

    assert payloads['operator_runtime']['recent_execution_outcomes']['fallback_engaged'] >= 1
    assert payloads['operator_summary']['recent_execution_outcomes']['fallback_engaged'] >= 1
    assert payloads['ops_status']['recent_execution_outcomes']['fallback_engaged'] >= 1
    assert payloads['dashboard']['recent_execution_outcomes']['fallback_engaged'] >= 1
    assert payloads['founder_summary']['recent_fallback_engaged'] >= 1
    assert payloads['founder_snapshot']['recent_execution_outcomes']['fallback_engaged'] >= 1


def test_canonical_v5_recent_outcome_visibility_surfaces_stay_in_parity_for_review():
    payloads = _exercise_surfaces(
        {
            'success': False,
            'status': 'review_required',
            'gate_enforcement_summary': {'requires_review': True},
            'enforcement_summary': {'blocked': False},
        },
        task_description='review me',
    )

    assert payloads['execute']['execution_status'] == 'review_required'
    assert payloads['execute']['approval_pending'] is True
    assert payloads['operator_runtime']['recent_execution_outcomes']['latest_status'] == 'review_required'
    assert payloads['operator_summary']['recent_execution_outcomes']['latest_status'] == 'review_required'
    assert payloads['ops_status']['recent_execution_outcomes']['latest_status'] == 'review_required'
    assert payloads['dashboard']['recent_execution_outcomes']['latest_status'] == 'review_required'
    assert payloads['founder_summary']['latest_execution_status'] == 'review_required'
    assert payloads['founder_snapshot']['recent_execution_outcomes']['latest_status'] == 'review_required'

    assert payloads['operator_runtime']['recent_execution_outcomes']['approval_pending'] >= 1
    assert payloads['operator_summary']['recent_execution_outcomes']['approval_pending'] >= 1
    assert payloads['ops_status']['recent_execution_outcomes']['approval_pending'] >= 1
    assert payloads['dashboard']['recent_execution_outcomes']['approval_pending'] >= 1
    assert payloads['founder_summary']['recent_approval_pending'] >= 1
    assert payloads['founder_snapshot']['recent_execution_outcomes']['approval_pending'] >= 1


def test_canonical_v5_recent_outcome_visibility_surfaces_stay_in_parity_for_hitl():
    payloads = _exercise_surfaces(
        {
            'success': False,
            'status': 'hitl_required',
            'gate_enforcement_summary': {'requires_hitl': True},
            'enforcement_summary': {'blocked': False},
        },
        task_description='hitl me',
    )

    assert payloads['execute']['execution_status'] == 'hitl_required'
    assert payloads['execute']['approval_pending'] is True
    assert payloads['operator_runtime']['recent_execution_outcomes']['latest_status'] == 'hitl_required'
    assert payloads['operator_summary']['recent_execution_outcomes']['latest_status'] == 'hitl_required'
    assert payloads['ops_status']['recent_execution_outcomes']['latest_status'] == 'hitl_required'
    assert payloads['dashboard']['recent_execution_outcomes']['latest_status'] == 'hitl_required'
    assert payloads['founder_summary']['latest_execution_status'] == 'hitl_required'
    assert payloads['founder_snapshot']['recent_execution_outcomes']['latest_status'] == 'hitl_required'

    assert payloads['operator_runtime']['recent_execution_outcomes']['approval_pending'] >= 1
    assert payloads['operator_summary']['recent_execution_outcomes']['approval_pending'] >= 1
    assert payloads['ops_status']['recent_execution_outcomes']['approval_pending'] >= 1
    assert payloads['dashboard']['recent_execution_outcomes']['approval_pending'] >= 1
    assert payloads['founder_summary']['recent_approval_pending'] >= 1
    assert payloads['founder_snapshot']['recent_execution_outcomes']['approval_pending'] >= 1


def test_canonical_v5_recent_outcome_visibility_surfaces_stay_in_parity_for_blocked():
    payloads = _exercise_surfaces(
        {
            'success': False,
            'status': 'blocked',
            'gate_enforcement_summary': {'blocking_gates': ['security']},
            'enforcement_summary': {'blocked': True},
        },
        task_description='block me',
    )

    assert payloads['execute']['execution_status'] == 'blocked'
    assert payloads['execute']['blocked'] is True
    assert payloads['operator_runtime']['recent_execution_outcomes']['latest_status'] == 'blocked'
    assert payloads['operator_summary']['recent_execution_outcomes']['latest_status'] == 'blocked'
    assert payloads['ops_status']['recent_execution_outcomes']['latest_status'] == 'blocked'
    assert payloads['dashboard']['recent_execution_outcomes']['latest_status'] == 'blocked'
    assert payloads['founder_summary']['latest_execution_status'] == 'blocked'
    assert payloads['founder_snapshot']['recent_execution_outcomes']['latest_status'] == 'blocked'

    assert payloads['operator_runtime']['recent_execution_outcomes']['blocked'] >= 1
    assert payloads['operator_summary']['recent_execution_outcomes']['blocked'] >= 1
    assert payloads['ops_status']['recent_execution_outcomes']['blocked'] >= 1
    assert payloads['dashboard']['recent_execution_outcomes']['blocked'] >= 1
    assert payloads['founder_summary']['recent_blocked'] >= 1
    assert payloads['founder_snapshot']['recent_execution_outcomes']['blocked'] >= 1
