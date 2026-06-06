"""
PATCH-R418 — Unified Feature Inventory
========================================

WHAT THIS IS:
  Single source of truth for "what does Murphy offer on the website?"
  Reads /var/lib/murphy-production/route_registry.json (the live FastAPI
  route dump from src/route_registry.py) and groups every public surface
  into named features with: status, primary URL, supporting APIs, and
  evidence file.

WHY IT EXISTS:
  Founder request 2026-06-01: "unify on a saved list of all features
  currently pointed toward our website" + "map our system backend calls
  into a proper UI experience".

  Before this: 944 API endpoints, 137 page routes, but only 27 mapped on
  the landing page. No single document told you "feature X exists and
  here's where you click on it". nav_registry.py had ~50 stale entries
  with three different features all pointing at /ui/management. The
  ConnexAI-style site needs a clean catalog underneath the visuals.

HOW IT FITS:
  Read-only consumer of route_registry.json. Emits:
    1. feature_inventory.json — canonical feature catalog
    2. backend_ui_map.json    — every /api/ endpoint → its UI page
    3. /api/inventory + /api/inventory/feature/{id} — query endpoints
    4. /inventory page — browseable UI

  Run via:
    POST /api/inventory/rebuild  (founder-only, regenerates from live routes)

ENDPOINTS:
  GET  /api/inventory                  — full catalog as JSON
  GET  /api/inventory/feature/{id}     — one feature with its API endpoints
  GET  /api/inventory/orphans          — APIs with no UI surface
  POST /api/inventory/rebuild          — regenerate from live route_registry

LAST UPDATED: 2026-06-01 — R418 initial wiring
"""
from __future__ import annotations
import json, logging, time
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("murphy.feature_inventory")

INVENTORY_PATH = Path("/var/lib/murphy-production/feature_inventory.json")
UI_MAP_PATH    = Path("/var/lib/murphy-production/backend_ui_map.json")
ROUTE_REG_PATH = Path("/var/lib/murphy-production/route_registry.json")

# ── Feature definitions (the canonical catalog) ─────────────────────
# Each feature has:
#   id          — short slug for URL & query
#   name        — human label
#   category    — top-level group on the website
#   description — 1-2 sentence what-it-does
#   primary_url — the page user clicks to reach it
#   api_prefix  — string prefix(es) of /api/ endpoints powering it
#   evidence    — file paths backing the claim (R208 audit-first rule)
#   status      — live | partial | stub | broken
#   tier        — public | tenant | founder

FEATURES: List[Dict[str, Any]] = [
    # ── Public marketing surfaces ─────────────────────────────────
    {
        "id": "landing",
        "name": "Landing Page",
        "category": "Marketing",
        "description": "Hero + sector tiles + roles strip + pricing.",
        "primary_url": "/",
        "api_prefix": ["/api/public/pulse"],
        "evidence": ["murphy_landing_page.html"],
        "status": "live", "tier": "public",
    },
    {
        "id": "demo",
        "name": "Watch Murphy Work",
        "category": "Marketing",
        "description": "Live demo of system cascade with org-chart, decisions, and HITL.",
        "primary_url": "/demo",
        "api_prefix": ["/api/public/cascade", "/api/public/pulse"],
        "evidence": ["mep_demo_standalone.html", "static/mission.html"],
        "status": "live", "tier": "public",
    },
    {
        "id": "mission",
        "name": "Mission Control (public)",
        "category": "Marketing",
        "description": "3-column view of org chart, cascade traces, and HITL telemetry.",
        "primary_url": "/mission",
        "api_prefix": ["/api/public/cascade", "/api/public/pulse", "/api/public/hitl"],
        "evidence": ["static/mission.html"],
        "status": "live", "tier": "public",
    },
    {
        "id": "pitch",
        "name": "Pitch Deck",
        "category": "Marketing",
        "description": "Investor / customer pitch deck served at /pitch and /deck.",
        "primary_url": "/pitch",
        "api_prefix": [],
        "evidence": ["pitch_deck.html"],
        "status": "live", "tier": "public",
    },
    {
        "id": "sector_mep",
        "name": "MEP & Construction",
        "category": "Marketing",
        "description": "Cascadia MEP demo + Oregon contractor reciprocity flow.",
        "primary_url": "/cascadia_mep.html",
        "api_prefix": ["/api/mep/"],
        "evidence": ["cascadia_mep.html", "oregon_mep_demo_assistant.html"],
        "status": "live", "tier": "public",
    },
    {
        "id": "sector_compliance",
        "name": "Compliance",
        "category": "Marketing",
        "description": "HIPAA/SOC2/GDPR as build-time gates. Hash-chained audit trails.",
        "primary_url": "/compliance",
        "api_prefix": ["/api/compliance/"],
        "evidence": ["compliance_dashboard.html", "cascadia_compliance_demo.html"],
        "status": "live", "tier": "public",
    },
    {
        "id": "how_we_work",
        "name": "How Murphy Works",
        "category": "Marketing",
        "description": "Explanation of swarm + cascade + souls + HITL.",
        "primary_url": "/how-we-work",
        "api_prefix": [],
        "evidence": ["static/how-we-work.html"],
        "status": "live", "tier": "public",
    },

    # ── Conversion surfaces ───────────────────────────────────────
    {
        "id": "signup",
        "name": "Sign Up",
        "category": "Conversion",
        "description": "6-stage signup: wizard → config → role → payment → tenant → first agent.",
        "primary_url": "/signup",
        "api_prefix": ["/api/onboarding/", "/api/auth/signup"],
        "evidence": ["static/signup.html"],
        "status": "live", "tier": "public",
    },
    {
        "id": "billing",
        "name": "Payments & Pricing",
        "category": "Conversion",
        "description": "NOWPayments crypto checkout (USD via Mercuryo card / wallet). Pilot $99 / Growth $499 / Scale $1499.",
        "primary_url": "/pricing",
        "api_prefix": ["/api/payments/nowpayments/", "/api/billing/plans"],
        "evidence": ["src/patch370_nowpayments_billing.py", "src/billing_plans.py"],
        "status": "live", "tier": "public",
    },
    {
        "id": "book",
        "name": "Book a Call",
        "category": "Conversion",
        "description": "Schedule an audit / demo call with Corey.",
        "primary_url": "/book",
        "api_prefix": [],
        "evidence": ["static/book.html"],
        "status": "live", "tier": "public",
    },
    {
        "id": "contact",
        "name": "Contact",
        "category": "Conversion",
        "description": "Inbound support ticket creation.",
        "primary_url": "/contact",
        "api_prefix": ["/api/support/ticket"],
        "evidence": ["static/contact.html"],
        "status": "live", "tier": "public",
    },

    # ── Tenant surfaces (logged-in customer) ──────────────────────
    {
        "id": "tenant_control",
        "name": "Tenant Control Room",
        "category": "Tenant",
        "description": "Customer's home base: chat their Murphy, see their pulse, manage their account.",
        "primary_url": "/tenant/control",
        "api_prefix": ["/api/chat", "/api/my/"],
        "evidence": ["tenant_control.html"],
        "status": "live", "tier": "tenant",
    },
    {
        "id": "tenant_dashboard",
        "name": "Tenant Dashboard",
        "category": "Tenant",
        "description": "Per-account dashboard: deals, runs, automations, billing.",
        "primary_url": "/dashboard",
        "api_prefix": ["/api/crm/", "/api/my/"],
        "evidence": ["static/dashboard.html"],
        "status": "live", "tier": "tenant",
    },
    {
        "id": "tenant_crm",
        "name": "CRM",
        "category": "Tenant",
        "description": "Contacts, deals, pipeline, activity timeline — tenant-scoped.",
        "primary_url": "/ui/crm",
        "api_prefix": ["/api/crm/"],
        "evidence": ["src/crm_routes.py"],
        "status": "live", "tier": "tenant",
    },
    {
        "id": "tenant_hitl",
        "name": "Approval Queue (HITL)",
        "category": "Tenant",
        "description": "Items requiring human approval before Murphy sends/acts.",
        "primary_url": "/hitl",
        "api_prefix": ["/api/swarm/hitl/", "/api/my/hitl/"],
        "evidence": ["hitl_dashboard.html", "src/hitl_engine.py"],
        "status": "live", "tier": "tenant",
    },
    {
        "id": "tenant_automations",
        "name": "Automations",
        "category": "Tenant",
        "description": "Recurring / triggered workflows the tenant has running.",
        "primary_url": "/ui/automations",
        "api_prefix": ["/api/automations/", "/api/my/automations"],
        "evidence": ["src/automations/engine.py"],
        "status": "partial", "tier": "tenant",
    },
    {
        "id": "tenant_settings",
        "name": "Settings & Team",
        "category": "Tenant",
        "description": "Account settings, team members, integrations, API keys.",
        "primary_url": "/ui/settings",
        "api_prefix": ["/api/auth/", "/api/my/team", "/api/integrations/"],
        "evidence": ["src/tenant_settings.py"],
        "status": "partial", "tier": "tenant",
    },

    # ── Founder surfaces ──────────────────────────────────────────
    {
        "id": "founder_control",
        "name": "Founder Control Room",
        "category": "Founder",
        "description": "Substrate-aware chat + system pulse + every page in the system.",
        "primary_url": "/founder",
        "api_prefix": ["/api/chat", "/api/swarm/", "/api/self/"],
        "evidence": ["founder.html"],
        "status": "live", "tier": "founder",
    },
    {
        "id": "founder_patcher",
        "name": "Patch Console",
        "category": "Founder",
        "description": "Apply / review self-modification patches.",
        "primary_url": "/patcher",
        "api_prefix": ["/api/self-modify/", "/api/platform/admin/"],
        "evidence": ["static/patcher.html"],
        "status": "partial", "tier": "founder",
    },
    {
        "id": "founder_shape",
        "name": "Shape Verifier",
        "category": "Founder",
        "description": "Auto-verifier scorecard for substrate health.",
        "primary_url": "/ops",
        "api_prefix": ["/api/self/shape", "/api/self/grep", "/api/self/read"],
        "evidence": ["static/ops.html", "shape_state.json"],
        "status": "live", "tier": "founder",
    },
    {
        "id": "founder_mind",
        "name": "Mind Cycle",
        "category": "Founder",
        "description": "Autonomous mind cycle proposals + decisions.",
        "primary_url": "/ops/mind",
        "api_prefix": ["/api/swarm/mind/", "/api/mind/"],
        "evidence": ["src/murphy_mind_clean.py"],
        "status": "live", "tier": "founder",
    },
]

# ── Category metadata ─────────────────────────────────────────────
CATEGORIES = {
    "Marketing":   {"icon": "◆", "color": "#7afcff", "order": 1},
    "Conversion":  {"icon": "▸", "color": "#00d4aa", "order": 2},
    "Tenant":      {"icon": "◉", "color": "#ff7eb6", "order": 3},
    "Founder":     {"icon": "⚙", "color": "#ffa940", "order": 4},
}

STATUS_META = {
    "live":    {"label": "Live",    "color": "#00ff6a", "emoji": "✅"},
    "partial": {"label": "Partial", "color": "#ffa940", "emoji": "⚠"},
    "stub":    {"label": "Stub",    "color": "#5a6e66", "emoji": "○"},
    "broken":  {"label": "Broken",  "color": "#ff5c7c", "emoji": "❌"},
}


def _load_routes() -> List[Dict[str, Any]]:
    if not ROUTE_REG_PATH.exists():
        return []
    try:
        return json.loads(ROUTE_REG_PATH.read_text()).get("routes", [])
    except Exception as e:
        log.error("route_registry load failed: %s", e)
        return []


def _resolve_status(feature: Dict[str, Any], live_routes: List[str]) -> Dict[str, Any]:
    """Compare claimed URLs against live route table; downgrade if missing."""
    url = feature["primary_url"]
    if url not in live_routes and not any(url.startswith(p.replace("{page_name:path}", "")) for p in live_routes):
        # Page route literally not registered — downgrade
        feature = dict(feature, status="broken", broken_reason=f"primary_url {url} not in live route table")
    return feature


def _enrich_with_api_counts(feature: Dict[str, Any], live_routes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """For each api_prefix, count matching live API routes."""
    counts = {}
    for prefix in feature.get("api_prefix", []):
        n = sum(1 for r in live_routes if r["path"].startswith(prefix))
        counts[prefix] = n
    feature = dict(feature, api_route_count=counts, api_total=sum(counts.values()))
    return feature


def build_inventory() -> Dict[str, Any]:
    """Generate the canonical feature inventory."""
    raw_routes = _load_routes()
    live_paths = {r["path"] for r in raw_routes}

    enriched = []
    for f in FEATURES:
        f = _resolve_status(f, live_paths)
        f = _enrich_with_api_counts(f, raw_routes)
        enriched.append(f)

    # Find orphan APIs — endpoints not claimed by any feature
    claimed_prefixes = []
    for f in FEATURES:
        claimed_prefixes.extend(f.get("api_prefix", []))

    orphans = []
    for r in raw_routes:
        path = r["path"]
        if not path.startswith("/api/"):
            continue
        if any(path.startswith(p) for p in claimed_prefixes):
            continue
        # Group by 2nd segment
        parts = path.split("/")
        group = parts[2] if len(parts) > 2 else "misc"
        orphans.append({"path": path, "methods": r.get("methods", []), "group": group})

    by_category = {}
    for f in enriched:
        by_category.setdefault(f["category"], []).append(f)

    inventory = {
        "generated_at": time.time(),
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_features": len(enriched),
        "total_categories": len(by_category),
        "live": sum(1 for f in enriched if f["status"] == "live"),
        "partial": sum(1 for f in enriched if f["status"] == "partial"),
        "broken": sum(1 for f in enriched if f["status"] == "broken"),
        "stub": sum(1 for f in enriched if f["status"] == "stub"),
        "total_api_endpoints_claimed": sum(f.get("api_total", 0) for f in enriched),
        "total_api_endpoints_live": sum(1 for r in raw_routes if r["path"].startswith("/api/")),
        "orphan_api_count": len(orphans),
        "categories": CATEGORIES,
        "status_meta": STATUS_META,
        "features": enriched,
        "by_category": by_category,
        "orphans_sample": orphans[:50],
        "orphans_by_group": {},
    }

    # Group orphans
    for o in orphans:
        inventory["orphans_by_group"].setdefault(o["group"], []).append(o["path"])

    return inventory


def build_ui_map() -> Dict[str, Any]:
    """For every /api/ endpoint, declare which UI page should surface it."""
    inv = build_inventory()
    ui_map = {}
    for f in inv["features"]:
        for prefix in f.get("api_prefix", []):
            ui_map[prefix] = {
                "ui_page": f["primary_url"],
                "feature_id": f["id"],
                "feature_name": f["name"],
                "category": f["category"],
                "tier": f["tier"],
            }
    return {
        "generated_at": time.time(),
        "ui_map": ui_map,
        "orphan_groups": inv["orphans_by_group"],
    }


def persist() -> Dict[str, Any]:
    """Generate and write both JSONs to disk."""
    inv = build_inventory()
    INVENTORY_PATH.write_text(json.dumps(inv, indent=2, default=str))
    ui_map = build_ui_map()
    UI_MAP_PATH.write_text(json.dumps(ui_map, indent=2, default=str))
    return {
        "inventory": str(INVENTORY_PATH), "inv_size": INVENTORY_PATH.stat().st_size,
        "ui_map": str(UI_MAP_PATH), "map_size": UI_MAP_PATH.stat().st_size,
        "total_features": inv["total_features"],
        "live_features": inv["live"],
        "broken_features": inv["broken"],
        "orphan_apis": inv["orphan_api_count"],
    }


def load_inventory() -> Optional[Dict[str, Any]]:
    if not INVENTORY_PATH.exists():
        return persist() and json.loads(INVENTORY_PATH.read_text())
    return json.loads(INVENTORY_PATH.read_text())
