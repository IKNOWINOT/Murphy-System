"""Static catalog of known Base44 third-party skills + platform skills.

Used by C.2 (suggest_skill_installation) to recommend a ready-made
skill before writing code from scratch. Sourced from Base44 docs
snapshot 2026-05-22.

Format: keyword-indexed entries. Each entry has name, kind, category,
description, install_path (how user would install).
"""
from typing import Dict, List

# Third-party "skill store" entries (subset of the 130+ in the store)
THIRD_PARTY = [
    {"name": "docx", "kind": "third_party", "category": "documents",
     "description": "Read and write Microsoft Word documents",
     "keywords": ["word", "docx", "document", "doc"],
     "install": "suggest_skill_installation(query='docx')"},
    {"name": "pdf", "kind": "third_party", "category": "documents",
     "description": "Parse and generate PDF files",
     "keywords": ["pdf", "document", "report"],
     "install": "suggest_skill_installation(query='pdf')"},
    {"name": "excel", "kind": "third_party", "category": "documents",
     "description": "Read and write Excel/xlsx spreadsheets",
     "keywords": ["excel", "xlsx", "spreadsheet", "csv", "sheet"],
     "install": "suggest_skill_installation(query='excel')"},
    {"name": "email", "kind": "third_party", "category": "communication",
     "description": "Send and parse emails via SMTP/IMAP",
     "keywords": ["email", "smtp", "imap", "mail", "send mail"],
     "install": "suggest_skill_installation(query='email')"},
    {"name": "crm", "kind": "third_party", "category": "business",
     "description": "Generic CRM operations (contacts, deals, pipelines)",
     "keywords": ["crm", "contact", "deal", "pipeline", "salesforce"],
     "install": "suggest_skill_installation(query='crm')"},
    {"name": "weather", "kind": "third_party", "category": "data",
     "description": "Fetch current and forecast weather data",
     "keywords": ["weather", "forecast", "temperature", "rain"],
     "install": "suggest_skill_installation(query='weather')"},
    {"name": "stock", "kind": "third_party", "category": "data",
     "description": "Stock quotes and market data",
     "keywords": ["stock", "ticker", "market", "quote", "nasdaq", "wix"],
     "install": "suggest_skill_installation(query='stock')"},
    {"name": "calendar", "kind": "third_party", "category": "communication",
     "description": "Calendar event management",
     "keywords": ["calendar", "event", "meeting", "schedule", "appointment"],
     "install": "suggest_skill_installation(query='calendar')"},
]

# Platform skills (lazy-load via activate_platform_skill)
PLATFORM = [
    {"name": "channel-connections", "kind": "platform",
     "description": "Telegram, WhatsApp, iMessage messaging channels",
     "keywords": ["telegram", "whatsapp", "imessage", "channel", "messaging"]},
    {"name": "connectors", "kind": "platform",
     "description": "OAuth services (Google, Slack, GitHub, etc.)",
     "keywords": ["oauth", "google", "slack", "github", "connector", "auth"]},
    {"name": "backend-functions", "kind": "platform",
     "description": "Deploy HTTP backend functions (Deno runtime)",
     "keywords": ["backend", "function", "deno", "http endpoint", "api"]},
    {"name": "stripe-payments", "kind": "platform",
     "description": "Stripe products, prices, checkout sessions",
     "keywords": ["stripe", "payment", "checkout", "subscription", "billing"]},
    {"name": "browserbase", "kind": "platform",
     "description": "Browser automation — navigate, screenshot, click",
     "keywords": ["browser", "browserbase", "navigate", "screenshot", "scrape"]},
    {"name": "skills", "kind": "platform",
     "description": "Create and run reusable scripts in .agents/skills/",
     "keywords": ["skill", "create skill", "script", "reusable"]},
    {"name": "skill-store", "kind": "platform",
     "description": "Browse 130+ ready-made third-party skills",
     "keywords": ["store", "marketplace", "library", "ready-made", "browse"]},
]

ALL = THIRD_PARTY + PLATFORM


def search(query: str, *, limit: int = 5) -> List[Dict]:
    """Keyword-match a query against the catalog."""
    if not query:
        return []
    q = query.lower().strip()
    q_tokens = set(q.split())
    scored: List = []
    for entry in ALL:
        score = 0
        for kw in entry.get("keywords", []):
            kw_lower = kw.lower()
            if kw_lower in q:
                score += 3
            elif any(t in kw_lower or kw_lower in t for t in q_tokens):
                score += 1
        # Boost matches by name
        if entry["name"].lower() in q:
            score += 5
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda x: -x[0])
    return [{**e, "_score": s} for s, e in scored[:limit]]
