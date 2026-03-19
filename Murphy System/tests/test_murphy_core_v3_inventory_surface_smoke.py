from fastapi.testclient import TestClient

from src.murphy_core.app_v3_inventory_surface import create_app


client = TestClient(create_app())


def test_production_inventory_endpoint_exists():
    response = client.get('/api/operator/production-inventory')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert 'runtime_order' in payload
    assert 'families' in payload
    assert payload['validation']['family_count'] >= 1


def test_production_inventory_summary_endpoint_exists():
    response = client.get('/api/operator/production-inventory-summary')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert 'runtime_order' in payload
    assert 'by_layer' in payload


def test_ui_and_ops_inventory_surface_endpoints_exist():
    response_dashboard = client.get('/api/ui/runtime-dashboard')
    response_ops = client.get('/api/ops/status')
    response_runbook = client.get('/api/ops/runbook')
    assert response_dashboard.status_code == 200
    assert response_ops.status_code == 200
    assert response_runbook.status_code == 200
