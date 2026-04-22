"""Production subsystem → AionMind capability bridge (Phase 2 / C13).

Wraps ``/api/production/proposals``, work orders, and scheduling.
``proposal.delete`` is HIGH risk — a CRITICAL tier could be a
follow-up if the policy ever wants "never auto-approve".
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
_PROVIDER = "production"


def _try_import_subsystem() -> Any:
    for path in (
        "src.production.production_engine",
        "src.production",
        "production.production_engine",
        "production",
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
            capability_id="production.proposals.list",
            name="List Production Proposals",
            description="Return active production proposals.",
            provider=_PROVIDER,
            input_schema={"_": {"type": "null"}},
            output_schema={
                "status": {"type": "string"},
                "proposals": {"type": "array"},
            },
            risk_level=RISK_LOW,
            tags=["production", "proposals", "read"],
            handler=_h("list_proposals", RISK_LOW),
        ),
        BridgeCapability(
            capability_id="production.proposals.create",
            name="Create Production Proposal",
            description="Submit a new production proposal.",
            provider=_PROVIDER,
            input_schema={"proposal": {"type": "object", "required": True}},
            output_schema={
                "status": {"type": "string"},
                "proposal_id": {"type": "string"},
            },
            risk_level=RISK_MEDIUM,
            tags=["production", "proposals", "write"],
            handler=_h("create_proposal", RISK_MEDIUM),
        ),
        BridgeCapability(
            capability_id="production.proposals.delete",
            name="Delete Production Proposal",
            description="Permanently delete a production proposal.",
            provider=_PROVIDER,
            input_schema={"proposal_id": {"type": "string", "required": True}},
            output_schema={
                "status": {"type": "string"},
                "deleted": {"type": "boolean"},
            },
            risk_level=RISK_HIGH,
            requires_approval=True,
            tags=["production", "proposals", "delete"],
            metadata={"never_auto_approve": True},
            handler=_h("delete_proposal", RISK_HIGH),
        ),
        BridgeCapability(
            capability_id="production.work_orders.create",
            name="Create Work Order",
            description="Create a production work order.",
            provider=_PROVIDER,
            input_schema={"work_order": {"type": "object", "required": True}},
            output_schema={
                "status": {"type": "string"},
                "work_order_id": {"type": "string"},
            },
            risk_level=RISK_MEDIUM,
            tags=["production", "work_orders", "write"],
            handler=_h("create_work_order", RISK_MEDIUM),
        ),
        BridgeCapability(
            capability_id="production.schedule.set",
            name="Set Production Schedule",
            description="Update the production schedule.",
            provider=_PROVIDER,
            input_schema={"schedule": {"type": "object", "required": True}},
            output_schema={
                "status": {"type": "string"},
                "scheduled": {"type": "boolean"},
            },
            risk_level=RISK_MEDIUM,
            tags=["production", "schedule", "write"],
            handler=_h("set_schedule", RISK_MEDIUM),
        ),
    ]


def load_production_capabilities_into_kernel(kernel: Any) -> int:
    subsystem = _try_import_subsystem()
    caps = _build_capabilities(subsystem)
    return register_bridge_capabilities(kernel, "production", caps)
