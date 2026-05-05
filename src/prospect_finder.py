"""
prospect_finder.py — Autonomous Prospect Discovery Engine (PATCH-190)
Sources: WorldCorpus (news/tech/finance articles) -> company extraction ->
         Hunter.io free-tier email lookup -> ICP scoring -> CRM insert.
DNC gate applied before any record is created.
"""
import sqlite3 as _sq3
import logging
import re
import uuid
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import List, Dict, Optional

# Load environment from file if not already set (for test/standalone runs)
_ENV_FILE = "/etc/murphy-production/environment"
if os.path.exists(_ENV_FILE) and not os.environ.get("NEWSAPI_KEY"):
    try:
        with open(_ENV_FILE) as _ef:
            for _line in _ef:
                _line = _line.strip()
                if _line and "=" in _line and not _line.startswith("#"):
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
    except Exception:
        pass

logger = logging.getLogger(__name__)

CORPUS_DB  = "/var/lib/murphy-production/world_corpus.db"
CRM_DB     = "/var/lib/murphy-production/crm.db"
HUNTER_KEY   = os.environ.get("HUNTER_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# ── Illuminate — Murphy's own contact intelligence (PATCH-192) ──────────────
def _illuminate_lookup(domain: str) -> Optional[Dict]:
    """
    Illuminate domain search — Murphy's own Hunter.io replacement.
    Always free, no API key needed. Called FIRST before Hunter.
    Returns Hunter-compatible dict or None.
    """
    try:
        import src.illuminate as _il
        _il.ensure_tables()
        result = _il.domain_search(domain, verify=False)
        contacts = result.get("contacts", [])
        if not contacts:
            return None
        # Sort by confidence desc, prefer scraped over github
        contacts.sort(key=lambda c: -c.get("confidence", 0))
        best = contacts[0]
        email = best.get("email", "")
        if not email:
            return None
        # Parse name from email local part if no name available
        name = best.get("name", "")
        first, last = "", ""
        if name and " " in name:
            parts = name.split(None, 1)
            first, last = parts[0], parts[1]
        elif not name and "@" in email:
            local = email.split("@")[0]
            if "." in local:
                parts = local.split(".", 1)
                first, last = parts[0].capitalize(), parts[1].capitalize()
        return {
            "email":      email,
            "first_name": first,
            "last_name":  last,
            "position":   best.get("title", ""),
            "confidence": best.get("confidence", 60),
            "source":     "illuminate",
        }
    except Exception as ex:
        logger.debug("[ProspectFinder] Illuminate lookup failed for %s: %s", domain, ex)
        return None

# ICP definition — tunable via env
ICP_INDUSTRIES   = os.environ.get("ICP_INDUSTRIES",  "saas,fintech,operations,ai,automation,compliance,hr,logistics").split(",")
ICP_MIN_SIZE_SIG = os.environ.get("ICP_SIZE_SIGNAL", "team,employees,staff,headcount,workforce")  # signals in article
ICP_KEYWORDS     = ["automate","compliance","efficiency","workflow","scale","operations","revenue"]

# ── Company name extractor (heuristic from article text) ─────────────────────
_ORG_PATTERNS = [
    r'(?:at|by|from|joins?|company|startup|firm|platform|provider)\s+([A-Z][A-Za-z0-9&\.]+(?:\s[A-Z][A-Za-z0-9]+){0,2})',
    r'([A-Z][A-Za-z0-9]+(?:\s[A-Z][A-Za-z0-9]+){0,2})(?:\s+(?:Inc|LLC|Ltd|Corp|Co|Technologies|Systems|Labs|AI|Software|Platform|Solutions))\.?',
    r'([A-Z][A-Za-z0-9]+(?:AI|Tech|Labs|HQ|Systems|Works|Flow|Base|Stack|Scale|Ops))',
]

_STOP_WORDS = {
    "The","This","That","These","Those","Their","There","When","Where","Which",
    "What","Who","How","New","First","Last","Best","Top","More","Most","Also",
    "Murphy","System","Steve","PATCH","Monday","Tuesday","Wednesday",
}


def _extract_companies(text: str) -> List[str]:
    found = set()
    for pat in _ORG_PATTERNS:
        for m in re.finditer(pat, text):
            name = m.group(1).strip()
            if name and name not in _STOP_WORDS and len(name) > 3:
                found.add(name)
    return list(found)[:5]


def _score_icp(text: str, company: str) -> int:
    """Return 0-100 ICP fit score based on article signals."""
    score = 0
    low = text.lower()
    for kw in ICP_KEYWORDS:
        if kw in low:
            score += 8
    for ind in ICP_INDUSTRIES:
        if ind in low:
            score += 12
    if any(sig in low for sig in ICP_MIN_SIZE_SIG.split(",")):
        score += 10
    return min(score, 100)


def _domain_from_company(company: str) -> str:
    """Best-guess domain from company name."""
    clean = re.sub(r'[^a-z0-9]', '', company.lower())
    return f"{clean}.com"


def _hunter_lookup(domain: str) -> Optional[Dict]:
    """
    Hunter.io Domain Search — returns first verified email contact.
    Free tier: 25 searches/month. Returns None if key missing or no results.
    """
    if not HUNTER_KEY:
        return None
    try:
        url = (
            "https://api.hunter.io/v2/domain-search?"
            + urllib.parse.urlencode({
                "domain": domain,
                "api_key": HUNTER_KEY,
                "limit": 3,
                "type": "personal",
            })
        )
        req = urllib.request.Request(url, headers={"User-Agent": "MurphySystem/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        emails = data.get("data", {}).get("emails", [])
        # Prefer verified, then highest confidence
        emails.sort(key=lambda e: (e.get("verification", {}).get("status") != "valid", -e.get("confidence", 0)))
        if emails:
            e = emails[0]
            return {
                "email":      e.get("value", ""),
                "first_name": e.get("first_name", ""),
                "last_name":  e.get("last_name", ""),
                "position":   e.get("position", ""),
                "confidence": e.get("confidence", 0),
            }
    except Exception as ex:
        logger.debug("[ProspectFinder] Hunter lookup failed for %s: %s", domain, ex)
    return None


def _already_in_crm(email: str) -> bool:
    try:
        with _sq3.connect(CRM_DB, timeout=5) as conn:
            row = conn.execute(
                "SELECT id FROM contacts WHERE LOWER(email)=? LIMIT 1",
                (email.lower(),)
            ).fetchone()
            return row is not None
    except Exception:
        return False


def _insert_prospect(name: str, email: str, company: str,
                     position: str, source_url: str, icp_score: int) -> str:
    """Insert a new prospect into CRM contacts. Returns contact ID."""
    contact_id = f"auto_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    tags = json.dumps(["auto_prospect", f"icp_{icp_score}"])
    custom = json.dumps({
        "icp_score": icp_score,
        "source_url": source_url,
        "position": position,
        "discovery_method": "prospect_finder",
    })
    try:
        with _sq3.connect(CRM_DB, timeout=5) as conn:
            conn.execute(
                "INSERT INTO contacts (id,name,email,phone,company,contact_type,tags,custom_fields,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (contact_id, name, email, '', company, 'prospect', tags, custom, now)
            )
            conn.commit()
            logger.info("[ProspectFinder] Added prospect: %s <%s> @ %s (ICP: %d)", name, email, company, icp_score)
    except Exception as e:
        logger.error("[ProspectFinder] insert error: %s", e)
    return contact_id


def _already_in_crm_by_company(company: str) -> bool:
    """Check if company already has any contact in CRM."""
    try:
        with _sq3.connect(CRM_DB, timeout=5) as conn:
            row = conn.execute(
                "SELECT id FROM contacts WHERE LOWER(company)=? LIMIT 1",
                (company.lower(),)
            ).fetchone()
            return row is not None
    except Exception:
        return False


def _fetch_newsapi_signals() -> List[str]:
    """
    Pull fresh B2B SaaS / AI / automation company signals from NewsAPI.
    Returns list of headline strings. Requires NEWSAPI_KEY env var.
    """
    newsapi_key = os.environ.get("NEWSAPI_KEY", "")
    if not newsapi_key:
        return []
    results = []
    queries = [
        "AI automation startup funding",
        "SaaS company growth Series",
        "B2B software company hiring",
        "workflow automation platform launch",
    ]
    for q in queries[:2]:  # 2 queries to conserve API calls
        try:
            url = (
                "https://newsapi.org/v2/everything?"
                + urllib.parse.urlencode({
                    "q": q, "apiKey": newsapi_key,
                    "language": "en", "pageSize": 20,
                    "sortBy": "publishedAt",
                })
            )
            req = urllib.request.Request(url, headers={"User-Agent": "MurphySystem/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
            for art in data.get("articles", []):
                title = art.get("title", "") or ""
                source = art.get("source", {}).get("name", "")
                results.append(f"{title} | {source}")
        except Exception as ex:
            logger.debug("[ProspectFinder] NewsAPI signal fetch error: %s", ex)
    return results


def run_discovery(max_new: int = 10) -> Dict:
    """
    Main discovery cycle. Called by swarm scheduler every 6 hours.
    1. Pull recent corpus articles (tech + finance + news)
    2. Extract company names
    3. Score ICP fit
    4. Hunter.io email lookup
    5. DNC check
    6. Insert into CRM if passes all gates
    Returns summary dict.
    """
    from src.dnc_engine import check as dnc_check
    import src.dnc_engine as dnc_mod
    dnc_mod.ensure_table()

    results = {"discovered": 0, "dnc_blocked": 0, "already_known": 0,
               "no_email": 0, "low_icp": 0, "prospects": []}

    try:
        corpus_conn = _sq3.connect(CORPUS_DB, timeout=5)
        rows = corpus_conn.execute(
            "SELECT content, domain FROM corpus "
            "WHERE domain IN ('tech','finance','news') "
            "ORDER BY collected_at DESC LIMIT 200"
        ).fetchall()
        corpus_conn.close()
    except Exception as e:
        logger.error("[ProspectFinder] Corpus read error: %s", e)
        return results

    seen_companies = set()
    for row in rows:
        if results["discovered"] >= max_new:
            break

        content, domain_tag = row[0], row[1]
        companies = _extract_companies(content)

        for company in companies:
            if company in seen_companies or results["discovered"] >= max_new:
                continue
            seen_companies.add(company)

            icp_score = _score_icp(content, company)
            if icp_score < 20:
                results["low_icp"] += 1
                continue

            guess_domain = _domain_from_company(company)
            # ── PATCH-192: Illuminate-first lookup, Hunter as fallback ──
            contact_data = _illuminate_lookup(guess_domain)
            _source = "illuminate"

            if not contact_data or not contact_data.get("email"):
                # Illuminate found nothing — try Hunter if key is available
                contact_data = _hunter_lookup(guess_domain)
                _source = "hunter"

            if not contact_data or not contact_data.get("email"):
                # Neither found anything — placeholder for high-ICP companies
                if icp_score >= 80:
                    name = company + " (Contact TBD)"
                    if not _already_in_crm(""):
                        _insert_prospect(
                            name=name, email='', company=company,
                            position='Unknown', source_url=content[:120],
                            icp_score=icp_score
                        )
                        results["discovered"] += 1
                        results["prospects"].append({"company": company, "icp": icp_score, "email": None, "source": "tbd"})
                else:
                    results["no_email"] += 1
                continue

            email     = contact_data["email"]
            first     = contact_data.get("first_name", "")
            last      = contact_data.get("last_name", "")
            position  = contact_data.get("position", "")
            full_name = f"{first} {last}".strip() or company
            logger.info("[ProspectFinder] Contact found via %s: %s", _source, email)

            # Gate 1 — Already in CRM?
            if _already_in_crm(email):
                results["already_known"] += 1
                continue

            # Gate 2 — DNC check
            blocked, reason = dnc_check(email=email)
            if blocked:
                results["dnc_blocked"] += 1
                logger.info("[ProspectFinder] DNC blocked %s: %s", email, reason)
                continue

            # All gates passed — insert
            _insert_prospect(
                name=full_name, email=email, company=company,
                position=position, source_url=content[:120],
                icp_score=icp_score
            )
            results["discovered"] += 1
            results["prospects"].append({
                "company": company, "email": email,
                "name": full_name, "icp": icp_score,
                "confidence": contact_data.get("confidence", 0),
            })

    logger.info("[ProspectFinder] Cycle complete: %s", results)
    return results
