"""HITL subsystem → AionMind capability bridge (Phase 2 / C10)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from aionmind._bridge_base import (
    RISK_LOW,
    RISK_MEDIUM,
    BridgeCapability,
    make_unavailable_handler,
    register_bridge_capabilities,
)

logger = logging.getLogger(__name__)
_PROVIDER = "hitl"


def _try_import_subsystem() -> Any:
    for path in (
        "src.hitl.hitl_engine",
        "src.hitl",
        "hitl.hitl_engine",
        "hitl",
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
            capability_id="hitl.queue.list",
            name="List HITL Queue",
            description="Return the current HITL request queue.",
            provider=_PROVIDER,
            input_schema={"_": {"type": "null"}},
            output_schema={
                "status": {"type": "string"},
                "queue": {"type": "array"},
            },
            risk_level=RISK_LOW,
            tags=["hitl", "list", "read"],
            handler=_h("list_queue", RISK_LOW),
        ),
        BridgeCapability(
            capability_id="hitl.pending.list",
            name="List Pending HITL Items",
            description="Return HITL items still awaiting a decision.",
            provider=_PROVIDER,
            input_schema={"_": {"type": "null"}},
            output_schema={
                "status": {"type": "string"},
                "pending": {"type": "array"},
            },
            risk_level=RISK_LOW,
            tags=["hitl", "pending", "read"],
            handler=_h("list_pending", RISK_LOW),
        ),
        BridgeCapability(
            capability_id="hitl.decide",
            name="Decide HITL Item",
            description="Approve or reject a HITL item.",
            provider=_PROVIDER,
            input_schema={
                "item_id": {"type": "string", "required": True},
                "decision": {"type": "string", "required": True},
                "rationale": {"type": "string"},
            },
            output_schema={
                "status": {"type": "string"},
                "decision": {"type": "string"},
            },
            risk_level=RISK_MEDIUM,
            requires_approval=False,
            tags=["hitl", "decide", "write"],
            handler=_h("decide", RISK_MEDIUM),
        ),
        BridgeCapability(
            capability_id="hitl.intervention.respond",
            name="Respond to HITL Intervention",
            description="Submit a response to an in-progress intervention.",
            provider=_PROVIDER,
            input_schema={
                "intervention_id": {"type": "string", "required": True},
                "response": {"type": "object"},
            },
            output_schema={
                "status": {"type": "string"},
                "accepted": {"type": "boolean"},
            },
            risk_level=RISK_MEDIUM,
            tags=["hitl", "respond", "write"],
            handler=_h("respond", RISK_MEDIUM),
        ),
    ]


def load_hitl_capabilities_into_kernel(kernel: Any) -> int:
    subsystem = _try_import_subsystem()
    caps = _build_capabilities(subsystem)
    return register_bridge_capabilities(kernel, "hitl", caps)
