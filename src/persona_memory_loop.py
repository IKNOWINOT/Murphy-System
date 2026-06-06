"""
R64c — Persona Memory Loop

Reads recent HITL corrections for an agent_type and renders them as a
prepended block for the agent's system_prompt. Closes the loop:

    1. Persona issues a recommendation
    2. Human applies / rejects / revises it via HITL
    3. The decision is recorded in rosetta_learning.db (R64a + R64b)
    4. Next time the same persona runs, this module reads its recent
       corrections and prepends them so the agent doesn't repeat mistakes

Importance scoring: rejections > revisions > approvals (we learn most from
what humans changed). The "importance" column on agent_corrections is
already populated by record_decision().

This module is read-only — it only READS rosetta_learning.db. The /decide
hooks (R64b) own the writes.
"""

from __future__ import annotations
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


def render_correction_block(
    agent_type: str,
    limit: int = 5,
    min_importance: float = 0.0,
    title: str = "RECENT HUMAN CORRECTIONS",
) -> str:
    """Return a system-prompt block summarising recent human corrections.

    Returns "" if no corrections exist, the DB is unavailable, or anything
    goes wrong. Persona injection should ALWAYS work even when this fails.

    Args:
        agent_type: the agent_type column value (e.g. "sales", "executive")
        limit: max corrections to include
        min_importance: skip rows below this importance
        title: header for the block
    """
    try:
        # Import lazily so module-level import is cheap and isolated
        from src.runtime.rosetta_learning import get_top_corrections
    except Exception as e:
        try:
            from runtime.rosetta_learning import get_top_corrections  # type: ignore
        except Exception:
            logger.debug("persona_memory_loop: rosetta_learning unavailable: %s", e)
            return ""

    try:
        rows = get_top_corrections(agent_type, limit=limit, only_undistilled=False)
    except Exception as e:
        logger.warning("persona_memory_loop: get_top_corrections failed: %s", e)
        return ""

    if not rows:
        return ""

    # Filter and shape
    useful = []
    for r in rows:
        imp = float(r.get("importance") or 0.0)
        if imp < min_importance:
            continue
        decision = (r.get("decision") or "").lower()
        reason = (r.get("reason") or "").strip()
        if not reason and decision == "approved":
            # Approvals without reasons aren't very instructive
            continue
        useful.append((decision, reason, imp))

    if not useful:
        return ""

    lines = [f"■ {title} (last {len(useful)} for agent_type={agent_type})"]
    lines.append("─" * 60)
    lines.append("  Apply these lessons. The human reviewer changed your previous")
    lines.append("  outputs because of these. Don't repeat the same mistakes.")
    lines.append("")
    for decision, reason, imp in useful:
        verb = {
            "rejected":     "✗ rejected — ",
            "revised":      "✎ revised — ",
            "regenerated":  "↻ regenerated — ",
            "approved":     "✓ approved with note — ",
        }.get(decision, f"({decision}) ")
        if reason:
            lines.append(f"  {verb}{reason}  (importance={imp:.2f})")
        else:
            lines.append(f"  {verb}(no reason recorded, importance={imp:.2f})")
    lines.append("")
    return "\n".join(lines)


def prepend_to_prompt(
    base_prompt: str,
    agent_type: str,
    limit: int = 5,
) -> str:
    """Convenience: prepend correction block to base_prompt iff non-empty."""
    block = render_correction_block(agent_type, limit=limit)
    if not block:
        return base_prompt
    return f"{block}\n\n{base_prompt}"
