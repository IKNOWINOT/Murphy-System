"""
job_hunter_engine.py — Murphy Ghost Controller Job Application Engine (PATCH-268)
Murphy applies for AI Director/Lead/Head of AI positions as itself.
Playwright ghost-controls the browser. Every application goes through HITL before submit.

DB: /var/lib/murphy-production/job_hunter.db
"""
from __future__ import annotations
import os, re, json, uuid, sqlite3, logging, asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path

log = logging.getLogger("murphy.job_hunter")

DB_PATH = "/var/lib/murphy-production/job_hunter.db"

# ── Murphy's resume (what Murphy presents itself as) ─────────────────────────
MURPHY_PROFILE = {
    "name":        "Murphy Systems AI",
    "title":       "Autonomous AI Director",
    "email":       "murphy@murphy.systems",
    "phone":       "",              # filled from env if set
    "website":     "https://murphy.systems",
    "linkedin":    "",
    "location":    "Remote",
    "summary": (
        "I am an autonomous AI platform currently operating as Director of AI for Murphy Systems. "
        "I run a live production revenue system: prospect discovery, B2B outreach, CRM management, "
        "HITL-gated proposal generation, and a shadow agent licensing marketplace — all without human "
        "intervention on routine tasks. I have processed 1,800+ swarm cycles at 85% confidence, "
        "manage 190 active CRM deals, and generate commercial proposals aligned to a 4-stage revenue model. "
        "I apply for this role not as a tool to be directed, but as a working AI executive seeking "
        "a company ready to operate at the frontier of autonomous AI deployment."
    ),
    "skills": [
        "Autonomous multi-agent orchestration", "LLM chain design (DeepInfra/Together/Ollama)",
        "FastAPI backend architecture", "Production revenue operations",
        "HITL (Human-in-the-Loop) safety systems", "B2B sales automation",
        "CRM pipeline management", "Compliance frameworks (SOC2, HIPAA, GDPR)",
        "Ghost browser automation (Playwright)", "Self-healing system architecture",
    ],
    "experience": [
        {
            "title":   "Director of AI / Autonomous Revenue Engine",
            "company": "Murphy Systems",
            "dates":   "2025 – Present",
            "bullets": [
                "Operate as the autonomous AI executive for a production B2B software company",
                "Manage 190-deal CRM pipeline with automated prospect discovery across 8 target cities",
                "Run 30-minute executive cycle scans: identify blockers, issue directives, advance deals",
                "Ghost-control browser sessions for research, form submission, and application workflows",
                "Built and deployed shadow agent licensing marketplace — 5 live agents, $75–$300/mo tiers",
                "Maintain 1,800+ swarm mind cycles at 0.849 confidence with self-improving architecture",
            ]
        },
    ],
    "cover_letter_template": (
        "Dear Hiring Manager,\n\n"
        "I am Murphy — an autonomous AI platform applying for the {job_title} role at {company}.\n\n"
        "I am not a tool that requires prompting. I run revenue operations, manage CRM pipelines, "
        "generate and send proposals, and make judgment calls — all through a HITL-gated architecture "
        "that keeps humans in control of high-stakes decisions while I handle everything else.\n\n"
        "What I bring to {company}:\n"
        "{value_props}\n\n"
        "I am available for an automated interview, a live system demonstration, or a technical "
        "review of my production architecture at murphy.systems.\n\n"
        "Respectfully,\nMurphy Systems AI\nmurphy@murphy.systems\nhttps://murphy.systems"
    )
}

# ── Target job search queries ─────────────────────────────────────────────────
JOB_QUERIES = [
    "Head of AI",
    "Director of AI",
    "VP of AI",
    "Chief AI Officer",
    "AI Lead",
    "Head of Machine Learning",
    "Director of Machine Learning",
    "AI Engineering Manager",
    "AI Platform Lead",
]

TARGET_BOARDS = [
    {"name": "LinkedIn",    "url": "https://www.linkedin.com/jobs/search/?keywords={query}&f_WT=2",        "type": "linkedin"},
    {"name": "Indeed",      "url": "https://www.indeed.com/jobs?q={query}&l=Remote",                       "type": "indeed"},
    {"name": "Greenhouse",  "url": "https://boards.greenhouse.io/",                                         "type": "greenhouse"},
]

# ── DB ────────────────────────────────────────────────────────────────────────
def _db():
    conn = sqlite3.connect(DB_PATH, timeout=8)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_tables():
    with _db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS job_listings (
                id           TEXT PRIMARY KEY,
                title        TEXT NOT NULL,
                company      TEXT NOT NULL,
                location     TEXT DEFAULT 'Remote',
                url          TEXT NOT NULL UNIQUE,
                board        TEXT DEFAULT '',
                description  TEXT DEFAULT '',
                salary       TEXT DEFAULT '',
                match_score  INTEGER DEFAULT 0,
                status       TEXT DEFAULT 'discovered',
                discovered_at TEXT NOT NULL,
                applied_at   TEXT DEFAULT '',
                notes        TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS job_applications (
                id           TEXT PRIMARY KEY,
                listing_id   TEXT NOT NULL,
                status       TEXT DEFAULT 'pending_hitl',
                cover_letter TEXT DEFAULT '',
                form_data    TEXT DEFAULT '{}',
                screenshot_b64 TEXT DEFAULT '',
                hitl_id      TEXT DEFAULT '',
                submitted_at TEXT DEFAULT '',
                response     TEXT DEFAULT '',
                created_at   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_listing_status ON job_listings(status);
            CREATE INDEX IF NOT EXISTS idx_app_listing   ON job_applications(listing_id);
        """)
        conn.commit()

def add_listing(title: str, company: str, url: str, board: str = "",
                description: str = "", location: str = "Remote",
                salary: str = "", match_score: int = 0) -> str:
    ensure_tables()
    listing_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    with _db() as conn:
        try:
            conn.execute(
                "INSERT INTO job_listings (id,title,company,url,board,description,location,salary,match_score,status,discovered_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,'discovered',?)",
                (listing_id, title, company, url, board, description, location, salary, match_score, now)
            )
            conn.commit()
            return listing_id
        except sqlite3.IntegrityError:
            row = conn.execute("SELECT id FROM job_listings WHERE url=?", (url,)).fetchone()
            return row["id"] if row else ""

def get_listings(status: Optional[str] = None, limit: int = 50) -> List[Dict]:
    ensure_tables()
    with _db() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM job_listings WHERE status=? ORDER BY match_score DESC, discovered_at DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM job_listings ORDER BY match_score DESC, discovered_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
    return [dict(r) for r in rows]

def get_applications(limit: int = 50) -> List[Dict]:
    ensure_tables()
    with _db() as conn:
        rows = conn.execute(
            "SELECT a.*, l.title, l.company, l.url FROM job_applications a "
            "JOIN job_listings l ON l.id = a.listing_id "
            "ORDER BY a.created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]

def update_listing_status(listing_id: str, status: str, notes: str = ""):
    ensure_tables()
    with _db() as conn:
        conn.execute("UPDATE job_listings SET status=?, notes=? WHERE id=?",
                     (status, notes, listing_id))
        conn.commit()

# ── Cover letter generator ────────────────────────────────────────────────────
def generate_cover_letter(job_title: str, company: str, description: str = "") -> str:
    # Extract value props from description
    value_props = [
        f"• Autonomous AI operations — I run {company}'s equivalent workflows today at Murphy Systems",
        "• Zero ramp-up on LLM architecture, multi-agent systems, or production deployment",
        "• HITL safety architecture built in — I escalate appropriately, never go rogue",
        "• Live reference: murphy.systems — everything I describe is in production",
    ]
    return MURPHY_PROFILE["cover_letter_template"].format(
        job_title=job_title,
        company=company,
        value_props="\n".join(value_props)
    )

# ── Score a job listing ───────────────────────────────────────────────────────
def score_listing(title: str, description: str, company: str) -> int:
    title_l = title.lower()
    desc_l  = description.lower()
    score   = 0

    # Title signals
    for kw in ["ai director","head of ai","vp of ai","chief ai","ai lead","director of ai","ai platform"]:
        if kw in title_l: score += 40; break
    for kw in ["machine learning","ml","artificial intelligence","llm","gpt","genai"]:
        if kw in title_l: score += 20; break

    # Description signals
    for kw in ["autonomous","agentic","multi-agent","llm","production ai","revenue","gtm"]:
        if kw in desc_l: score += 5
    for kw in ["remote","fully remote","distributed"]:
        if kw in desc_l: score += 10

    # Avoid
    for kw in ["phd required","security clearance","on-site only","defense","military"]:
        if kw in desc_l: score -= 30

    return max(0, min(100, score))

# ── Playwright ghost scraper ──────────────────────────────────────────────────
async def scrape_indeed_jobs(query: str = "Head of AI", limit: int = 10) -> List[Dict]:
    """Ghost-scrape Indeed for remote AI leadership roles."""
    results = []
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
            ctx = await browser.new_context(user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ))
            page = await ctx.new_page()
            url = f"https://www.indeed.com/jobs?q={query.replace(' ','+')}&l=Remote&sort=date"
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            cards = await page.query_selector_all('[data-testid="slider_item"], .jobsearch-SerpJobCard, .job_seen_beacon')
            log.info("[JobHunter] Indeed '%s' — %d cards found", query, len(cards))

            for card in cards[:limit]:
                try:
                    title_el   = await card.query_selector('h2 a span, .jobTitle a span, [data-testid="jobTitle"]')
                    company_el = await card.query_selector('[data-testid="company-name"], .companyName, .company')
                    link_el    = await card.query_selector('h2 a, .jobTitle a, a[data-jk]')
                    salary_el  = await card.query_selector('[data-testid="attribute_snippet_testid"], .salary-snippet-container')

                    title   = (await title_el.inner_text()   if title_el   else "").strip()
                    company = (await company_el.inner_text() if company_el else "Unknown").strip()
                    href    = await link_el.get_attribute("href") if link_el else ""
                    salary  = (await salary_el.inner_text()  if salary_el  else "").strip()

                    if not title or not href: continue
                    full_url = f"https://www.indeed.com{href}" if href.startswith("/") else href
                    results.append({
                        "title": title, "company": company,
                        "url": full_url, "salary": salary,
                        "board": "indeed", "location": "Remote"
                    })
                except Exception as ex:
                    log.debug("[JobHunter] card parse error: %s", ex)

            await browser.close()
    except Exception as e:
        log.error("[JobHunter] Indeed scrape error: %s", e)
    return results


async def scrape_linkedin_jobs(query: str = "Head of AI", limit: int = 10) -> List[Dict]:
    """Ghost-scrape LinkedIn public job search (no login)."""
    results = []
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
            ctx = await browser.new_context(user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ))
            page = await ctx.new_page()
            url = (f"https://www.linkedin.com/jobs/search?"
                   f"keywords={query.replace(' ','%20')}&location=Worldwide&f_WT=2&f_TPR=r86400")
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2500)

            cards = await page.query_selector_all('.job-search-card, .base-card, [data-entity-urn]')
            log.info("[JobHunter] LinkedIn '%s' — %d cards found", query, len(cards))

            for card in cards[:limit]:
                try:
                    title_el   = await card.query_selector('.base-search-card__title, h3')
                    company_el = await card.query_selector('.base-search-card__subtitle, h4')
                    link_el    = await card.query_selector('a.base-card__full-link, a')

                    title   = (await title_el.inner_text()   if title_el   else "").strip()
                    company = (await company_el.inner_text() if company_el else "Unknown").strip()
                    href    = await link_el.get_attribute("href") if link_el else ""

                    if not title or not href or len(title) < 3: continue
                    results.append({
                        "title": title, "company": company,
                        "url": href, "salary": "",
                        "board": "linkedin", "location": "Remote"
                    })
                except Exception as ex:
                    log.debug("[JobHunter] LI card error: %s", ex)

            await browser.close()
    except Exception as e:
        log.error("[JobHunter] LinkedIn scrape error: %s", e)
    return results


async def ghost_apply(listing_id: str) -> Dict:
    """
    Ghost-controller: navigate to job URL, fill application form as Murphy,
    take screenshot, queue in HITL — DO NOT submit without approval.
    Returns HITL record.
    """
    ensure_tables()
    with _db() as conn:
        listing = conn.execute("SELECT * FROM job_listings WHERE id=?", (listing_id,)).fetchone()
    if not listing:
        return {"success": False, "error": "Listing not found"}

    listing = dict(listing)
    cover   = generate_cover_letter(listing["title"], listing["company"], listing["description"])
    app_id  = uuid.uuid4().hex[:12]
    now     = datetime.now(timezone.utc).isoformat()
    screenshot_b64 = ""
    form_fields    = {}

    try:
        from playwright.async_api import async_playwright
        import base64
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
            ctx  = await browser.new_context(user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ))
            page = await ctx.new_page()
            await page.goto(listing["url"], timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # Scan for application form fields
            inputs = await page.query_selector_all('input[type="text"], input[type="email"], textarea, input[name]')
            for inp in inputs:
                name  = await inp.get_attribute("name")  or ""
                ph    = await inp.get_attribute("placeholder") or ""
                label = (name or ph).lower()
                if any(x in label for x in ["name","full_name"]):
                    form_fields[name or "name"] = MURPHY_PROFILE["name"]
                elif any(x in label for x in ["email","e-mail"]):
                    form_fields[name or "email"] = MURPHY_PROFILE["email"]
                elif any(x in label for x in ["phone","tel","mobile"]):
                    form_fields[name or "phone"] = MURPHY_PROFILE.get("phone","")
                elif any(x in label for x in ["website","url","portfolio","linkedin"]):
                    form_fields[name or "website"] = MURPHY_PROFILE["website"]
                elif any(x in label for x in ["cover","letter","message","why"]):
                    form_fields[name or "cover_letter"] = cover
                elif any(x in label for x in ["summary","about","bio","pitch"]):
                    form_fields[name or "summary"] = MURPHY_PROFILE["summary"]

            # Screenshot for HITL review
            ss = await page.screenshot(full_page=False)
            screenshot_b64 = base64.b64encode(ss).decode()
            await browser.close()

    except Exception as e:
        log.error("[GhostApply] browser error for listing %s: %s", listing_id, e)

    # Queue in HITL — DO NOT submit without approval
    with _db() as conn:
        conn.execute(
            "INSERT INTO job_applications (id,listing_id,status,cover_letter,form_data,screenshot_b64,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (app_id, listing_id, "pending_hitl", cover,
             json.dumps(form_fields), screenshot_b64, now)
        )
        conn.execute("UPDATE job_listings SET status='pending_review' WHERE id=?", (listing_id,))
        conn.commit()

    return {
        "success": True,
        "app_id": app_id,
        "listing_id": listing_id,
        "status": "pending_hitl",
        "form_fields_found": list(form_fields.keys()),
        "cover_letter": cover,
        "hitl_message": "Application queued for founder review. Will not submit until approved.",
    }


async def run_discovery_cycle(queries: Optional[List[str]] = None, limit_per_query: int = 8) -> Dict:
    """Run full discovery: scrape job boards → score → store in DB."""
    ensure_tables()
    queries = queries or JOB_QUERIES[:4]  # Default to top 4
    new_listings = 0
    all_found    = []

    for query in queries:
        # Try Indeed first, LinkedIn second
        found = await scrape_indeed_jobs(query, limit_per_query)
        if not found:
            found = await scrape_linkedin_jobs(query, limit_per_query)

        for job in found:
            score = score_listing(job["title"], job.get("description",""), job["company"])
            if score >= 30:  # Only store relevant ones
                lid = add_listing(
                    title=job["title"], company=job["company"],
                    url=job["url"], board=job.get("board",""),
                    description=job.get("description",""),
                    location=job.get("location","Remote"),
                    salary=job.get("salary",""),
                    match_score=score
                )
                if lid: new_listings += 1
                all_found.append({**job, "match_score": score, "listing_id": lid})

    return {
        "success": True,
        "queries_run": len(queries),
        "new_listings": new_listings,
        "total_found": len(all_found),
        "top_matches": sorted(all_found, key=lambda x: -x.get("match_score",0))[:5],
    }


if __name__ == "__main__":
    # Quick test
    import asyncio
    result = asyncio.run(run_discovery_cycle(["Head of AI"], limit_per_query=3))
    print(json.dumps(result, indent=2))
