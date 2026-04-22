"""Automations subsystem → AionMind capability bridge (Phase 2 / C9).

Wraps the ``/api/automations/*`` surface as discrete AionMind
capabilities so the Reasoning Engine can plan against them.

Risk taxonomy
-------------
* ``automations.workflows.list``  — LOW
* ``automations.workflows.get``   — LOW
* ``automations.workflows.execute``    — MEDIUM (side-effects)
* ``automations.fire_trigger``         — MEDIUM
* ``automations.commission``           — MEDIUM
* ``automations.workflows.delete``     — HIGH (data loss)

The actual subsystem may be unavailable at boot; in that case
:func:`make_unavailable_handler` is used so capabilities still appear
in the registry and a clear "unavailable" payload is returned at
execute time.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from aionmind._bridge_base import (
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    BridgeCapability,
    make_unavailable_handler,
    register_bridge_capabilities,
)

logger = logging.getLogger(__name__)


_PROVIDER = "automations"


def _try_import_subsystem() -> Any:
    """Best-effort import of the automations subsystem."""
    for path in (
        "src.automations.automation_engine",
        "src.automations",
        "automations.automation_engine",
        "automations",
    ):
        try:
            mod = __import__(path, fromlist=["*"])
            return mod
        except Exception:
            continue
    return None


def _build_capabilities(subsystem: Any) -> List[BridgeCapability]:
    """Declare every capability this bridge offers."""
    available = subsystem is not None

    def _h(action: str, risk: str):
        if not available:
            return make_unavailable_handler(_PROVIDER, f"{action}_no_subsystem")

        def _handler(node: Any) -> Dict[str, Any]:
            params = getattr(node, "parameters", {}) or {}
            return {
                "status": "delegated",
                "subsystem": _PROVIDER,
                "action": action,
                "risk": risk,
                "params": params,
            }

        return _handler

    return [
        BridgeCapability(
            capability_id="automations.workflows.list",
            name="List Automation Workflows",
            description="Return all registered automation workflows.",
            provider=_PROVIDER,
            input_schema={"_": {"type": "null"}},
            output_schema={
                "status": {"type": "string"},
                "workflows": {"type": "array"},
            },
            risk_level=RISK_LOW,
            tags=["automations", "list", "read"],
            handler=_h("list", RISK_LOW),
        ),
        BridgeCapability(
            capability_id="automations.workflows.get",
            name="Get Automation Workflow",
            description="Fetch a single automation workflow by id.",
            provider=_PROVIDER,
            input_schema={"workflow_id": {"type": "string", "required": True}},
            output_schema={
                "status": {"type": "string"},
                "workflow": {"type": "object"},
            },
            risk_level=RISK_LOW,
            tags=["automations", "read"],
            handler=_h("get", RISK_LOW),
        ),
        BridgeCapability(
            capability_id="automations.workflows.execute",
            name="Execute Automation Workflow",
            description="Trigger an automation workflow run.",
            provider=_PROVIDER,
            input_schema={
                "workflow_id": {"type": "string", "required": True},
                "inputs": {"type": "object"},
            },
            output_schema={
                "status": {"type": "string"},
                "run_id": {"type": "string"},
            },
            risk_level=RISK_MEDIUM,
            tags=["automations", "execute", "write"],
            handler=_h("execute", RISK_MEDIUM),
        ),
        BridgeCapability(
            capability_id="automations.fire_trigger",
            name="Fire Automation Trigger",
            description="Manually fire a registered automation trigger.",
            provider=_PROVIDER,
            input_schema={
                "trigger_id": {"type": "string", "required": True},
                "payload": {"type": "object"},
            },
            output_schema={
                "status": {"type": "string"},
                "fired": {"type": "boolean"},
            },
            risk_level=RISK_MEDIUM,
            tags=["automations", "trigger", "write"],
            handler=_h("fire_trigger", RISK_MEDIUM),
        ),
        BridgeCapability(
            capability_id="automations.commission",
            name="Commission Automation",
            description="Commission (provision + activate) an automation.",
            provider=_PROVIDER,
            input_schema={"workflow_id": {"type": "string", "required": True}},
            output_schema={
                "status": {"type": "string"},
                "commissioned": {"type": "boolean"},
            },
            risk_level=RISK_MEDIUM,
            tags=["automations", "commission", "write"],
            handler=_h("commission", RISK_MEDIUM),
        ),
        BridgeCapability(
            capability_id="automations.workflows.delete",
            name="Delete Automation Workflow",
            description="Permanently delete an automation workflow.",
            provider=_PROVIDER,
            input_schema={"workflow_id": {"type": "string", "required": True}},
            output_schema={
                "status": {"type": "string"},
                "deleted": {"type": "boolean"},
            },
            risk_level=RISK_HIGH,
            requires_approval=True,
            tags=["automations", "delete", "write"],
            handler=_h("delete", RISK_HIGH),
        ),
    ]


def load_automations_capabilities_into_kernel(kernel: Any) -> int:
    """Register every automations capability with *kernel*.

    Returns the number of capabilities registered.  Always non-zero
    when the bridge module imports successfully — capabilities are
    declared even if the underlying subsystem is missing (an
    "unavailable" handler short-circuits at execute time).
    """
    subsystem = _try_import_subsystem()
    caps = _build_capabilities(subsystem)
    return register_bridge_capabilities(kernel, "automations", caps)
