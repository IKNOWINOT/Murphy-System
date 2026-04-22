"""Living Document → AionMind capability bridge (Phase 2 / C15)."""

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
_PROVIDER = "document"


def _try_import_subsystem() -> Any:
    for path in (
        "src.runtime.living_document",
        "src.living_document",
        "runtime.living_document",
        "living_document",
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
            capability_id="document.gates.list",
            name="List Living Document Gates",
            description="Return all gates defined on the Living Document.",
            provider=_PROVIDER,
            input_schema={"_": {"type": "null"}},
            output_schema={
                "status": {"type": "string"},
                "gates": {"type": "array"},
            },
            risk_level=RISK_LOW,
            tags=["document", "gates", "read"],
            handler=_h("list_gates", RISK_LOW),
        ),
        BridgeCapability(
            capability_id="document.gates.evaluate",
            name="Evaluate Living Document Gate",
            description="Evaluate a single gate by id.",
            provider=_PROVIDER,
            input_schema={"gate_id": {"type": "string", "required": True}},
            output_schema={
                "status": {"type": "string"},
                "passed": {"type": "boolean"},
            },
            risk_level=RISK_LOW,
            tags=["document", "gates", "read"],
            handler=_h("evaluate_gate", RISK_LOW),
        ),
        BridgeCapability(
            capability_id="document.blocks.get",
            name="Get Document Block",
            description="Fetch a block from the document tree by id.",
            provider=_PROVIDER,
            input_schema={"block_id": {"type": "string", "required": True}},
            output_schema={
                "status": {"type": "string"},
                "block": {"type": "object"},
            },
            risk_level=RISK_LOW,
            tags=["document", "blocks", "read"],
            handler=_h("get_block", RISK_LOW),
        ),
        BridgeCapability(
            capability_id="document.blocks.update",
            name="Update Document Block",
            description="Update a block in the document tree.",
            provider=_PROVIDER,
            input_schema={
                "block_id": {"type": "string", "required": True},
                "patch": {"type": "object", "required": True},
            },
            output_schema={
                "status": {"type": "string"},
                "updated": {"type": "boolean"},
            },
            risk_level=RISK_MEDIUM,
            tags=["document", "blocks", "write"],
            handler=_h("update_block", RISK_MEDIUM),
        ),
    ]


def load_document_capabilities_into_kernel(kernel: Any) -> int:
    subsystem = _try_import_subsystem()
    caps = _build_capabilities(subsystem)
    return register_bridge_capabilities(kernel, "document", caps)
