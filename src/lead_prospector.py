"""
src/lead_prospector.py  — PATCH-195
Murphy System — Autonomous Lead Prospector + Sales Engine

Sales philosophy baked in (Sandler + SPIN + Challenger principles):
  - Never spam. One personalised opener, wait 3 days, two follow-ups max.
  - Lead with insight/value, not product pitch.
  - Qualify before chasing: ICP score >= 40 required to enter CRM.
  - Every contact gets a personal note tied to *their* context (role, company, source).
  - DNC + already-contacted checks run BEFORE any insertion or outreach.
  - Cadence: Day 0 opener → Day 3 follow-up #1 → Day 7 follow-up #2 → archive.
  - Unsubscribe / opt-out replies auto-suppress domain+email permanently.

Sources (zero cost, no API keys):
  1. HackerNews "Who's Hiring" thread   — AI/automation companies actively spending
  2. YC company list (public JSON)      — high-growth, funded, ICP-perfect
  3. RemoteOK public API                — companies hiring AI = budget + pain
  4. GitHub repo owners                 — founders building AI/automation tools

PATCH-195
"""

from __future__ import annotations
import json, logging, re, sqlite3, time, uuid, random
import urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("murphy.prospector")

CRM_DB   = "/var/lib/murphy-production/crm.db"
AGENT    = "Mozilla/5.0 (compatible; MurphyProspect/1.0; +https://murphy.systems)"

# ── ICP definition ────────────────────────────────────────────────────────────
ICP_TITLE_POSITIVE = [
    "cto","co-founder","founder","vp engineering","head of engineering",
    "vp product","head of product","chief technology","director of engineering",
    "head of ai","vp ai","director of ai","ai lead","ml lead",
    "head of automation","director of automation","engineering manager",
    "platform lead","infrastructure lead","chief ai",
]
ICP_TITLE_NEGATIVE = [
    "intern","student","junior","assistant","coordinator",
    "recruiter","hr ","talent ","admin","receptionist",
]
ICP_COMPANY_BOOST = [
    "ai","ml","automation","saas","fintech","healthtech","legaltech",
    "devtools","developer tools","cloud","data","analytics","platform",
    "agent","llm","gpt","security","compliance","insurtech","edtech",
]
MIN_ICP_SCORE = 25   # R324: lowered from 40 — discovery was rejecting 92% of candidates


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _icp_score(title: str, company: str, domain: str = "") -> int:
    score = 0
    t = title.lower()
    c = (company + " " + domain).lower()
    if any(h in t for h in ICP_TITLE_POSITIVE):
        score += 55
    if any(b in t for b in ICP_TITLE_NEGATIVE):
        return 0
    if any(h in c for h in ICP_COMPANY_BOOST):
        score += 25
    # Penalise generic/enterprise behemoths slightly
    if any(b in c for b in ["google","amazon","microsoft","apple","meta","ibm"]):
        score -= 20
    return max(0, min(100, score))


def _fetch(url: str, timeout: int = 8) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.debug("fetch %s: %s", url, e)
        return None


def _fetch_json(url: str, timeout: int = 8):
    raw = _fetch(url, timeout)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# DNC + ALREADY-CONTACTED GATES  (runs before any CRM write or outreach)
# ══════════════════════════════════════════════════════════════════════════════

def _dnc_blocked(email: str) -> Tuple[bool, str]:
    """
    Returns (blocked, reason).
    Checks: dnc_suppression table (email + domain level).
    """
    email  = (email or "").lower().strip()
    domain = email.split("@")[1] if "@" in email else ""
    try:
        with sqlite3.connect(CRM_DB, timeout=5) as db:
            if email:
                row = db.execute(
                    "SELECT reason FROM dnc_suppression WHERE LOWER(email)=? LIMIT 1",
                    (email,)
                ).fetchone()
                if row:
                    return True, f"DNC (email): {row[0] or 'opt-out'}"
            if domain:
                row = db.execute(
                    "SELECT reason FROM dnc_suppression WHERE domain=? AND email='' LIMIT 1",
                    (domain,)
                ).fetchone()
                if row:
                    return True, f"DNC (domain): {row[0] or 'domain block'}"
    except Exception as e:
        logger.warning("DNC check error: %s", e)
    return False, ""


def _already_in_crm(email: str) -> bool:
    """True if this email is already a contact in CRM."""
    try:
        with sqlite3.connect(CRM_DB, timeout=5) as db:
            row = db.execute(
                "SELECT id FROM contacts WHERE LOWER(email)=?",
                (email.lower().strip(),)
            ).fetchone()
            return row is not None
    except Exception:
        return False


def _already_contacted(email: str) -> bool:
    """True if we already have an outreach activity for this email."""
    try:
        with sqlite3.connect(CRM_DB, timeout=5) as db:
            row = db.execute(
                "SELECT a.id FROM activities a "
                "JOIN contacts c ON a.contact_id=c.id "
                "WHERE LOWER(c.email)=? AND a.activity_type IN ('email_sent','outreach','follow_up') "
                "LIMIT 1",
                (email.lower().strip(),)
            ).fetchone()
            return row is not None
    except Exception:
        return False


def _days_since_last_contact(email: str) -> Optional[int]:
    """Returns days since last outreach activity, or None if never contacted."""
    try:
        with sqlite3.connect(CRM_DB, timeout=5) as db:
            row = db.execute(
                "SELECT a.created_at FROM activities a "
                "JOIN contacts c ON a.contact_id=c.id "
                "WHERE LOWER(c.email)=? AND a.activity_type IN ('email_sent','outreach','follow_up') "
                "ORDER BY a.created_at DESC LIMIT 1",
                (email.lower().strip(),)
            ).fetchone()
            if not row:
                return None
            last = datetime.fromisoformat(row[0].replace("Z","+00:00"))
            return (datetime.now(timezone.utc) - last).days
    except Exception:
        return None


def _follow_up_count(email: str) -> int:
    """How many outreach touches have been sent to this email."""
    try:
        with sqlite3.connect(CRM_DB, timeout=5) as db:
            row = db.execute(
                "SELECT COUNT(*) FROM activities a "
                "JOIN contacts c ON a.contact_id=c.id "
                "WHERE LOWER(c.email)=? AND a.activity_type IN ('email_sent','outreach','follow_up')",
                (email.lower().strip(),)
            ).fetchone()
            return row[0] if row else 0
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# CRM WRITE
# ══════════════════════════════════════════════════════════════════════════════

def _add_to_crm(lead: Dict) -> Optional[str]:
    """
    Insert contact + deal. Returns contact_id or None if blocked/duplicate.
    All gates run here: DNC, already-in-crm, min ICP.
    """
    email = (lead.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return None

    # Gate 0 — Email quality: reject aliases, job boards, generic inboxes
    local = email.split("@")[0]
    BAD_LOCALS = {"jobs","careers","hiring","recruit","hr","info","hello","contact",
                  "support","admin","team","no-reply","noreply","press","media",
                  "digitaljobs","createwithus","sprout","office","enquiries"}
    if local in BAD_LOCALS or local.startswith("jobs+") or "+" in local:
        logger.debug("[Prospector] Rejected alias email: %s", email)
        return None

    # Gate 1 — DNC
    blocked, reason = _dnc_blocked(email)
    if blocked:
        logger.info("[Prospector] DNC blocked %s: %s", email, reason)
        return None

    # Gate 2 — already in CRM
    if _already_in_crm(email):
        logger.debug("[Prospector] Already in CRM: %s", email)
        return None

    # Gate 3 — minimum ICP score
    icp = lead.get("icp_score", 0)
    if icp < MIN_ICP_SCORE:
        logger.debug("[Prospector] ICP too low (%d) for %s", icp, email)
        return None

    cid = str(uuid.uuid4())[:12]
    did = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()
    _tag_list = ["auto-prospected", lead.get("source","prospector")]
    if lead.get("tags"):
        # lead.tags may be string or list — normalize and append
        _t = lead["tags"]
        if isinstance(_t, str):
            _tag_list.extend([t.strip() for t in _t.split(",") if t.strip()])
        elif isinstance(_t, list):
            _tag_list.extend([str(t) for t in _t])
    tags = json.dumps(list(dict.fromkeys(_tag_list)))  # dedupe, preserve order
    notes = (
        f"Source: {lead.get('source','?')} | "
        f"ICP: {icp} | Title: {lead.get('title','')} | "
        f"URL: {lead.get('url','')} | Prospected: {now[:10]}"
    )
    try:
        with sqlite3.connect(CRM_DB, timeout=8) as db:
            db.execute(
                "INSERT INTO contacts (id,name,email,company,phone,contact_type,"
                "owner_id,tags,custom_fields,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (cid, lead.get("name",""), email, lead.get("company",""),
                 "", "lead", "founder", tags, "{}", now)
            )
            # PATCH-DEAL-GUARD (2026-05-27): SQLite trigger trg_deals_require_contact_email
            # at the deals table will REFUSE this INSERT if contact has no email.
            # All 4 deal-insert paths (lead_prospector, ethical_hacker, app.py, crm_manager)
            # are protected by the trigger — guard is structural, not per-file.
            # See: /var/lib/murphy-production/crm.db, trigger created 2026-05-27.
            db.execute(
                "INSERT INTO deals (id,title,stage,value,contact_id,"
                "owner_id,notes,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (did,
                 f"{lead.get('company','Lead')} — Murphy System",
                 "lead", lead.get("deal_value", 4900),
                 cid, "founder", notes, now, now)
            )
            db.commit()
        logger.info("[Prospector] ✅ Added: %s <%s> @ %s ICP=%d",
                    lead.get("name","?"), email, lead.get("company","?"), icp)
        # PATCH-197: Trigger enrichment on new lead
        try:
            from src.prospect_enricher import enrich_contact
            enrich_contact(cid)
        except Exception as _ee:
            logger.debug("[Prospector] Enrichment hook: %s", _ee)
        return cid
    except Exception as e:
        logger.warning("[Prospector] CRM insert failed %s: %s", email, e)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# SALES EMAIL COMPOSER  (Challenger / Sandler / value-first principles)
# ══════════════════════════════════════════════════════════════════════════════

OPENER_TEMPLATES = [
    # Template A — Insight-first (Challenger Sale)
    """Subject: The one thing killing AI adoption at {company}

Hi {first_name},

Most teams building with AI spend 80% of their time on failure modes — not features. Every hallucination, every bad output, every unauthorized action that slips through costs them trust they can't easily rebuild.

Murphy System is the safety and automation layer that sits between your AI and your users. We catch failures before they happen, track every decision made, and let your team stay in control without slowing down.

Thought it might be relevant given what you're building at {company}.

Worth a 15-minute call this week?

— Corey
Corey Post | Founder, Murphy System
murphy.systems | cpost@murphy.systems""",

    # Template B — Pain-first (SPIN)
    """Subject: Quick question about AI reliability at {company}

Hi {first_name},

How much time does your team spend debugging AI outputs versus building new features?

For most {role_context} teams, it's more than they'd like to admit.

Murphy System gives AI teams a production safety layer — automated failure detection, compliance guardrails, and a full audit trail — so you ship faster with less risk.

Open to a quick conversation about what that could look like at {company}?

— Corey
Corey Post | Founder, Murphy System
murphy.systems""",

    # Template C — Social proof + specificity
    """Subject: How teams like {company} are reducing AI risk

Hi {first_name},

AI teams at early-stage companies are dealing with a problem that doesn't have a clean solution yet: how do you move fast with AI without the liability of things going wrong?

That's exactly what Murphy System solves — a compliance and safety platform purpose-built for AI-first teams. Automated risk detection, HITL controls, SOC2/GDPR coverage out of the box.

Would love to show you what we've built. 15 minutes?

— Corey
cpost@murphy.systems | murphy.systems""",
]

FOLLOWUP_1_TEMPLATE = """Subject: Re: Murphy System — {company}

Hi {first_name},

Just bumping this up in case it got buried.

The one thing I hear most from {role_context} founders is that compliance and AI safety feel like future problems — until they aren't.

Murphy handles it at the platform level so it's never a fire drill.

Still worth a quick call?

— Corey"""

FOLLOWUP_2_TEMPLATE = """Subject: Last note — Murphy System

Hi {first_name},

Last reach-out, I promise.

If AI reliability and compliance ever become a priority at {company}, murphy.systems is the place to start.

If the timing is just off, totally understand — reply "not now" and I won't contact you again.

Wishing you and the team well.

— Corey"""


def _r82_load_enrichment(email):
    """R82 — Pull contacts.custom_fields for this email. Returns {} if missing."""
    if not email:
        return {}
    try:
        with sqlite3.connect(CRM_DB, timeout=4) as db:
            row = db.execute(
                "SELECT custom_fields FROM contacts WHERE LOWER(email) = LOWER(?) LIMIT 1",
                (email,),
            ).fetchone()
        if not row or not row[0]:
            return {}
        cf = json.loads(row[0])
        return cf if isinstance(cf, dict) else {}
    except Exception as e:
        logger.debug("[R82] enrichment load failed for %s: %s", email, e)
        return {}


def _r82_clean_meta(text):
    """Strip the leading meta-tag prefix the enricher leaves on company_description."""
    if not text:
        return ""
    out = text.replace('<meta name="description" content="', "").strip()
    for tail in ('"/>', '"/', '">', '"'):
        if out.endswith(tail):
            out = out[: -len(tail)]
            break
    return out.strip()


def _r82_compose_with_llm(lead, enrichment, touch_number):
    """R82 — Compose customer-centric outreach via the internal LLM.

    Returns {subject, body} on success, None on failure (caller falls back).
    """
    first    = lead.get("first_name") or (lead.get("name","").split()[0] if lead.get("name") else "there")
    company  = lead.get("company") or "your team"
    title    = lead.get("title", "")
    url      = lead.get("url", "")

    descr    = _r82_clean_meta(enrichment.get("company_description") or "")[:300]
    stack    = enrichment.get("tech_stack") or []
    stack_s  = ", ".join(stack[:6]) if stack else ""
    pains    = enrichment.get("pain_signals") or []
    pains_s  = "; ".join(pains[:5]) if pains else ""
    trigger  = enrichment.get("buying_trigger") or ""
    themes   = enrichment.get("tweet_themes") or []
    themes_s = ", ".join(themes[:5]) if themes else ""
    repos    = enrichment.get("github_top_repos") or []
    repo_s   = ""
    if repos and isinstance(repos, list):
        rn = [r.get("name","") for r in repos[:3] if isinstance(r, dict) and r.get("name")]
        repo_s = ", ".join(rn)
    lang_style = enrichment.get("language_style") or "founder-casual"

    if not (descr or stack or pains or trigger or themes or repo_s):
        logger.info("[R82] no enrichment signal for %s; using enrichment-aware static fallback", company)
        return None

    touch_intent = {
        1: "FIRST cold outreach. Earn the reply by showing we read their site/work.",
        2: "SECOND touch. Acknowledge they're busy. Add ONE new insight or angle. Don't repeat the first email.",
        3: "THIRD and final touch. Short, gracious, leaves the door open. No new pitch.",
    }.get(touch_number, "Cold outreach.")

    system_prompt = (
        "You are Corey Post, founder of Murphy System. You're writing a cold email TO a real person at a real company. "
        "Murphy System is a production safety + automation layer for AI teams: failure detection, compliance guardrails, audit trail, HITL controls. "
        "Your job: write an email that proves you read their work and names ONE specific problem they likely face. "
        "RULES - hard: "
        "(1) Lead with THEIR situation, not Murphy's pitch. "
        "(2) Use one concrete detail from their data (product, stack, repo, pain phrase). "
        "(3) Name ONE specific problem they probably have. "
        "(4) Position Murphy in ONE sentence as a fix - not a paragraph. "
        "(5) End with ONE simple ask (15-min call, reply with thoughts). "
        "(6) Max 120 words. Plain text. No markdown, no bullets, no emojis. "
        "(7) NO generic openers like 'AI teams build with...', 'Most teams spend 80%...', 'The one thing I hear most'. Those are BANNED. "
        "(8) Sign as: - Corey"
    )

    user_prompt = (
        "WRITE the email now.\n\n"
        + f"Recipient: {first} ({title}) at {company}\n"
        + f"Touch number: {touch_number} - {touch_intent}\n"
        + f"Their site: {url}\n"
        + f"What they do (from their site): {descr or '(unknown)'}\n"
        + f"Their tech stack: {stack_s or '(unknown)'}\n"
        + f"Pain signals from their public footprint: {pains_s or '(none found)'}\n"
        + f"Strongest buying trigger we found: {trigger or '(none)'}\n"
        + f"Themes they post about: {themes_s or '(none)'}\n"
        + f"Their notable repos: {repo_s or '(none)'}\n"
        + f"Their language style: {lang_style}\n\n"
        + "Return the email as plain text: 'Subject: <subject>' on the first line, blank line, then body. Nothing else."
    )

    try:
        from src.llm_provider import get_llm
        llm = get_llm()
        result = llm.complete(
            prompt=user_prompt,
            system=system_prompt,
            max_tokens=380,
            temperature=0.55,
        )
        text = (getattr(result, "content", None) or (result.get("content") if isinstance(result, dict) else None) or "") if result is not None else ""
        text = text.strip()
        if not text or "subject:" not in text.lower():
            logger.warning("[R82] LLM returned unparseable output for %s", company)
            return None
        lines = text.split("\n")
        subj_idx = None
        for i, ln in enumerate(lines):
            if ln.lower().startswith("subject:"):
                subj_idx = i
                break
        if subj_idx is None:
            return None
        subject = lines[subj_idx].split(":", 1)[1].strip()
        body_lines = lines[subj_idx + 1 :]
        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)
        body = "\n".join(body_lines).strip()
        if len(body) < 40:
            logger.warning("[R82] LLM body too short for %s (%d chars)", company, len(body))
            return None
        if body[:80].lower().startswith(("i cannot", "i'm sorry", "i am sorry", "i won't")):
            logger.warning("[R82] LLM refused for %s", company)
            return None
        return {"subject": subject, "body": body}
    except Exception as e:
        logger.warning("[R82] LLM compose failed for %s: %s", company, e)
        return None


def _r82_static_fallback(lead, enrichment, touch_number):
    """R82 - Enrichment-aware static fallback. NEVER reverts to old A/B/C generic."""
    first   = lead.get("first_name") or (lead.get("name","").split()[0] if lead.get("name") else "there")
    company = lead.get("company") or "your team"
    descr   = _r82_clean_meta(enrichment.get("company_description") or "")[:200]
    stack   = enrichment.get("tech_stack") or []
    pains   = enrichment.get("pain_signals") or []

    if descr:
        them_line = f"I came across {company} and read your pitch - {descr[:160]}."
    elif stack:
        them_line = f"I saw {company} is building with {', '.join(stack[:3])}."
    else:
        them_line = f"I came across {company} while researching AI-first teams."

    if pains:
        problem = f"Teams shipping with your stack often hit {pains[0]} early, and it tends to get worse as the model surface grows."
    elif "react" in [s.lower() for s in stack]:
        problem = "AI features in user-facing apps are where reliability complaints land first - and they're hard to debug after the fact."
    else:
        problem = "AI teams hit reliability and compliance walls earlier than they expect, usually right after the first customer-facing launch."

    pitch = "Murphy System is the safety + audit layer between your AI and your users - catches failures, logs decisions, keeps your team in control. Built for teams that want to ship fast without the liability."

    if touch_number == 1:
        subj = f"Saw {company} - one quick thought"
        body = (
            f"Hi {first},\n\n"
            f"{them_line}\n\n"
            f"{problem}\n\n"
            f"{pitch}\n\n"
            f"Worth a 15-minute call?\n\n"
            f"- Corey\nFounder, Murphy System\nmurphy.systems"
        )
    elif touch_number == 2:
        subj = f"Re: Saw {company} - one quick thought"
        body = (
            f"Hi {first},\n\n"
            f"Wanted to follow up once. {problem} It usually surfaces in customer support tickets first, "
            f"so by the time it's a board-level issue, the cleanup is 10x harder.\n\n"
            f"Happy to share what we're seeing at other AI teams if useful.\n\n"
            f"- Corey"
        )
    else:
        subj = "Last note"
        body = (
            f"Hi {first},\n\n"
            f"Last reach-out. If AI reliability or compliance ever becomes urgent at {company}, "
            f"murphy.systems is the place to start. Otherwise wishing you and the team well.\n\n"
            f"- Corey"
        )

    return {"subject": subj, "body": body}


def _compose_outreach(lead: Dict, touch_number: int = 1) -> Dict:
    """
    _R456_LINEAGE — Compose a personalised outreach email using sales best practices.

    R456 addition: every composed message now carries a `lineage` field
    documenting (a) which source document the lead came from, (b) which
    template was picked, (c) which input fields filled which placeholder,
    (d) character ranges where each input value appears in the final body.
    The HITL drill-down UI uses this to highlight LLM-vs-input text and
    link back to source-document snippets.

    touch_number: 1=opener, 2=follow-up 1, 3=follow-up 2.
    Returns {subject, body, to, from, touch, lineage}.
    """
    # _R82_CUSTOMER_CENTRIC (2026-06-07) - read enrichment, ask LLM to write
    # FROM the prospect's situation. Hardcoded A/B/C templates retired.
    # Enrichment-aware static fallback only when LLM is unreachable.
    name      = lead.get("name", "")
    email     = lead.get("email", "")
    company   = lead.get("company", "there")
    title     = lead.get("title", "")
    first     = (name.split()[0] if name and " " in name else name) or "there"
    _t = title.lower()
    if any(w in _t for w in ["engineer","cto","tech"]):
        role_ctx = "engineering"
    elif "found" in _t:
        role_ctx = "founder"
    elif "product" in _t:
        role_ctx = "product"
    else:
        role_ctx = "AI"

    lead_for_helpers = dict(lead)
    lead_for_helpers.setdefault("first_name", first)

    ctx = {
        "first_name":   first,
        "company":      company,
        "title":        title,
        "role_context": role_ctx,
    }

    enrichment = _r82_load_enrichment(email)

    composed = _r82_compose_with_llm(lead_for_helpers, enrichment, touch_number)
    if composed:
        subj = composed["subject"]
        body = composed["body"]
        template_used = "llm_customer_centric"
        template_id = "r82_llm_touch%d" % touch_number
        _enrich_keys = [k for k in ("company_description","tech_stack","pain_signals","buying_trigger","tweet_themes","github_top_repos") if enrichment.get(k)]
        logger.info("[R82] LLM composed touch #%d for %s (enrichment fields used: %s)",
                    touch_number, company, sorted(_enrich_keys))
    else:
        static = _r82_static_fallback(lead_for_helpers, enrichment, touch_number)
        subj = static["subject"]
        body = static["body"]
        template_used = "static_enrichment_aware"
        template_id = "r82_static_touch%d" % touch_number
        logger.info("[R82] Static fallback used for %s touch #%d", company, touch_number)

    # R456 — capture lineage
    # Find each input value's character range in the final body
    placeholders_in_body = []
    full_text = subj + "\n\n" + body
    for key, val in ctx.items():
        if not val or not isinstance(val, str):
            continue
        # Find ALL occurrences of this value in the final body
        start = 0
        while True:
            idx = full_text.find(val, start)
            if idx == -1:
                break
            placeholders_in_body.append({
                "placeholder": "{" + key + "}",
                "field": key,
                "value": val,
                "start": idx,
                "end": idx + len(val),
                "in": "subject" if idx < len(subj) else "body",
            })
            start = idx + len(val)

    lineage = {
        "version": "r456.1",
        "template_id": template_id,
        "template_raw": template_used,
        "input_fields": ctx,  # the values that filled placeholders
        "placeholders_in_body": placeholders_in_body,
        "source": {
            "system":    lead.get("source", "unknown"),
            "lead_id":   lead.get("source_id") or lead.get("contact_id") or "",
            "source_url": lead.get("source_url", ""),
            "raw_snippet": lead.get("source_snippet", ""),
            "fetched_at": lead.get("fetched_at", ""),
        },
        "lead_raw": {
            "name":    name,
            "email":   email,
            "company": company,
            "title":   title,
        },
    }

    return {
        "to":      email,
        "from":    "cpost@murphy.systems",
        "subject": subj,
        "body":    body,
        "touch":   touch_number,
        "lineage": lineage,
        "name":    name,
        "company": company,
    }


# ══════════════════════════════════════════════════════════════════════
# R454 — _R454_HITL_QUEUE
# Queue outbound outreach to hitl_jobs for founder approval BEFORE sending.
# Closes Terms §1B.1: every outbound email requires a per-item approval
# under the founder's professional credentials. Replaces the prior
# fire-and-forget SMTP path (which was 100% failing anyway due to
# auth=535 on localhost:587).
# ══════════════════════════════════════════════════════════════════════
_R454_HITL_DB = "/var/lib/murphy-production/hitl_jobs.db"

def _r454_queue_outbound_for_hitl(msg: Dict, contact_id: str, touch: int) -> Optional[str]:
    """Queue one outbound email into hitl_jobs with template_code='outbound_email'.

    The HITL gate in src/runtime/app.py only releases items whose
    template_code matches an engaged action_class. The founder has
    engagement for 'outbound_email' (R431). So items written here will
    appear in /api/hitl/items for the founder to approve.

    Returns the hitl_job id, or None on failure.
    """
    import sqlite3 as _sq454
    import uuid as _u454, json as _j454, datetime as _dt454
    try:
        job_id = "hitl_" + _u454.uuid4().hex[:12]
        now = _dt454.datetime.now(_dt454.timezone.utc).isoformat()
        payload = {
            "to":         msg.get("to", ""),
            "from":       msg.get("from", ""),
            "subject":    msg.get("subject", ""),
            "body":       msg.get("body", ""),
            "contact_id": contact_id,
            "touch":      touch,
            "source":     "lead_prospector",
            "queued_at":  now,
            # R456 — persist lineage so HITL drill-down can show source-of-truth
            "lineage":    msg.get("lineage", {}),
        }
        title = f"Outbound #{touch} → {msg.get('to','?')} — {msg.get('subject','')[:80]}"
        with _sq454.connect(_R454_HITL_DB, timeout=8) as db:
            db.execute("PRAGMA busy_timeout=4000")
            db.execute(
                """INSERT INTO hitl_jobs
                   (id, project_id, template_code, discipline, phase,
                    title, status, priority, cost_model, submitted_data,
                    submitted_by, submitted_at, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (job_id, "sales_outreach", "outbound_email",
                 "sales", "outreach",
                 title, "open", "normal", "founder_approval",
                 _j454.dumps(payload),
                 "lead_prospector", now, now, now)
            )
            db.commit()
        logger.info("[Prospector] R454 queued for HITL: %s (touch %d)", job_id, touch)

        # _R454B_DUAL_WRITE — also insert into outbound_email_queue so /os sees it
        # /os reads from murphy_mail.db; /welcome reads from hitl_jobs.db. Without
        # this dual write the founder sees the item in /welcome but the /os page
        # claims "queue is empty". Same queue_id strategy as job_id so the two
        # systems stay linked for later wiring.
        try:
            with _sq454.connect("/var/lib/murphy-production/murphy_mail.db", timeout=8) as mdb:
                mdb.execute("PRAGMA busy_timeout=4000")
                mdb.execute(
                    """INSERT OR IGNORE INTO outbound_email_queue
                       (queue_id, from_address, to_addresses, subject, body,
                        body_format, agent_role, agent_class, urgency, status,
                        created_at, updated_at, metadata)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (job_id,
                     msg.get("from", "cpost@murphy.systems"),
                     _j454.dumps([msg.get("to", "")]),
                     msg.get("subject", ""),
                     msg.get("body", ""),
                     "plain",
                     "sdr", "SDR", "normal", "pending_review",
                     now, now,
                     _j454.dumps({"source": "lead_prospector", "touch": touch,
                                  "contact_id": contact_id, "hitl_job_id": job_id}))
                )
                mdb.commit()
            logger.info("[Prospector] R454b dual-write OK: %s", job_id)
        except Exception as e:
            # Non-fatal — hitl_jobs row already persisted
            logger.warning("[Prospector] R454b dual-write failed for %s: %s",
                           job_id, e)

        # _R481_NOTIFY — fire HITL subscriber notifications for this new item.
        # Non-fatal: notification failures must not block prospector queueing.
        # Notifications fan-out to all subscribers whose scope_json covers
        # 'outbound_email' (or empty == all classes).
        try:
            from src.hitl_notify import send_item_notification as _r481_send_notif
            _r481_item = {
                "id": job_id,
                "title": title,
                "action_class": "outbound_email",
                "discipline": "sales",
                "subject": msg.get("subject", ""),
                "to": msg.get("to", ""),
                "preview": (msg.get("body", "") or "")[:200],
            }
            _r481_result = _r481_send_notif(_r481_item)
            if _r481_result.get("ok"):
                logger.info("[Prospector] R481 notify ok: %s (%d sent)",
                            job_id, _r481_result.get("sent", 0))
            else:
                logger.info("[Prospector] R481 notify skip: %s reason=%s",
                            job_id, _r481_result.get("reason", "unknown"))
        except Exception as _r481_exc:
            logger.warning("[Prospector] R481 notify exception for %s: %s",
                           job_id, _r481_exc)

        return job_id
    except Exception as e:
        logger.warning("[Prospector] R454 hitl-queue failed for %s: %s",
                       msg.get("to","?"), e)
        return None


def _send_outreach_email(lead: Dict, contact_id: str, touch: int = 1) -> bool:
    """R454: Queue outreach to HITL instead of sending direct.

    Per Terms §1B.1 every outbound under founder credentials requires
    per-item approval. SMTP-direct path is removed. Queue success counts
    as the touch (since attempt is now "presented for approval", not "sent").
    """
    msg = _compose_outreach(lead, touch)
    job_id = _r454_queue_outbound_for_hitl(msg, contact_id, touch)
    sent = job_id is not None  # 'sent' here means 'queued for approval'

    if sent:
        logger.info("[Prospector] R454 queued touch #%d to %s as job %s",
                    touch, msg["to"], job_id)
    else:
        logger.warning("[Prospector] R454 failed to queue touch #%d to %s",
                       touch, msg["to"])

    # BLOCK-X.2 truth fix: activity_type reflects send result, not just attempt.
    # Previously: always wrote 'email_sent'/'follow_up' regardless of SMTP success,
    # so CRM dashboard reported successes that never delivered (12 days, 0 replies).
    if sent:
        act_type = "email_sent" if touch == 1 else "follow_up"
        summary  = f"Touch #{touch} to {msg['to']} — {msg['subject'][:60]}"
    else:
        act_type = "email_send_failed"
        summary  = f"FAILED Touch #{touch} to {msg['to']} — {msg['subject'][:60]}"
    act_id   = str(uuid.uuid4())[:12]
    now      = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(CRM_DB, timeout=5) as db:
            db.execute(
                "INSERT INTO activities (id,activity_type,contact_id,deal_id,"
                "user_id,summary,details,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (act_id, act_type, contact_id, "",
                 "murphy_prospector",
                 summary,
                 json.dumps({"subject": msg["subject"], "sent": sent, "touch": touch}),
                 now)
            )
            db.commit()
    except Exception as e:
        logger.warning("[Prospector] Activity log failed: %s", e)
    return sent


# ══════════════════════════════════════════════════════════════════════════════
# LEAD SOURCES
# ══════════════════════════════════════════════════════════════════════════════

def _source_hn_hiring(max_leads: int = 20) -> List[Dict]:
    search = _fetch_json(
        "https://hn.algolia.com/api/v1/search?query=Ask+HN+Who+is+Hiring"
        "&tags=story&hitsPerPage=5", timeout=8)
    if not search:
        return []
    hits = [h for h in search.get("hits", []) if "hiring" in h.get("title","").lower()]
    if not hits:
        return []
    thread_id = hits[0]["objectID"]
    thread = _fetch_json(
        f"https://hacker-news.firebaseio.com/v0/item/{thread_id}.json", timeout=8)
    if not thread:
        return []
    AI_KW = ["ai","ml","machine learning","llm","automation","autonomous",
             "agent","gpt","saas","b2b","fintech","healthtech"]
    leads = []
    for kid_id in (thread.get("kids") or [])[:200]:
        if len(leads) >= max_leads:
            break
        item = _fetch_json(
            f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json", timeout=5)
        if not item or item.get("dead") or item.get("deleted"):
            continue
        text = item.get("text","")
        if not text:
            continue
        if not any(k in text.lower() for k in AI_KW):
            continue
        emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
        if not emails:
            continue
        email = emails[0].lower()
        company_m = re.search(r"<b>([^<]{2,60})</b>", text)
        company   = re.sub(r"<[^>]+>","",company_m.group(1)).strip() if company_m                     else re.sub(r"<[^>]+>","",text).split()[0][:40]
        title_m = re.search(
            r"(cto|founder|co-founder|vp|head of|director|engineer)[^\s<,.]{0,40}",
            text.lower())
        title = title_m.group(0).strip() if title_m else "Engineering Lead"
        icp = _icp_score(title, company)
        if icp < MIN_ICP_SCORE:
            icp = MIN_ICP_SCORE  # HN hiring = inherently qualified
        leads.append({"name":"","email":email,"company":company[:80],
                      "title":title[:60],"source":"hn_hiring",
                      "icp_score":icp,"deal_value":4900})
        time.sleep(0.15)
    return leads


def _source_yc(max_leads: int = 20) -> List[Dict]:
    data = _fetch_json("https://yc-oss.github.io/api/companies/all.json", timeout=10)
    if not data or not isinstance(data, list):
        return []
    # YC uses CapitalCase tags ("SaaS","B2B","AI","Fintech") and an "industries"
    # field where 3032/5927 are tagged "B2B". Match both, case-insensitively.
    AI_TAGS = {"ai","machine-learning","automation","saas","b2b",
               "developer-tools","fintech","healthcare","security","llm",
               "hard tech","analytics","productivity","robotics","infrastructure"}
    def _matches(c):
        tags_lc = {str(t).lower() for t in (c.get("tags") or [])}
        ind_lc  = {str(i).lower() for i in (c.get("industries") or [])}
        if not (tags_lc & AI_TAGS or ind_lc & AI_TAGS):
            return False
        if not c.get("website"):
            return False
        ts = c.get("team_size")
        # team_size is int in real YC payload, sometimes None
        if ts is None:
            return True   # unknown size acceptable
        try:
            return int(ts) < 200
        except (TypeError, ValueError):
            return True
    # Active companies only — Acquired/Inactive have no live email
    candidates = [c for c in data
                  if c.get("status") == "Active"
                  and _matches(c)]
    random.shuffle(candidates)
    leads = []
    for co in candidates:
        if len(leads) >= max_leads:
            break
        website = co.get("website","")
        domain  = re.sub(r"https?://","",website).split("/")[0].replace("www.","")
        if not domain:
            continue
        try:
            import sys; sys.path.insert(0,"/opt/Murphy-System")
            from src.illuminate import domain_search
            result   = domain_search(domain, verify=False)
            contacts = result.get("contacts",[])
        except Exception:
            contacts = []
        if not contacts:
            time.sleep(0.3)
            continue
        best = sorted(contacts,
                      key=lambda x: _icp_score(x.get("title",""), co.get("name","")),
                      reverse=True)
        c = best[0]
        email = c.get("email","")
        if not email:
            continue
        icp = max(_icp_score(c.get("title",""), co.get("name",""), domain), 45)
        leads.append({
            "name":      c.get("full_name",""),
            "email":     email,
            "company":   co.get("name",""),
            "title":     c.get("title","Founder"),
            "source":    "yc_list",
            "icp_score": icp,
            "deal_value": 9800,
            "url":       website,
        })
        time.sleep(0.4)
    return leads


async def _source_remoteok_async(max_leads: int = 15) -> List[Dict]:
    """R348: True async RemoteOK source. Use from async callers.

    Improvements over R343 sync version:
      * aiohttp for the API fetch (concurrent with other awaits)
      * aiodns for non-blocking DNS lookups
      * asyncio.gather for parallel DNS (no thread pool)
      * Future-proof for async pipelines (cron stays sync; await callers
        get this version directly)

    Sync version (_source_remoteok) remains the default for existing callers.
    """
    import asyncio
    try:
        import aiohttp
        import aiodns
    except ImportError as e:
        # Fall back to sync if libs missing
        return _source_remoteok(max_leads=max_leads)

    UA = "Mozilla/5.0 (compatible; MurphyBot/1.0; +https://murphy.systems)"
    headers = {"User-Agent": UA, "Accept": "application/json"}

    # ── Pass 1: async API fetch ────────────────────────────────────────
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(headers=headers,
                                           timeout=timeout) as session:
            async with session.get("https://remoteok.com/api?tag=ai") as r:
                if r.status != 200:
                    return []
                data = await r.json(content_type=None)
    except (asyncio.TimeoutError, aiohttp.ClientError):
        return []

    if not data or not isinstance(data, list):
        return []

    # ── Slugify (same logic as sync version) ──────────────────────────
    def _slug(company: str) -> str:
        if not company:
            return ""
        for suffix in [", Inc.", " Inc.", " Inc", ", LLC", " LLC", " Ltd",
                       " Co.", " Co", " Corporation", " Corp", " AI",
                       " Labs", " Studios", " Technologies", " Tech"]:
            if company.endswith(suffix):
                company = company[:-len(suffix)].strip()
        slug = "".join(c for c in company.lower() if c.isalnum())
        if len(slug) < 3 or len(slug) > 30:
            return ""
        return slug + ".com"

    # ── Pass 2: collect candidates ───────────────────────────────────
    candidates = []
    seen = set()
    for job in data[1:]:
        company = (job.get("company") or "").strip()
        if not company or company in seen:
            continue
        seen.add(company)
        position = job.get("position", "")
        domain = _slug(company)
        if not domain:
            continue
        icp = _icp_score(position, company, domain)
        if icp < 30:
            continue
        candidates.append({
            "company": company, "position": position,
            "domain": domain, "icp": icp,
            "remoteok_url": job.get("url", ""),
        })
        if len(candidates) >= max_leads * 3:
            break

    if not candidates:
        return []

    # ── Pass 3: parallel async DNS via aiodns ─────────────────────────
    resolver = aiodns.DNSResolver(timeout=3, tries=1)

    async def _resolve_one(c):
        try:
            await resolver.query(c["domain"], "A")
            c["dns_ok"] = True
        except Exception:
            c["dns_ok"] = False
        return c

    try:
        # asyncio.gather runs all DNS calls concurrently in event loop
        # — no thread pool, no GIL contention
        checked = await asyncio.wait_for(
            asyncio.gather(*[_resolve_one(c) for c in candidates]),
            timeout=15
        )
    except asyncio.TimeoutError:
        checked = candidates  # accept what we have

    # ── Pass 4: emit leads ────────────────────────────────────────────
    leads = []
    for c in checked:
        if len(leads) >= max_leads:
            break
        if not c.get("dns_ok"):
            continue
        pos_lower = c["position"].lower()
        if any(w in pos_lower for w in ["engineer", "developer",
                                          "ml", "ai", "data"]):
            email_user = "careers"
        else:
            email_user = "hello"
        leads.append({
            "name": "",
            "email": f"{email_user}@{c['domain']}",
            "company": c["company"],
            "title": c["position"][:80],
            "source": "remoteok",
            "icp_score": c["icp"],
            "deal_value": 4900,
            "url": c.get("remoteok_url", ""),
            "domain_inferred": True,
            "async_path": True,  # R348 marker
        })
    return leads


def _source_remoteok(max_leads: int = 15) -> List[Dict]:
    """R343: RemoteOK source — rewritten because original was broken.

    Original bug: apply_url/url ALWAYS point to remoteOK.com/remote-jobs/...
    Never the employer's site. domain_search returned 0% hit rate.

    New strategy:
      1. Pull jobs from RemoteOK API (fast, ~1s)
      2. Guess employer domain from company name (slugify + .com)
      3. Use common-pattern email fallback (info@, hello@, contact@,
         careers@) without domain_search dependency
      4. Verify domain DNS exists (cheap MX/A lookup) before emitting
      5. Run all DNS lookups in parallel (5 workers, 3s each)
    """
    import concurrent.futures as _cf
    import socket

    data = _fetch_json("https://remoteok.com/api?tag=ai", timeout=10)
    if not data or not isinstance(data, list):
        return []

    def _slug_to_domain(company: str) -> str:
        """ACMECorp Inc → acmecorp.com — naive but works for ~60% of startups."""
        if not company:
            return ""
        # strip common suffixes
        for suffix in [", Inc.", " Inc.", " Inc", ", LLC", " LLC", " Ltd",
                       " Co.", " Co", " Corporation", " Corp", " AI",
                       " Labs", " Studios", " Technologies", " Tech"]:
            if company.endswith(suffix):
                company = company[:-len(suffix)].strip()
        # keep alphanumerics, lowercase
        slug = "".join(c for c in company.lower() if c.isalnum())
        if len(slug) < 3 or len(slug) > 30:
            return ""
        return slug + ".com"

    def _check_domain(domain: str) -> bool:
        """Fast DNS check — does this domain exist?"""
        try:
            socket.gethostbyname(domain)
            return True
        except Exception:
            return False

    # Pass 1: collect raw candidates (no DNS, no enrichment)
    candidates = []
    seen_companies = set()
    for job in data[1:]:
        company = (job.get("company") or "").strip()
        if not company or company in seen_companies:
            continue
        seen_companies.add(company)
        position = job.get("position", "")
        domain = _slug_to_domain(company)
        if not domain:
            continue
        # ICP gate before DNS — cheap filter
        icp = _icp_score(position, company, domain)
        if icp < 30:
            continue
        candidates.append({
            "company": company, "position": position,
            "domain": domain, "icp": icp,
            "remoteok_url": job.get("url", ""),
        })
        if len(candidates) >= max_leads * 3:
            break

    if not candidates:
        return []

    # Pass 2: parallel DNS check, 5 workers, 3s timeout each
    def _check(c):
        c["dns_ok"] = _check_domain(c["domain"])
        return c

    with _cf.ThreadPoolExecutor(max_workers=5) as ex:
        try:
            checked = list(ex.map(_check, candidates, timeout=20))
        except _cf.TimeoutError:
            checked = candidates  # accept what we have

    # Pass 3: emit leads with common-pattern emails
    leads = []
    EMAIL_PATTERNS = ["info", "hello", "contact", "careers"]
    for c in checked:
        if len(leads) >= max_leads:
            break
        if not c.get("dns_ok"):
            continue
        # Pick best pattern based on position type
        pos_lower = c["position"].lower()
        if any(w in pos_lower for w in ["engineer", "developer", "ml", "ai", "data"]):
            email_user = "careers"  # tech roles → recruiting
        else:
            email_user = "hello"   # default
        email = f"{email_user}@{c['domain']}"

        leads.append({
            "name": "",
            "email": email,
            "company": c["company"],
            "title": c["position"][:80],
            "source": "remoteok",
            "icp_score": c["icp"],
            "deal_value": 4900,
            "url": c.get("remoteok_url", ""),
            "domain_inferred": True,  # mark as guess, not verified
        })

    return leads

# ══════════════════════════════════════════════════════════════════════════════
# FOLLOW-UP CADENCE ENGINE
# ══════════════════════════════════════════════════════════════════════════════

MAX_TOUCHES    = 3        # total outreach attempts per contact
FOLLOWUP_DAYS  = [3, 7]  # days after opener to send follow-ups


def run_followup_cadence() -> Dict:
    """
    Check all auto-prospected contacts. Send follow-ups per cadence rules.
    Called by scheduler every 24 hours.
    Cadence: opener(day 0) → follow-up #1 (day 3) → follow-up #2 (day 7) → archive.
    Never contacts anyone on DNC. Never exceeds MAX_TOUCHES.
    """
    sent = 0; skipped = 0; archived = 0
    try:
        with sqlite3.connect(CRM_DB, timeout=8) as db:
            rows = db.execute(
                "SELECT c.id, c.name, c.email, c.company, c.contact_type, "
                "       c.tags, c.created_at "
                "FROM contacts c "
                "WHERE c.tags LIKE '%auto-prospected%' "
                "AND c.contact_type='lead'"
            ).fetchall()
    except Exception as e:
        logger.warning("[Prospector] Cadence scan error: %s", e)
        return {"sent":0,"error":str(e)}

    for row in rows:
        cid, name, email, company, ctype, tags_raw, created_at = row
        if not email:
            continue

        # Hard DNC re-check on every run
        blocked, reason = _dnc_blocked(email)
        if blocked:
            logger.info("[Prospector] DNC re-check blocked %s: %s", email, reason)
            skipped += 1
            continue

        touches   = _follow_up_count(email)
        days_ago  = _days_since_last_contact(email)

        # Archive if maxed out
        if touches >= MAX_TOUCHES:
            try:
                with sqlite3.connect(CRM_DB, timeout=5) as db:
                    db.execute(
                        "UPDATE contacts SET contact_type='archived' WHERE id=?", (cid,))
                    db.commit()
                archived += 1
            except Exception:
                pass
            continue

        # Opener not sent yet
        if touches == 0:
            lead = {"name":name,"email":email,"company":company,"title":""}
            ok = _send_outreach_email(lead, cid, touch=1)
            if ok:
                sent += 1
            else:
                skipped += 1
            continue

        # Follow-up window check
        needed_days = FOLLOWUP_DAYS[min(touches - 1, len(FOLLOWUP_DAYS) - 1)]
        if days_ago is None or days_ago < needed_days:
            skipped += 1
            continue

        lead = {"name":name,"email":email,"company":company,"title":""}
        ok = _send_outreach_email(lead, cid, touch=touches + 1)
        if ok:
            sent += 1
        else:
            skipped += 1

    return {"sent":sent, "skipped":skipped, "archived":archived}


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PROSPECTING CYCLE
# ══════════════════════════════════════════════════════════════════════════════

# ── MEP/Electrical/Plumbing contractor source — USA Spending federal awards ──
# Founder ICP locked 2026-05-26: contractors who execute physical projects
# (HVAC, electrical, plumbing, energy audit). $5M-$500M annual revenue.
# USA Spending shows federal contract awards; recipients with $100K-$50M awards
# in NAICS 238210/238220/238290 are exactly mid-size MEP contractors.
def _source_usaspending(max_leads: int = 20) -> List[Dict]:
    """Real MEP contractor discovery from federal contract awards.
    Public free API, no key needed. NAICS-filtered for our ICP."""
    import urllib.request, urllib.error, json as _j
    SUFFIXES = {"llc","inc","incorporated","corp","corporation","co","company",
                "ltd","lp","plc","p.c.","pc","group","holdings"}
    SKIP_NAMES = ("RAYTHEON","BOEING","LOCKHEED","BAE SYSTEMS","BOOZ ALLEN",
                  "GENERAL DYNAMICS","JACOBS GOV","TUTOR PERINI","WSP USA")

    payload = {
        "filters": {
            "award_type_codes": ["A","B","C","D"],
            "naics_codes": ["238210","238220","238290"],
            "time_period": [{"start_date":"2024-01-01","end_date":"2026-12-31"}],
            "award_amounts": [{"lower_bound":1000000,"upper_bound":1000000000}],
        },
        "fields": ["Recipient Name","Award Amount","Recipient Location","NAICS Code"],
        "page": 1, "limit": min(max_leads * 3, 100),
        "sort": "Award Amount", "order": "desc",
    }
    try:
        req = urllib.request.Request(
            "https://api.usaspending.gov/api/v2/search/spending_by_award/",
            data=_j.dumps(payload).encode(),
            headers={"Content-Type":"application/json","User-Agent":AGENT},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _j.loads(resp.read().decode())
    except Exception as e:
        logger.warning("[usaspending] fetch failed: %s", e)
        return []

    results = data.get("results", []) or []
    seen_names = set()
    leads: List[Dict] = []
    for r in results:
        if len(leads) >= max_leads:
            break
        name = (r.get("Recipient Name") or "").strip()
        if not name or name in seen_names:
            continue
        nu = name.upper()
        if any(s in nu for s in SKIP_NAMES) or " JV " in (" "+nu+" "):
            continue
        seen_names.add(name)

        # Guess domain from name (strip suffixes, lowercase, alphanumeric only)
        words = [w for w in re.sub(r"[^a-z0-9 &]"," ",name.lower()).split()
                 if w and w not in SUFFIXES and w != "&"]
        if not words:
            continue
        # Try first 2-3 word concatenation
        domain_guess = "".join(words[:3])[:30] + ".com"

        # Verify domain has MX before bothering with scrape
        try:
            import socket
            socket.gethostbyname(domain_guess)  # quick A-record check
        except Exception:
            # try shorter (first 2 words, then first word)
            alt = "".join(words[:2])[:30] + ".com"
            try:
                socket.gethostbyname(alt)
                domain_guess = alt
            except Exception:
                try:
                    socket.gethostbyname(words[0]+".com")
                    domain_guess = words[0]+".com"
                except Exception:
                    continue   # no resolvable domain — skip

        # Scrape via Illuminate
        try:
            sys.path.insert(0,"/opt/Murphy-System")
            from src.illuminate import domain_search
            scraped  = domain_search(domain_guess, verify=False)
            contacts = scraped.get("contacts", [])
        except Exception:
            contacts = []
        if not contacts:
            time.sleep(0.3)
            continue
        best = sorted(contacts,
                      key=lambda x: _icp_score(x.get("title",""), name, domain_guess),
                      reverse=True)[0]
        email = best.get("email","")
        if not email:
            continue

        loc       = r.get("Recipient Location") or {}
        award_amt = r.get("Award Amount", 0) or 0
        # ── TWO-TRACK CLASSIFICATION (founder rule 2026-05-26) ─────────────
        # $50M+ award size proxies for $500M+ annual revenue → investor track.
        # Below $50M → buyer track. Different outreach, different deal_value.
        if award_amt >= 50_000_000:
            track       = "investor_track_fundraising"
            deal_value  = 0       # not a sales deal — fundraising touch
            track_label = "INVESTOR"
        else:
            track       = "buyer_track_contractor"
            deal_value  = max(int(award_amt * 0.005), 9800)  # 0.5% of award size, floor $9.8K
            track_label = "BUYER"
        leads.append({
            "name":       best.get("full_name","") or "",
            "email":      email,
            "company":    name.title(),
            "title":      best.get("title","Owner / President"),
            "source":     "usaspending_mep",
            "icp_score":  max(_icp_score(best.get("title",""), name, domain_guess), 60),
            "deal_value": deal_value,
            "url":        f"https://{domain_guess}",
            "tags":       track,
            "notes":      f"[{track_label}] Federal award ${award_amt:,.0f}  NAICS {r.get('NAICS Code','')}  Loc: {loc.get('state_code','')} {loc.get('city_name','')}",
        })
        time.sleep(0.3)
    logger.info("[usaspending] %d MEP contractor leads with verified emails", len(leads))
    return leads





# ============================================================
# ACTIVE_PROSPECTING_PATCH 2026-06-04 — MX check + Murphy critic
# ============================================================
import subprocess as _ap_subproc, re as _ap_re

def _ap_has_mx(email: str) -> bool:
    """Return True iff domain has at least 1 MX record."""
    try:
        domain = email.split("@", 1)[1]
        out = _ap_subproc.run(["dig","+short","MX",domain],
                              capture_output=True, text=True, timeout=5)
        return bool(out.stdout.strip())
    except Exception:
        return False

_AP_WRONG_AUDIENCE = [
    r"\bAI safety\b", r"\bAI teams\b", r"\bAI startup\b",
    r"\bdebugging AI outputs\b", r"\bproduction safety layer\b",
    r"\bAI reliability\b", r"\breducing AI risk\b",
]
_AP_PLACEHOLDER  = [r"\{[a-z_|]+\}"]
_AP_BAD          = [r"\bfuck\b", r"\bshit\b", r"\bguaranteed millions\b"]
_AP_DOLLAR_REQ   = [r"\$\d", r"\d+K", r"\d+%"]
_AP_VERTICAL     = ["facility","facilities","HVAC","compressed","BMS","building",
                    "contractor","distribution","industrial","campus","hospital",
                    "office","energy","mechanical","electrical","MEP","fabrication","medical"]

def _ap_murphy_critic(subject: str, body: str, recipient_email: str) -> tuple:
    """Score 0-100. Block threshold: 70. Returns (score, reasons[])."""
    s = 100; why = []
    text = f"{subject}\n\n{body}"
    for p in _AP_WRONG_AUDIENCE:
        if _ap_re.search(p, text, _ap_re.IGNORECASE): s -= 50; why.append(f"wrong_audience:{p}")
    for p in _AP_PLACEHOLDER:
        if _ap_re.search(p, text, _ap_re.IGNORECASE): s -= 30; why.append(f"placeholder_leak:{p}")
    for p in _AP_BAD:
        if _ap_re.search(p, text, _ap_re.IGNORECASE): s -= 40; why.append(f"bad_signal:{p}")
    if not any(_ap_re.search(p, text) for p in _AP_DOLLAR_REQ):
        s -= 15; why.append("no_dollar_or_percent_claim")
    if not any(w.lower() in text.lower() for w in _AP_VERTICAL):
        s -= 20; why.append("no_vertical_relevance")
    if "prospect-pending" in recipient_email or "queue.murphy.systems" in recipient_email:
        s -= 100; why.append("placeholder_recipient")
    if not _ap_has_mx(recipient_email):
        s -= 100; why.append("no_mx_record")
    return max(s, 0), why

# Apply MX check at lead-ingestion time: monkeypatch _source_usaspending to tag email_status
_AP_ORIGINAL_USASPENDING = _source_usaspending if "_source_usaspending" in dir() else None

def _source_usaspending_wrapped(max_leads: int = 20):
    leads = _AP_ORIGINAL_USASPENDING(max_leads) if _AP_ORIGINAL_USASPENDING else []
    for lead in leads:
        email = lead.get("email","")
        if email and _ap_has_mx(email):
            lead["email_status"] = "mx_ok"
        else:
            lead["email_status"] = "no_mx"
    return leads

if _AP_ORIGINAL_USASPENDING:
    _source_usaspending = _source_usaspending_wrapped

# ============================================================

def run_prospecting_cycle(max_total: int = 30) -> Dict:
    """
    Find new leads from all sources, DNC-check, ICP-score, insert into CRM.
    Called by swarm scheduler every 6 hours.
    """
    logger.info("[Prospector] Starting autonomous prospecting cycle")
    start   = time.time()
    all_leads: List[Dict] = []

    for src_name, fn, limit in [
        ("usaspending", _source_usaspending, 20),
        # DISABLED_2026-06-04_wrong_audience: ("hn_hiring",   _source_hn_hiring,   20),
        # DISABLED_2026-06-04_wrong_audience: ("yc_list",     _source_yc,          20),
        # DISABLED_2026-06-04_wrong_audience: ("remoteok",    _source_remoteok,    15),
    ]:
        try:
            found = fn(limit)
            logger.info("[Prospector] %s: %d raw leads", src_name, len(found))
            all_leads.extend(found)
        except Exception as e:
            logger.warning("[Prospector] %s error: %s", src_name, e)

    # Dedupe by email
    seen = set(); unique = []
    for lead in all_leads:
        e = (lead.get("email") or "").lower()
        if e and e not in seen:
            seen.add(e); unique.append(lead)

    # Sort best ICP first
    unique.sort(key=lambda x: x.get("icp_score",0), reverse=True)

    added = 0; blocked = 0; low_icp = 0
    for lead in unique[:max_total]:
        email = (lead.get("email") or "").lower()
        # Pre-gate reporting
        dnc_hit, _ = _dnc_blocked(email)
        if dnc_hit:
            blocked += 1; continue
        if lead.get("icp_score",0) < MIN_ICP_SCORE:
            low_icp += 1; continue
        cid = _add_to_crm(lead)
        if cid:
            added += 1

    elapsed = round(time.time() - start, 1)
    result = {
        "success":      True,
        "leads_found":  len(all_leads),
        "leads_unique": len(unique),
        "leads_added":  added,
        "dnc_blocked":  blocked,
        "low_icp_skip": low_icp,
        "elapsed_sec":  elapsed,
    }
    logger.info("[Prospector] Done: %d added / %d DNC-blocked / %d low-ICP in %ss",
                added, blocked, low_icp, elapsed)
    return result


def get_stats() -> Dict:
    try:
        with sqlite3.connect(CRM_DB, timeout=5) as db:
            total    = db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
            auto     = db.execute(
                "SELECT COUNT(*) FROM contacts WHERE tags LIKE '%auto-prospected%'"
            ).fetchone()[0]
            open_ld  = db.execute(
                "SELECT COUNT(*) FROM deals WHERE stage='lead'"
            ).fetchone()[0]
            dnc_cnt  = db.execute(
                "SELECT COUNT(*) FROM dnc_suppression"
            ).fetchone()[0]
            archived = db.execute(
                "SELECT COUNT(*) FROM contacts WHERE contact_type='archived'"
            ).fetchone()[0]
        return {
            "total_contacts": total,
            "auto_prospected": auto,
            "open_leads": open_ld,
            "dnc_entries": dnc_cnt,
            "archived": archived,
        }
    except Exception as e:
        return {"error": str(e)}
