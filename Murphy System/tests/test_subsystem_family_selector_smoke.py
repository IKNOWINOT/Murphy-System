from src.murphy_core.capability_gating import CapabilityGatingService
from src.murphy_core.config import CoreConfig
from src.murphy_core.contracts import CoreRequest, RouteType
from src.murphy_core.provider_service import AdapterBackedProviderService
from src.murphy_core.registry import ModuleRegistry
from src.murphy_core.rosetta import RosettaCore
from src.murphy_core.subsystem_family_selector import SubsystemFamilySelector


def test_subsystem_family_selector_selects_swarm_family():
    registry = ModuleRegistry()
    provider = AdapterBackedProviderService(config=CoreConfig(default_provider="local_rules"))
    request = CoreRequest.new(message="run a swarm task")
    inference = provider.infer(request)
    rosetta = RosettaCore().normalize(inference)
    capability_gate = CapabilityGatingService(registry).to_gate_evaluation(inference, rosetta)
    selector = SubsystemFamilySelector()
    result = selector.select(inference, rosetta, [capability_gate], RouteType.SWARM)
    assert result["primary_family"]
    assert "swarms_bots_agents" in result["selected_families"]


def test_subsystem_family_selector_selects_workflow_family():
    registry = ModuleRegistry()
    provider = AdapterBackedProviderService(config=CoreConfig(default_provider="local_rules"))
    request = CoreRequest.new(message="build a workflow plan with security review")
    inference = provider.infer(request)
    rosetta = RosettaCore().normalize(inference)
    capability_gate = CapabilityGatingService(registry).to_gate_evaluation(inference, rosetta)
    selector = SubsystemFamilySelector()
    result = selector.select(inference, rosetta, [capability_gate], RouteType.HYBRID)
    assert result["selected_families"]
    assert "workflow_compiler_storage" in result["selected_families"]
