"""
Ship 31f - Category Learning Loop (2026-06-10)
================================================

Machine-learns which categories Murphy sees inquiries from, tracks demand,
and promotes high-recurrence categories to starter agents in agent_contracts.

LOOP:
  1. Every stranger inquiry -> classify_category() returns a category slug
  2. log_inquiry() records the demand in category_demand_ledger
  3. evaluate_promotions() checks if any category has crossed threshold
     (default: 3 inquiries in 14 days, all with quality >= 7.0)
  4. promote_category() copies the BEST on-the-fly agent description into
     agent_contracts as is_starter_agent=1
  5. Next inquiry in that category: lookup_starter() returns the pre-built
     description; stranger_responder uses it as bootstrap (saves cost,
     improves consistency)

NOT MAGIC: starter agents are still magnify-drilled per-request, just
seeded with the curated description instead of cold-prompted.

PUBLIC SURFACE:
  classify_category(subject, body) -> {slug, label, vertical, confidence}
  log_inquiry(category, inquiry_id, mode, from_addr, subject, agent_desc, cost, quality_score=None)
  evaluate_promotions() -> [{slug, action, reason}]
  lookup_starter(category_slug) -> agent description or None
  get_underserved_categories(top_n=10) -> [{slug, demand, has_starter}]
  get_stats() -> aggregate stats

LAST UPDATED: 2026-06-10
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

sys.path.insert(0, "/opt/Murphy-System")

_DB = "/var/lib/murphy-production/entity_graph.db"

# Defaults (overridable per category in category_promotion_rules)
DEFAULT_INQUIRIES_REQUIRED = 3
DEFAULT_WINDOW_DAYS = 14
DEFAULT_MIN_QUALITY = 7.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def _slugify(label: str) -> str:
    """Reduce a free-text label to a stable slug."""
    import re
    s = label.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:60] or "unknown"


# ----------------------------------------------------------------------
# Classification - LLM-driven
# ----------------------------------------------------------------------

# (inline prompt now lives inside classify_category for vocab control)


def _list_existing_starters() -> List[Dict]:
    """Return all promoted starter categories with slug + label, for controlled vocab."""
    conn = _conn()
    try:
        rows = conn.execute(
            """SELECT starter_category_slug AS slug, role_title AS label, domain AS vertical
               FROM agent_contracts
               WHERE is_starter_agent = 1
               ORDER BY starter_use_count DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def classify_category(subject: str, body: str) -> Dict:
    """LLM-classify an inquiry. PREFER existing starter slugs over minting new ones.
    
    Strategy:
      1. Pull list of existing starter slugs
      2. Ask the LLM: "does this fit one of [...starters...]? If yes, return its slug.
         If no, propose a new slug."
      3. If the LLM returns an existing slug, use it (starter gets reused)
      4. If new, slugify cleanly and let promotion loop decide later
    """
    try:
        from src.llm_provider import get_llm
        existing = _list_existing_starters()
        vocab_block = ""
        if existing:
            vocab_lines = []
            for e in existing[:50]:  # cap at 50 for prompt size
                vocab_lines.append(f"  - {e['slug']}  ({e['label']}, {e['vertical']})")
            vocab_block = (
                "EXISTING STARTER AGENTS — strongly prefer reusing one of these slugs if the inquiry fits:\n"
                + "\n".join(vocab_lines)
                + "\n\nOnly mint a NEW slug if NONE of the above categories fit the inquiry.\n"
            )
        
        prompt = f"""You are Murphy's category classifier. Match this inquiry to an existing starter agent OR mint a new category.

{vocab_block}INQUIRY SUBJECT: {(subject or '')[:200]}
INQUIRY BODY: {(body or '')[:800]}

Respond with EXACTLY this JSON (no markdown, no explanation):
{{"slug": "<lowercase_snake_case>", "label": "<2-5 word business category>", "vertical": "<services|retail|hospitality|healthcare|finance|legal|real_estate|manufacturing|tech_saas|marketing|education|logistics|nonprofit|other>", "reused_existing": <true|false>, "confidence": <0.0-1.0>}}

If you pick an existing slug, set reused_existing=true and use its EXACT slug spelling. If you mint a new slug, set reused_existing=false."""
        
        result = get_llm().complete(prompt, model_hint="fast", max_tokens=160)
        text = (getattr(result, "content", "") or "").strip()
        if "```" in text:
            text = text.split("```")[1].strip()
            if text.startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
        slug = (data.get("slug") or "unknown").strip().lower()
        # Validate: if reused_existing=true, slug must match one we have
        existing_slugs = {e["slug"] for e in existing}
        if data.get("reused_existing") and slug not in existing_slugs:
            # LLM hallucinated a near-match — fall back to its label as new slug
            slug = _slugify(data.get("label") or slug)
        # Sanitize new slugs
        if not data.get("reused_existing"):
            slug = _slugify(slug or data.get("label") or "unknown")
        
        return {
            "slug": slug,
            "label": (data.get("label") or slug).strip(),
            "vertical": (data.get("vertical") or "other").strip().lower(),
            "confidence": float(data.get("confidence", 0.5)),
            "reused_existing": bool(data.get("reused_existing")),
        }
    except Exception as e:
        return {
            "slug": "unclassified",
            "label": "unclassified",
            "vertical": "other",
            "confidence": 0.0,
            "reused_existing": False,
            "error": str(e),
        }


# ----------------------------------------------------------------------
# Demand ledger
# ----------------------------------------------------------------------

def log_inquiry(
    category: Dict,
    inquiry_id: Optional[int] = None,
    delivery_mode: str = "direct",
    from_addr: str = "",
    from_domain: str = "",
    subject: str = "",
    agent_desc: str = "",
    cost_usd: float = 0.0,
    quality_score: Optional[float] = None,
    starter_used: bool = False,
    starter_id: Optional[str] = None,
) -> int:
    """Insert a row into category_demand_ledger. Returns row id."""
    conn = _conn()
    try:
        cur = conn.execute(
            """INSERT INTO category_demand_ledger
               (ts, category_slug, category_label, vertical, inquiry_id,
                delivery_mode, from_addr, from_domain, subject,
                agent_desc, quality_score, cost_usd, starter_used, starter_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (_now_iso(), category.get("slug"), category.get("label"),
             category.get("vertical"), inquiry_id, delivery_mode,
             (from_addr or "").lower(), (from_domain or "").lower(),
             (subject or "")[:300], (agent_desc or "")[:4000],
             quality_score, float(cost_usd or 0.0),
             1 if starter_used else 0, starter_id),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ----------------------------------------------------------------------
# Starter lookup + promotion
# ----------------------------------------------------------------------

def lookup_starter(category_slug: str) -> Optional[Dict]:
    """Returns the starter agent for a category, or None if not yet promoted."""
    conn = _conn()
    try:
        row = conn.execute(
            """SELECT agent_id, agent_name, role_title, duties_text,
                      authorised_actions, off_limits, ocean_json,
                      starter_quality_score, starter_use_count
               FROM agent_contracts
               WHERE is_starter_agent = 1 AND starter_category_slug = ?
               ORDER BY starter_quality_score DESC NULLS LAST
               LIMIT 1""",
            (category_slug,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def evaluate_promotions(now: Optional[datetime] = None) -> List[Dict]:
    """Walk category_demand_ledger, find categories that cross promotion thresholds,
    promote the best-quality agent description into agent_contracts."""
    if now is None:
        now = datetime.now(timezone.utc)
    
    conn = _conn()
    actions = []
    try:
        # Pull all category counts in window
        window_start = (now - timedelta(days=DEFAULT_WINDOW_DAYS)).isoformat()
        rows = conn.execute(
            """SELECT category_slug, category_label, vertical,
                      COUNT(*) AS n,
                      AVG(quality_score) AS avg_q,
                      MAX(quality_score) AS max_q
               FROM category_demand_ledger
               WHERE ts > ? AND category_slug NOT IN ('unclassified', 'unknown')
               GROUP BY category_slug
               ORDER BY n DESC""",
            (window_start,),
        ).fetchall()
        
        for r in rows:
            slug = r["category_slug"]
            n = r["n"]
            avg_q = r["avg_q"]
            
            # Check if already promoted
            existing = conn.execute(
                "SELECT * FROM category_promotion_rules WHERE category_slug = ?",
                (slug,),
            ).fetchone()
            if existing and existing["promoted_at"]:
                actions.append({"slug": slug, "action": "skipped",
                                "reason": f"already promoted at {existing['promoted_at']}"})
                continue
            
            # Check threshold
            required = (existing["inquiries_required"] if existing else DEFAULT_INQUIRIES_REQUIRED)
            min_q = (existing["min_quality_score"] if existing else DEFAULT_MIN_QUALITY)
            
            if n < required:
                actions.append({"slug": slug, "action": "under_threshold",
                                "reason": f"{n}/{required} inquiries"})
                continue
            
            # Quality gate: only promote if at least one inquiry was rated >= min_q,
            # OR if quality is None (no reviews yet, but volume crossed threshold)
            if avg_q is not None and avg_q < min_q:
                actions.append({"slug": slug, "action": "quality_gate_fail",
                                "reason": f"avg_q={avg_q:.2f} < {min_q}"})
                continue
            
            # Promote: pick the highest-quality (or most recent) agent_desc for this slug
            best = conn.execute(
                """SELECT agent_desc, category_label, vertical, quality_score, ts
                   FROM category_demand_ledger
                   WHERE category_slug = ? AND agent_desc IS NOT NULL
                     AND LENGTH(agent_desc) > 100
                   ORDER BY COALESCE(quality_score, 0) DESC, ts DESC
                   LIMIT 1""",
                (slug,),
            ).fetchone()
            if not best:
                actions.append({"slug": slug, "action": "no_desc_available",
                                "reason": "no agent_desc on file"})
                continue
            
            import secrets
            agent_id = f"starter_{slug}_{secrets.token_hex(4)}"
            agent_name = f"Starter Agent: {r['category_label']}"
            role_title = r["category_label"]
            
            conn.execute(
                """INSERT INTO agent_contracts
                   (id, agent_id, agent_name, role_title, department, domain,
                    duties_text, is_starter_agent, starter_category_slug,
                    starter_quality_score, starter_use_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 0)""",
                (agent_id, agent_id, agent_name, role_title, "starter",
                 r["vertical"], best["agent_desc"], slug,
                 best["quality_score"]),
            )
            
            # Upsert into promotion_rules
            if existing:
                conn.execute(
                    """UPDATE category_promotion_rules
                       SET promoted_at = ?, promoted_agent_id = ?, last_evaluated_at = ?
                       WHERE category_slug = ?""",
                    (_now_iso(), agent_id, _now_iso(), slug),
                )
            else:
                conn.execute(
                    """INSERT INTO category_promotion_rules
                       (category_slug, inquiries_required, window_days,
                        min_quality_score, promoted_at, promoted_agent_id,
                        last_evaluated_at, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (slug, DEFAULT_INQUIRIES_REQUIRED, DEFAULT_WINDOW_DAYS,
                     DEFAULT_MIN_QUALITY, _now_iso(), agent_id, _now_iso(),
                     f"auto-promoted from {n} inquiries"),
                )
            conn.commit()
            actions.append({"slug": slug, "action": "promoted",
                            "agent_id": agent_id, "label": r["category_label"],
                            "inquiries": n})
        
        return actions
    finally:
        conn.close()


# ----------------------------------------------------------------------
# Observability
# ----------------------------------------------------------------------

def get_underserved_categories(top_n: int = 10, window_days: int = 30) -> List[Dict]:
    """Categories with demand but no starter yet, OR low starter quality."""
    conn = _conn()
    try:
        window_start = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
        rows = conn.execute(
            """SELECT cdl.category_slug,
                      cdl.category_label,
                      cdl.vertical,
                      COUNT(*) AS demand,
                      AVG(cdl.quality_score) AS avg_q,
                      MAX(CASE WHEN ac.is_starter_agent = 1 THEN 1 ELSE 0 END) AS has_starter,
                      MAX(ac.starter_quality_score) AS starter_q
               FROM category_demand_ledger cdl
               LEFT JOIN agent_contracts ac
                 ON ac.starter_category_slug = cdl.category_slug AND ac.is_starter_agent = 1
               WHERE cdl.ts > ?
                 AND cdl.category_slug NOT IN ('unclassified','unknown')
               GROUP BY cdl.category_slug
               ORDER BY (CASE WHEN MAX(ac.is_starter_agent) = 1 THEN 1 ELSE 0 END) ASC,
                        COUNT(*) DESC
               LIMIT ?""",
            (window_start, top_n),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_stats() -> Dict:
    conn = _conn()
    try:
        ledger = conn.execute(
            """SELECT COUNT(*) total_inquiries,
                      COUNT(DISTINCT category_slug) unique_categories,
                      COUNT(DISTINCT from_domain) unique_domains,
                      AVG(quality_score) avg_quality,
                      SUM(cost_usd) total_cost
               FROM category_demand_ledger"""
        ).fetchone()
        starters = conn.execute(
            "SELECT COUNT(*) starter_count, AVG(starter_quality_score) avg_q FROM agent_contracts WHERE is_starter_agent = 1"
        ).fetchone()
        promoted = conn.execute(
            "SELECT COUNT(*) FROM category_promotion_rules WHERE promoted_at IS NOT NULL"
        ).fetchone()[0]
        return {
            "ledger": dict(ledger),
            "starter_agents": dict(starters),
            "promoted_categories": promoted,
        }
    finally:
        conn.close()
