from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .capabilities import CapabilityService
from .contracts import ControlTrace, CoreRequest
from .executor import CoreExecutor
from .gates import GatePipeline
from .planner import CorePlanner
from .providers import CoreProviderService
from .registry import ModuleRegistry
from .rosetta import RosettaCore
from .routing import CoreRouter
from .tracing import TraceStore


def create_app() -> FastAPI:
    app = FastAPI(
        title="Murphy Core",
        description="Canonical typed runtime spine for Murphy System",
        version="0.1.0",
    )

    registry = ModuleRegistry()
    capabilities = CapabilityService(registry)
    providers = CoreProviderService()
    rosetta = RosettaCore()
    gates = GatePipeline()
    router = CoreRouter()
    planner = CorePlanner()
    executor = CoreExecutor()
    traces = TraceStore()

    app.state.registry = registry
    app.state.capabilities = capabilities
    app.state.providers = providers
    app.state.rosetta = rosetta
    app.state.gates = gates
    app.state.router = router
    app.state.planner = planner
    app.state.executor = executor
    app.state.traces = traces

    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID", str(uuid4()))
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response

    @app.get("/api/health")
    async def health() -> JSONResponse:
        return JSONResponse({
            "status": "healthy",
            "service": "murphy_core",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @app.get("/api/readiness")
    async def readiness() -> JSONResponse:
        runtime_hints = router.runtime_hints()
        return JSONResponse({
            "status": "ready",
            "core": {
                "registry_loaded": True,
                "provider_layer": True,
                "rosetta": True,
                "gate_pipeline": True,
                "router": True,
                "planner": True,
                "executor": True,
                "trace_store": True,
            },
            "adapters": runtime_hints,
        })

    @app.get("/api/capabilities/effective")
    async def effective_capabilities() -> JSONResponse:
        return JSONResponse({"success": True, **capabilities.effective_capabilities()})

    @app.get("/api/registry/modules")
    async def registry_modules() -> JSONResponse:
        return JSONResponse({"success": True, "modules": registry.to_dicts(), "count": len(registry.to_dicts())})

    @app.get("/api/system/map")
    async def system_map() -> JSONResponse:
        return JSONResponse({
            "success": True,
            "canonical_path": [
                "request",
                "inference",
                "rosetta",
                "gates",
                "routing",
                "planner",
                "execution",
                "trace",
                "delivery",
            ],
            "runtime_hints": router.runtime_hints(),
        })

    async def _run_core(message: str, session_id: str | None, mode: str, context: Dict[str, Any]) -> Dict[str, Any]:
        req = CoreRequest.new(message=message, session_id=session_id, mode=mode, context=context)
        trace = ControlTrace.new(req)
        traces.save(trace)

        inference = providers.infer(req)
        trace.inference_summary = inference.to_dict()
        traces.save(trace)

        rosetta_env = rosetta.normalize(inference)
        trace.rosetta_summary = rosetta_env.to_dict()
        traces.save(trace)

        gate_results = gates.evaluate(inference, rosetta_env)
        trace.gate_summaries = [g.to_dict() for g in gate_results]
        traces.save(trace)

        selected_route = router.select_route(inference, rosetta_env, gate_results)
        trace.route = selected_route.value
        traces.save(trace)

        expansion = planner.expand(inference, rosetta_env, selected_route)
        trace.selected_modules = expansion.selected_module_families
        traces.save(trace)

        plan = planner.compile_plan(expansion, gate_results, req.message)
        trace.execution_status = "planned"
        traces.save(trace)

        result = await executor.execute(req, plan)
        trace.execution_status = result.get("status", "completed")
        trace.outcome = result
        traces.save(trace)

        return {
            "success": result.get("success", True),
            "trace_id": trace.trace_id,
            "request_id": req.request_id,
            "route": selected_route.value,
            "gate_results": [g.to_dict() for g in gate_results],
            "result": result,
        }

    @app.post("/api/chat")
    async def chat(request: Request) -> JSONResponse:
        body = await request.json()
        message = body.get("message", "")
        if not message:
            raise HTTPException(status_code=400, detail="message is required")
        result = await _run_core(
            message=message,
            session_id=body.get("session_id"),
            mode="chat",
            context=body.get("context", {}),
        )
        return JSONResponse(result)

    @app.post("/api/execute")
    async def execute(request: Request) -> JSONResponse:
        body = await request.json()
        message = body.get("task_description") or body.get("message") or ""
        if not message:
            raise HTTPException(status_code=400, detail="task_description or message is required")
        result = await _run_core(
            message=message,
            session_id=body.get("session_id"),
            mode="execute",
            context=body.get("parameters", {}) or body.get("context", {}),
        )
        return JSONResponse(result)

    @app.get("/api/traces/recent")
    async def recent_traces(limit: int = 20) -> JSONResponse:
        recent = [t.to_dict() for t in traces.recent(limit)]
        return JSONResponse({"success": True, "traces": recent, "count": len(recent)})

    @app.get("/api/traces/{trace_id}")
    async def get_trace(trace_id: str) -> JSONResponse:
        trace = traces.get(trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail="trace not found")
        return JSONResponse({"success": True, "trace": trace.to_dict()})

    return app
