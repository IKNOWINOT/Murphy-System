"""
PATCH-HITL-PROV-ADAPTER-001 (2026-05-28 R66) — Provenance → HITL review adapter

WHAT THIS IS:
  Exposes hitl_provenance trails (R64) through a shape compatible with whatever
  hitl_review_builder produces, so existing HITL review UIs/callers can show
  provenance-flagged trails alongside their existing review items.

WHY IT EXISTS:
  R65 wrapped 5 commands with provenance. Trails accumulate in hitl_provenance.db
  but no human-facing surface presents them. 7 existing HITL modules handle
  reviews but don't know about provenance trails. Rather than edit any of
  them (many importers, brittle), this adapter exposes trails in a
  consumable shape.

HOW IT FITS:
  hitl_provenance.list_trails() returns raw trail rows.
  This adapter converts those into "review items" matching the shape used by
  hitl_review_builder consumers — so the existing review surfaces can include
  them with one extra import.

ENDPOINTS / PUBLIC SURFACE:
  get_provenance_review_items(status='pending', limit=20) -> List[Dict]
  get_flagged_count() -> int
  summarize_trail_for_human(trail_id) -> Dict  # human-readable card
  
DEPENDENCIES:
  - src.hitl_provenance (R64)

LAST UPDATED: 2026-05-28 R66
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger("hitl_prov_adapter")


def get_provenance_review_items(status: str = "pending", limit: int = 20) -> List[Dict[str, Any]]:
    """
    Return provenance trails in a shape suitable for HITL review queues.

    Each item:
      {
        "kind":              "provenance_trail",
        "id":                trail_id,
        "title":             "module.function — source_kind",
        "description":       short human-readable summary,
        "status":            pending | flagged | verified | corrected,
        "captured_at":       ISO timestamp,
        "verify_url":        /api/hitl/trail/<id>,
        "feedback_url":      /api/hitl/feedback/<id>,
        "source_kind":       db | config | llm | api | hardcoded | computed,
        "source_hint":       where the data actually came from,
        "raw":               full trail dict (for deep inspection),
      }
    """
    try:
        from src.hitl_provenance import list_trails
    except ImportError:
        logger.debug("hitl_provenance not available")
        return []

    trails = list_trails(hitl_status=status if status != "all" else None, limit=limit)
    items = []
    for t in trails:
        items.append({
            "kind":          "provenance_trail",
            "id":            t["trail_id"],
            "title":         f"{t.get('command_module','?')}.{t.get('command_function','?')} — {t.get('source_kind','?')}",
            "description":   (
                f"Command returned a result derived from {t.get('source_kind','?')} source: "
                f"{t.get('source_hint','?')}. Human verification requested."
            ),
            "status":        t.get("hitl_status", "pending"),
            "captured_at":   t.get("captured_at"),
            "verify_url":    f"/api/hitl/trail/{t['trail_id']}",
            "feedback_url":  f"/api/hitl/feedback/{t['trail_id']}",
            "source_kind":   t.get("source_kind"),
            "source_hint":   t.get("source_hint"),
            "raw":           t,
        })
    return items


def get_flagged_count() -> int:
    """How many provenance trails are flagged for review (have HITL tickets)."""
    try:
        from src.hitl_provenance import list_trails
        return len(list_trails(hitl_status="flagged", limit=10000))
    except ImportError:
        return 0


def summarize_trail_for_human(trail_id: str) -> Dict[str, Any]:
    """
    Return a human-readable card for a single trail — what to show in a UI:
    title, plain-English description, source explanation, raw command/result,
    action buttons (verify | flag | dispute).
    """
    try:
        from src.hitl_provenance import get_trail
    except ImportError:
        return {"error": "hitl_provenance not available"}

    trail = get_trail(trail_id)
    if not trail:
        return {"error": "trail not found", "trail_id": trail_id}

    # Build a human-friendly explanation of the source
    source_kind = trail.get("source_kind", "unknown")
    explanations = {
        "db":         "This came from a database table — verifiable by checking the underlying rows.",
        "config":     "This came from a configuration file — verifiable by checking the config source.",
        "llm":        "This came from an LLM response — verifiable only by inspecting the prompt and the model output.",
        "api":        "This came from an external API call — verifiable by reproducing the API request.",
        "hardcoded":  "This came from a HARDCODED literal in source code — verifiable by reading the literal.",
        "memory":     "This came from in-process memory state — verifiable by inspecting the same instance.",
        "computed":   "This was COMPUTED from inputs — verifiable by re-running with the same inputs.",
    }

    return {
        "trail_id":          trail_id,
        "title":             f"{trail.get('command_module','?')}.{trail.get('command_function','?')}",
        "what_it_did":       f"Called {trail.get('command_function','?')} with inputs.",
        "source_kind":       source_kind,
        "source_hint":       trail.get("source_hint"),
        "source_explanation": explanations.get(source_kind, "Unknown source — needs manual review."),
        "captured_at":       trail.get("captured_at"),
        "hitl_status":       trail.get("hitl_status"),
        "command_inputs":    trail.get("command_inputs"),
        "command_result":    trail.get("command_result"),
        "open_tickets":      len([t for t in trail.get("tickets", []) if t.get("status") == "open"]),
        "actions": {
            "verify_url":      f"/api/hitl/trail/{trail_id}/verify",
            "flag_url":        f"/api/hitl/trail/{trail_id}/flag",
            "feedback_url":    f"/api/hitl/feedback/{trail_id}",
        },
        "wire_version":      "HITL-PROV-ADAPTER-001",
    }


if __name__ == "__main__":
    print("── R66 smoke ──")
    items = get_provenance_review_items(status="all", limit=5)
    print(f"  Items: {len(items)}")
    for i in items[:3]:
        print(f"  • {i['title']:50} status={i['status']}")
    print(f"\n  Flagged count: {get_flagged_count()}")
    if items:
        card = summarize_trail_for_human(items[0]["id"])
        print(f"\n  Human card for {items[0]['id']}:")
        for k in ("title", "what_it_did", "source_kind", "source_explanation", "hitl_status"):
            print(f"    {k}: {card.get(k)}")
