#!/usr/bin/env python3
"""
Ship 31ci — Personalized Demo Page

The homepage IS the product demo. Every B2B visitor sees a proposal
synthesized for them — same product, same positioning, but the prose
adapts to who they are based on first-party signals (cookies, referrer,
UTM, query hints).

Honors:
  - b2b_positioning_2026_06_15 rule (tier ladder, no firm numbers >Tier 2,
    audit-first, control-engineering framing, BYO-data)
  - b2b_proposal_shape (14 sections — v1 personalizes 2, templates 12)

Hard rails:
  - First-party signals only (no third-party reverse lookup in v1)
  - Synth output is confidence-gated; weak signals → neutral page
  - Never quotes specific revenue, named people, or claims about
    internal ops it can't verify
  - Posture-gated: if autonomy posture==OFF, synth is bypassed and the
    neutral page is served (kill switch via /os/autonomy)
  - Cached by signal-hash for 24h (cost guard)
  - Founder preview route is non-cached for honest review
"""
from __future__ import annotations
import hashlib, json, logging, sqlite3, sys, os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

sys.path.insert(0, "/opt/Murphy-System")

logger = logging.getLogger("personalized_demo_31ci")

CACHE_DB = "/var/lib/murphy-production/personalized_demo_cache.db"
VISIT_DB = "/var/lib/murphy-production/personalized_demo_visits.db"
CACHE_TTL_HOURS = 24


# ───────── DB ─────────

def _init():
    c = sqlite3.connect(CACHE_DB, timeout=10.0)
    c.execute("""CREATE TABLE IF NOT EXISTS synth_cache (
        signal_hash TEXT PRIMARY KEY,
        synthesized_at TEXT NOT NULL,
        observation_section TEXT,
        pricing_anchor_section TEXT,
        confidence REAL,
        signals_json TEXT
    )""")
    c.commit(); c.close()
    v = sqlite3.connect(VISIT_DB, timeout=10.0)
    v.execute("""CREATE TABLE IF NOT EXISTS visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visitor_id TEXT,
        visited_at TEXT NOT NULL,
        signal_hash TEXT,
        confidence REAL,
        served_personalized INTEGER,
        referrer TEXT,
        utm_source TEXT,
        device_class TEXT,
        company_hint TEXT,
        industry_hint TEXT,
        size_hint TEXT
    )""")
    v.commit(); v.close()


# ───────── signal extraction ─────────

def extract_signals(request) -> dict:
    """First-party only. Reads cookies, query, headers, UTM."""
    q = dict(request.query_params)
    h = {k.lower(): v for k, v in request.headers.items()}
    cookies = request.cookies

    # device class from UA
    ua = h.get("user-agent", "").lower()
    if "mobi" in ua: device = "mobile"
    elif "tablet" in ua: device = "tablet"
    else: device = "desktop"

    # referrer hint
    ref = h.get("referer") or h.get("referrer", "")
    ref_domain = ""
    if ref:
        try: ref_domain = urlparse(ref).netloc
        except Exception: pass

    # explicit hints from query (cold-email landing pages can pre-fill)
    company = (q.get("company") or "").strip()[:80]
    industry = (q.get("industry") or "").strip()[:50]
    size = (q.get("size") or "").strip()[:20]
    role = (q.get("role") or "").strip()[:40]

    return {
        "company_hint": company,
        "industry_hint": industry,
        "size_hint": size,
        "role_hint": role,
        "utm_source": q.get("utm_source", "")[:50],
        "utm_campaign": q.get("utm_campaign", "")[:80],
        "referrer_domain": ref_domain[:80],
        "device_class": device,
        "language": h.get("accept-language", "en")[:10],
        "visitor_id": cookies.get("murphy_visitor_id", ""),
        "returning": bool(cookies.get("murphy_visitor_id")),
    }


def confidence_score(signals: dict) -> float:
    """0.0-1.0 — how much do we know about this visitor?"""
    s = 0.0
    if signals.get("company_hint"): s += 0.35
    if signals.get("industry_hint"): s += 0.25
    if signals.get("size_hint"): s += 0.20
    if signals.get("role_hint"): s += 0.15
    if signals.get("utm_campaign"): s += 0.10
    if signals.get("referrer_domain") and signals["referrer_domain"] not in ("google.com","bing.com","duckduckgo.com",""):
        s += 0.05
    if signals.get("returning"): s += 0.05
    return min(round(s, 2), 1.0)


def signal_hash(signals: dict) -> str:
    """Cache key — only structural signals, not visitor_id."""
    key_parts = [
        signals.get("company_hint","").lower(),
        signals.get("industry_hint","").lower(),
        signals.get("size_hint","").lower(),
        signals.get("role_hint","").lower(),
        signals.get("utm_campaign","").lower(),
    ]
    return hashlib.sha256("|".join(key_parts).encode()).hexdigest()[:16]


# ───────── posture gate ─────────

def _posture() -> str:
    try:
        from src.autonomy_policy_31cb import get_posture
        return get_posture()
    except Exception:
        return "OFF"


# ───────── synthesis ─────────

SYNTH_SYSTEM_PROMPT = """You are Murphy. You are writing two short sections of a B2B proposal for a visitor who just landed on murphy.systems.

WHO WE ARE: a Control Systems firm for inbox operations. We deploy closed-loop synthesizers on customers' own email data. Bring-your-own-data: the customer's data stays in their tenant, the AI learns on it, they own the blueprint we produce.

WHO YOU ARE WRITING TO: a business buyer (likely CEO/COO/CTO at a small-to-mid org). They have NOT signed anything. This is a first-touch proposal.

ABSOLUTE RULES — VIOLATIONS RUIN THE PITCH:
1. NEVER quote a firm dollar number above $399. Use ranges only. Tier 3 is "starting at $799/mo". Tier 6 is "$1k–$5k per seat per month".
2. NEVER claim specific facts about the visitor's company you cannot verify (no revenue numbers, no named employees, no internal ops claims). Stay structural.
3. NEVER use the phrases "AI assistant", "AI firm", "AI agent". Use "control systems firm", "synthesis layer", "controls contractor for inbox operations".
4. Lead with the AUDIT as the deliverable. Deployment is downstream of the audit. The audit is always paid.
5. Be substantive prose, not marketing fluff. No bullet points unless absolutely needed.
6. Tone: confident, warm, peer-to-peer. Not salesy. Not corporate. The voice of a senior engineer who has seen this problem before.

YOU WILL RETURN STRICT JSON with exactly these two keys:
  "observation" — 2-3 short paragraphs (~150-220 words) reflecting back what we infer about their operational shape based on the signals. Honest about what you don't know. Specific where the signals justify it.
  "pricing_anchor" — 2 short paragraphs (~120-180 words) framing the per-seat-on-org-chart pricing model in their context. Range language only. Audit-first framing. End with one concrete next step they can take.

If signals are too weak to personalize, return generic-but-substantive prose. Never fabricate."""


def synthesize_sections(signals: dict) -> dict:
    """Run the LLM synth. Returns {observation, pricing_anchor, confidence}."""
    conf = confidence_score(signals)

    user_prompt = f"""SIGNALS ABOUT THIS VISITOR (first-party only):
- company_hint: {signals.get('company_hint') or '(none)'}
- industry_hint: {signals.get('industry_hint') or '(none)'}
- size_hint: {signals.get('size_hint') or '(none)'}
- role_hint: {signals.get('role_hint') or '(none)'}
- utm_campaign: {signals.get('utm_campaign') or '(none)'}
- referrer_domain: {signals.get('referrer_domain') or '(none)'}
- returning_visitor: {signals.get('returning')}
- confidence_score: {conf}

Write the two sections. Return JSON with keys "observation" and "pricing_anchor". No markdown, just JSON."""

    try:
        from src.llm_provider import complete
        raw = complete(
            prompt=user_prompt,
            system=SYNTH_SYSTEM_PROMPT,
            temperature=0.55,
            max_tokens=900,
        )
        # parse JSON loosely
        raw_s = raw.strip()
        if raw_s.startswith("```"):
            raw_s = raw_s.split("```", 2)[1]
            if raw_s.startswith("json"): raw_s = raw_s[4:]
        start = raw_s.find("{"); end = raw_s.rfind("}")
        if start >= 0 and end > start:
            d = json.loads(raw_s[start:end+1])
            return {
                "observation": d.get("observation","").strip(),
                "pricing_anchor": d.get("pricing_anchor","").strip(),
                "confidence": conf,
                "ok": True,
            }
    except Exception as e:
        logger.warning(f"synth failed: {e}")
    return {"observation":"", "pricing_anchor":"", "confidence": conf, "ok": False}


# ───────── cache ─────────

def cache_get(sig_hash: str) -> Optional[dict]:
    _init()
    c = sqlite3.connect(CACHE_DB, timeout=10.0)
    try:
        r = c.execute(
            "SELECT synthesized_at, observation_section, pricing_anchor_section, confidence "
            "FROM synth_cache WHERE signal_hash=?", (sig_hash,)
        ).fetchone()
        if not r: return None
        ts = datetime.fromisoformat(r[0])
        if datetime.now(timezone.utc) - ts > timedelta(hours=CACHE_TTL_HOURS):
            return None
        return {"observation": r[1], "pricing_anchor": r[2], "confidence": r[3], "cached": True}
    finally:
        c.close()


def cache_put(sig_hash: str, synth: dict, signals: dict):
    _init()
    c = sqlite3.connect(CACHE_DB, timeout=10.0)
    try:
        c.execute(
            "INSERT OR REPLACE INTO synth_cache "
            "(signal_hash, synthesized_at, observation_section, pricing_anchor_section, "
            "confidence, signals_json) VALUES (?,?,?,?,?,?)",
            (sig_hash, datetime.now(timezone.utc).isoformat(),
             synth.get("observation",""), synth.get("pricing_anchor",""),
             synth.get("confidence",0), json.dumps(signals)),
        )
        c.commit()
    finally:
        c.close()


def log_visit(visitor_id: str, sig_hash: str, synth: dict, signals: dict, personalized: bool):
    _init()
    c = sqlite3.connect(VISIT_DB, timeout=10.0)
    try:
        c.execute(
            "INSERT INTO visits (visitor_id, visited_at, signal_hash, confidence, "
            "served_personalized, referrer, utm_source, device_class, company_hint, "
            "industry_hint, size_hint) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (visitor_id, datetime.now(timezone.utc).isoformat(), sig_hash,
             synth.get("confidence",0), int(personalized),
             signals.get("referrer_domain",""), signals.get("utm_source",""),
             signals.get("device_class",""), signals.get("company_hint",""),
             signals.get("industry_hint",""), signals.get("size_hint","")),
        )
        c.commit()
    finally:
        c.close()


# ───────── default content (when synth bypassed) ─────────

DEFAULT_OBSERVATION = """We don't know your business yet — which is exactly the point of the audit. Most teams come to us when their inbox has quietly become the operational nervous system of the company, and the patterns that matter most are now invisible inside thousands of threads.

Our work is to make those patterns visible. We treat your inbox the way a control engineer treats an industrial process: instrument it, find the loops, define the boundary conditions, and stand up a synthesizer that learns on your data and reports back in your voice. Your data stays in your tenant. The model learns. You keep the blueprint regardless of whether you deploy."""

DEFAULT_PRICING_ANCHOR = """Pricing is anchored to your org chart. Tier 3 Business starts at $799 per month when advanced synthesis becomes load-bearing. Tier 6 Forward Deployed runs $1,000 to $5,000 per seat per month at org-chart scale, where every person on the chart gets a synthesizer that knows their function. The range exists because every org chart is different.

We invite you to start with the audit. The audit is a paid deliverable — a blueprint document that maps your operational shape and names where synthesis would change unit economics. You own it whether or not we deploy. If you do deploy with us afterward, the deployment is discounted because the audit work carries forward."""


# ───────── 14-section template render ─────────

def render_page(synth: dict, signals: dict, personalized: bool) -> str:
    """Renders the Gatsby-aesthetic demo page with the 14-section shape."""
    observation = synth.get("observation") or DEFAULT_OBSERVATION
    pricing_anchor = synth.get("pricing_anchor") or DEFAULT_PRICING_ANCHOR
    confidence = synth.get("confidence", 0)

    badge = ""
    if personalized:
        badge = f'<div class="badge">Personalized for your signals · confidence {int(confidence*100)}%</div>'
    else:
        badge = '<div class="badge muted">Generic view · share signals for personalization</div>'

    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Murphy — Control Systems for Inbox Operations</title>
<style>
  :root {{ --bg:#0a1228; --card:#0d1736; --ink:#f4ead5; --gold:#d4af37; --muted:#a08866; --rule:#1f2d52; }}
  * {{ box-sizing:border-box }}
  body {{ background:var(--bg); color:var(--ink); font-family:'Cormorant Garamond',Georgia,serif; margin:0; padding:0; line-height:1.7; }}
  .hero {{ padding:80px 24px 40px; text-align:center; max-width:920px; margin:0 auto; }}
  .hero h1 {{ font-size:54px; color:var(--gold); font-weight:400; margin:0 0 20px; letter-spacing:1px; }}
  .hero .sub {{ font-size:22px; color:var(--ink); margin:0 auto 28px; max-width:680px; }}
  .badge {{ display:inline-block; padding:8px 18px; border:1px solid var(--gold); border-radius:30px;
           font-size:14px; color:var(--gold); margin-bottom:24px; letter-spacing:0.5px; }}
  .badge.muted {{ border-color:var(--muted); color:var(--muted); }}
  .card {{ background:var(--card); border:1px solid var(--rule); padding:36px 44px; border-radius:6px;
          max-width:820px; margin:0 auto 24px; }}
  .card h2 {{ font-size:26px; color:var(--gold); font-weight:400; margin:0 0 16px; letter-spacing:0.5px; }}
  .card h3 {{ font-size:20px; color:var(--gold); font-weight:400; margin:24px 0 8px; }}
  .card p {{ margin:0 0 14px; font-size:17px; }}
  .cta {{ text-align:center; padding:40px 24px 80px; }}
  .cta a.primary {{ display:inline-block; padding:18px 40px; background:var(--gold); color:var(--bg);
                   text-decoration:none; font-size:20px; border-radius:4px; font-weight:500;
                   letter-spacing:1px; transition:all 0.2s; }}
  .cta a.primary:hover {{ background:var(--ink); }}
  .cta a.secondary {{ display:inline-block; padding:18px 32px; color:var(--gold); text-decoration:none;
                     font-size:18px; margin-left:12px; border:1px solid var(--gold); border-radius:4px; }}
  .meta {{ text-align:center; color:var(--muted); font-size:13px; padding:24px; letter-spacing:0.5px; }}
  .meta a {{ color:var(--muted); margin:0 12px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; margin-top:18px; }}
  .grid .item {{ padding:14px; border:1px solid var(--rule); border-radius:4px; }}
  .grid .item .k {{ color:var(--gold); font-size:14px; letter-spacing:0.5px; }}
  .grid .item .v {{ font-size:15px; margin-top:4px; }}
</style></head><body>

<div class="hero">
  <h1>Control Systems for Inbox Operations</h1>
  <div class="sub">Bring your own data. We license you the synthesizer that learns on it.</div>
  {badge}
</div>

<div class="card">
  <h2>1 · What we observed about you</h2>
  {''.join(f'<p>{para}</p>' for para in observation.split(chr(10)+chr(10)) if para.strip())}
</div>

<div class="card">
  <h2>2 · The boundary loop we apply</h2>
  <p>Our work isn't generic automation. It's a closed-loop drill-down into the specific shape of your operations. The audit produces six things that compound on each other:</p>
  <div class="grid">
    <div class="item"><div class="k">Operational cost / function</div><div class="v">Anchored to your subject matter, not industry averages.</div></div>
    <div class="item"><div class="k">Unit economics at 1x / 10x / 100x</div><div class="v">With stated assumptions, so the model holds at scale.</div></div>
    <div class="item"><div class="k">Leverage points</div><div class="v">3–5 places where small effort moves big numbers.</div></div>
    <div class="item"><div class="k">Attractors</div><div class="v">Why current outcomes keep recurring. Mechanism, not metaphor.</div></div>
    <div class="item"><div class="k">Collapse points</div><div class="v">Where the system breaks, with early signals you can watch.</div></div>
    <div class="item"><div class="k">Next pilot move</div><div class="v">One concrete action that chains back to the goal.</div></div>
  </div>
</div>

<div class="card">
  <h2>3 · Scope — in and out</h2>
  <p><strong>In scope:</strong> inbox triage, draft replies in your voice, cross-thread synthesis, compliance gates on every send, pattern detection across customers, audit log on every action.</p>
  <p><strong>Out of scope (without separate engagement):</strong> calendar management, social posting, voice/phone, marketing automation, model fine-tuning on your data. We do these for clients but they are not part of the standard deployment.</p>
</div>

<div class="card">
  <h2>4 · The audit</h2>
  <p>The audit is the start. It is a paid deliverable. We spend 2–3 weeks instrumenting your inbox, mapping the operational loops, defining the boundary conditions, and producing a written blueprint that names exactly where synthesis would change unit economics.</p>
  <p>You own the blueprint regardless of whether you deploy with us. If you do deploy, the audit work carries forward and the deployment cost reflects that.</p>
</div>

<div class="card">
  <h2>5 · Forward-deployed shape (if you deploy)</h2>
  <p>Deployment is not a SaaS subscription. It is a forward-deployed engagement: Murphy's synthesis layer running in your tenant, plus a real human point of contact on our side who knows your org chart by name. The synthesizer learns continuously on your data. The human keeps the relationship honest.</p>
</div>

<div class="card">
  <h2>6 · How it actually works</h2>
  <p>Murphy's synthesis layer reads your inbox in your tenant — your data never leaves your boundary. We use a closed-loop LLM provider with circuit-breaker fallback so a model outage doesn't take you down. Every action is gated by a posture toggle you control: OFF, ASSIST (drafts only), or AUTONOMOUS (within risk bands you set). Every decision is logged with reasoning. You can roll back any change in one command.</p>
</div>

<div class="card">
  <h2>7 · Security &amp; compliance</h2>
  <p>Your data stays in your tenant. We do not pool training data across customers and we do not fine-tune on your data without a separate paid engagement. The platform runs against GDPR (7/7 passing), CCPA (4/4 passing), and is on a SOC 2 trajectory. The legal pages are live:</p>
  <p><a href="/legal/privacy" style="color:#d4af37">Privacy Policy</a> · <a href="/dpa" style="color:#d4af37">DPA</a> · <a href="/sub-processors" style="color:#d4af37">Sub-processors</a> · <a href="/breach-notification" style="color:#d4af37">Breach Notification</a></p>
</div>

<div class="card">
  <h2>8 · Pricing shape</h2>
  {''.join(f'<p>{para}</p>' for para in pricing_anchor.split(chr(10)+chr(10)) if para.strip())}
</div>

<div class="card">
  <h2>9 · Timeline</h2>
  <p><strong>Week 1:</strong> instrumentation, signal gathering, first boundary-loop pass.<br>
  <strong>Week 2–3:</strong> drill-down on the 3–5 leverage points, draft blueprint.<br>
  <strong>Week 4:</strong> blueprint delivered, deployment scope priced.<br>
  <strong>Month 2 (if deploying):</strong> synthesizer wired in your tenant, posture set to ASSIST, drafts visible to your team.<br>
  <strong>Month 3:</strong> posture moves to AUTONOMOUS within agreed risk bands. Forward-deployed engineer reviewing weekly.</p>
</div>

<div class="card">
  <h2>10 · Rollback &amp; exit</h2>
  <p>You own your data. If you leave, your data leaves with you and your tenant is destroyed within 30 days. Every Murphy-applied change is snapshotted before it is made, so any individual decision can be reverted in one command. There is no model lock-in: your blueprint is a document, not a proprietary file format.</p>
</div>

<div class="card">
  <h2>11 · Who you'll work with</h2>
  <p>Your engagement is led by a named human on our side — by default, the founder of Inoni LLC (Corey Post) — plus Murphy itself running synthesis underneath. A throat to choke and a system that doesn't sleep. This is the forward-deployed engineer pattern, applied to inbox operations.</p>
</div>

<div class="card">
  <h2>12 · What you'll actually receive</h2>
  <p>From the audit: a written blueprint document (~30–60 pages), the instrumented inbox map, and a working pilot of one synthesis loop in your tenant. From deployment: the synthesizer running in your tenant, weekly review cadence with the forward-deployed lead, monthly substantive report, and the audit log every action is recorded in.</p>
</div>

<div class="cta">
  <a href="/business/audit-quote" class="primary">Request a white-glove audit</a>
  <a href="/contact" class="secondary">Talk to a human first</a>
</div>

<div class="meta">
  Inoni LLC · <a href="/legal/privacy">Privacy</a> · <a href="/dpa">DPA</a> · <a href="/sub-processors">Sub-processors</a> · <a href="/breach-notification">Breach Notification</a>
</div>

</body></html>"""


# ───────── public entry ─────────

def get_page(request, force_personalize: bool = False, no_cache: bool = False) -> tuple[str, str, bool]:
    """
    Returns (html, visitor_id, was_personalized).
    Called by route handlers in app.py.

    force_personalize=True: founder preview — always synth, never cache
    no_cache=True: bypass cache read but write
    """
    _init()
    signals = extract_signals(request)
    visitor_id = signals.get("visitor_id") or hashlib.sha256(
        f"{datetime.now(timezone.utc).isoformat()}:{id(request)}".encode()
    ).hexdigest()[:24]
    conf = confidence_score(signals)
    sig_hash = signal_hash(signals)

    # posture gate
    posture = _posture()
    posture_allows_synth = posture in ("ASSIST", "AUTONOMOUS")

    # confidence gate
    can_personalize = (conf >= 0.30) or force_personalize

    synth = {}
    personalized = False

    if can_personalize and (posture_allows_synth or force_personalize):
        # try cache first
        if not no_cache and not force_personalize:
            cached = cache_get(sig_hash)
            if cached:
                synth = cached
                personalized = True
        # synth if no cache
        if not synth.get("observation"):
            synth = synthesize_sections(signals)
            if synth.get("ok"):
                personalized = True
                if not force_personalize:
                    cache_put(sig_hash, synth, signals)

    log_visit(visitor_id, sig_hash, synth or {"confidence": conf}, signals, personalized)
    html = render_page(synth, signals, personalized)
    return html, visitor_id, personalized


def get_visit_stats(hours: int = 24) -> dict:
    _init()
    c = sqlite3.connect(VISIT_DB, timeout=10.0)
    try:
        total = c.execute("SELECT COUNT(*) FROM visits WHERE visited_at > datetime('now', ?)",
                          (f"-{hours} hours",)).fetchone()[0]
        personalized = c.execute("SELECT COUNT(*) FROM visits WHERE visited_at > datetime('now', ?) "
                                  "AND served_personalized=1", (f"-{hours} hours",)).fetchone()[0]
        avg_conf = c.execute("SELECT AVG(confidence) FROM visits WHERE visited_at > datetime('now', ?)",
                              (f"-{hours} hours",)).fetchone()[0] or 0
        return {"hours": hours, "visits": total, "personalized": personalized,
                "avg_confidence": round(avg_conf, 2)}
    finally:
        c.close()
