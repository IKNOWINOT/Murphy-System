"""Hygiene enforcement per Shogun spec §7."""
from typing import Dict

_REJECT_MARKERS = (
    "[LLM error]",
    "[empty answer blocked]",
    "[creative output contract violation]",
    "Traceback",
)


def is_usable_substrate(node: Dict) -> bool:
    """Return False if this node should NEVER be selected as future substrate."""
    if not node:
        return False
    md = node.get("metadata") or {}
    h = md.get("hygiene_status", "USABLE_CREATIVE_SUBSTRATE")
    if h == "REJECT_FUTURE_SELECTION":
        return False
    # Content-based markers (spec §7)
    payload = str(md.get("payload_preview", ""))
    if any(m in payload for m in _REJECT_MARKERS):
        return False
    return True


def mark_rejected(node: Dict, reason: str = "failed_generation_artifact") -> Dict:
    """Stamp a node as REJECT_FUTURE_SELECTION. Preserves the node for audit."""
    md = node.setdefault("metadata", {})
    md["hygiene_status"] = "REJECT_FUTURE_SELECTION"
    md["hygiene_reason"] = reason
    return node
