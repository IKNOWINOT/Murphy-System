"""Founder maintenance → AionMind capability bridge (Phase 2 / C12).

Every capability here is gated by ``metadata.founder == True`` on the
ContextObject — the kernel's reasoner / planner is expected to filter
these out for non-founder callers.  Bridges cannot enforce that on
their own, but they declare ``metadata={"requires_founder": True}``
so any UI / policy layer can refuse to surface them.

Risk: all capabilities here are MEDIUM or HIGH; nothing in the
founder pack should ever be auto-approvable for a non-owner role.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from aionmind._bridge_base import (
    RISK_HIGH,
    RISK_MEDIUM,
    BridgeCapability,
    make_unavailable_handler,
    register_bridge_capabilities,
)

logger = logging.getLogger(__name__)
_PROVIDER = "founder"
_FOUNDER_GATE = {"requires_founder": True}


def _try_import_subsystem() -> Any:
    for path in (
        "src.founder.founder_engine",
        "src.founder",
        "founder.founder_engine",
        "founder",
    ):
        try:
            return __import__(path, fromlist=["*"])
        except Exception:
            continue
    return None


def _build_capabilities(subsystem: Any) -> List[BridgeCapability]:
    available = subsystem is not None

    def _h(action: str, risk: str):
        if not available:
            return make_unavailable_handler(_PROVIDER, f"{action}_no_subsystem")

        def _handler(node: Any) -> Dict[str, Any]:
            return {
                "status": "delegated",
                "subsystem": _PROVIDER,
                "action": action,
                "risk": risk,
                "params": getattr(node, "parameters", {}) or {},
            }

        return _handler

    return [
        BridgeCapability(
            capability_id="founder.maintenance.run",
            name="Run Founder Maintenance",
            description="Execute the founder maintenance routine.",
            provider=_PROVIDER,
            input_schema={"task": {"type": "string"}},
            output_schema={
                "status": {"type": "string"},
                "report": {"type": "object"},
            },
            risk_level=RISK_MEDIUM,
            tags=["founder", "maintenance", "write"],
            metadata=dict(_FOUNDER_GATE),
            handler=_h("maintenance_run", RISK_MEDIUM),
        ),
        BridgeCapability(
            capability_id="founder.update",
            name="Update Founder Settings",
            description="Modify founder-only configuration.",
            provider=_PROVIDER,
            input_schema={"patch": {"type": "object", "required": True}},
            output_schema={
                "status": {"type": "string"},
                "updated": {"type": "boolean"},
            },
            risk_level=RISK_MEDIUM,
            requires_approval=True,
            tags=["founder", "update", "write"],
            metadata=dict(_FOUNDER_GATE),
            handler=_h("update", RISK_MEDIUM),
        ),
        BridgeCapability(
            capability_id="founder.password.rotate",
            name="Rotate Founder Password",
            description="Rotate the founder account password — never auto-approve.",
            provider=_PROVIDER,
            input_schema={"new_password_hash": {"type": "string", "required": True}},
            output_schema={
                "status": {"type": "string"},
                "rotated": {"type": "boolean"},
            },
            risk_level=RISK_HIGH,
            requires_approval=True,
            tags=["founder", "security", "write"],
            metadata={**_FOUNDER_GATE, "never_auto_approve": True},
            handler=_h("password_rotate", RISK_HIGH),
        ),
    ]


def load_founder_capabilities_into_kernel(kernel: Any) -> int:
    subsystem = _try_import_subsystem()
    caps = _build_capabilities(subsystem)
    return register_bridge_capabilities(kernel, "founder", caps)
