"""3-state provenance classification per Shogun spec §5."""
from typing import Dict, Optional

AUDIT_STATES = (
    "DLF_AVAILABLE",
    "DLF_SELECTED_OR_INJECTED",
    "DLF_SUBSTRATE_PROVENANCE_CONFIRMED",
)


def classify(node: Dict, weaves: Optional[list] = None) -> str:
    """Classify the audit state of a node.

    DLF_AVAILABLE                     — node exists; no use shown
    DLF_SELECTED_OR_INJECTED          — node entered generation context
    DLF_SUBSTRATE_PROVENANCE_CONFIRMED — has CREATIVE_SUBSTRATE/DERIVED_FROM weave
    """
    if not node:
        return "DLF_AVAILABLE"
    weaves = weaves or []
    confirming = {"CREATIVE_SUBSTRATE", "DERIVED_FROM"}
    nid = node.get("id")
    for w in weaves:
        if w.get("target") == nid and w.get("type") in confirming:
            return "DLF_SUBSTRATE_PROVENANCE_CONFIRMED"
    md = node.get("metadata") or {}
    if md.get("selected") or md.get("injected"):
        return "DLF_SELECTED_OR_INJECTED"
    return "DLF_AVAILABLE"
