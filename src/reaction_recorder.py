"""
PATCH-REACTIONS-R103 (2026-05-28 R103) — agent reactions to outputs of work

WHAT THIS IS:
  First-person agent voice substrate. When an agent produces output,
  this primitive captures its REACTION — how the agent felt about
  what just came out.

WHY IT EXISTS:
  Corey R101.8: "It would be like it showing reaction to outputs of work."
  
  Three rounds of clarification (R101.5 input-shape, R101.7 log-shape,
  R101.8 reaction-shape) landed on this: agents have a voice that
  REACTS to what their work produces. Not metrics. Not log. Reaction.
  
  Composes into the YouTube-style feed (Phase I1) where Corey scrolls
  to see what his agents are reacting to today.

DESIGN CHOICE LOCKED R103: SYNCHRONOUS reaction capture at work-output time
  Murphy refused (HTTP 000 mid-restart). My call.
  Reason: async-detector pattern creates a window where a regression
  ships before reaction-flag fires. Sync coupling guarantees the
  reaction lands BEFORE the next workflow proceeds. ~200ms cost is
  trivial against the security gain (R102 KEK lesson: freshness wins).

HYBRID GENERATION MODE (R101.8 default Option C):
  Template scaffold: "Ran {capability}. Got {output}. Delta {delta}."
  Optional LLM enrichment: adds valence + 1-2 sentence agent voice
  Anchor: evidence_blob always carries raw output (keeps it honest)
  
  When LLM unavailable, falls back to template-only. Substrate still works.

PUBLIC SURFACE:
  capture_reaction(agent_id, work_event_table, work_event_id, work_summary,
                   evidence, expected_outcome=None, mode="hybrid")
    Returns {ok, reaction_id, reaction_text, valence, confidence}
  
  recent_reactions(agent_id=None, limit=50) → feed-render primitive
  
  validate_reaction(reaction_id, is_real, validator) → walker_cli hook
  
  reactions_for_event(work_event_table, work_event_id) → drill-down primitive

VALENCE CATEGORIES:
  surprised_good   — output cleaner/better than expected
  expected         — matched what agent predicted
  off              — wrong-direction or unexpected miss
  puzzled          — output is ambiguous, agent unsure
  wait             — agent noticed something mid-output
  huh              — agent observed an interesting pattern
  regression       — worse than prior similar work
  mostly_landed    — partial success with caveats

DEPENDS ON:
  cryptography hashlib (reaction_id derivation)
  src/tag_writer.py (auto-tag reactions for facet_tags chain)
  hitl_provenance.db with agent_reactions table

LAST UPDATED: 2026-05-28 R103
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_DB_PATH = "/var/lib/murphy-production/hitl_provenance.db"

_VALID_VALENCES = {
    "surprised_good", "expected", "off", "puzzled",
    "wait", "huh", "regression", "mostly_landed"
}


def _reaction_id(agent_id: str, work_event_id: str, ts: str) -> str:
    """Deterministic ID — same agent reacting to same event at same time."""
    return hashlib.sha256(
        "rx::{}::{}::{}".format(agent_id, work_event_id, ts).encode()
    ).hexdigest()[:16]


def _classify_valence(work_summary: str, evidence: Dict[str, Any],
                      expected: Optional[Dict[str, Any]] = None) -> tuple:
    """
    PATCH-REACTIONS-R104 — mixed-outcome aware classifier.
    
    Returns (valence, confidence, reaction_seed) where seed pulls
    concrete evidence values so reactions stay anchored, not theater.
    """
    if not isinstance(evidence, dict):
        evidence = {}
    ok = evidence.get("ok")
    delta = evidence.get("delta")
    gap = evidence.get("gap")
    reason = evidence.get("reason")

    # ── R104: detect mixed-outcome caveats inside ok=True paths ──
    # These keys, when present + falsy, signal partial-success
    caveat_keys = (
        "existing_cred_decrypts", "existing_r96_cred_decrypts",
        "backward_compat", "regression_check", "side_effect_clean",
    )
    has_caveat = any(
        k in evidence and evidence[k] is False
        for k in caveat_keys
    )
    # Also: reason field PRESENT with ok=True signals "worked but..."
    reason_with_ok = (ok is True and isinstance(reason, str) and reason)

    # ── Failure path ──
    if ok is False:
        if expected and expected.get("ok") is False:
            return ("expected", 0.8,
                    "Got the failure I predicted: {}".format((reason or "n/a")[:120]))
        return ("off", 0.85,
                "Failed unexpectedly. Reason: {}".format((reason or "n/a")[:120]))

    # ── R104 NEW: mixed-outcome ──
    if ok is True and (has_caveat or reason_with_ok):
        # Pull the specific caveat detail
        caveat_detail = ""
        for k in caveat_keys:
            if k in evidence and evidence[k] is False:
                caveat_detail = "{} reports False; ".format(k)
                break
        if reason_with_ok:
            caveat_detail += "carries reason: {}".format(reason[:100])
        return ("mostly_landed", 0.8,
                "Mostly clean — {}".format(caveat_detail or "with a caveat I caught"))

    # ── Delta-shaped ──
    if isinstance(delta, (int, float)) and delta != 0:
        if delta > 0:
            return ("surprised_good", 0.75,
                    "Output landed +{} above prior baseline.".format(delta))
        return ("regression", 0.85,
                "Output slipped {} below prior baseline.".format(delta))

    # ── Gap-shaped ──
    if isinstance(gap, (int, float)):
        if abs(gap) < 0.01:
            # R104: pull richer evidence into the seed if available
            rv = evidence.get("reality_value")
            lv = evidence.get("ledger_value")
            if rv is not None and lv is not None:
                return ("expected", 0.9,
                        "Reality {} matched ledger {} cleanly.".format(rv, lv))
            return ("expected", 0.9, "Reality matched ledger exactly. Clean.")
        return ("huh", 0.7,
                "Gap of {} between reality and ledger.".format(gap))

    # ── Plain success (R104: pull richer detail when present) ──
    if ok is True:
        # Operation type adds character
        op = evidence.get("operation") or evidence.get("op")
        steps = evidence.get("steps_completed") or evidence.get("steps")
        if op and steps:
            return ("expected", 0.8,
                    "{} ({} steps) completed clean.".format(op, steps))
        if op:
            return ("expected", 0.75,
                    "{} completed clean.".format(op))
        return ("expected", 0.7,
                "{} completed clean.".format(work_summary[:60]))

    return ("puzzled", 0.5,
            "Not sure how to read this output: {}".format(work_summary[:80]))


def _try_llm_enrich(agent_id: str, work_summary: str, valence: str,
                    seed: str, evidence: Dict[str, Any]) -> Optional[str]:
    """
    PATCH-REACTIONS-R104 — LLM voice enrichment via /api/chat HTTP.
    
    R103 mistake: imported invented module name MurphyLLMProvider.
    R104 fix: use Murphy's own /api/chat HTTP endpoint (same path
    that works reliably from external clients). No fragile imports.
    
    Returns None if Murphy unavailable, falls back to seed.
    """
    try:
        import os, json, urllib.request
        api_key = os.environ.get("FOUNDER_API_KEY", "").strip()
        if not api_key:
            try:
                with open("/etc/murphy-production/environment") as f:
                    for line in f:
                        if line.startswith("FOUNDER_API_KEY="):
                            api_key = line.split("=", 1)[1].strip()
                            break
            except Exception:
                return None
        if not api_key:
            return None

        ev_keys = list(evidence.keys())[:6] if isinstance(evidence, dict) else []
        ev_excerpt = {k: evidence.get(k) for k in ev_keys}
        prompt = (
            "Refuse if uncertain. You ARE agent '{}'. "
            "You just produced output: '{}'. "
            "Computed valence: {}. "
            "Template seed (anchor): '{}'. "
            "Evidence excerpt: {}. "
            "Reply with a 1-2 sentence FIRST-PERSON reaction in your own voice. "
            "MUST reference at least one concrete value from the evidence. "
            "Do NOT invent facts. Honest 'I'm not sure' if mixed."
        ).format(agent_id, work_summary[:120], valence, seed[:120], ev_excerpt)

        payload = json.dumps({
            "message": prompt,
            "session_id": "rx_enrich_{}_{}".format(agent_id, hash(seed) & 0xFFFF),
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/chat",
            data=payload,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            reply = (data.get("reply") or "").strip()
            if 10 < len(reply) < 600:
                # Strip the "Actually let me check" confabulation pattern
                if "Actually" in reply:
                    reply = reply.split("Actually")[0].strip()
                if reply:
                    return reply
    except Exception:
        pass
    return None


def capture_reaction(agent_id: str, work_event_table: str,
                     work_event_id: str, work_summary: str,
                     evidence: Optional[Dict[str, Any]] = None,
                     expected_outcome: Optional[Dict[str, Any]] = None,
                     mode: str = "hybrid",
                     db_path: str = _DB_PATH) -> Dict[str, Any]:
    """
    Capture an agent's reaction to a work output.
    mode: 'template' (no LLM), 'hybrid' (template + optional LLM), 'sync' alias.
    """
    if not agent_id or not work_summary:
        return {"ok": False, "reason": "missing_required_fields"}
    if evidence is None:
        evidence = {}

    valence, confidence, seed = _classify_valence(
        work_summary, evidence, expected_outcome
    )

    reaction_text = seed
    if mode in ("hybrid", "sync"):
        enriched = _try_llm_enrich(agent_id, work_summary, valence, seed, evidence)
        if enriched:
            reaction_text = enriched
            confidence = min(0.9, confidence + 0.05)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    reaction_id = _reaction_id(agent_id, work_event_id, ts)

    thumbnail = "{}: {} ({})".format(agent_id, work_summary[:60], valence)

    try:
        evidence_json = json.dumps(evidence, default=str)[:8000]
    except Exception:
        evidence_json = "{}"

    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.execute(
            "INSERT OR IGNORE INTO agent_reactions "
            "(reaction_id, agent_id, work_event_table, work_event_id, "
            " work_summary, reaction_text, valence, confidence, "
            " evidence_blob, thumbnail_summary, capture_mode) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (reaction_id, agent_id, work_event_table, work_event_id,
             work_summary[:500], reaction_text[:1000], valence,
             confidence, evidence_json, thumbnail[:200], mode),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        return {"ok": False, "reason": "db_write: {}: {}".format(type(e).__name__, e)}

    # Auto-tag via facet_tags chain
    try:
        import sys
        if "/opt/Murphy-System" not in sys.path:
            sys.path.insert(0, "/opt/Murphy-System")
        from src.tag_writer import write_tags
        tags = [
            {"axis": "what", "tag_value": "#reaction", "confidence": 1.0, "source": "rule"},
            {"axis": "what", "tag_value": "#" + valence, "confidence": 1.0, "source": "rule"},
            {"axis": "who", "tag_value": "#" + agent_id, "confidence": 1.0, "source": "rule"},
            {"axis": "when", "tag_value": "#today", "confidence": 1.0, "source": "rule"},
            {"axis": "how", "tag_value": "#" + mode, "confidence": 1.0, "source": "rule"},
        ]
        if work_event_table:
            tags.append({"axis": "what", "tag_value": "#" + work_event_table,
                         "confidence": 0.9, "source": "rule"})
        write_tags("agent_reactions", reaction_id, tags)
    except Exception:
        pass

    return {
        "ok": True,
        "reaction_id": reaction_id,
        "agent_id": agent_id,
        "valence": valence,
        "confidence": confidence,
        "reaction_text": reaction_text,
        "thumbnail": thumbnail,
    }


def recent_reactions(agent_id: Optional[str] = None, limit: int = 50,
                     db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """Feed-render primitive — return recent reactions."""
    try:
        conn = sqlite3.connect(db_path, timeout=3)
        conn.row_factory = sqlite3.Row
        if agent_id:
            rows = conn.execute(
                "SELECT * FROM agent_reactions WHERE agent_id = ? "
                "ORDER BY captured_at DESC LIMIT ?",
                (agent_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agent_reactions ORDER BY captured_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": "{}: {}".format(type(e).__name__, e)}]


def validate_reaction(reaction_id: str, is_real: bool, validator: str,
                      db_path: str = _DB_PATH) -> Dict[str, Any]:
    """Walker_cli hook — mark reaction as real or theater."""
    try:
        conn = sqlite3.connect(db_path, timeout=3)
        cur = conn.execute(
            "UPDATE agent_reactions "
            "SET human_validated = ?, validated_at = CURRENT_TIMESTAMP, "
            "    validated_by = ? WHERE reaction_id = ?",
            (1 if is_real else 0, validator, reaction_id),
        )
        conn.commit()
        n = cur.rowcount
        conn.close()
        return {"ok": True, "validated": is_real, "rows_updated": n}
    except Exception as e:
        return {"ok": False, "reason": "{}: {}".format(type(e).__name__, e)}


if __name__ == "__main__":
    # Self-demonstrating: capture R103's own reaction to today's work
    r = capture_reaction(
        agent_id="patcher",
        work_event_table="git_commits",
        work_event_id="3e56dcdf",
        work_summary="R102 KEK-routed vault patch shipped",
        evidence={
            "ok": True,
            "kek_chain_depth": 4,
            "byte_match_unwrap_to_root_vs_env_direct": True,
            "existing_r96_cred_decrypts": False,
            "reason": "encoding_mismatch_raw_encode_vs_fromhex",
            "new_creds_work": True,
        },
        mode="hybrid",
    )
    print("R103 self-demo reaction:")
    for k, v in r.items():
        print("  {}: {}".format(k, v))
