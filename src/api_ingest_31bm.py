"""
Ship 31bm.API_INGEST — pull cporter202/API-mega-list into api_registry.

Per Murphy's architecture decision (2026-06-13):
  - Use existing api_registry table (don't create new)
  - Strip affiliate codes (?fpr=...) before storing
  - Status starts as 'pending' — patcher promotes to 'active' on health pass
  - R424 auto-bridges 'active' rows to AionMind capabilities

Source: https://raw.githubusercontent.com/cporter202/API-mega-list/main/README.md
Categories prioritized: MCP Servers, Open Source, Developer Tools, AI.
Skipped: 80%+ Apify Actors (pay-per-run, affiliate-linked).
"""
import re
import sqlite3
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

DB = "/var/lib/murphy-production/api_registry.db"
SOURCE_URL = "https://raw.githubusercontent.com/cporter202/API-mega-list/main/README.md"

# Priority categories (per cost/value analysis)
PRIORITY_CATEGORIES = {
    "mcp-servers":     {"tier": 2, "default_status": "pending"},
    "open-source":     {"tier": 2, "default_status": "pending"},
    "developer-tools": {"tier": 3, "default_status": "pending"},
    "ai":              {"tier": 3, "default_status": "pending"},
    "integrations":    {"tier": 3, "default_status": "pending"},
}
# Skip these entirely (affiliate-heavy, low utility)
SKIP_CATEGORIES = {"agents", "automation", "ecommerce", "social-media",
                   "real-estate", "travel", "videos", "lead-generation",
                   "jobs", "news", "seo-tools", "other", "business"}


def strip_affiliate(url: str) -> str:
    """Strip affiliate query params from URLs."""
    if not url:
        return ""
    # Strip ?fpr=, &fpr=, ?ref=, &ref=, ?aff=, &aff=
    url = re.sub(r'[?&]fpr=[^&]+', '', url)
    url = re.sub(r'[?&]ref=[^&]+', '', url)
    url = re.sub(r'[?&]aff=[^&]+', '', url)
    # If URL ended with ? and nothing else, strip the ?
    url = url.rstrip('?&')
    return url


def url_to_id(url: str) -> str:
    """Derive a stable ID from the URL."""
    clean = strip_affiliate(url).lower().rstrip('/')
    return "mega_" + hashlib.sha1(clean.encode()).hexdigest()[:16]


def parse_readme(text: str) -> List[Dict]:
    """Parse the mega-list README into structured API records.

    Format is markdown sections like:
      ## Agents
      | API Name | Description |
      | [Name](url?fpr=X) | desc... |
    """
    apis = []
    current_category = None
    lines = text.split('\n')

    for line in lines:
        # Detect section heading "## CategoryName"
        m = re.match(r'^##\s+([A-Za-z][A-Za-z\s&\-]+)\s*$', line)
        if m:
            cat = m.group(1).strip().lower().replace(' ', '-').replace('&', 'and')
            current_category = cat
            continue

        # Detect table row: | [Name](url) | description |
        m = re.match(r'^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*(.+?)\s*\|\s*$', line)
        if m and current_category:
            name = m.group(1).strip()
            url = strip_affiliate(m.group(2).strip())
            desc = m.group(3).strip().rstrip('.')

            # Skip if name is just markdown formatting
            if name.lower() in ("api name", "----------"):
                continue
            apis.append({
                "category": current_category,
                "name":     name,
                "url":      url,
                "description": desc[:500],  # cap description length
            })

    return apis


def fetch_megalist() -> str:
    """Download the README from GitHub."""
    req = urllib.request.Request(SOURCE_URL, headers={
        "User-Agent": "Murphy/31bm (https://murphy.systems)"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def categorize_auth(url: str) -> str:
    """Best-guess auth type from URL pattern."""
    if "apify.com" in url:           return "apify_token"
    if "openai.com" in url:          return "bearer"
    if "anthropic.com" in url:       return "x-api-key"
    if "rapidapi.com" in url:        return "rapidapi_key"
    return "unknown"


def ingest() -> Dict:
    """Run full ingestion. Returns stats dict."""
    # Fetch
    try:
        readme = fetch_megalist()
    except Exception as e:
        return {"error": f"fetch_failed: {e}"}

    # Parse
    all_apis = parse_readme(readme)

    # Filter to priority categories only
    keep = [a for a in all_apis if a["category"] in PRIORITY_CATEGORIES]
    skipped_by_cat = {}
    for a in all_apis:
        if a["category"] in SKIP_CATEGORIES:
            skipped_by_cat[a["category"]] = skipped_by_cat.get(a["category"], 0) + 1

    # Insert into api_registry
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB, timeout=15.0)
    inserted = 0
    skipped_dup = 0
    by_category = {}

    for a in keep:
        api_id = url_to_id(a["url"])
        # Skip if already present (idempotent re-runs)
        existing = conn.execute("SELECT 1 FROM api_registry WHERE id=?", (api_id,)).fetchone()
        if existing:
            skipped_dup += 1
            continue
        cat_meta = PRIORITY_CATEGORIES[a["category"]]
        try:
            conn.execute("""INSERT INTO api_registry
                (id, name, tier, status, auth_type, api_key, key_env,
                 base_url, test_url, description, tags, registered_at, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                api_id,
                a["name"][:200],
                cat_meta["tier"],
                cat_meta["default_status"],
                categorize_auth(a["url"]),
                "", "",
                a["url"],
                a["url"],
                a["description"],
                json.dumps([a["category"], "mega_list", "cporter202"]),
                now,
                f"source:cporter202/API-mega-list; ingested via 31bm",
            ))
            inserted += 1
            by_category[a["category"]] = by_category.get(a["category"], 0) + 1
        except Exception as e:
            pass

    conn.commit()
    conn.close()

    return {
        "source":          SOURCE_URL,
        "ingested_at":     now,
        "total_parsed":    len(all_apis),
        "kept_categories": list(PRIORITY_CATEGORIES.keys()),
        "skipped_categories": skipped_by_cat,
        "inserted":        inserted,
        "skipped_duplicate": skipped_dup,
        "by_category":     by_category,
    }


if __name__ == "__main__":
    import sys
    result = ingest()
    print(json.dumps(result, indent=2))
