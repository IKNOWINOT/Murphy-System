# Copyright © 2026 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Murphy-Conductor HTTP surface — R77.P1 (2026-06-07)

WHAT THIS IS
  HTTP routes that expose the pure-functional state_machine.evaluate
  + apply_* primitives. In-process registry of active workflows
  (Phase 1 — Phase 2 will persist to sqlite).

WHY
  Founder R77 directive: every aspect of the architecture must be
  callable through the webpage. The conductor was unwired. This is
  the wire.

DESIGN
  - One module-level dict (the registry) keyed by workflow_id.
  - Singleton accessor get_conductor_registry().
  - All routes thin: parse JSON → call state_machine fn → return JSON.
  - No LLM calls. No external HTTP. Sub-millisecond.

ROUTES
  GET    /api/conductor/healthz
  POST   /api/conductor/workflow                       create from WorkflowDef JSON
  GET    /api/conductor/workflow/{wf_id}               read runtime
  POST   /api/conductor/workflow/{wf_id}/evaluate      run evaluate(), return Decision
  POST   /api/conductor/workflow/{wf_id}/advance       advance_step + return Decision
  POST   /api/conductor/workflow/{wf_id}/task/{tid}/schedule
  POST   /api/conductor/workflow/{wf_id}/task/{tid}/start
  POST   /api/conductor/workflow/{wf_id}/task/{tid}/complete
  POST   /api/conductor/workflow/{wf_id}/task/{tid}/fail
  GET    /api/conductor/workflows                      list active

LICENSE: BSL 1.1
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────
# In-process registry (Phase 1) — Phase 2 swaps to sqlite
# ─────────────────────────────────────────────────────────────────────


class _ConductorRegistry:
    """Thread-safe in-memory store of (WorkflowDef, WorkflowRuntime) pairs."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # workflow_id -> {"def": WorkflowDef, "runtime": WorkflowRuntime, "created": float}
        self._workflows: Dict[str, Dict[str, Any]] = {}

    def put(self, wf_def, runtime) -> None:
        with self._lock:
            self._workflows[wf_def.workflow_id] = {
                "def": wf_def,
                "runtime": runtime,
                "created": time.time(),
            }

    def get(self, wf_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._workflows.get(wf_id)

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._workflows.values())

    def remove(self, wf_id: str) -> bool:
        with self._lock:
            return self._workflows.pop(wf_id, None) is not None


_REGISTRY: Optional[_ConductorRegistry] = None
_REGISTRY_LOCK = threading.Lock()


def get_conductor_registry() -> _ConductorRegistry:
    """Module singleton — survives across requests within a process."""
    global _REGISTRY
    if _REGISTRY is None:
        with _REGISTRY_LOCK:
            if _REGISTRY is None:
                _REGISTRY = _ConductorRegistry()
    return _REGISTRY


# ─────────────────────────────────────────────────────────────────────
# Serializers
# ─────────────────────────────────────────────────────────────────────


def _serialize_runtime(runtime) -> Dict[str, Any]:
    return {
        "workflow_id": runtime.workflow_id,
        "state": runtime.state.value if hasattr(runtime.state, "value") else str(runtime.state),
        "current_step_index": runtime.current_step_index,
        "started_at": runtime.started_at,
        "completed_at": runtime.completed_at,
        "tasks": {
            tid: {
                "task_id": tr.task_id,
                "state": tr.state.value if hasattr(tr.state, "value") else str(tr.state),
                "attempts": tr.attempts,
                "started_at": tr.started_at,
                "completed_at": tr.completed_at,
                "last_error": tr.last_error,
            }
            for tid, tr in runtime.tasks.items()
        },
    }


def _serialize_def(wf_def) -> Dict[str, Any]:
    return {
        "workflow_id": wf_def.workflow_id,
        "name": wf_def.name,
        "tenant_id": getattr(wf_def, "tenant_id", "inoni"),
        "steps": [
            {
                "step_id": step.step_id,
                "tasks": [
                    {
                        "task_id": t.task_id,
                        "task_type": t.task_type,
                        "payload": t.payload,
                        "max_attempts": t.max_attempts,
                        "max_run_seconds": t.max_run_seconds,
                        "optional": t.optional,
                    }
                    for t in step.tasks
                ],
            }
            for step in wf_def.steps
        ],
    }


def _serialize_decision(d) -> Dict[str, Any]:
    return {
        "to_schedule": list(d.to_schedule),
        "to_timeout": list(d.to_timeout),
        "to_retry": list(d.to_retry),
        "workflow_complete": d.workflow_complete,
        "workflow_failed": d.workflow_failed,
        "reason": d.reason,
    }


def _parse_workflow_def(payload: Dict[str, Any]):
    """Build a WorkflowDef from JSON payload."""
    from src.conductor.state_machine import StepDef, TaskDef, WorkflowDef

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be an object")
    if not payload.get("workflow_id") or not payload.get("name"):
        raise HTTPException(status_code=400, detail="workflow_id and name required")
    if not isinstance(payload.get("steps"), list) or not payload["steps"]:
        raise HTTPException(status_code=400, detail="steps required (non-empty list)")

    steps = []
    for s in payload["steps"]:
        if not isinstance(s, dict) or not s.get("step_id") or not isinstance(s.get("tasks"), list):
            raise HTTPException(status_code=400, detail="each step needs step_id + tasks[]")
        tasks = []
        for t in s["tasks"]:
            if not isinstance(t, dict) or not t.get("task_id") or not t.get("task_type"):
                raise HTTPException(
                    status_code=400, detail="each task needs task_id + task_type"
                )
            tasks.append(
                TaskDef(
                    task_id=t["task_id"],
                    task_type=t["task_type"],
                    payload=t.get("payload", {}),
                    max_attempts=int(t.get("max_attempts", 3)),
                    max_run_seconds=int(t.get("max_run_seconds", 300)),
                    optional=bool(t.get("optional", False)),
                )
            )
        steps.append(StepDef(step_id=s["step_id"], tasks=tasks))

    return WorkflowDef(
        workflow_id=payload["workflow_id"],
        name=payload["name"],
        steps=steps,
        tenant_id=payload.get("tenant_id", "inoni"),
    )


# ─────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────


@router.get("/api/conductor/healthz")
async def conductor_healthz() -> JSONResponse:
    """Sub-millisecond health probe."""
    return JSONResponse(
        {
            "ok": True,
            "module": "conductor.state_machine",
            "version": "R77.P1",
            "registry_size": len(get_conductor_registry().list_all()),
            "ts": time.time(),
        }
    )


@router.post("/api/conductor/workflow")
async def conductor_create_workflow(request: Request) -> JSONResponse:
    """Create a workflow. Body = WorkflowDef JSON. Returns runtime + def."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON")

    # Allow ?demo=1 shortcut to spawn the canonical demo workflow
    if not payload and request.query_params.get("demo") == "1":
        from src.conductor.state_machine import _build_demo_workflow

        wf_def = _build_demo_workflow()
        # Give it a unique id so multiple demo runs don't collide
        wf_def.workflow_id = f"wf_demo_{int(time.time() * 1000)}"
    else:
        wf_def = _parse_workflow_def(payload)

    from src.conductor.state_machine import WorkflowRuntime

    runtime = WorkflowRuntime(workflow_id=wf_def.workflow_id)
    runtime.started_at = time.time()

    reg = get_conductor_registry()
    if reg.get(wf_def.workflow_id):
        raise HTTPException(
            status_code=409, detail=f"workflow_id {wf_def.workflow_id} already exists"
        )
    reg.put(wf_def, runtime)

    return JSONResponse(
        {
            "ok": True,
            "workflow_id": wf_def.workflow_id,
            "definition": _serialize_def(wf_def),
            "runtime": _serialize_runtime(runtime),
        }
    )


@router.get("/api/conductor/workflow/{wf_id}")
async def conductor_get_workflow(wf_id: str) -> JSONResponse:
    """Read current definition + runtime for a workflow."""
    entry = get_conductor_registry().get(wf_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"workflow {wf_id} not found")
    return JSONResponse(
        {
            "ok": True,
            "workflow_id": wf_id,
            "definition": _serialize_def(entry["def"]),
            "runtime": _serialize_runtime(entry["runtime"]),
            "created": entry["created"],
        }
    )


@router.post("/api/conductor/workflow/{wf_id}/evaluate")
async def conductor_evaluate(wf_id: str) -> JSONResponse:
    """Run evaluate() — returns the Decision but does NOT apply it."""
    entry = get_conductor_registry().get(wf_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"workflow {wf_id} not found")

    from src.conductor.state_machine import evaluate

    decision = evaluate(entry["def"], entry["runtime"])
    return JSONResponse(
        {
            "ok": True,
            "workflow_id": wf_id,
            "decision": _serialize_decision(decision),
            "runtime": _serialize_runtime(entry["runtime"]),
        }
    )


@router.post("/api/conductor/workflow/{wf_id}/advance")
async def conductor_advance(wf_id: str) -> JSONResponse:
    """Call advance_step() then re-evaluate. Returns Decision."""
    entry = get_conductor_registry().get(wf_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"workflow {wf_id} not found")

    from src.conductor.state_machine import advance_step, evaluate

    try:
        advance_step(entry["runtime"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"advance_step failed: {exc}")
    decision = evaluate(entry["def"], entry["runtime"])
    return JSONResponse(
        {
            "ok": True,
            "workflow_id": wf_id,
            "decision": _serialize_decision(decision),
            "runtime": _serialize_runtime(entry["runtime"]),
        }
    )


@router.post("/api/conductor/workflow/{wf_id}/task/{task_id}/schedule")
async def conductor_task_schedule(wf_id: str, task_id: str) -> JSONResponse:
    """apply_schedule — worker acknowledges it's claiming the task."""
    entry = get_conductor_registry().get(wf_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"workflow {wf_id} not found")

    from src.conductor.state_machine import apply_schedule

    try:
        apply_schedule(entry["runtime"], task_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"apply_schedule failed: {exc}")
    return JSONResponse(
        {"ok": True, "workflow_id": wf_id, "task_id": task_id,
         "runtime": _serialize_runtime(entry["runtime"])}
    )


@router.post("/api/conductor/workflow/{wf_id}/task/{task_id}/start")
async def conductor_task_start(wf_id: str, task_id: str) -> JSONResponse:
    """apply_start — worker reports it has begun execution."""
    entry = get_conductor_registry().get(wf_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"workflow {wf_id} not found")

    from src.conductor.state_machine import apply_start

    try:
        apply_start(entry["runtime"], task_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"apply_start failed: {exc}")
    return JSONResponse(
        {"ok": True, "workflow_id": wf_id, "task_id": task_id,
         "runtime": _serialize_runtime(entry["runtime"])}
    )


@router.post("/api/conductor/workflow/{wf_id}/task/{task_id}/complete")
async def conductor_task_complete(wf_id: str, task_id: str) -> JSONResponse:
    """apply_complete — worker reports success."""
    entry = get_conductor_registry().get(wf_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"workflow {wf_id} not found")

    from src.conductor.state_machine import apply_complete

    try:
        apply_complete(entry["runtime"], task_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"apply_complete failed: {exc}")
    return JSONResponse(
        {"ok": True, "workflow_id": wf_id, "task_id": task_id,
         "runtime": _serialize_runtime(entry["runtime"])}
    )


@router.post("/api/conductor/workflow/{wf_id}/task/{task_id}/fail")
async def conductor_task_fail(wf_id: str, task_id: str, request: Request) -> JSONResponse:
    """apply_fail — worker reports failure. Body {error: '...'}."""
    entry = get_conductor_registry().get(wf_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"workflow {wf_id} not found")

    try:
        body = await request.json()
    except Exception:
        body = {}
    err = str(body.get("error", "unspecified"))[:500]

    from src.conductor.state_machine import apply_fail

    try:
        apply_fail(entry["runtime"], task_id, error=err)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"apply_fail failed: {exc}")
    return JSONResponse(
        {"ok": True, "workflow_id": wf_id, "task_id": task_id,
         "runtime": _serialize_runtime(entry["runtime"])}
    )


@router.get("/api/conductor/workflows")
async def conductor_list_workflows() -> JSONResponse:
    """List active workflows in the in-process registry."""
    entries = get_conductor_registry().list_all()
    return JSONResponse(
        {
            "ok": True,
            "count": len(entries),
            "workflows": [
                {
                    "workflow_id": e["def"].workflow_id,
                    "name": e["def"].name,
                    "state": e["runtime"].state.value
                    if hasattr(e["runtime"].state, "value")
                    else str(e["runtime"].state),
                    "current_step_index": e["runtime"].current_step_index,
                    "steps_total": len(e["def"].steps),
                    "tasks_total": sum(len(s.tasks) for s in e["def"].steps),
                    "created": e["created"],
                }
                for e in entries
            ],
        }
    )
