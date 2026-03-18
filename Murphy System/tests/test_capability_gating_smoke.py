from src.murphy_core.capability_gating import CapabilityGatingService
from src.murphy_core.config import CoreConfig
from src.murphy_core.provider_service import AdapterBackedProviderService
from src.murphy_core.registry import ModuleRegistry
from src.murphy_core.rosetta import RosettaCore


def test_capability_gating_returns_gate_evaluation():
    registry = ModuleRegistry()
    provider = AdapterBackedProviderService(config=CoreConfig(default_provider="local_rules"))
    request = provider.infer.__self__.adapters["local_rules"].infer.__globals__["CoreRequest"].new(
        "build a workflow with security review"
    )
    inference = provider.infer(request)
    rosetta = RosettaCore().normalize(inference)
    gating = CapabilityGatingService(registry)
    result = gating.to_gate_evaluation(inference, rosetta)
    assert result.gate_name == "capability_selection"
    assert result.decision
    assert isinstance(result.metadata, dict)


def test_capability_gating_reports_module_buckets():
    registry = ModuleRegistry()
    provider = AdapterBackedProviderService(config=CoreConfig(default_provider="local_rules"))
    request = provider.infer.__self__.adapters["local_rules"].infer.__globals__["CoreRequest"].new(
        "run a swarm task"
    )
    inference = provider.infer(request)
    rosetta = RosettaCore().normalize(inference)
    gating = CapabilityGatingService(registry)
    result = gating.evaluate_capabilities(inference, rosetta)
    assert "eligible_modules" in result
    assert "review_required_modules" in result
    assert "blocked_modules" in result
