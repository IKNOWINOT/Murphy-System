"""
Ship 31m — Contextual Ad Engine for free-tier email replies.

Picks a relevant sponsored line based on (role, vertical, topic_keywords)
extracted from the inbound email. Records impressions + clicks.

DESIGN PRINCIPLES (founder-locked 2026-06-10):
- One ad max per reply
- Confidence threshold: NO AD beats a bad ad
- FTC-compliant "Sponsored" label always
- Free tier only — paid tiers skip ad injection entirely
- No tracking pixels — plain clickable links with UTM tags
- Honest: log every match decision for audit

Schema:
  ad_inventory(id, advertiser, headline, body_line, click_url,
               role_targets, vertical_targets, keyword_targets,
               cpc_usd, status, impressions, clicks, created_ts)
  ad_impressions(id, ad_id, reply_id, role_detected, vertical_detected,
                 keywords_matched, score, sent_ts, click_ts)
"""

import re, sqlite3, hashlib, logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
DB = "/var/lib/murphy-production/entity_graph.db"
MIN_MATCH_SCORE = 0.40   # below this → no ad, better than bad ad
TRACKING_BASE = "https://murphy.systems/r/"  # redirect endpoint for click tracking


# ─── Schema ───────────────────────────────────────────────────────────
def ensure_schema():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS ad_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        advertiser TEXT NOT NULL,
        headline TEXT NOT NULL,
        body_line TEXT NOT NULL,
        click_url TEXT NOT NULL,
        role_targets TEXT,
        vertical_targets TEXT,
        keyword_targets TEXT,
        cpc_usd REAL DEFAULT 0.0,
        status TEXT DEFAULT 'active',
        impressions INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        created_ts TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS ad_impressions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad_id INTEGER NOT NULL,
        reply_to_addr TEXT,
        role_detected TEXT,
        vertical_detected TEXT,
        keywords_matched TEXT,
        score REAL,
        sent_ts TEXT,
        click_ts TEXT,
        click_token TEXT UNIQUE
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ad_status ON ad_inventory(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_imp_ad ON ad_impressions(ad_id)")
    c.commit(); c.close()


# ─── Topic extraction (regex first, LLM later if needed) ──────────────
_STOP = set("a an the to in on at for of and or but is are was were be been being have has had do does did will would could should may might must can shall this that these those it its their there here you your we our with from as by".split())


def extract_topic_keywords(subject: str, body: str, max_kw: int = 8):
    """Cheap keyword extractor — frequency in subject+body, minus stopwords.

    Returns lowercase list. Roles/verticals come from elsewhere; this is
    purely topical (e.g. "audit", "saas", "renewal", "hiring").
    """
    text = ((subject or "") + " " + (body or "")[:2000]).lower()
    # tokenize: keep alphanumeric words of length >= 4
    words = re.findall(r"\b[a-z][a-z0-9]{3,}\b", text)
    words = [w for w in words if w not in _STOP]
    # frequency
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    # top N
    top = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
    return [w for w, _ in top[:max_kw]]


# ─── Match scoring ────────────────────────────────────────────────────
def _parse_targets(field):
    """role_targets etc. stored as comma-separated string."""
    if not field:
        return set()
    return set(x.strip().lower() for x in field.split(",") if x.strip())


def _score_ad(ad_row, role, vertical, keywords):
    """0.0–1.0 match score for an ad against detected context.

    Weights:
      role match:     0.40  (strong signal)
      vertical match: 0.30
      keyword overlap: up to 0.30 (proportional)
    """
    role_targets = _parse_targets(ad_row["role_targets"])
    vert_targets = _parse_targets(ad_row["vertical_targets"])
    kw_targets = _parse_targets(ad_row["keyword_targets"])

    score = 0.0
    matched_kws = []
    if role and role.lower() in role_targets:
        score += 0.40
    if vertical and vertical.lower() in vert_targets:
        score += 0.30
    if kw_targets and keywords:
        kw_set = set(k.lower() for k in keywords)
        overlap = kw_set & kw_targets
        matched_kws = sorted(overlap)
        if kw_targets:
            score += 0.30 * (len(overlap) / max(1, len(kw_targets)))
    return min(1.0, score), matched_kws


def pick_ad(role: str, vertical: str, keywords):
    """Return best-matching ad dict, or None if no match above threshold."""
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    rows = c.execute("SELECT * FROM ad_inventory WHERE status='active'").fetchall()
    c.close()
    if not rows:
        return None
    best = None
    best_score = 0.0
    best_kws = []
    for row in rows:
        s, kws = _score_ad(row, role, vertical, keywords)
        if s > best_score:
            best_score = s; best = row; best_kws = kws
    if best_score < MIN_MATCH_SCORE:
        logger.info("pick_ad: no match above threshold (best=%.2f)", best_score)
        return None
    return {
        "id": best["id"], "advertiser": best["advertiser"],
        "headline": best["headline"], "body_line": best["body_line"],
        "click_url": best["click_url"], "cpc_usd": best["cpc_usd"],
        "score": round(best_score, 3), "matched_keywords": best_kws,
    }


# ─── Render + track ───────────────────────────────────────────────────
def _make_tracking_url(ad_id: int, reply_to_addr: str, click_url: str):
    """Make a tracked click URL.

    Generates a token, records impression, returns redirect URL.
    Falls back to direct URL if DB insert fails (better link than no link).
    """
    seed = f"{ad_id}:{reply_to_addr}:{datetime.now(timezone.utc).isoformat()}"
    token = hashlib.sha256(seed.encode()).hexdigest()[:24]
    return TRACKING_BASE + token, token


def render_ad_block(ad: dict) -> str:
    """Render the ad as a small plaintext block to append to a reply."""
    if not ad:
        return ""
    return ("\n\n— — —\n"
            "Sponsored: " + ad["headline"] + "\n"
            + ad["body_line"] + "\n"
            + ad["click_url"] + "\n"
            "— — —")


def record_impression(ad_id: int, reply_to_addr: str, role: str,
                      vertical: str, keywords_matched, score: float):
    """Log that ad was shown to user. Returns click_token."""
    seed = f"{ad_id}:{reply_to_addr}:{datetime.now(timezone.utc).isoformat()}"
    token = hashlib.sha256(seed.encode()).hexdigest()[:24]
    try:
        c = sqlite3.connect(DB)
        c.execute("""INSERT INTO ad_impressions
            (ad_id, reply_to_addr, role_detected, vertical_detected,
             keywords_matched, score, sent_ts, click_token)
            VALUES (?,?,?,?,?,?,?,?)""",
            (ad_id, reply_to_addr, role, vertical,
             ",".join(keywords_matched or []), score,
             datetime.now(timezone.utc).isoformat(), token))
        c.execute("UPDATE ad_inventory SET impressions=impressions+1 WHERE id=?", (ad_id,))
        c.commit(); c.close()
    except Exception as exc:
        logger.warning("record_impression failed: %s", exc)
    return token


def inject_ad_into_reply(reply_text: str, role: str, vertical: str,
                          subject: str, body: str, reply_to_addr: str,
                          tier: str = "free"):
    """Main entry point. Returns (new_reply_text, ad_meta) tuple.

    If tier != 'free' → no ad ever.
    If no good match → no ad.
    Otherwise: pick, render, append, record impression.
    """
    if tier != "free":
        return reply_text, None
    ensure_schema()
    keywords = extract_topic_keywords(subject, body)
    ad = pick_ad(role, vertical, keywords)
    if not ad:
        return reply_text, {"injected": False, "reason": "no match above threshold"}
    token = record_impression(ad["id"], reply_to_addr, role, vertical,
                               ad.get("matched_keywords"), ad.get("score", 0))
    # For now, keep the click_url as-is — redirect endpoint not yet built
    # (Ship 31m.1 will add /r/<token> route for tracked clicks)
    new_text = reply_text + render_ad_block(ad)
    return new_text, {
        "injected": True, "ad_id": ad["id"], "advertiser": ad["advertiser"],
        "score": ad["score"], "matched_keywords": ad.get("matched_keywords"),
        "click_token": token,
    }
