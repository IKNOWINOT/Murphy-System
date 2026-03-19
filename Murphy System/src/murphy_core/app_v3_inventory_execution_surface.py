from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .capability_gating import CapabilityGatingService
from .config import CoreConfig
from .contracts import ControlTrace, CoreRequest
from .executor import CoreExecutor
from .gate_service import AdapterBackedGateService
from .operations_status import OperationsStatus
from .operator_runtime_surface_v2 import OperatorRuntimeSurfaceV2
from .operator_status_runtime import ConfigurableOperatorStatusService
from .planner import CorePlanner
from .production_inventory import ProductionInventory
from .provider_service import AdapterBackedProviderService
from .registry import ModuleRegistry
from .rosetta import RosettaCore
from .routing import CoreRouter
from .system_map import SystemMapService
from .tracing import TraceStore
from .ui_runtime_dashboard import UIRuntimeDashboard


class CoreV3InventoryExecutionSurfaceServices:
    def __init__(self, config: CoreConfig | None = None) -> None:
        self.config = config or CoreConfig.from_env()
        self.registry = ModuleRegistry()
        self.providers = AdapterBackedProviderService(config=self.config)
        self.gates = AdapterBackedGateService()
        self.capability_gates = CapabilityGatingService(self.registry)
        self.rosetta = RosettaCore()
        self.router = CoreRouter()
        self.planner = CorePlanner()
        self.executor = CoreExecutor()
        self.traces = TraceStore()
        self.system_map = SystemMapService(self.registry, self.router)
        self.operator_status = ConfigurableOperatorStatusService(
            self.config,
            self.registry,
            self.providers,
            self.gates,
            self.system_map,
            preferred_factory="murphy_core_v3",
        )
        self.runtime_surface = OperatorRuntimeSurfaceV2(self.operator_status)
        self.production_inventory = ProductionInventory()
        self.ui_dashboard = UIRuntimeDashboard(self.runtime_surface)
        self.ops_status = OperationsStatus(self.runtime_surface)


def create_app() -> FastAPI:
    services = CoreV3InventoryExecutionSurfaceServices()
    app = FastAPI(
        title=services.config.app_name,
        description="Murphy System inventory execution surface with capability-aware gating",
        version=services.config.version,
    )
    app.state.services = services

    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID", str(uuid4()))
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response

    @app.get("/api/health")
    async def health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "healthy",
                "service": "murphy_core_v3_inventory_execution_surface",
                "environment": services.config.environment,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    @app.get("/api/readiness")
    async def readiness() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ready",
                "service": "murphy_core_v3_inventory_execution_surface",
                "provider_health": services.providers.health(),
                "gate_health": services.gates.health(),
                "runtime_hints": services.router.runtime_hints(),
                "runtime_summary": services.runtime_surface.ui_summary(),
                "inventory_validation": services.production_inventory.validate(),
                "capability_gate": {"name": "capability_selection", "enabled": True},
            }
        )

    @app.get("/api/operator/runtime")
    async def operator_runtime() -> JSONResponse:
        return JSONResponse({"success": True, **services.runtime_surface.snapshot()})

    @app.get("/api/operator/runtime-summary")
    async def operator_runtime_summary() -> JSONResponse:
        return JSONResponse({"success": True, **services.runtime_surface.ui_summary()})

    @app.get("/api/operator/production-inventory")
    async def production_inventory() -> JSONResponse:
        return JSONResponse({"success": True, **services.production_inventory.to_dict()})

    @app.get("/api/operator/production-inventory-summary")
    async def production_inventory_summary() -> JSONResponse:
        inventory = services.production_inventory.to_dict()
        return JSONResponse(
            {
                "success": True,
                "runtime_order": inventory["runtime_order"],
                "family_count": inventory["validation"]["family_count"],
                "validation": inventory["validation"],
                "by_layer": inventory["by_layer"],
            }
        )

    @app.get("/api/ui/runtime-dashboard")
    async def runtime_dashboard() -> JSONResponse:
        return JSONResponse({"success": True, **services.ui_dashboard.build()})

    @app.get("/api/ops/status")
    async def ops_status() -> JSONResponse:
        return JSONResponse({"success": True, **services.ops_status.snapshot()})

    @app.get("/api/ops/runbook")
    async def ops_runbook() -> JSONResponse:
        return JSONResponse({"success": True, "runbook": services.ops_status.runbook()})

    async def _run_core(message: str, session_id: str | None, mode: str, context: Dict[str, Any]) -> Dict[str, Any]:
        req = CoreRequest.new(message=message, session_id=session_id, mode=mode, context=context)
        trace = ControlTrace.new(req)
        services.traces.save(trace)

        inference = services.providers.infer(req)
        trace.inference_summary = inference.to_dict()
        services.traces.save(trace)

        rosetta_env = services.rosetta.normalize(inference)
        trace.rosetta_summary = rosetta_env.to_dict()
        services.traces.save(trace)

        generic_gates = services.gates.evaluate(inference, rosetta_env)
        capability_gate = services.capability_gates.to_gate_evaluation(inference, rosetta_env)
        gate_results = [*generic_gates, capability_gate]
        trace.gate_summaries = [g.to_dict() for g in gate_results]
        services.traces.save(trace)

        selected_route = services.router.select_route(inference, rosetta_env, gate_results)
        trace.route = selected_route.value
        services.traces.save(trace)

        expansion = services.planner.expand(inference, rosetta_env, selected_route)
        trace.selected_modules = expansion.selected_module_families
        services.traces.save(trace)

        plan = services.planner.compile_plan(expansion, gate_results, req.message)
        trace.execution_status = "planned"
        services.traces.save(trace)

        result = await services.executor.execute(req, plan)
        trace.execution_status = result.get("status", "completed")
        trace.outcome = result
        services.traces.save(trace)

        return {
            "success": result.get("success", True),
            "trace_id": trace.trace_id,
            "request_id": req.request_id,
            "route": selected_route.value,
            "gate_results": [g.to_dict() for g in gate_results],
            "capability_gate": capability_gate.to_dict(),
            "result": result,
        }

    @app.post("/api/chat")
    async def chat(request: Request) -> JSONResponse:
        body = await request.json()
        message = body.get("message", "")
        if not message:
            raise HTTPException(status_code=400, detail="message is required")
        result = await _run_core(message, body.get("session_id"), "chat", body.get("context", {}))
        return JSONResponse(result)

    @app.post("/api/execute")
    async def execute(request: Request) -> JSONResponse:
        body = await request.json()
        message = body.get("task_description") or body.get("message") or ""
        if not message:
            raise HTTPException(status_code=400, detail="task_description or message is required")
        result = await _run_core(
            message,
            body.get("session_id"),
            "execute",
            body.get("parameters", {}) or body.get("context", {}),
        )
        return JSONResponse(result)

    @app.get("/api/traces/recent")
    async def recent_traces(limit: int = 20) -> JSONResponse:
        recent = [t.to_dict() for t in services.traces.recent(limit)]
        return JSONResponse({"success": True, "traces": recent, "count": len(recent)})

    @app.get("/api/traces/{trace_id}")
    async def get_trace(trace_id: str) -> JSONResponse:
        trace = services.traces.get(trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail="trace not found")
        return JSONResponse({"success": True, "trace": trace.to_dict()})

    return app
