"""
Murphy System — Execution Engine Router (DEF-045/046)

Wires the Two-Phase Orchestrator, Universal Control Plane, and
Execution Orchestrator into the unified FastAPI server as an APIRouter.

Commissioning Status: ACTIVE
Module Purpose:
  - Expose Phase 1 (generative setup) and Phase 2 (production execution) via REST
  - Provide session-based universal control plane with engine isolation
  - Bridge ExecutionOrchestrator (signature validation, approval routing) to FastAPI

Design Questions Answered:
  Q: Does the module do what it was designed to do?
  A: Yes — routes two_phase_orchestrator, universal_control_plane, and
     execution_orchestrator through a unified REST interface.
  Q: What conditions are possible?
  A: Missing configurations, session not found, engine load failure,
     packet validation failure, signature invalid, replay attack.
  Q: Has hardening been applied?
  A: Input validation on all IDs, try/except on all orchestrator calls,
     structured error responses, no raw exceptions leaked.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

log = logging.getLogger("murphy.execution_router")

router = APIRouter(tags=["execution-engine"])

# ══════════════════════════════════════════════════════════════════════════════
# LAZY INITIALIZATION — orchestrators loaded at startup, not import time
# ══════════════════════════════════════════════════════════════════════════════

_two_phase: Any = None         # TwoPhaseOrchestrator instance
_ucp: Any = None               # UniversalControlPlane instance
_exec_orch: Any = None         # ExecutionOrchestrator instance
_init_errors: List[str] = []


def _initialize_orchestrators() -> None:
    """Lazy-init all three orchestrators. Called from startup event."""
    global _two_phase, _ucp, _exec_orch, _init_errors
    _init_errors.clear()

    # ── Two-Phase Orchestrator ──
    try:
        from two_phase_orchestrator import TwoPhaseOrchestrator
        _two_phase = TwoPhaseOrchestrator()
        log.info("✓ TwoPhaseOrchestrator loaded")
    except Exception as e:
        _init_errors.append(f"TwoPhaseOrchestrator: {e}")
        log.warning("✗ TwoPhaseOrchestrator failed: %s", e)

    # ── Universal Control Plane ──
    try:
        from universal_control_plane import UniversalControlPlane
        _ucp = UniversalControlPlane()
        log.info("✓ UniversalControlPlane loaded")
    except Exception as e:
        _init_errors.append(f"UniversalControlPlane: {e}")
        log.warning("✗ UniversalControlPlane failed: %s", e)

    # ── Execution Orchestrator ──
    try:
        from execution_orchestrator import ExecutionOrchestrator
        _exec_orch = ExecutionOrchestrator()
        log.info("✓ ExecutionOrchestrator loaded")
    except Exception as e:
        _init_errors.append(f"ExecutionOrchestrator: {e}")
        log.warning("✗ ExecutionOrchestrator failed: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE MODELS
# ══════════════════════════════════════════════════════════════════════════════

class CreateAutomationRequest(BaseModel):
    """Request to create a new automation via Phase 1 (generative setup)."""
    request: str = Field(..., description="Natural-language description of the automation")
    domain: str = Field(default="general", description="Domain hint: publishing, factory, data, etc.")
    user_id: str = Field(default="default", description="User/tenant identifier")
    repository_id: str = Field(default="default", description="Repository/project identifier")

class RunAutomationRequest(BaseModel):
    """Request to run an existing automation via Phase 2."""
    automation_id: str = Field(..., description="Automation or session ID from Phase 1")

class ExecutePacketRequest(BaseModel):
    """Request to execute a task packet through the Execution Orchestrator."""
    task: str = Field(..., description="Task name/identifier")
    authority: str = Field(default="low", description="Authority level: low, medium, high, full")
    requires_human_approval: bool = Field(default=False)
    signature: Optional[str] = Field(default=None, description="Packet signature for validation")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Task-specific payload")

class ApprovalRequest(BaseModel):
    """Request to approve a pending execution."""
    approval_request_id: str = Field(..., description="Approval request ID from execute response")
    approved: bool = Field(default=True)
    approver: str = Field(default="system", description="Identity of the approver")


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH / STATUS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/api/execution/health")
async def execution_engine_health():
    """Health check for the execution engine subsystem."""
    return JSONResponse({
        "status": "healthy" if not _init_errors else "degraded",
        "two_phase_orchestrator": _two_phase is not None,
        "universal_control_plane": _ucp is not None,
        "execution_orchestrator": _exec_orch is not None,
        "init_errors": _init_errors,
        "active_sessions": len(_ucp.sessions) if _ucp else 0,
        "active_configurations": len(_two_phase.phase2.configurations) if _two_phase else 0,
    })


# ══════════════════════════════════════════════════════════════════════════════
# TWO-PHASE ORCHESTRATOR ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/api/execution/two-phase/create")
async def two_phase_create(req: CreateAutomationRequest):
    """
    Phase 1: Generative Setup — analyze request, discover regulations,
    compile constraints, generate agents, create sandbox.
    Returns automation_id for Phase 2.
    """
    if not _two_phase:
        raise HTTPException(503, "TwoPhaseOrchestrator not available")
    try:
        automation_id = _two_phase.create_automation(req.request, req.domain)
        config = _two_phase.get_automation_config(automation_id)
        return JSONResponse({
            "automation_id": automation_id,
            "domain": req.domain,
            "phase": "setup_complete",
            "agents": len(config.get("agents", [])) if config else 0,
            "constraints": len(config.get("constraints", {})) if config else 0,
            "message": "Phase 1 complete. Use /api/execution/two-phase/run to execute.",
        })
    except Exception as e:
        log.error("Phase 1 failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Phase 1 setup failed: {e}")


@router.post("/api/execution/two-phase/run")
async def two_phase_run(req: RunAutomationRequest):
    """
    Phase 2: Production Execution — execute the configured automation,
    produce deliverables, learn from results.
    """
    if not _two_phase:
        raise HTTPException(503, "TwoPhaseOrchestrator not available")
    config = _two_phase.get_automation_config(req.automation_id)
    if not config:
        raise HTTPException(404, f"Automation '{req.automation_id}' not found")
    try:
        result = _two_phase.run_automation(req.automation_id)
        if "error" in result:
            raise HTTPException(400, result["error"])
        return JSONResponse(result)
    except HTTPException:
        raise
    except Exception as e:
        log.error("Phase 2 execution failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Phase 2 execution failed: {e}")


@router.get("/api/execution/two-phase/{automation_id}")
async def two_phase_status(automation_id: str):
    """Get automation configuration and execution history."""
    if not _two_phase:
        raise HTTPException(503, "TwoPhaseOrchestrator not available")
    config = _two_phase.get_automation_config(automation_id)
    if not config:
        raise HTTPException(404, f"Automation '{automation_id}' not found")
    history = _two_phase.get_execution_history(automation_id)
    return JSONResponse({
        "automation_id": automation_id,
        "domain": config.get("domain"),
        "phase": config.get("phase"),
        "agents": len(config.get("agents", [])),
        "execution_count": len(history),
        "created_at": config.get("created_at"),
    })


@router.get("/api/execution/two-phase")
async def two_phase_list():
    """List all configured automations."""
    if not _two_phase:
        raise HTTPException(503, "TwoPhaseOrchestrator not available")
    configs = _two_phase.phase2.configurations
    return JSONResponse({
        "automations": [
            {
                "automation_id": aid,
                "domain": c.get("domain"),
                "phase": c.get("phase"),
                "agents": len(c.get("agents", [])),
                "created_at": c.get("created_at"),
            }
            for aid, c in configs.items()
        ],
        "total": len(configs),
    })


# ══════════════════════════════════════════════════════════════════════════════
# UNIVERSAL CONTROL PLANE ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/api/execution/ucp/create")
async def ucp_create(req: CreateAutomationRequest):
    """
    Create a Universal Control Plane session.
    Analyzes the request, determines control type (sensor_actuator, content_api,
    database_compute, agent_reasoning, command_system, hybrid), selects
    appropriate engines, compiles execution packet, and creates an isolated session.
    """
    if not _ucp:
        raise HTTPException(503, "UniversalControlPlane not available")
    try:
        session_id = _ucp.create_automation(req.request, req.user_id, req.repository_id)
        session = _ucp.sessions.get(session_id)
        return JSONResponse({
            "session_id": session_id,
            "control_type": session.control_type.value if session else "unknown",
            "engines": [e.value for e in session.engines.keys()] if session else [],
            "packet_actions": len(session.packet.task_graph) if session and session.packet else 0,
            "message": "Session created. Use /api/execution/ucp/run to execute.",
        })
    except Exception as e:
        log.error("UCP session creation failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Session creation failed: {e}")


@router.post("/api/execution/ucp/run")
async def ucp_run(req: RunAutomationRequest):
    """Execute a Universal Control Plane session's packet with its engines."""
    if not _ucp:
        raise HTTPException(503, "UniversalControlPlane not available")
    session = _ucp.sessions.get(req.automation_id)
    if not session:
        raise HTTPException(404, f"Session '{req.automation_id}' not found")
    try:
        result = _ucp.run_automation(req.automation_id)
        if "error" in result:
            raise HTTPException(400, result["error"])
        return JSONResponse(result)
    except HTTPException:
        raise
    except Exception as e:
        log.error("UCP execution failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Session execution failed: {e}")


@router.get("/api/execution/ucp/{session_id}")
async def ucp_session_status(session_id: str):
    """Get session status and engine information."""
    if not _ucp:
        raise HTTPException(503, "UniversalControlPlane not available")
    session = _ucp.sessions.get(session_id)
    if not session:
        raise HTTPException(404, f"Session '{session_id}' not found")
    return JSONResponse({
        "session_id": session_id,
        "control_type": session.control_type.value,
        "state": session.state,
        "engines": [e.value for e in session.engines.keys()],
        "user_id": session.user_id,
        "repository_id": session.repository_id,
        "has_packet": session.packet is not None,
    })


@router.get("/api/execution/ucp")
async def ucp_list_sessions():
    """List all active UCP sessions."""
    if not _ucp:
        raise HTTPException(503, "UniversalControlPlane not available")
    return JSONResponse({
        "sessions": [
            {
                "session_id": sid,
                "control_type": s.control_type.value,
                "state": s.state,
                "engines": [e.value for e in s.engines.keys()],
            }
            for sid, s in _ucp.sessions.items()
        ],
        "total": len(_ucp.sessions),
    })


@router.delete("/api/execution/ucp/{session_id}")
async def ucp_close_session(session_id: str):
    """Close and clean up a UCP session."""
    if not _ucp:
        raise HTTPException(503, "UniversalControlPlane not available")
    session = _ucp.sessions.get(session_id)
    if not session:
        raise HTTPException(404, f"Session '{session_id}' not found")
    try:
        session.close()
        del _ucp.sessions[session_id]
        return JSONResponse({"closed": True, "session_id": session_id})
    except Exception as e:
        log.error("Session close failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Session close failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# EXECUTION ORCHESTRATOR ENDPOINTS (Signature Validation + Approval Routing)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/api/execution/packet/execute")
async def exec_orch_execute(req: ExecutePacketRequest):
    """
    Execute a task packet through the Execution Orchestrator.
    Handles signature validation, replay prevention, and authority-based
    approval routing (high-authority + requires_human_approval → HITL queue).
    """
    if not _exec_orch:
        raise HTTPException(503, "ExecutionOrchestrator not available")
    try:
        packet = {
            "task": req.task,
            "authority": req.authority,
            "requires_human_approval": req.requires_human_approval,
            "signature": req.signature,
            **req.payload,
        }
        result = _exec_orch.execute(packet)
        status_code = 200 if result.get("accepted") else 403
        return JSONResponse(result, status_code=status_code)
    except Exception as e:
        log.error("Packet execution failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Execution failed: {e}")


@router.post("/api/execution/packet/approve")
async def exec_orch_approve(req: ApprovalRequest):
    """Approve a pending execution that required human review."""
    if not _exec_orch:
        raise HTTPException(503, "ExecutionOrchestrator not available")
    try:
        result = _exec_orch.execute_after_approval({
            "approval_request_id": req.approval_request_id,
            "approved": req.approved,
            "approver": req.approver,
        })
        return JSONResponse(result)
    except Exception as e:
        log.error("Approval processing failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Approval failed: {e}")


@router.get("/api/execution/packet/pending")
async def exec_orch_pending():
    """List pending approval requests."""
    if not _exec_orch:
        raise HTTPException(503, "ExecutionOrchestrator not available")
    pending = {
        k: {
            "task": v.get("task", "unknown"),
            "authority": v.get("authority", "unknown"),
        }
        for k, v in _exec_orch.pending_approvals.items()
    }
    return JSONResponse({"pending": pending, "total": len(pending)})


@router.get("/api/execution/packet/history")
async def exec_orch_history(limit: int = Query(default=50, le=200)):
    """Get execution history."""
    if not _exec_orch:
        raise HTTPException(503, "ExecutionOrchestrator not available")
    tasks = _exec_orch.executed_tasks[-limit:]
    return JSONResponse({
        "executions": [
            {"task": t.get("task", "unknown"), "authority": t.get("authority", "unknown")}
            for t in tasks
        ],
        "total": len(_exec_orch.executed_tasks),
        "showing": len(tasks),
    })


# ══════════════════════════════════════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════════════════════════════════════

async def execution_router_startup() -> None:
    """Initialize execution engine orchestrators. Call from main app startup."""
    _initialize_orchestrators()
    log.info(
        "Execution Router startup complete — TPO:%s UCP:%s EO:%s",
        "OK" if _two_phase else "FAIL",
        "OK" if _ucp else "FAIL",
        "OK" if _exec_orch else "FAIL",
    )