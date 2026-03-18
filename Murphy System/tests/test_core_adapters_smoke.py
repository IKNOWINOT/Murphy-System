from src.murphy_core.contracts import CoreRequest
from src.murphy_core.gate_adapters import (
    DefaultBudgetGateAdapter,
    DefaultComplianceGateAdapter,
    DefaultConfidenceGateAdapter,
    DefaultHITLGateAdapter,
    DefaultSecurityGateAdapter,
)
from src.murphy_core.provider_adapters import LegacyMurphyInferenceAdapter, LocalRulesAdapter
from src.murphy_core.rosetta import RosettaCore


def test_local_rules_adapter_infers():
    adapter = LocalRulesAdapter()
    request = CoreRequest.new("build a production workflow for invoice processing")
    inference = adapter.infer(request)
    assert inference.request_id == request.request_id
    assert inference.provider == "local_rules"
    assert inference.intent


def test_legacy_murphy_adapter_has_health():
    adapter = LegacyMurphyInferenceAdapter()
    health = adapter.health()
    assert health.provider_name == "legacy_murphy"
    assert isinstance(health.available, bool)


def test_default_gate_adapters_evaluate():
    provider = LocalRulesAdapter()
    request = CoreRequest.new("build a production workflow for compliance review")
    inference = provider.infer(request)
    rosetta = RosettaCore().normalize(inference)

    for gate in [
        DefaultSecurityGateAdapter(),
        DefaultComplianceGateAdapter(),
        DefaultConfidenceGateAdapter(),
        DefaultHITLGateAdapter(),
        DefaultBudgetGateAdapter(),
    ]:
        result = gate.evaluate(inference, rosetta)
        assert result.gate_name
        assert result.decision
