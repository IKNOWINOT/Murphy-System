from fastapi.testclient import TestClient

from src.murphy_core.app_v3_canonical_execution_surface_v5 import create_app
from src.murphy_core.provider_adapters import LocalRulesAdapter
from src.murphy_core.contracts import CoreRequest
from src.murphy_core.gate_adapters import DefaultHITLGateAdapter
from src.murphy_core.rosetta import RosettaCore


def test_local_rules_routes_platform_change_to_founder_hitl_requirement():
    adapter = LocalRulesAdapter()
    request = CoreRequest.new(
        message='change the platform runtime and add code to the repo',
        mode='execute',
        context={'target_scope': 'platform'},
    )

    inference = adapter.infer(request)

    assert inference.constraints['target_scope'] == 'platform'
    assert inference.constraints['platform_change'] is True
    assert inference.constraints['organization_change'] is False
    assert 'founder_hitl' in inference.required_approvals
    assert 'org_hitl' not in inference.required_approvals


def test_local_rules_routes_org_change_to_org_hitl_requirement():
    adapter = LocalRulesAdapter()
    request = CoreRequest.new(
        message='update organization workspace settings for the team',
        mode='execute',
        context={'target_scope': 'organization'},
    )

    inference = adapter.infer(request)

    assert inference.constraints['target_scope'] == 'organization'
    assert inference.constraints['platform_change'] is False
    assert inference.constraints['organization_change'] is True
    assert 'org_hitl' in inference.required_approvals
    assert 'founder_hitl' not in inference.required_approvals


def test_hitl_gate_marks_founder_scope_for_platform_change():
    adapter = LocalRulesAdapter()
    rosetta = RosettaCore()
    gate = DefaultHITLGateAdapter()
    request = CoreRequest.new(
        message='change the platform runtime and patch the codebase',
        mode='execute',
        context={'target_scope': 'platform'},
    )

    inference = adapter.infer(request)
    rosetta_env = rosetta.normalize(inference)
    evaluation = gate.evaluate(inference, rosetta_env)

    assert evaluation.decision.value == 'requires_hitl'
    assert evaluation.metadata['hitl_scope'] == 'founder'
    assert evaluation.metadata['target_scope'] == 'platform'


def test_hitl_gate_marks_org_scope_for_organization_change():
    adapter = LocalRulesAdapter()
    rosetta = RosettaCore()
    gate = DefaultHITLGateAdapter()
    request = CoreRequest.new(
        message='change organization billing workflow for the workspace',
        mode='execute',
        context={'target_scope': 'organization'},
    )

    inference = adapter.infer(request)
    rosetta_env = rosetta.normalize(inference)
    evaluation = gate.evaluate(inference, rosetta_env)

    assert evaluation.decision.value == 'requires_hitl'
    assert evaluation.metadata['hitl_scope'] == 'organization'
    assert evaluation.metadata['target_scope'] == 'organization'


def test_canonical_v5_platform_change_exposes_founder_hitl_scope():
    client = TestClient(create_app())
    response = client.post(
        '/api/execute',
        json={
            'task_description': 'change the platform runtime and add code to the repo',
            'context': {'target_scope': 'platform'},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['execution_status'] == 'hitl_required'
    assert payload['approval_pending'] is True
    assert payload['recovery']['gate_enforcement_summary']['hitl_scope'] == 'founder'
    assert payload['recovery']['gate_enforcement_summary']['target_scope'] == 'platform'


def test_canonical_v5_org_change_exposes_org_hitl_scope():
    client = TestClient(create_app())
    response = client.post(
        '/api/execute',
        json={
            'task_description': 'update organization workspace settings for the team',
            'context': {'target_scope': 'organization'},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['execution_status'] == 'hitl_required'
    assert payload['approval_pending'] is True
    assert payload['recovery']['gate_enforcement_summary']['hitl_scope'] == 'organization'
    assert payload['recovery']['gate_enforcement_summary']['target_scope'] == 'organization'
