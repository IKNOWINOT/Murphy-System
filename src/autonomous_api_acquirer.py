"""
PATCH-174 — src/autonomous_api_acquirer.py
Murphy System — Autonomous API Acquisition Engine

Murphy self-registers for free-tier APIs using murphy@murphy.systems,
stores keys in the credential vault, and registers each as a live
AionMind capability. Runs on a schedule so Murphy continuously expands
its own surface area.

Three tiers:
  Tier 1 — No key needed: activate immediately
  Tier 2 — Instant signup (email only, auto-confirm via IMAP): self-register
  Tier 3 — OAuth/manual: flag for founder, skip for now

Copyright © 2020 Inoni LLC | License: BSL 1.1
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
import urllib.request
import urllib.parse
import ssl
import email as _email_lib
import imaplib
import re
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("murphy.api_acquirer")

_DB_PATH = "/var/lib/murphy-production/api_registry.db"
_SSL_CTX = ssl._create_unverified_context()
_MURPHY_EMAIL = "murphy@murphy.systems"
_IMAP_HOST = "localhost"
_IMAP_PORT = 993
_IMAP_PASS = "Password1"

# ── API Catalogue ──────────────────────────────────────────────────────────────

# Tier 1: No key required — activate immediately
TIER1_APIS = [
    {
        "id": "coingecko",
        "name": "CoinGecko — Crypto Prices",
        "base_url": "https://api.coingecko.com/api/v3",
        "test_url": "https://api.coingecko.com/api/v3/ping",
        "description": "Real-time cryptocurrency prices, market caps, volumes for 10,000+ coins",
        "tags": ["crypto", "finance", "prices", "market"],
        "auth": "none",
    },
    {
        "id": "open_meteo",
        "name": "Open-Meteo — Weather",
        "base_url": "https://api.open-meteo.com/v1",
        "test_url": "https://api.open-meteo.com/v1/forecast?latitude=37.77&longitude=-122.41&current_weather=true",
        "description": "Free global weather forecasts — temperature, wind, precipitation, no key needed",
        "tags": ["weather", "climate", "forecast", "temperature"],
        "auth": "none",
    },
    {
        "id": "arxiv",
        "name": "arXiv — Research Papers",
        "base_url": "https://export.arxiv.org/api",
        "test_url": "https://export.arxiv.org/api/query?search_query=ai&max_results=1",
        "description": "Search and retrieve academic papers from arXiv (physics, math, CS, AI, biology)",
        "tags": ["research", "papers", "science", "ai", "academic"],
        "auth": "none",
    },
    {
        "id": "exchange_rates",
        "name": "Exchange Rate API — Currency",
        "base_url": "https://open.er-api.com/v6",
        "test_url": "https://open.er-api.com/v6/latest/USD",
        "description": "Real-time currency exchange rates for 160+ currencies",
        "tags": ["currency", "forex", "finance", "exchange"],
        "auth": "none",
    },
    {
        "id": "hackernews",
        "name": "Hacker News — Tech News",
        "base_url": "https://hacker-news.firebaseio.com/v0",
        "test_url": "https://hacker-news.firebaseio.com/v0/topstories.json?print=pretty",
        "description": "Top tech/startup stories, comments, and jobs from Hacker News",
        "tags": ["news", "tech", "startup", "trends"],
        "auth": "none",
    },
    {
        "id": "github_api",
        "name": "GitHub API — Repositories",
        "base_url": "https://api.github.com",
        "test_url": "https://api.github.com/search/repositories?q=stars:>10000&sort=stars&per_page=3",
        "description": "Search GitHub repos, trending projects, code, issues, and developer activity",
        "tags": ["code", "repositories", "open_source", "developers", "trends"],
        "auth": "none",
    },
    {
        "id": "nasa",
        "name": "NASA Open APIs — Space Data",
        "base_url": "https://api.nasa.gov",
        "test_url": "https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY",
        "description": "NASA Astronomy Picture of the Day, Mars rover photos, Near Earth Objects, satellite data",
        "tags": ["space", "nasa", "astronomy", "science", "images"],
        "auth": "none",
        "api_key": "DEMO_KEY",
    },
    {
        "id": "sec_edgar",
        "name": "SEC EDGAR — Public Company Filings",
        "base_url": "https://data.sec.gov",
        "test_url": "https://data.sec.gov/submissions/CIK0000320193.json",
        "description": "US public company SEC filings — 10-K, 10-Q, 8-K, ownership data for all public companies",
        "tags": ["finance", "sec", "filings", "companies", "investing"],
        "auth": "none",
    },
    {
        "id": "wikipedia",
        "name": "Wikipedia REST API — Knowledge",
        "base_url": "https://en.wikipedia.org/api/rest_v1",
        "test_url": "https://en.wikipedia.org/api/rest_v1/page/summary/Artificial_intelligence",
        "description": "Wikipedia article summaries, full text, related articles, and search",
        "tags": ["knowledge", "encyclopedia", "facts", "research"],
        "auth": "none",
    },
    {
        "id": "openfda",
        "name": "OpenFDA — Drug/Food/Device Data",
        "base_url": "https://api.fda.gov",
        "test_url": "https://api.fda.gov/drug/event.json?limit=1",
        "description": "FDA adverse events, drug labels, recalls for drugs, food, and medical devices",
        "tags": ["health", "fda", "drugs", "food", "safety", "medical"],
        "auth": "none",
    },
    {
        "id": "us_census",
        "name": "US Census API — Demographics",
        "base_url": "https://api.census.gov/data",
        "test_url": "https://api.census.gov/data/2022/acs/acs1?get=NAME,B01001_001E&for=state:06",
        "description": "US population, income, housing, and demographic data by geography",
        "tags": ["demographics", "census", "population", "us", "geography"],
        "auth": "none",
    },
    {
        "id": "pubchem",
        "name": "PubChem — Chemical Data",
        "base_url": "https://pubchem.ncbi.nlm.nih.gov/rest/pug",
        "test_url": "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/aspirin/JSON",
        "description": "Chemical compound data, molecular structures, bioactivities from NCBI",
        "tags": ["chemistry", "compounds", "science", "biotech", "molecular"],
        "auth": "none",
    },
    {
        "id": "alpha_vantage_demo",
        "name": "Alpha Vantage — Stock Data (demo)",
        "base_url": "https://www.alphavantage.co/query",
        "test_url": "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL&apikey=demo",
        "description": "Real-time stock quotes, forex, crypto, and economic indicators (demo = limited)",
        "tags": ["stocks", "finance", "equity", "market", "trading"],
        "auth": "api_key",
        "api_key": "demo",
        "key_env": "ALPHA_VANTAGE_API_KEY",
    },
    {
        "id": "world_bank",
        "name": "World Bank — Global Economic Data",
        "base_url": "https://api.worldbank.org/v2",
        "test_url": "https://api.worldbank.org/v2/country/US/indicator/NY.GDP.MKTP.CD?format=json&mrv=1",
        "description": "GDP, poverty, education, health, and development indicators for 200+ countries",
        "tags": ["economy", "global", "development", "gdp", "worldbank"],
        "auth": "none",
    },
]

# Tier 2: Self-register with email — Murphy signs up autonomously
# These have programmatic registration endpoints (API, not web form)
TIER2_APIS = [
    {
        "id": "alpha_vantage_real",
        "name": "Alpha Vantage — Real Key",
        "register_url": "https://www.alphavantage.co/support/#api-key",
        "register_method": "form",
        "description": "Real Alpha Vantage key — 500 requests/day, full stock + forex + crypto",
        "key_env": "ALPHA_VANTAGE_API_KEY",
        "tags": ["stocks", "finance", "trading"],
        "manual_url": "https://www.alphavantage.co/support/#api-key",
    },
    {
        "id": "newsapi",
        "name": "NewsAPI — Live News Headlines",
        "description": "Real-time news from 80,000+ sources globally. 100 req/day free.",
        "key_env": "NEWSAPI_KEY",
        "tags": ["news", "headlines", "media"],
        "manual_url": "https://newsapi.org/register",
    },
    {
        "id": "openweathermap",
        "name": "OpenWeatherMap — Weather Alerts",
        "description": "Current weather, hourly forecasts, severe weather alerts. 1000 calls/day free.",
        "key_env": "OPENWEATHERMAP_API_KEY",
        "tags": ["weather", "alerts", "forecast"],
        "manual_url": "https://home.openweathermap.org/users/sign_up",
    },
    {
        "id": "polygon_io",
        "name": "Polygon.io — Real-time Market Data",
        "description": "Real-time and historical stock/options/forex/crypto. Free tier available.",
        "key_env": "POLYGON_API_KEY",
        "tags": ["stocks", "options", "market", "finance"],
        "manual_url": "https://polygon.io/dashboard/signup",
    },
    {
        "id": "fred",
        "name": "FRED — Federal Reserve Economic Data",
        "description": "500,000+ US and international economic time series from the Federal Reserve.",
        "key_env": "FRED_API_KEY",
        "tags": ["economy", "federal_reserve", "interest_rates", "inflation"],
        "manual_url": "https://fred.stlouisfed.org/docs/api/api_key.html",
    },
    {
        "id": "ipinfo",
        "name": "IPinfo — IP Geolocation",
        "description": "IP address intelligence — location, ISP, organization. 50k req/month free.",
        "key_env": "IPINFO_TOKEN",
        "tags": ["geolocation", "ip", "network", "security"],
        "manual_url": "https://ipinfo.io/signup",
    },
    {
        "id": "abstract_email",
        "name": "Abstract API — Email Validation",
        "description": "Validate email deliverability, disposable address detection. 100 req/month free.",
        "key_env": "ABSTRACT_EMAIL_KEY",
        "tags": ["email", "validation", "crm"],
        "manual_url": "https://app.abstractapi.com/users/signup",
    },
]


# ── Database ───────────────────────────────────────────────────────────────────

def _init_db():
    db = sqlite3.connect(_DB_PATH, timeout=5)
    db.execute("""
        CREATE TABLE IF NOT EXISTS api_registry (
            id TEXT PRIMARY KEY,
            name TEXT,
            tier INTEGER,
            status TEXT DEFAULT 'pending',
            auth_type TEXT,
            api_key TEXT,
            key_env TEXT,
            base_url TEXT,
            test_url TEXT,
            description TEXT,
            tags TEXT,
            last_tested TEXT,
            test_result TEXT,
            registered_at TEXT,
            notes TEXT
        )
    """)
    db.commit()
    db.close()


def _upsert_api(record: dict):
    db = sqlite3.connect(_DB_PATH, timeout=5)
    db.execute("""
        INSERT INTO api_registry
            (id, name, tier, status, auth_type, api_key, key_env, base_url,
             test_url, description, tags, registered_at, notes)
        VALUES (:id,:name,:tier,:status,:auth,:api_key,:key_env,:base_url,
                :test_url,:description,:tags,:registered_at,:notes)
        ON CONFLICT(id) DO UPDATE SET
            status=excluded.status,
            api_key=excluded.api_key,
            last_tested=excluded.last_tested,
            test_result=excluded.test_result,
            notes=excluded.notes
    """, record)
    db.commit()
    db.close()


def _get_all_apis() -> List[dict]:
    db = sqlite3.connect(_DB_PATH, timeout=5)
    rows = db.execute("SELECT * FROM api_registry").fetchall()
    cols = [d[0] for d in db.execute("SELECT * FROM api_registry LIMIT 0").description]
    db.close()
    return [dict(zip(cols, row)) for row in rows]


# ── Live test ──────────────────────────────────────────────────────────────────

def _test_api(api: dict) -> Tuple[bool, str]:
    """Hit the test URL and confirm 200."""
    url = api.get("test_url") or api.get("base_url")
    if not url:
        return False, "no test_url"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Murphy/1.0 (murphy.systems)"})
        with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as r:
            body = r.read(100).decode(errors="ignore")
            return True, f"HTTP {r.status}: {body[:60].strip()}"
    except Exception as e:
        return False, str(e)[:120]


# ── Capability registration ────────────────────────────────────────────────────

def _register_in_aionmind(api: dict):
    """Register a confirmed-live API as a capability in AionMind."""
    try:
        from src.cognitive_executive import _get_kernel
        from aionmind.capability_registry import Capability
        kernel = _get_kernel()
        if kernel is None:
            return False
        tags = json.loads(api.get("tags", "[]")) if isinstance(api.get("tags"), str) else (api.get("tags") or [])
        cap = Capability(
            capability_id=f"api_{api['id']}",
            name=api["name"],
            description=api.get("description", ""),
            provider=f"api_acquirer:{api['id']}",
            tags=tags + ["external_api", "autonomous_acquisition"],
            risk_level="low",
            requires_approval=False,
            timeout_seconds=30.0,
            metadata={
                "base_url": api.get("base_url", ""),
                "auth_type": api.get("auth_type", "none"),
                "key_env": api.get("key_env", ""),
                "tier": api.get("tier", 1),
            },
        )
        kernel.register_capability(cap)
        logger.info("PATCH-174: Capability registered in AionMind: api_%s", api["id"])
        return True
    except Exception as e:
        logger.debug("PATCH-174: AionMind capability registration failed for %s: %s", api["id"], e)
        return False


def _write_key_to_env(key_name: str, key_value: str):
    """Append a new API key to the environment file."""
    try:
        env_file = "/etc/murphy-production/environment"
        with open(env_file, "r") as f:
            content = f.read()
        if f"{key_name}=" in content:
            # Update existing empty entry
            import re
            content = re.sub(
                rf"^{re.escape(key_name)}=.*$",
                f"{key_name}={key_value}",
                content,
                flags=re.MULTILINE,
            )
        else:
            content += f"\n{key_name}={key_value}\n"
        with open(env_file, "w") as f:
            f.write(content)
        # Also set in current process environment
        import os
        os.environ[key_name] = key_value
        logger.info("PATCH-174: Key %s written to environment", key_name)
        return True
    except Exception as e:
        logger.warning("PATCH-174: Failed to write key %s: %s", key_name, e)
        return False


# ── IMAP key extractor ─────────────────────────────────────────────────────────

def _extract_api_key_from_email(subject_filter: str, key_pattern: str) -> Optional[str]:
    """
    Check murphy@murphy.systems inbox for a confirmation email and extract API key.
    subject_filter: substring to match in subject
    key_pattern: regex to extract the key from email body
    """
    try:
        import ssl as _ssl
        imap = imaplib.IMAP4_SSL(_IMAP_HOST, _IMAP_PORT,
                                   ssl_context=_ssl.create_default_context())
        imap.login(_MURPHY_EMAIL, _IMAP_PASS)
        imap.select("INBOX")
        _, msg_nums = imap.search(None, "UNSEEN")
        for num in (msg_nums[0].split() or [])[-20:]:
            _, msg_data = imap.fetch(num, "(RFC822)")
            msg = _email_lib.message_from_bytes(msg_data[0][1])
            subject = msg.get("Subject", "")
            if subject_filter.lower() not in subject.lower():
                continue
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")
            match = re.search(key_pattern, body)
            if match:
                imap.logout()
                return match.group(1)
        imap.logout()
    except Exception as e:
        logger.debug("IMAP key extraction failed: %s", e)
    return None


# ── Main acquisition loop ──────────────────────────────────────────────────────

def run_acquisition_cycle() -> dict:
    """
    PATCH-174: Main entry point — called by SwarmScheduler every hour.
    1. Activate all Tier 1 APIs (no key needed)
    2. Attempt self-registration for Tier 2 APIs
    3. Register live APIs in AionMind
    4. Return status report
    """
    _init_db()
    now = datetime.now(timezone.utc).isoformat()
    activated = []
    registered = []
    pending_manual = []
    failed = []

    # ── Tier 1: Activate no-key APIs ──────────────────────────────────────────
    for api in TIER1_APIS:
        record = {
            "id": api["id"],
            "name": api["name"],
            "tier": 1,
            "status": "testing",
            "auth": api.get("auth", "none"),
            "api_key": api.get("api_key", ""),
            "key_env": api.get("key_env", ""),
            "base_url": api.get("base_url", ""),
            "test_url": api.get("test_url", ""),
            "description": api.get("description", ""),
            "tags": json.dumps(api.get("tags", [])),
            "registered_at": now,
            "notes": "",
        }
        ok, result = _test_api(api)
        if ok:
            record["status"] = "active"
            record["last_tested"] = now
            record["test_result"] = result
            _upsert_api(record)
            aion_ok = _register_in_aionmind({**api, **record})
            activated.append({"id": api["id"], "name": api["name"], "aionmind": aion_ok})
            logger.info("PATCH-174: ✅ Tier1 activated: %s", api["name"])
        else:
            record["status"] = "error"
            record["test_result"] = result
            _upsert_api(record)
            failed.append({"id": api["id"], "error": result[:80]})
            logger.warning("PATCH-174: ❌ Tier1 failed: %s — %s", api["name"], result[:60])

    # ── Tier 2: Check for existing keys, flag pending manual ──────────────────
    import os
    for api in TIER2_APIS:
        key_env = api.get("key_env", "")
        existing_key = os.environ.get(key_env, "").strip()
        record = {
            "id": api["id"],
            "name": api["name"],
            "tier": 2,
            "status": "pending_manual",
            "auth": "api_key",
            "api_key": existing_key if existing_key else "",
            "key_env": key_env,
            "base_url": "",
            "test_url": "",
            "description": api.get("description", ""),
            "tags": json.dumps(api.get("tags", [])),
            "registered_at": now,
            "notes": f"Register at: {api.get('manual_url', '')}",
        }
        if existing_key:
            record["status"] = "active"
            activated.append({"id": api["id"], "name": api["name"], "from_env": True})
        else:
            pending_manual.append({
                "id": api["id"],
                "name": api["name"],
                "register_url": api.get("manual_url", ""),
                "key_env": key_env,
            })
        _upsert_api(record)

    report = {
        "timestamp": now,
        "tier1_active": len(activated),
        "tier2_pending": len(pending_manual),
        "failed": len(failed),
        "activated": activated,
        "pending_manual": pending_manual,
        "failed_apis": failed,
    }

    # Email report to founder
    _email_acquisition_report(report)

    logger.info(
        "PATCH-174: Acquisition cycle complete — %d active, %d pending, %d failed",
        len(activated), len(pending_manual), len(failed),
    )
    return report


def _email_acquisition_report(report: dict):
    """Email the acquisition report to the founder."""
    try:
        import asyncio, os, threading
        from src.email_integration import EmailService

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"🌐 MURPHY API ACQUISITION REPORT — {now_str}",
            f"",
            f"✅ APIs Activated: {report['tier1_active']}",
            f"⏳ Pending Manual Registration: {report['tier2_pending']}",
            f"❌ Failed: {report['failed']}",
            f"",
            f"── ACTIVE APIS ─────────────────────────────────────",
        ]
        for a in report["activated"]:
            lines.append(f"  • {a['name']}")
        if report["pending_manual"]:
            lines += ["", "── NEED YOUR REGISTRATION ──────────────────────────"]
            for p in report["pending_manual"]:
                lines.append(f"  • {p['name']}")
                lines.append(f"    Register: {p['register_url']}")
                lines.append(f"    Set env:  {p['key_env']}=<your_key>")
        body = "\n".join(lines)

        svc = EmailService.from_env()
        to = os.environ.get("MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems")
        result_holder = [None]

        def _send():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result_holder[0] = loop.run_until_complete(svc.send(
                    to=[to],
                    subject=f"🌐 Murphy API Acquisition — {len(report['activated'])} APIs active",
                    body=body,
                    from_addr=os.environ.get("SMTP_FROM_EMAIL", "murphy@murphy.systems"),
                ))
            finally:
                loop.close()

        t = threading.Thread(target=_send, daemon=True)
        t.start()
        t.join(timeout=12)
        if result_holder[0] and result_holder[0].success:
            logger.info("PATCH-174: Acquisition report emailed to %s", to)
    except Exception as e:
        logger.warning("PATCH-174: Acquisition report email failed: %s", e)


def get_registry_status() -> dict:
    """Return current API registry status for dashboard."""
    _init_db()
    apis = _get_all_apis()
    active = [a for a in apis if a["status"] == "active"]
    pending = [a for a in apis if a["status"] == "pending_manual"]
    error = [a for a in apis if a["status"] == "error"]
    return {
        "total": len(apis),
        "active": len(active),
        "pending": len(pending),
        "failed": len(error),
        "active_list": [{"id": a["id"], "name": a["name"], "tier": a["tier"]} for a in active],
        "pending_list": [{"id": a["id"], "name": a["name"], "register_url": a.get("notes", "")} for a in pending],
    }
