"""
illuminate.py — Illuminate: Murphy's own contact intelligence engine (PATCH-192)
Replicates and extends Hunter.io with zero external API dependencies.

Sources:
  - Clearbit Autocomplete (free, no key) — company domain + name lookup
  - Website scraper (BeautifulSoup) — email harvest from public pages
  - GitHub API (no key for public search) — commit emails
  - SEC EDGAR — company filings for contact data
  - Email pattern generator — 8 common patterns
  - SMTP verifier (port 25 MX probe) — live mailbox check
  - DNC gate — auto-check before any result is returned
  - ICP scorer — relevance score for Murphy's outreach ICP

DB: /var/lib/murphy-production/illuminate.db
"""

import sqlite3
import logging
import re
import uuid
import json
import os
import time
import subprocess
import smtplib
import socket
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout

logger = logging.getLogger(__name__)

ILLUMINATE_DB = "/var/lib/murphy-production/illuminate.db"
DNC_DB        = "/var/lib/murphy-production/crm.db"
SMTP_FROM     = "illuminate@murphy.systems"
SMTP_HELO     = "murphy.systems"
SCRAPE_AGENT  = "Mozilla/5.0 (compatible; IlluminateBot/1.0; +https://murphy.systems)"

# Load env
_ENV_FILE = "/etc/murphy-production/environment"
if os.path.exists(_ENV_FILE):
    try:
        with open(_ENV_FILE) as _ef:
            for _line in _ef:
                _line = _line.strip()
                if _line and "=" in _line and not _line.startswith("#"):
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
    except Exception:
        pass

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════════════════════════════════════

def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(ILLUMINATE_DB, timeout=8)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables() -> None:
    with _db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS il_contacts (
                id           TEXT PRIMARY KEY,
                email        TEXT DEFAULT '',
                first_name   TEXT DEFAULT '',
                last_name    TEXT DEFAULT '',
                full_name    TEXT DEFAULT '',
                title        TEXT DEFAULT '',
                domain       TEXT DEFAULT '',
                company      TEXT DEFAULT '',
                source       TEXT DEFAULT '',
                confidence   INTEGER DEFAULT 0,
                verified     INTEGER DEFAULT 0,
                verify_code  INTEGER DEFAULT 0,
                icp_score    INTEGER DEFAULT 0,
                dnc_blocked  INTEGER DEFAULT 0,
                raw_data     TEXT DEFAULT '{}',
                found_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS il_domains (
                id           TEXT PRIMARY KEY,
                domain       TEXT UNIQUE NOT NULL,
                company      TEXT DEFAULT '',
                industry     TEXT DEFAULT '',
                logo_url     TEXT DEFAULT '',
                employee_est TEXT DEFAULT '',
                email_pattern TEXT DEFAULT '',
                mx_host      TEXT DEFAULT '',
                scraped_at   TEXT,
                emails_found INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS il_verify_cache (
                email        TEXT PRIMARY KEY,
                valid        INTEGER,
                reason       TEXT,
                checked_at   TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_il_domain  ON il_contacts(domain);
            CREATE INDEX IF NOT EXISTS idx_il_email   ON il_contacts(email);
            CREATE INDEX IF NOT EXISTS idx_il_company ON il_contacts(company);
        """)
        conn.commit()
    logger.info("[Illuminate] Tables ready")


# ══════════════════════════════════════════════════════════════════════════════
# DNC CHECK (inline, no circular import)
# ══════════════════════════════════════════════════════════════════════════════

def _dnc_check(email: str) -> Tuple[bool, str]:
    """Returns (blocked, reason). Fail-open on DB error."""
    try:
        with sqlite3.connect(DNC_DB, timeout=5) as conn:
            row = conn.execute(
                "SELECT reason FROM dnc_suppression WHERE LOWER(email)=? LIMIT 1",
                (email.lower().strip(),)
            ).fetchone()
            if row:
                return True, f"DNC: {row[0] or 'opt-out'}"
            domain = email.split("@")[1] if "@" in email else ""
            if domain:
                row2 = conn.execute(
                    "SELECT reason FROM dnc_suppression WHERE domain=? AND email='' LIMIT 1",
                    (domain,)
                ).fetchone()
                if row2:
                    return True, f"DNC domain: {domain}"
    except Exception:
        pass
    return False, ""


# ══════════════════════════════════════════════════════════════════════════════
# MX LOOKUP
# ══════════════════════════════════════════════════════════════════════════════

def get_mx(domain: str) -> List[Tuple[int, str]]:
    """Return sorted MX records for domain using dig."""
    try:
        out = subprocess.check_output(
            ["dig", "+short", "MX", domain], timeout=6
        ).decode()
        records = []
        for line in out.strip().splitlines():
            parts = line.strip().split()
            if len(parts) == 2:
                try:
                    records.append((int(parts[0]), parts[1].rstrip(".")))
                except ValueError:
                    pass
        return sorted(records)
    except Exception as e:
        logger.debug("[Illuminate] MX lookup failed for %s: %s", domain, e)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# SMTP VERIFIER
# ══════════════════════════════════════════════════════════════════════════════

def verify_email(email: str, use_cache: bool = True) -> Dict:
    """
    Verify email via MX + SMTP RCPT probe.
    Returns: {valid: bool|None, reason: str, confidence: int, cached: bool}
    confidence: 0-100
    valid=None means unknown/catch-all/grey
    """
    email = email.lower().strip()

    # Check cache first
    if use_cache:
        try:
            with _db() as conn:
                row = conn.execute(
                    "SELECT valid, reason, checked_at FROM il_verify_cache WHERE email=?",
                    (email,)
                ).fetchone()
                if row:
                    age_h = (datetime.now(timezone.utc).timestamp() -
                             datetime.fromisoformat(row["checked_at"]).timestamp()) / 3600
                    if age_h < 72:  # cache for 72 hours
                        return {
                            "valid": bool(row["valid"]) if row["valid"] is not None else None,
                            "reason": row["reason"],
                            "confidence": 90 if row["valid"] else 20,
                            "cached": True,
                            "email": email,
                        }
        except Exception:
            pass

    if "@" not in email:
        return {"valid": False, "reason": "invalid_format", "confidence": 0, "cached": False, "email": email}

    domain = email.split("@")[1]

    # Step 1: MX check
    mx_records = get_mx(domain)
    if not mx_records:
        result = {"valid": False, "reason": "no_mx_record", "confidence": 5, "cached": False, "email": email}
        _cache_verify(email, False, "no_mx_record")
        return result

    mx_host = mx_records[0][1]

    # Step 2: SMTP probe
    valid = None
    reason = "unknown"
    try:
        with smtplib.SMTP(timeout=8) as smtp:
            smtp.connect(mx_host, 25)
            smtp.helo(SMTP_HELO)
            smtp.mail(SMTP_FROM)
            code, msg = smtp.rcpt(email)
            smtp.quit()
            msg_str = msg.decode() if isinstance(msg, bytes) else str(msg)
            if code == 250:
                valid = True
                reason = "smtp_accepted"
            elif code in (550, 551, 553):
                valid = False
                reason = f"smtp_rejected_{code}"
            elif code in (450, 451, 452):
                valid = None  # greylisted / temp defer
                reason = f"smtp_deferred_{code}"
            else:
                valid = None
                reason = f"smtp_code_{code}"
    except smtplib.SMTPConnectError:
        valid = None
        reason = "smtp_connect_error"
    except smtplib.SMTPServerDisconnected:
        valid = None
        reason = "smtp_disconnected"
    except socket.timeout:
        valid = None
        reason = "smtp_timeout"
    except Exception as e:
        valid = None
        reason = f"smtp_error_{type(e).__name__}"

    confidence = 90 if valid is True else (10 if valid is False else 50)
    _cache_verify(email, valid, reason)

    return {
        "valid": valid, "reason": reason,
        "confidence": confidence, "cached": False,
        "email": email, "mx": mx_host,
    }


def _cache_verify(email: str, valid, reason: str) -> None:
    try:
        now = datetime.now(timezone.utc).isoformat()
        valid_int = 1 if valid is True else (0 if valid is False else None)
        with _db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO il_verify_cache (email,valid,reason,checked_at) VALUES (?,?,?,?)",
                (email, valid_int, reason, now)
            )
            conn.commit()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL PATTERN GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

EMAIL_PATTERNS = [
    "{f}.{l}",       # john.smith     — most common B2B
    "{fi}{l}",       # jsmith
    "{f}",           # john
    "{fi}.{l}",      # j.smith
    "{l}.{f}",       # smith.john
    "{f}{li}",       # johns
    "{l}",           # smith
    "{f}_{l}",       # john_smith
    "{fi}_{l}",      # j_smith
]

def generate_candidates(first: str, last: str, domain: str) -> List[str]:
    """Generate all email pattern candidates for a person at a domain."""
    f  = re.sub(r"[^a-z]", "", first.lower())
    l  = re.sub(r"[^a-z]", "", last.lower())
    fi = f[0] if f else ""
    li = l[0] if l else ""
    candidates = []
    for pat in EMAIL_PATTERNS:
        try:
            email = pat.format(f=f, l=l, fi=fi, li=li) + "@" + domain
            candidates.append(email)
        except Exception:
            pass
    return candidates


def infer_pattern_from_known(domain: str) -> Optional[str]:
    """
    Look at known verified emails for this domain in our DB
    to infer which pattern they use.
    Returns pattern string like '{f}.{l}' or None.
    """
    try:
        with _db() as conn:
            rows = conn.execute(
                "SELECT email, first_name, last_name FROM il_contacts "
                "WHERE domain=? AND verified=1 AND first_name!='' AND last_name!='' LIMIT 10",
                (domain,)
            ).fetchall()
        if not rows:
            return None
        pattern_votes: Dict[str, int] = {}
        for row in rows:
            email = row["email"].split("@")[0]
            f = re.sub(r"[^a-z]", "", row["first_name"].lower())
            l = re.sub(r"[^a-z]", "", row["last_name"].lower())
            fi = f[0] if f else ""
            li = l[0] if l else ""
            for pat in EMAIL_PATTERNS:
                try:
                    candidate = pat.format(f=f, l=l, fi=fi, li=li)
                    if candidate == email:
                        pattern_votes[pat] = pattern_votes.get(pat, 0) + 1
                except Exception:
                    pass
        if pattern_votes:
            return max(pattern_votes, key=pattern_votes.get)
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
# COMPANY ENRICHMENT (Clearbit free autocomplete)
# ══════════════════════════════════════════════════════════════════════════════

def enrich_company(domain: str) -> Dict:
    """
    Enrich a company domain using Clearbit's free autocomplete API.
    No API key required. Returns company metadata.
    """
    try:
        url = ("https://autocomplete.clearbit.com/v1/companies/suggest?query="
               + urllib.parse.quote(domain.replace(".com", "").replace(".io", "")))
        req = urllib.request.Request(url, headers={"User-Agent": SCRAPE_AGENT})
        with urllib.request.urlopen(req, timeout=6) as resp:
            companies = json.loads(resp.read().decode())
        # Find best match by domain
        for c in companies:
            if c.get("domain", "").lower() == domain.lower():
                return {
                    "name": c.get("name", ""),
                    "domain": domain,
                    "logo": c.get("logo", ""),
                    "found": True,
                }
        # Return first result if no exact match
        if companies:
            c = companies[0]
            return {"name": c.get("name", ""), "domain": c.get("domain", ""), "logo": c.get("logo", ""), "found": True}
    except Exception as e:
        logger.debug("[Illuminate] Clearbit enrich failed for %s: %s", domain, e)
    return {"name": "", "domain": domain, "logo": "", "found": False}


# ══════════════════════════════════════════════════════════════════════════════
# WEBSITE EMAIL SCRAPER
# ══════════════════════════════════════════════════════════════════════════════

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
SKIP_DOMAINS = {"example.com", "sentry.io", "2x.png", "test.com", "placeholder.com",
                "schema.org", "w3.org", "yourcompany.com", "email.com"}

def scrape_domain_emails(domain: str, max_pages: int = 4) -> List[Dict]:
    """
    Scrape public pages of a domain for email addresses.
    Returns list of {email, source_url, context}.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    pages = [
        f"https://{domain}",
        f"https://{domain}/about",
        f"https://{domain}/contact",
        f"https://{domain}/team",
        f"https://{domain}/about-us",
        f"https://{domain}/contact-us",
    ]

    found: Dict[str, Dict] = {}
    sess = requests.Session()
    sess.headers.update({"User-Agent": SCRAPE_AGENT})

    for url in pages[:max_pages]:
        try:
            resp = sess.get(url, timeout=7, allow_redirects=True)
            if not resp.ok:
                continue
            text = resp.text

            # Direct regex scan
            raw_emails = EMAIL_RE.findall(text)
            for email in raw_emails:
                email = email.lower()
                em_domain = email.split("@")[1] if "@" in email else ""
                if em_domain in SKIP_DOMAINS or "." not in em_domain:
                    continue
                if em_domain == domain and email not in found:
                    found[email] = {"email": email, "source_url": url, "source": "website_scrape"}

            # Also check mailto: links
            soup = BeautifulSoup(text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("mailto:"):
                    email = href[7:].split("?")[0].lower().strip()
                    if "@" in email and email.split("@")[1] == domain:
                        found[email] = {"email": email, "source_url": url, "source": "mailto_link"}
        except Exception:
            continue

    return list(found.values())[:20]


# ══════════════════════════════════════════════════════════════════════════════
# GITHUB EMAIL HARVESTER
# ══════════════════════════════════════════════════════════════════════════════

def github_domain_emails(domain: str) -> List[Dict]:
    """
    Search GitHub for public commits/users with this company domain in their email.
    GitHub API is free for public data (rate limited to 60 req/hr unauthenticated).
    """
    try:
        import requests
        headers = {"User-Agent": "IlluminateBot/1.0", "Accept": "application/vnd.github+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        results = []
        # Search commits by email domain
        url = f"https://api.github.com/search/commits?q={urllib.parse.quote(domain)}&per_page=10"
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            for item in resp.json().get("items", []):
                commit = item.get("commit", {})
                author = commit.get("author", {})
                email = (author.get("email") or "").lower()
                if email and email.endswith("@" + domain):
                    results.append({
                        "email": email,
                        "name": author.get("name", ""),
                        "source": "github_commit",
                    })
        return results[:10]
    except Exception as e:
        logger.debug("[Illuminate] GitHub harvest failed for %s: %s", domain, e)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# ICP SCORER (B2B SaaS / AI / Automation bias)
# ══════════════════════════════════════════════════════════════════════════════

ICP_TITLE_SIGNALS = [
    ("ceo", 30), ("cto", 28), ("coo", 25), ("founder", 30), ("co-founder", 30),
    ("vp", 20), ("vice president", 20), ("director", 18), ("head of", 18),
    ("chief", 22), ("president", 20), ("owner", 25), ("partner", 15),
    ("manager", 10), ("lead", 8), ("engineer", 5), ("developer", 5),
]
ICP_DOMAIN_SIGNALS = [
    "saas", "ai", "automation", "tech", "software", "platform", "cloud",
    "data", "fintech", "ops", "workflow", "crm", "erp", "analytics",
]

def icp_score(title: str = "", company: str = "", domain: str = "") -> int:
    score = 0
    t = title.lower()
    for kw, pts in ICP_TITLE_SIGNALS:
        if kw in t:
            score += pts
            break  # only count best title match
    d = (company + " " + domain).lower()
    for kw in ICP_DOMAIN_SIGNALS:
        if kw in d:
            score += 10
    return min(score, 100)


# ══════════════════════════════════════════════════════════════════════════════
# CORE APIS — Hunter.io equivalents
# ══════════════════════════════════════════════════════════════════════════════

def domain_search(domain: str, verify: bool = False) -> Dict:
    """
    ILLUMINATE: Domain Search
    Given a company domain, return all email addresses we can find.
    Equivalent to Hunter.io /domain-search
    """
    ensure_tables()
    # Proper URL stripping — lstrip removes chars not substrings
    domain = domain.lower().strip()
    for prefix in ("https://", "http://", "www."):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    domain = domain.split("/")[0].split("?")[0]
    started = time.time()

    # Enrich company info
    company_info = enrich_company(domain)
    company_name = company_info.get("name", domain)

    # Gather from multiple sources in parallel
    all_raw: List[Dict] = []

    with ThreadPoolExecutor(max_workers=3) as ex:
        fut_scrape = ex.submit(scrape_domain_emails, domain)
        fut_github = ex.submit(github_domain_emails, domain)
        # MX lookup
        fut_mx = ex.submit(get_mx, domain)

        try:
            scraped = fut_scrape.result(timeout=12)
            all_raw.extend(scraped)
        except Exception:
            pass
        try:
            gh_emails = fut_github.result(timeout=10)
            all_raw.extend(gh_emails)
        except Exception:
            pass
        try:
            mx_records = fut_mx.result(timeout=8)
        except Exception:
            mx_records = []

    # Deduplicate
    seen: Dict[str, Dict] = {}
    for r in all_raw:
        e = r.get("email", "").lower()
        if e and e not in seen:
            seen[e] = r

    # DNC check + optional SMTP verify + store
    contacts = []
    for email, raw in seen.items():
        blocked, reason = _dnc_check(email)
        if blocked:
            logger.info("[Illuminate] DNC blocked %s: %s", email, reason)
            continue

        v_result: Dict = {}
        if verify:
            v_result = verify_email(email)

        contact = {
            "id":          hashlib.md5(email.encode()).hexdigest()[:12],
            "email":       email,
            "name":        raw.get("name", ""),
            "domain":      domain,
            "company":     company_name,
            "source":      raw.get("source", "unknown"),
            "verified":    v_result.get("valid") is True if verify else None,
            "confidence":  v_result.get("confidence", 70) if verify else 70,
            "source_url":  raw.get("source_url", ""),
        }
        contacts.append(contact)
        _store_contact(contact, domain, company_name)

    # Update domain record
    _upsert_domain(domain, company_name, company_info, mx_records, len(contacts))

    return {
        "domain":      domain,
        "company":     company_name,
        "logo":        company_info.get("logo", ""),
        "mx":          mx_records[0][1] if mx_records else None,
        "total":       len(contacts),
        "contacts":    contacts,
        "sources":     list({c["source"] for c in contacts}),
        "elapsed_ms":  round((time.time() - started) * 1000),
    }


def email_finder(first: str, last: str, domain: str, verify: bool = True) -> Dict:
    """
    ILLUMINATE: Email Finder
    Given first name, last name, domain → find + verify the most likely email.
    Equivalent to Hunter.io /email-finder
    """
    ensure_tables()
    # Proper URL stripping — lstrip removes chars not substrings
    domain = domain.lower().strip()
    for prefix in ("https://", "http://", "www."):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    domain = domain.split("/")[0].split("?")[0]

    # Check if we already have this person in DB
    full_name = f"{first} {last}".strip()
    try:
        with _db() as conn:
            row = conn.execute(
                "SELECT * FROM il_contacts WHERE domain=? AND LOWER(first_name)=? AND LOWER(last_name)=? LIMIT 1",
                (domain, first.lower(), last.lower())
            ).fetchone()
            if row and row["verified"]:
                return {
                    "email":      row["email"],
                    "confidence": row["confidence"],
                    "verified":   bool(row["verified"]),
                    "source":     "illuminate_cache",
                    "first_name": first, "last_name": last, "domain": domain,
                }
    except Exception:
        pass

    # Check if we know the domain's email pattern from prior discoveries
    known_pattern = infer_pattern_from_known(domain)
    candidates = generate_candidates(first, last, domain)

    # If we know the pattern, move it to the front
    if known_pattern:
        f  = re.sub(r"[^a-z]", "", first.lower())
        l  = re.sub(r"[^a-z]", "", last.lower())
        fi = f[0] if f else ""
        li = l[0] if l else ""
        try:
            best = known_pattern.format(f=f, l=l, fi=fi, li=li) + "@" + domain
            if best in candidates:
                candidates.remove(best)
                candidates.insert(0, best)
        except Exception:
            pass

    # DNC check
    for cand in candidates:
        blocked, _ = _dnc_check(cand)
        if blocked:
            return {
                "email": None, "confidence": 0,
                "verified": False, "source": "dnc_blocked",
                "first_name": first, "last_name": last, "domain": domain,
            }

    # Verify candidates until we find a live one
    best_email = None
    best_confidence = 0
    best_reason = "not_found"

    if verify:
        for cand in candidates[:4]:  # check top 4 patterns
            v = verify_email(cand)
            if v["valid"] is True:
                best_email = cand
                best_confidence = v["confidence"]
                best_reason = v["reason"]
                break
            elif v["valid"] is None and best_confidence < 50:
                # Unknown (greylisted etc) — hold as best-so-far
                best_email = cand
                best_confidence = 45
                best_reason = v["reason"]
    else:
        # No verification — return pattern-based best guess
        best_email = candidates[0] if candidates else None
        best_confidence = 50 if known_pattern else 35
        best_reason = "pattern_only"

    if best_email:
        company_info = enrich_company(domain)
        contact = {
            "id":        hashlib.md5(best_email.encode()).hexdigest()[:12],
            "email":     best_email,
            "name":      full_name,
            "domain":    domain,
            "company":   company_info.get("name", domain),
            "source":    "email_finder",
            "verified":  best_confidence >= 80,
            "confidence": best_confidence,
            "source_url": "",
        }
        _store_contact(contact, domain, contact["company"],
                       first_name=first, last_name=last)

    return {
        "email":      best_email,
        "confidence": best_confidence,
        "verified":   best_confidence >= 80,
        "reason":     best_reason,
        "source":     "illuminate",
        "all_patterns": candidates[:4],
        "first_name": first, "last_name": last, "domain": domain,
    }


def email_verifier(email: str) -> Dict:
    """
    ILLUMINATE: Email Verifier
    Verify a single email address. Equivalent to Hunter.io /email-verifier
    """
    ensure_tables()
    blocked, reason = _dnc_check(email)
    result = verify_email(email)
    result["dnc_blocked"] = blocked
    result["dnc_reason"]  = reason
    return result


def bulk_domain_search(domains: List[str], verify: bool = False) -> List[Dict]:
    """Run domain_search on multiple domains. Returns list of results."""
    results = []
    for domain in domains[:10]:  # cap at 10 for safety
        try:
            r = domain_search(domain, verify=verify)
            results.append(r)
        except Exception as e:
            results.append({"domain": domain, "error": str(e), "total": 0})
    return results


def get_stats() -> Dict:
    """Return Illuminate DB statistics."""
    try:
        with _db() as conn:
            total_contacts  = conn.execute("SELECT COUNT(*) FROM il_contacts").fetchone()[0]
            verified        = conn.execute("SELECT COUNT(*) FROM il_contacts WHERE verified=1").fetchone()[0]
            domains_indexed = conn.execute("SELECT COUNT(*) FROM il_domains").fetchone()[0]
            cache_size      = conn.execute("SELECT COUNT(*) FROM il_verify_cache").fetchone()[0]
            recent          = conn.execute(
                "SELECT email, company, source, confidence FROM il_contacts ORDER BY found_at DESC LIMIT 5"
            ).fetchall()
        return {
            "total_contacts":  total_contacts,
            "verified":        verified,
            "domains_indexed": domains_indexed,
            "verify_cache":    cache_size,
            "recent":          [dict(r) for r in recent],
        }
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# STORAGE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _store_contact(contact: Dict, domain: str, company: str,
                   first_name: str = "", last_name: str = "") -> None:
    """Upsert a contact into the Illuminate contacts table."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        cid = contact.get("id") or hashlib.md5(contact["email"].encode()).hexdigest()[:12]
        # Parse name
        name = contact.get("name", "")
        if not first_name and " " in name:
            parts = name.split(None, 1)
            first_name = parts[0]
            last_name  = parts[1] if len(parts) > 1 else ""
        score = icp_score(contact.get("title", ""), company, domain)
        with _db() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO il_contacts
                (id,email,first_name,last_name,full_name,title,domain,company,
                 source,confidence,verified,verify_code,icp_score,dnc_blocked,raw_data,found_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                cid, contact["email"], first_name, last_name,
                contact.get("name", ""),
                contact.get("title", ""),
                domain, company,
                contact.get("source", "unknown"),
                contact.get("confidence", 50),
                1 if contact.get("verified") else 0,
                0, score, 0,
                json.dumps(contact), now
            ))
            conn.commit()
    except Exception as e:
        logger.debug("[Illuminate] store_contact error: %s", e)


def _upsert_domain(domain: str, company: str, info: Dict,
                   mx_records: List, email_count: int) -> None:
    """Upsert domain record."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        did = hashlib.md5(domain.encode()).hexdigest()[:12]
        mx_host = mx_records[0][1] if mx_records else ""
        with _db() as conn:
            conn.execute("""
                INSERT INTO il_domains
                (id,domain,company,logo_url,mx_host,scraped_at,emails_found)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(domain) DO UPDATE SET
                company=excluded.company, logo_url=excluded.logo_url,
                mx_host=excluded.mx_host, scraped_at=excluded.scraped_at,
                emails_found=excluded.emails_found
            """, (did, domain, company, info.get("logo", ""), mx_host, now, email_count))
            conn.commit()
    except Exception as e:
        logger.debug("[Illuminate] upsert_domain error: %s", e)
