from __future__ import annotations

from dataclasses import dataclass

from .capabilities import CapabilityService
from .config import CoreConfig
from .executor import CoreExecutor
from .gates import GatePipeline
from .planner import CorePlanner
from .providers import CoreProviderService
from .registry import ModuleRegistry
from .rosetta import RosettaCore
from .routing import CoreRouter
from .tracing import TraceStore


@dataclass
class CoreServices:
    config: CoreConfig
    registry: ModuleRegistry
    capabilities: CapabilityService
    providers: CoreProviderService
    rosetta: RosettaCore
    gates: GatePipeline
    router: CoreRouter
    planner: CorePlanner
    executor: CoreExecutor
    traces: TraceStore


def build_services(config: CoreConfig | None = None) -> CoreServices:
    cfg = config or CoreConfig.from_env()
    registry = ModuleRegistry()
    capabilities = CapabilityService(registry)
    providers = CoreProviderService(preferred_provider=cfg.default_provider)
    rosetta = RosettaCore()
    gates = GatePipeline()
    router = CoreRouter()
    planner = CorePlanner()
    executor = CoreExecutor()
    traces = TraceStore()
    return CoreServices(
        config=cfg,
        registry=registry,
        capabilities=capabilities,
        providers=providers,
        rosetta=rosetta,
        gates=gates,
        router=router,
        planner=planner,
        executor=executor,
        traces=traces,
    )
