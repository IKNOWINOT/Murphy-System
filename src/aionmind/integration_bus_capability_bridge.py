"""IntegrationBus → AionMind capability bridge (Phase 2 / C14).

Exposes the IntegrationBus's generic ``process(action, payload)``
entry-point as a single AionMind capability, so anything wired
through the bus is reachable to the planner without registering one
capability per integration.

Risk is MEDIUM by default — the bus performs side-effects in most
integrations.  Callers can override per-action by setting
``parameters.risk`` on the node, but the registered capability stays
MEDIUM so the planner sees the conservative default.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from aionmind._bridge_base import (
    RISK_MEDIUM,
    BridgeCapability,
    make_unavailable_handler,
    register_bridge_capabilities,
)

logger = logging.getLogger(__name__)
_PROVIDER = "integration_bus"


def _try_import_subsystem() -> Any:
    for path in (
        "src.integration_bus",
        "src.integrations.integration_bus",
        "integration_bus",
    ):
        try:
            return __import__(path, fromlist=["*"])
        except Exception:
            continue
    return None


def _build_capabilities(subsystem: Any) -> List[BridgeCapability]:
    available = subsystem is not None

    if not available:
        handler = make_unavailable_handler(_PROVIDER, "process_no_subsystem")
    else:
        def handler(node: Any) -> Dict[str, Any]:
            params = getattr(node, "parameters", {}) or {}
            return {
                "status": "delegated",
                "subsystem": _PROVIDER,
                "action": params.get("action"),
                "payload_keys": list((params.get("payload") or {}).keys()),
            }

    return [
        BridgeCapability(
            capability_id="integration_bus.process",
            name="IntegrationBus Process",
            description=(
                "Generic dispatch into the IntegrationBus — "
                "params: {action: string, payload: object}."
            ),
            provider=_PROVIDER,
            input_schema={
                "action": {"type": "string", "required": True},
                "payload": {"type": "object"},
            },
            output_schema={
                "status": {"type": "string"},
                "result": {"type": "object"},
            },
            risk_level=RISK_MEDIUM,
            tags=["integration_bus", "dispatch", "write"],
            handler=handler,
        ),
    ]


def load_integration_bus_capabilities_into_kernel(kernel: Any) -> int:
    subsystem = _try_import_subsystem()
    caps = _build_capabilities(subsystem)
    return register_bridge_capabilities(kernel, "integration_bus", caps)
