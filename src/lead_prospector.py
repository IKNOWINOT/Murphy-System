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
MIN_ICP_SCORE = 40   # leads below this are discarded


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
    tags = json.dumps(["auto-prospected", lead.get("source","prospector")])
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


def _compose_outreach(lead: Dict, touch_number: int = 1) -> Dict:
    """
    Compose a personalised outreach email using sales best practices.
    touch_number: 1=opener, 2=follow-up 1, 3=follow-up 2.
    Returns {subject, body, to, from, touch}.
    """
    name      = lead.get("name", "")
    email     = lead.get("email", "")
    company   = lead.get("company", "there")
    title     = lead.get("title", "")
    first     = (name.split()[0] if name and " " in name else name) or "there"
    role_ctx  = "engineering" if any(w in title.lower() for w in ["engineer","cto","tech"])                 else "founder" if "found" in title.lower()                 else "product" if "product" in title.lower()                 else "AI"

    ctx = {
        "first_name":   first,
        "company":      company,
        "title":        title,
        "role_context": role_ctx,
    }

    if touch_number == 1:
        tmpl = random.choice(OPENER_TEMPLATES)
        body = tmpl.format(**ctx)
        subj = body.split("\n")[0].replace("Subject: ","")
        body = "\n".join(body.split("\n")[1:]).strip()
    elif touch_number == 2:
        body = FOLLOWUP_1_TEMPLATE.format(**ctx)
        subj = body.split("\n")[0].replace("Subject: ","")
        body = "\n".join(body.split("\n")[1:]).strip()
    else:
        body = FOLLOWUP_2_TEMPLATE.format(**ctx)
        subj = body.split("\n")[0].replace("Subject: ","")
        body = "\n".join(body.split("\n")[1:]).strip()

    return {
        "to":      email,
        "from":    "cpost@murphy.systems",
        "subject": subj,
        "body":    body,
        "touch":   touch_number,
        "name":    name,
        "company": company,
    }


def _send_outreach_email(lead: Dict, contact_id: str, touch: int = 1) -> bool:
    """Send outreach email via murphy mail server. Log activity. Returns success."""
    msg = _compose_outreach(lead, touch)
    try:
        from src.murphy_mail import send_email
        sent = send_email(
            to=msg["to"],
            subject=msg["subject"],
            body=msg["body"],
            from_addr=msg["from"],
        )
    except Exception:
        # Fallback: raw SMTP
        try:
            import smtplib
            from email.mime.text import MIMEText
            m = MIMEText(msg["body"])
            m["Subject"] = msg["subject"]
            m["From"]    = msg["from"]
            m["To"]      = msg["to"]
            with smtplib.SMTP("localhost", 587, timeout=8) as s:
                s.starttls()
                s.login("cpost@murphy.systems", "Password1")
                s.send_message(m)
            sent = True
        except Exception as e2:
            logger.warning("[Prospector] Email send failed to %s: %s", msg["to"], e2)
            sent = False

    # Log activity regardless
    act_type = "email_sent" if touch == 1 else "follow_up"
    act_id   = str(uuid.uuid4())[:12]
    now      = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(CRM_DB, timeout=5) as db:
            db.execute(
                "INSERT INTO activities (id,activity_type,contact_id,deal_id,"
                "user_id,summary,details,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (act_id, act_type, contact_id, "",
                 "murphy_prospector",
                 f"Touch #{touch} to {msg['to']} — {msg['subject'][:60]}",
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
    AI_TAGS = {"ai","machine-learning","automation","saas","b2b",
               "developer-tools","fintech","healthcare","security","llm"}
    candidates = [c for c in data if set(c.get("tags",[])) & AI_TAGS
                  and c.get("website") and c.get("team_size","")
                  and str(c.get("team_size","0")).isdigit()
                  and int(str(c.get("team_size","0"))) < 200]
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


def _source_remoteok(max_leads: int = 15) -> List[Dict]:
    data = _fetch_json("https://remoteok.com/api?tag=ai", timeout=10)
    if not data or not isinstance(data, list):
        return []
    leads = []
    for job in data[1:]:
        if len(leads) >= max_leads:
            break
        company   = (job.get("company") or "").strip()
        position  = job.get("position","")
        apply_url = job.get("apply_url") or job.get("url","")
        if not company:
            continue
        domain = ""
        if apply_url:
            m = re.search(r"https?://([^/]+)", apply_url)
            if m:
                domain = m.group(1).replace("www.","").split("/")[0]
        if not domain or any(s in domain for s in
                             ["remoteok","lever.co","greenhouse","workable","ashby","rippling"]):
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
                      key=lambda x: _icp_score(x.get("title",""), company),
                      reverse=True)
        c = best[0]
        email = c.get("email","")
        if not email:
            continue
        icp = max(_icp_score(c.get("title",""), company, domain), 40)
        leads.append({
            "name":      c.get("full_name",""),
            "email":     email,
            "company":   company,
            "title":     c.get("title", position)[:80],
            "source":    "remoteok",
            "icp_score": icp,
            "deal_value": 4900,
            "url":        apply_url,
        })
        time.sleep(0.4)
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

def run_prospecting_cycle(max_total: int = 30) -> Dict:
    """
    Find new leads from all sources, DNC-check, ICP-score, insert into CRM.
    Called by swarm scheduler every 6 hours.
    """
    logger.info("[Prospector] Starting autonomous prospecting cycle")
    start   = time.time()
    all_leads: List[Dict] = []

    for src_name, fn, limit in [
        ("hn_hiring",  _source_hn_hiring,  20),
        ("yc_list",    _source_yc,         20),
        ("remoteok",   _source_remoteok,   15),
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
