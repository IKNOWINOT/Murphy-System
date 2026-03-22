# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Task handlers: register action handlers for WorkflowDAGEngine."""

from __future__ import annotations

from typing import Any, Callable, Dict

try:
    from src.workflow_dag_engine import WorkflowDAGEngine
except ImportError:
    WorkflowDAGEngine = None  # type: ignore[misc,assignment]


def handle_human_required(step_def: Any, context: Dict) -> Dict:
    """Handler for tasks that require direct human action."""
    meta = getattr(step_def, "metadata", {}) or {}
    return {
        "action": "onboarding_human_required",
        "step_id": step_def.step_id,
        "status": "pending_human",
        "url": meta.get("url", ""),
        "hitl_level": meta.get("hitl_level", "blocked_human_required"),
        "instructions": f"Human action required: {step_def.name}",
        "time_estimate_minutes": meta.get("time_estimate", 0),
    }


def handle_agent_assisted(step_def: Any, context: Dict) -> Dict:
    """Handler for tasks where Murphy assists a human."""
    meta = getattr(step_def, "metadata", {}) or {}
    return {
        "action": "onboarding_agent_assisted",
        "step_id": step_def.step_id,
        "status": "agent_prepared",
        "url": meta.get("url", ""),
        "prefill_fields": meta.get("prefill_fields", {}),
        "description": meta.get("description", step_def.name),
        "estimated_value": meta.get("value"),
        "time_estimate_minutes": meta.get("time_estimate", 0),
    }


def handle_agent_auto(step_def: Any, context: Dict) -> Dict:
    """Handler for tasks Murphy can complete automatically."""
    meta = getattr(step_def, "metadata", {}) or {}
    return {
        "action": "onboarding_agent_auto",
        "step_id": step_def.step_id,
        "status": "completed",
        "url": meta.get("url", ""),
        "automated": True,
        "time_estimate_minutes": meta.get("time_estimate", 0),
    }


def handle_recurring(step_def: Any, context: Dict) -> Dict:
    """Handler for recurring maintenance tasks."""
    meta = getattr(step_def, "metadata", {}) or {}
    return {
        "action": "onboarding_recurring",
        "step_id": step_def.step_id,
        "status": "scheduled",
        "recurrence": meta.get("recurrence", "annual"),
        "url": meta.get("url", ""),
        "time_estimate_minutes": meta.get("time_estimate", 0),
    }


def register_onboarding_handlers(engine: "WorkflowDAGEngine") -> None:
    """Register all onboarding action handlers with the DAG engine."""
    engine.register_step_handler("onboarding_human_required", handle_human_required)
    engine.register_step_handler("onboarding_agent_assisted", handle_agent_assisted)
    engine.register_step_handler("onboarding_agent_auto", handle_agent_auto)
    engine.register_step_handler("onboarding_recurring", handle_recurring)
