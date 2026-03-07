"""
Bot Inventory → AionMind Capability Bridge.

Converts the capabilities defined in ``bot_inventory_library.BotInventoryLibrary``
into :class:`Capability` objects and bulk-registers them into a
:class:`CapabilityRegistry` so the Reasoning Engine can plan against real
system capabilities rather than manually registered stubs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from aionmind.capability_registry import Capability, CapabilityRegistry

logger = logging.getLogger(__name__)


def _convert_capability(
    cap_id: str,
    cap_info: Dict[str, Any],
) -> Capability:
    """Convert a single bot-inventory capability dict to a :class:`Capability`."""
    params = cap_info.get("parameters", {})
    input_schema: Dict[str, Any] = {}
    for param_name, param_type in params.items():
        input_schema[param_name] = {"type": str(param_type)}

    module = cap_info.get("module", "unknown")

    return Capability(
        capability_id=f"bot_inv:{cap_id}",
        name=cap_info.get("name", cap_id),
        description=cap_info.get("description", ""),
        provider=module,
        input_schema=input_schema,
        output_schema={},
        tags=_derive_tags(cap_id, cap_info),
        risk_level=_derive_risk(cap_id),
        requires_approval=_derive_approval(cap_id),
        metadata={"origin": "bot_inventory_library", "function": cap_info.get("function", "")},
    )


def _derive_tags(cap_id: str, cap_info: Dict[str, Any]) -> List[str]:
    """Derive free-form tags from the capability name / module."""
    tags: List[str] = []
    name_lower = cap_info.get("name", cap_id).lower()
    module = cap_info.get("module", "").lower()

    tag_keywords = {
        "analysis": ["analyz", "audit", "detect", "track", "monitor"],
        "generation": ["generat", "creat", "provid"],
        "validation": ["validat", "check", "verif", "compli"],
        "orchestration": ["coordinat", "manag", "workflow", "optimi", "handl"],
        "reporting": ["report", "alert"],
    }
    for tag, keywords in tag_keywords.items():
        if any(kw in name_lower for kw in keywords):
            tags.append(tag)

    if module:
        tags.append(module)

    if not tags:
        tags.append("general")
    return tags


def _derive_risk(cap_id: str) -> str:
    """Conservative risk assignment."""
    high_risk = {"audit_system", "generate_contracts", "handle_conflicts"}
    if cap_id in high_risk:
        return "medium"
    return "low"


def _derive_approval(cap_id: str) -> bool:
    """Certain capabilities should require approval by default."""
    approval_required = {"generate_contracts", "handle_conflicts"}
    return cap_id in approval_required


def load_bot_capabilities_into_registry(
    registry: CapabilityRegistry,
    *,
    inventory: Optional[Any] = None,
) -> int:
    """Load all bot-inventory capabilities into *registry*.

    Parameters
    ----------
    registry : CapabilityRegistry
        Target registry (typically ``AionMindKernel.registry``).
    inventory : BotInventoryLibrary, optional
        An existing :class:`BotInventoryLibrary` instance.  When ``None`` a
        fresh one is created.

    Returns
    -------
    int
        Number of capabilities registered.
    """
    if inventory is None:
        try:
            from bot_inventory_library import BotInventoryLibrary
            inventory = BotInventoryLibrary()
        except ImportError:
            logger.warning(
                "bot_inventory_library not available — "
                "skipping capability bridge."
            )
            return 0

    cap_registry_raw: Dict[str, Dict[str, Any]] = getattr(
        inventory, "capability_registry", {}
    )
    if not cap_registry_raw:
        logger.info("Bot inventory has no capabilities to bridge.")
        return 0

    count = 0
    for cap_id, cap_info in cap_registry_raw.items():
        try:
            cap = _convert_capability(cap_id, cap_info)
            registry.register(cap)
            count += 1
        except Exception as exc:
            logger.exception("Failed to convert bot capability %s: %s", cap_id, exc)

    logger.info(
        "Bot capability bridge: registered %d / %d capabilities.",
        count,
        len(cap_registry_raw),
    )
    return count
