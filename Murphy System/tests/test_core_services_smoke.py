from src.murphy_core.config import CoreConfig
from src.murphy_core.contracts import CoreRequest
from src.murphy_core.gate_service import AdapterBackedGateService
from src.murphy_core.provider_service import AdapterBackedProviderService
from src.murphy_core.rosetta import RosettaCore


def test_provider_service_health():
    service = AdapterBackedProviderService(config=CoreConfig(default_provider="local_rules"))
    health = service.health()
    assert health["preferred_provider"] == "local_rules"
    assert isinstance(health["providers"], list)
    assert len(health["providers"]) >= 1


def test_provider_service_infer():
    service = AdapterBackedProviderService(config=CoreConfig(default_provider="local_rules"))
    request = CoreRequest.new("build a workflow for invoice processing")
    inference = service.infer(request)
    assert inference.request_id == request.request_id
    assert inference.provider
    assert inference.provider_metadata["selected_provider"]


def test_gate_service_health_and_evaluate():
    provider = AdapterBackedProviderService(config=CoreConfig(default_provider="local_rules"))
    gate_service = AdapterBackedGateService()
    request = CoreRequest.new("build a production workflow for compliance review")
    inference = provider.infer(request)
    rosetta = RosettaCore().normalize(inference)

    health = gate_service.health()
    assert isinstance(health["gates"], list)
    assert len(health["gates"]) >= 1

    results = gate_service.evaluate(inference, rosetta)
    assert isinstance(results, list)
    assert len(results) >= 1
    assert all(result.gate_name for result in results)
