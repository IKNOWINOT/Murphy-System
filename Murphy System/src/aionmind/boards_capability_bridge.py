"""Boards subsystem → AionMind capability bridge (Phase 2 / C11)."""

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
_PROVIDER = "boards"


def _try_import_subsystem() -> Any:
    for path in (
        "src.boards.board_engine",
        "src.boards",
        "boards.board_engine",
        "boards",
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
            capability_id="boards.list",
            name="List Boards",
            description="Return all accessible boards.",
            provider=_PROVIDER,
            input_schema={"_": {"type": "null"}},
            output_schema={
                "status": {"type": "string"},
                "boards": {"type": "array"},
            },
            risk_level=RISK_LOW,
            tags=["boards", "list", "read"],
            handler=_h("list", RISK_LOW),
        ),
        BridgeCapability(
            capability_id="boards.get",
            name="Get Board",
            description="Fetch a single board by id.",
            provider=_PROVIDER,
            input_schema={"board_id": {"type": "string", "required": True}},
            output_schema={
                "status": {"type": "string"},
                "board": {"type": "object"},
            },
            risk_level=RISK_LOW,
            tags=["boards", "read"],
            handler=_h("get", RISK_LOW),
        ),
        BridgeCapability(
            capability_id="boards.create",
            name="Create Board",
            description="Create a new board.",
            provider=_PROVIDER,
            input_schema={
                "name": {"type": "string", "required": True},
                "description": {"type": "string"},
            },
            output_schema={
                "status": {"type": "string"},
                "board_id": {"type": "string"},
            },
            risk_level=RISK_MEDIUM,
            tags=["boards", "create", "write"],
            handler=_h("create", RISK_MEDIUM),
        ),
        BridgeCapability(
            capability_id="boards.update",
            name="Update Board",
            description="Update an existing board.",
            provider=_PROVIDER,
            input_schema={
                "board_id": {"type": "string", "required": True},
                "patch": {"type": "object", "required": True},
            },
            output_schema={
                "status": {"type": "string"},
                "updated": {"type": "boolean"},
            },
            risk_level=RISK_MEDIUM,
            tags=["boards", "update", "write"],
            handler=_h("update", RISK_MEDIUM),
        ),
        BridgeCapability(
            capability_id="boards.delete",
            name="Delete Board",
            description="Delete a board.",
            provider=_PROVIDER,
            input_schema={"board_id": {"type": "string", "required": True}},
            output_schema={
                "status": {"type": "string"},
                "deleted": {"type": "boolean"},
            },
            risk_level=RISK_MEDIUM,
            requires_approval=True,
            tags=["boards", "delete", "write"],
            handler=_h("delete", RISK_MEDIUM),
        ),
    ]


def load_boards_capabilities_into_kernel(kernel: Any) -> int:
    subsystem = _try_import_subsystem()
    caps = _build_capabilities(subsystem)
    return register_bridge_capabilities(kernel, "boards", caps)
