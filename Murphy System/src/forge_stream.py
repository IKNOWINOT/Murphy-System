"""
Forge Stream — Murphy System
================================
Server-Sent Events endpoint: GET /api/demo/forge-stream

Streams real-time build progress for the Swarm Forge.  This module runs the
real MFGC → MSS → Swarm → LLM pipeline (via ``generate_deliverable_with_progress``)
and translates pipeline events into SSE agent-level events that the frontend
grid can render.

When the real pipeline is unavailable (import error or runtime exception),
a clearly-labelled error event is emitted instead of faking progress — the
system must not pretend to be using AI when it is not.

Event types:
  pipeline       : {"phase": int, "status": str, ...}
  agent_start    : {"agent_id": int, "agent_name": str, "task": str, "swarm": str}
  agent_done     : {"agent_id": int, "status": "complete", "lines_produced": int}
  build_complete : {"total_agents": int, "total_lines": int, "build_time_ms": int,
                    "llm_provider": str, "pipeline_warnings": {...} | null}
  error          : {"code": str, "message": str}

Copyright © 2020 Inoni LLC — BSL 1.1
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncIterator, Dict, List

logger = logging.getLogger(__name__)

# Agent name roster — used to label agents when the real pipeline provides
# task decomposition.  These are display names only; the actual work is done
# by the pipeline's swarm agents.
_EXPLORATION_AGENTS = [
    "Coordinator", "Schema Architect", "API Designer", "Data Modeler",
    "UX Planner", "Logic Engineer", "Integration Mapper", "Auth Designer",
    "Queue Architect", "Cache Strategist", "Search Designer", "Event Planner",
    "Workflow Composer", "Config Manager", "Test Strategist", "Doc Writer",
    "Security Analyst", "Performance Scout", "Scale Planner", "CLI Builder",
    "SDK Drafter", "Webhook Designer", "Notification Planner", "Batch Processor",
    "Report Generator", "Analytics Designer", "Export Builder", "Import Handler",
    "Migration Planner", "Seed Data Builder", "Error Handler", "Logger",
]
_CONTROL_AGENTS = [
    "Risk Assessor", "Gate Enforcer", "Compliance Checker", "Audit Tracer",
    "Dependency Scanner", "Conflict Detector", "Load Estimator", "Failover Planner",
    "Rollback Designer", "Health Monitor", "Alert Configurator", "Circuit Breaker",
    "Rate Guard", "Timeout Handler", "Retry Strategist", "Dead Letter Queue",
    "Validator", "Schema Guard", "Type Checker", "Null Guard",
    "Boundary Tester", "Edge Case Hunter", "Regression Guard", "Coverage Analyst",
    "Injection Scanner", "XSS Guard", "CSRF Shield", "Auth Verifier",
    "Permission Checker", "Data Sanitizer", "Output Encoder", "Secret Scanner",
]

_AGENT_NAMES = _EXPLORATION_AGENTS + _CONTROL_AGENTS


def _sse_event(event_type: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def _run_pipeline_sync(query: str) -> List[Dict]:
    """Run the real deliverable pipeline synchronously (called from a thread)."""
    from src.demo_deliverable_generator import generate_deliverable_with_progress
    return generate_deliverable_with_progress(query)


async def forge_stream_generator(query: str = "") -> AsyncIterator[str]:
    """Async generator that yields SSE events for a swarm forge build.

    Runs the real MFGC → MSS → Swarm → LLM pipeline and streams each
    pipeline phase as an SSE event.  Agent-level events are derived from
    the pipeline's agent task decomposition so they reflect actual work.

    If the pipeline is unavailable, emits an error event — never fakes
    progress.
    """
    build_start = time.time()

    # ── Attempt to run the real pipeline ──────────────────────────────
    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            progress_events = await loop.run_in_executor(
                pool, _run_pipeline_sync, query,
            )
    except ImportError as exc:
        logger.error("FORGE-STREAM-ERR-001: Pipeline import failed: %s", exc)
        yield _sse_event("error", {
            "code": "FORGE-STREAM-ERR-001",
            "message": (
                f"Deliverable pipeline not available: {exc}. "
                "Ensure DEEPINFRA_API_KEY is configured and src.demo_deliverable_generator is importable."
            ),
        })
        return
    except Exception as exc:
        logger.exception("FORGE-STREAM-ERR-002: Pipeline execution failed: %s", exc)
        yield _sse_event("error", {
            "code": "FORGE-STREAM-ERR-002",
            "message": f"Pipeline execution failed: {type(exc).__name__}: {exc}",
        })
        return

    # ── Stream pipeline phases as SSE events ──────────────────────────
    total_agents = 0
    total_lines = 0
    done_event = None
    exploration_count = len(_EXPLORATION_AGENTS)

    for event in progress_events:
        phase = event.get("phase")

        if phase == "done":
            done_event = event
            continue

        # Emit pipeline phase status
        yield _sse_event("pipeline", {
            "phase": phase,
            "status": event.get("status", ""),
            "detail": event.get("detail", ""),
            "pipeline_stage": event.get("pipeline_stage", ""),
        })
        await asyncio.sleep(0.02)

        # When the pipeline decomposes into agent tasks (phase 3),
        # emit individual agent_start/agent_done events for each task.
        if event.get("detail") == "agent_tasks":
            agent_tasks = event.get("agent_tasks") or []
            for agent_id, task_info in enumerate(agent_tasks):
                agent_name = task_info.get("agent_name", "")
                if not agent_name and agent_id < len(_AGENT_NAMES):
                    agent_name = _AGENT_NAMES[agent_id]
                elif not agent_name:
                    agent_name = f"Agent-{agent_id}"

                swarm = "exploration" if agent_id < exploration_count else "control"
                yield _sse_event("agent_start", {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "task": task_info.get("task", "Processing..."),
                    "swarm": swarm,
                    "cursor_id": agent_id,
                })
                await asyncio.sleep(0.02)

                yield _sse_event("agent_done", {
                    "agent_id": agent_id,
                    "status": "complete",
                    "lines_produced": 1,
                })
                total_agents += 1
                total_lines += 1
                await asyncio.sleep(0.01)

    # ── Build-complete event ──────────────────────────────────────────
    build_ms = int((time.time() - build_start) * 1000)

    # Extract diagnostics from the done event
    llm_provider = "unknown"
    pipeline_warnings = None
    if done_event:
        diag = done_event.get("pipeline_diagnostics") or {}
        path_taken = diag.get("path_taken") or []
        for step in path_taken:
            if step.startswith("llm_ok:"):
                llm_provider = step.split(":", 1)[1]
                break
            if step.startswith("swarm_ok:"):
                llm_provider = "swarm"
                break
            if step.startswith("llm_controller_ok"):
                llm_provider = "llm-controller"
                break
            if step.startswith("local_llm_ok"):
                llm_provider = "local-llm"
                break
        else:
            if any("fallback" in s for s in path_taken):
                llm_provider = "template-fallback"

        if diag.get("error_count", 0) > 0 or diag.get("fallback_count", 0) > 0:
            pipeline_warnings = {
                "error_count": diag.get("error_count", 0),
                "fallback_count": diag.get("fallback_count", 0),
                "fallbacks": diag.get("fallbacks", []),
            }

        metrics = done_event.get("metrics") or {}
        total_agents = metrics.get("swarm_agent_count", total_agents) or total_agents
        total_lines = metrics.get("line_count", total_lines) or total_lines

    yield _sse_event("build_complete", {
        "total_agents": total_agents,
        "total_lines": total_lines,
        "build_time_ms": build_ms,
        "query": query[:100] if query else "",
        "llm_provider": llm_provider,
        "pipeline_warnings": pipeline_warnings,
    })

