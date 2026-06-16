"""
Ship 31cu — Pre-drill DLFR context injection.

Before the drill+rosetta pipeline runs on an inbound email, this module
writes the message's actual size/intent/sender into Rosetta's world_context
as a DLFR snapshot. Drill (step 1 of the bridge) reads world_context when
planning the deliverable, so it gets sized cues from the actual input.

This closes the loop that caused tonight's mcconnaire incident: drill was
producing a "substantive deliverable plan" for an 83-char casual probe,
because nothing told it the input was tiny and conversational.

Behavior:
  - For each inbound email, derive a {size_tier, intent_hint, sender_tier}
    triple from cheap heuristics (no LLM call).
  - Write it to rosetta_core.world_context under key
    "inbound_email:{from_addr}:{message_id}" — short-lived, per-request.
  - Optionally also pack as DLFR snapshot for audit.

Functionality preserved:
  - This is purely ADDITIVE — drill still runs on every email.
  - On any failure here, drill proceeds normally (graceful degradation).
  - No existing reply path is changed.

Reversible:
  - Skipping this module = old behavior (verified by tonight's logs).
"""
from __future__ import annotations

import logging
import hashlib
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def _size_tier(body: str) -> str:
    n = len(body or "")
    if n < 200:   return "tiny"        # casual probe / one-liner
    if n < 800:   return "short"       # short question
    if n < 3000:  return "medium"      # detailed question
    if n < 10000: return "long"        # involved correspondence
    return "very_long"                 # essay / thread


def _intent_hint(subject: str, body: str) -> str:
    t = (subject + " " + body).lower()
    if any(k in t for k in ("test", "see how it works", "what can you do", "hello", "hi ", "hmm")):
        return "casual_probe"
    if any(k in t for k in ("unsubscribe", "stop", "remove me", "opt out", "opt-out")):
        return "opt_out"
    if any(k in t for k in ("price", "cost", "quote", "pricing", "how much")):
        return "pricing_inquiry"
    if any(k in t for k in ("partnership", "collab", "joint", "white label")):
        return "partnership"
    if any(k in t for k in ("bug", "error", "broken", "not working", "issue with")):
        return "support_report"
    return "general_inquiry"


def _sender_tier(from_addr: str) -> str:
    addr = (from_addr or "").lower()
    if not addr:
        return "unknown"
    # Founder-invited allowlist
    try:
        with open("/etc/murphy-production/founder_invited.txt") as f:
            invited = {ln.strip().lower() for ln in f if ln.strip() and not ln.startswith("#")}
        if addr in invited:
            return "founder_invited"
    except Exception:
        pass
    # Free providers
    if any(addr.endswith(d) for d in ("@gmail.com", "@yahoo.com", "@hotmail.com",
                                       "@outlook.com", "@icloud.com")):
        return "consumer"
    # Likely-business domains
    return "business"


def shape_predrill_context(
    *,
    from_addr: str,
    subject: str,
    body: str,
    message_id: str = "",
) -> Dict:
    """Return a dict describing the shape of this inbound message."""
    size = _size_tier(body)
    intent = _intent_hint(subject, body)
    sender = _sender_tier(from_addr)

    # Map shape → recommended reply scale (overrides the global 5,000-char floor)
    scale_map = {
        ("tiny", "casual_probe"):   {"target_chars": (200, 600),  "tone": "casual"},
        ("tiny", "opt_out"):        {"target_chars": (50, 150),   "tone": "minimal"},
        ("short", "pricing_inquiry"): {"target_chars": (800, 1500), "tone": "direct"},
        ("short", "general_inquiry"): {"target_chars": (400, 1200), "tone": "casual"},
        ("medium", "support_report"): {"target_chars": (1500, 3000), "tone": "technical"},
        ("long", "partnership"):     {"target_chars": (3000, 6000), "tone": "substantive"},
    }
    scale = scale_map.get((size, intent), {"target_chars": (800, 2500), "tone": "balanced"})

    return {
        "size_tier": size,
        "intent_hint": intent,
        "sender_tier": sender,
        "input_chars": len(body or ""),
        "recommended_reply_chars_min": scale["target_chars"][0],
        "recommended_reply_chars_max": scale["target_chars"][1],
        "recommended_tone": scale["tone"],
        "from_addr": from_addr,
        "message_id": message_id,
    }


def inject_predrill_context(
    *,
    from_addr: str,
    subject: str,
    body: str,
    message_id: str = "",
) -> Optional[Dict]:
    """Write shape into rosetta_core.world_context for drill to read.

    Returns the shape dict on success, None on failure. NEVER raises.
    """
    try:
        shape = shape_predrill_context(
            from_addr=from_addr, subject=subject, body=body, message_id=message_id,
        )
        key_hash = hashlib.sha1(f"{from_addr}|{message_id}".encode()).hexdigest()[:12]
        ctx_key = f"inbound_email:{key_hash}"
        # Write to Rosetta soul (drill reads world_context during planning)
        try:
            from src.rosetta_core import get_rosetta_soul
            soul = get_rosetta_soul()
            import json
            payload = json.dumps(shape, sort_keys=True)
            # rosetta soul stores world_context as a dict of contexts
            soul.world_context[ctx_key] = payload
            if hasattr(soul, "save"):
                soul.save()
            logger.info("Ship 31cu: pre-drill context injected (size=%s intent=%s sender=%s -> reply %d-%d chars)",
                        shape["size_tier"], shape["intent_hint"], shape["sender_tier"],
                        shape["recommended_reply_chars_min"], shape["recommended_reply_chars_max"])
        except Exception as exc:
            logger.debug("Ship 31cu: rosetta world_context write failed (non-fatal): %s", exc)
        # Also snapshot as DLFR for audit
        try:
            from src.dlf_r import pack, store
            import json
            blob = pack(
                thread={"id": ctx_key, "kind": "inbound_email_predrill"},
                nodes=[{"id": "shape", "kind": "shape", "content": shape}],
                weaves=[],
            )
            store(blob, label=f"predrill_31cu:{ctx_key}")
        except Exception as exc:
            logger.debug("Ship 31cu: dlfr snapshot failed (non-fatal): %s", exc)
        return shape
    except Exception as exc:
        logger.warning("Ship 31cu: pre-drill injection completely failed (drill proceeds without): %s", exc)
        return None
