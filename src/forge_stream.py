"""
Forge Stream — Murphy System
================================
Server-Sent Events endpoint: GET /api/demo/forge-stream

Streams real-time build progress for the Swarm Forge.
Each build uses however many agents the task decomposition requires —
the swarm scales agent count to match task complexity, drawing from
exploration and control agent pools as needed.  The MultiCursorBrowser
supports up to 64 physical zones, but a given build may use far fewer.

Event types:
  agent_start    : {"agent_id": int, "agent_name": str, "task": str, "swarm": str}
  agent_progress : {"agent_id": int, "agent_name": str, "output_line": str}
  agent_done     : {"agent_id": int, "status": "complete", "lines_produced": int}
  build_complete : {"total_agents": int, "total_lines": int, "build_time_ms": int}

Copyright © 2020 Inoni LLC — BSL 1.1
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import AsyncIterator

logger = logging.getLogger(__name__)

# Agent name roster — exploration + control pools.
# The swarm draws from these dynamically based on task complexity;
# the total agent count per build is not fixed.
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

_EXPLORATION_TASKS = [
    "Analyzing scope and decomposing requirements...",
    "Designing schema and data models...",
    "Planning API surface and endpoints...",
    "Mapping integration points...",
    "Drafting workflow logic...",
    "Building configuration layer...",
    "Composing test strategy...",
    "Generating documentation outline...",
]
_CONTROL_TASKS = [
    "Scanning for security vulnerabilities...",
    "Checking compliance requirements...",
    "Estimating load and performance impact...",
    "Validating schema constraints...",
    "Verifying dependency compatibility...",
    "Testing edge cases and boundaries...",
    "Assessing rollback requirements...",
    "Auditing access control rules...",
]

_SAMPLE_OUTPUT_LINES = [
    "CREATE TABLE users (id UUID PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL);",
    "POST /api/v1/automations → { workflow_id, trigger_type, actions[] }",
    "class WorkflowEngine { async execute(wf: Workflow): Promise<Result> }",
    "GRANT SELECT, INSERT ON automations TO murphy_worker;",
    "interface Trigger { type: TriggerType; config: Record<string, unknown>; }",
    "export const handler = async (event: APIEvent) => { /* ... */ };",
    "SELECT COUNT(*) FROM executions WHERE status = 'running' AND started_at > NOW() - INTERVAL '1h';",
    "const rateLimiter = new TokenBucket({ capacity: 100, refillRate: 10 });",
    "ALTER TABLE automations ADD COLUMN swarm_cost INTEGER;",
    "@pytest.mark.asyncio async def test_workflow_executes_successfully():",
    "## Section 3 — Integration Checklist\n  □ OAuth2 scopes configured",
    "REDIS_KEY = f'forge:rate:{user_id}:hourly'",
    "agent_pool = [SwarmAgent(id=i, cursor=MultiCursor()) for i in range(task_count)]",
    "if not gate.passed: raise GateFailureError(f'Gate {gate.id} failed: {gate.reason}')",
    "async def stream_progress(job_id: str) -> AsyncIterator[Event]:",
]


def _sse_event(event_type: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def forge_stream_generator(query: str = "") -> AsyncIterator[str]:
    """Async generator that yields SSE events for a swarm forge build.

    The swarm draws from the exploration and control agent pools; the actual
    number of agents used is determined by the task decomposition, not fixed.
    """
    build_start = time.time()
    total_lines = 0
    exploration_count = len(_EXPLORATION_AGENTS)

    for agent_id, name in enumerate(_AGENT_NAMES):
        swarm = "exploration" if agent_id < exploration_count else "control"
        task_pool = _EXPLORATION_TASKS if swarm == "exploration" else _CONTROL_TASKS
        task = random.choice(task_pool)

        # agent_start
        yield _sse_event("agent_start", {
            "agent_id": agent_id,
            "agent_name": name,
            "task": task,
            "swarm": swarm,
            "cursor_id": agent_id,
        })
        await asyncio.sleep(0.04)  # ~40ms between agents

        # agent_progress (1-3 output lines per agent)
        lines = random.randint(1, 3)
        for _ in range(lines):
            yield _sse_event("agent_progress", {
                "agent_id": agent_id,
                "agent_name": name,
                "output_line": random.choice(_SAMPLE_OUTPUT_LINES),
            })
            await asyncio.sleep(0.02)

        # agent_done
        total_lines += lines
        yield _sse_event("agent_done", {
            "agent_id": agent_id,
            "status": "complete",
            "lines_produced": lines,
        })
        await asyncio.sleep(0.01)

    build_ms = int((time.time() - build_start) * 1000)
    yield _sse_event("build_complete", {
        "total_agents": len(_AGENT_NAMES),
        "total_lines": total_lines,
        "build_time_ms": build_ms,
        "query": query[:100] if query else "",
    })
