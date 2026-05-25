"""
PATCH-387 — Organizational Soul + WorldState wiring

Three additions, all into existing modules (RULE 1):

  A) entity_graph.db schema extension:
     - organizational_souls table (the business plan AS a soul)
     - worldstate_subscriptions table (each org subscribes to relevant domains)

  B) deep_soul_engine.build_deep_soul extension:
     - When building an agent's soul, also load the org's soul and prepend
     - Query worldstate_engine for the agent's org's subscribed domains
       relevant to task topic and append to L4 (live context)

  C) world_state_engine.py extension via runtime registration:
     - Register 5 new business-relevant fetchers (industry codes,
       construction starts, soc2/hipaa changes, competitive intel, ASHRAE)
     - These run on the existing 5-minute refresh loop

  D) Routes inside create_app():
     - POST /api/org/soul/create
     - GET  /api/org/soul/{org_id}
     - POST /api/org/soul/edit
     - GET  /api/dispatch/contextualized-soul
     - GET  /api/world/business-domains (preview new domains)

Plus seed:
  - Murphy.systems platform organizational soul (business plan as data)
  - Subscribe Murphy.systems to: soc2_hipaa, competitive_saas, regulatory_general

Applied: 2026-05-22
"""

# ════════════════════════════════════════════════════════════════════════
# A) NEW SQLITE SCHEMA — organizational_souls + worldstate_subscriptions
# ════════════════════════════════════════════════════════════════════════

SCHEMA_EXTENSION_SQL = """
CREATE TABLE IF NOT EXISTS organizational_souls (
    org_id              TEXT PRIMARY KEY,
    org_name            TEXT NOT NULL,
    org_type            TEXT,                -- "platform" | "tenant" | "department"
    parent_org_id       TEXT,                -- for departments under a parent
    vision              TEXT,                -- one-paragraph vision
    mission             TEXT,                -- mission statement
    market_position     TEXT,                -- where we play, who we serve
    business_plan_json  TEXT,                -- BusinessPlanMath as JSON
    strategic_priorities TEXT,               -- JSON list of {priority, weight, deadline}
    competitive_landscape TEXT,              -- JSON list of {competitor, threat_level, our_differentiator}
    constraints         TEXT,                -- JSON list of {type, description, severity}
    kpis_org_json       TEXT,                -- org-wide KPIs (rolled up from agents)
    culture_values      TEXT,                -- JSON list of cultural pillars
    risk_appetite       TEXT,                -- "conservative" | "moderate" | "aggressive"
    created_at          TEXT,
    updated_at          TEXT
);

CREATE TABLE IF NOT EXISTS worldstate_subscriptions (
    id                  TEXT PRIMARY KEY,
    org_id              TEXT NOT NULL,
    domain              TEXT NOT NULL,       -- e.g. "soc2_hipaa", "ashrae_updates"
    relevance_weight    REAL DEFAULT 1.0,    -- 0.0-1.0 multiplier
    auto_inject_to_l4   INTEGER DEFAULT 1,   -- 1 = yes, append to dispatch L4
    created_at          TEXT
);

CREATE INDEX IF NOT EXISTS idx_ws_sub_org ON worldstate_subscriptions(org_id);
CREATE INDEX IF NOT EXISTS idx_org_souls_type ON organizational_souls(org_type);
"""


# ════════════════════════════════════════════════════════════════════════
# B) MURPHY.SYSTEMS PLATFORM ORG SOUL (seed data)
# ════════════════════════════════════════════════════════════════════════

MURPHY_PLATFORM_SOUL = {
    "org_id": "murphy_systems_platform",
    "org_name": "Murphy.systems",
    "org_type": "platform",
    "parent_org_id": None,
    "vision": (
        "Be the autonomous operating system for small and mid-market businesses — "
        "compress an entire company's operations (sales, ops, finance, compliance) "
        "into a single platform that runs itself, with the founder in the loop only "
        "where it matters."
    ),
    "mission": (
        "Replace 5-8 SaaS tools + 2-3 contractors with one Murphy tenant for $99-$599/mo. "
        "Every operator gets a full executive team of AI agents who actually do the work, "
        "with provable compliance and full audit trail."
    ),
    "market_position": (
        "We sit between Zapier (too primitive) and Palantir (too expensive/enterprise). "
        "Target: SMB owner-operators with 1-50 employees who want big-company ops without "
        "big-company headcount. Initial wedge: regulated industries (engineering, healthcare, "
        "compliance-heavy services) where the audit trail is the killer feature."
    ),
    "business_plan_json": {
        "revenue_model": {
            "tiers": [
                {"name": "Solo", "price_monthly_usd": 99, "target_segment": "single-operator businesses"},
                {"name": "Team", "price_monthly_usd": 399, "target_segment": "5-15 employee shops"},
                {"name": "Enterprise", "price_monthly_usd": None, "target_segment": "custom, regulated, multi-entity"},
            ],
            "addons": [
                {"name": "System Influence", "price_monthly_usd": 50, "what": "Tenant can edit platform-level configs"},
                {"name": "Outreach Engine", "price_monthly_usd": 99, "what": "Automated prospecting + follow-up"},
                {"name": "HITL Reviewer", "price_monthly_usd": 199, "what": "Murphy reviews tenant's HITL queue"},
            ],
            "currencies_accepted": ["USD", "crypto (NOWPayments, 300+ coins)"],
            "treasury_policy": "50% ops cash, 50% staked Cosmos ATOM",
        },
        "unit_economics_target": {
            "ARR_year_1_usd": 1_000_000,
            "gross_margin_pct": 80,
            "CAC_payback_months": 6,
            "net_revenue_retention_pct": 115,
            "churn_monthly_pct_max": 3,
        },
        "valuation_basis": {
            "platform_arr_multiple": 20,
            "managed_arr_multiple": 3,
            "current_estimate_usd": [1_500_000, 6_400_000],
        },
    },
    "strategic_priorities": [
        {"priority": "Close G06-G14 autonomy gates", "weight": 1.0, "deadline": "2026-05-31", "status": "8/9 done"},
        {"priority": "Ship tenant self-service onboarding (PATCH-388)", "weight": 0.9, "deadline": "2026-06-15"},
        {"priority": "Get to 10 paying tenants", "weight": 0.95, "deadline": "2026-07-31"},
        {"priority": "SOC2 Type 1 readiness", "weight": 0.7, "deadline": "2026-09-30"},
        {"priority": "Cross-tenant learning network effect (PATCH-390)", "weight": 0.6, "deadline": "2026-08-31"},
    ],
    "competitive_landscape": [
        {"competitor": "Zapier / Make", "threat_level": "low", "our_differentiator": "We do business logic + reasoning, not just glue"},
        {"competitor": "Salesforce / HubSpot", "threat_level": "medium", "our_differentiator": "We DO the work, not just track it. Lower price, full ops not just CRM."},
        {"competitor": "Notion AI / ChatGPT teams", "threat_level": "medium", "our_differentiator": "We integrate with their systems and actually execute, not just draft documents"},
        {"competitor": "Custom GPT agencies", "threat_level": "high", "our_differentiator": "Flat-rate SaaS vs. retainer; auditable compliance vs. opaque"},
        {"competitor": "Palantir Foundry", "threat_level": "low", "our_differentiator": "1000x cheaper, no implementation team needed"},
    ],
    "constraints": [
        {"type": "regulatory", "description": "Must maintain HIPAA/SOC2/GDPR posture for any tenant in healthcare/regulated industries", "severity": "high"},
        {"type": "technical", "description": "Single-node deployment (Hetzner) — must scale before 100 tenants", "severity": "medium"},
        {"type": "founder_capacity", "description": "Corey is sole engineer — every patch must compound autonomy, not consume time", "severity": "high"},
        {"type": "financial", "description": "6-month runway minimum — cash conservation > growth in low-traction phase", "severity": "medium"},
    ],
    "kpis_org_json": {
        "ARR_usd": "1M EoY1",
        "platform_gates_live": "13/15",
        "tenant_count_paying": "10 by Q3",
        "platform_uptime_pct": 99.5,
        "tenant_NPS_min": 50,
        "monthly_churn_pct_max": 3,
        "autonomy_pct_min": 80,
    },
    "culture_values": [
        "Show your work — every action leaves a citation",
        "One patch, one thing — never bundle",
        "Build INTO existing modules, never sprawl",
        "Autonomy > activity — measure outcomes, not effort",
        "Compliance is structural, not bolted-on",
        "If we can't explain it to the tenant, we can't ship it",
    ],
    "risk_appetite": "moderate",
}

MURPHY_PLATFORM_SUBSCRIPTIONS = [
    {"domain": "soc2_hipaa_changes",   "relevance_weight": 1.0, "reason": "compliance posture"},
    {"domain": "competitive_saas",     "relevance_weight": 0.8, "reason": "market positioning"},
    {"domain": "regulatory_general",   "relevance_weight": 0.7, "reason": "audit readiness"},
    {"domain": "construction_starts",  "relevance_weight": 0.5, "reason": "engineering tenant market"},
    {"domain": "markets",              "relevance_weight": 0.4, "reason": "treasury ATOM exposure"},
]


# ════════════════════════════════════════════════════════════════════════
# C) NEW WORLDSTATE DOMAINS — business-relevant fetchers
#
# These are stub fetchers — they return structured DomainReadings with
# placeholder signals. They will be progressively wired to real feeds
# (RSS, API, scraping) in future patches.
# ════════════════════════════════════════════════════════════════════════

NEW_WORLDSTATE_DOMAINS_CODE = '''
# ──────────────────────────────────────────────────────────────────────
# PATCH-387 — Business-relevant WorldState domains
# Stub fetchers returning structured DomainReadings; wire to real feeds later
# ──────────────────────────────────────────────────────────────────────

def fetch_soc2_hipaa_changes():
    """Track changes to SOC2/HIPAA/GDPR frameworks that affect compliance posture."""
    from src.world_state_engine import DomainReading
    from datetime import datetime as _dt, timezone as _tz
    return DomainReading(
        domain="soc2_hipaa_changes",
        stability_score=0.85,
        raw_signals={
            "soc2_v2024_status": "stable",
            "hipaa_revision_pending": False,
            "gdpr_enforcement_actions_last_30d": 12,
            "active_advisories": [],
        },
        source="patch387_stub",
        fetched_at=_dt.now(_tz.utc).isoformat(),
        confidence=0.5,
    )


def fetch_competitive_saas():
    """Track competitive SaaS platform releases relevant to Murphy positioning."""
    from src.world_state_engine import DomainReading
    from datetime import datetime as _dt, timezone as _tz
    return DomainReading(
        domain="competitive_saas",
        stability_score=0.75,
        raw_signals={
            "salesforce_einstein_updates_30d": 0,
            "hubspot_ai_features_30d": 0,
            "zapier_agent_releases_30d": 0,
            "notable_funding_rounds": [],
            "ai_agent_market_news": [],
        },
        source="patch387_stub",
        fetched_at=_dt.now(_tz.utc).isoformat(),
        confidence=0.4,
    )


def fetch_regulatory_general():
    """Industry-agnostic regulatory pulse — financial, data, employment."""
    from src.world_state_engine import DomainReading
    from datetime import datetime as _dt, timezone as _tz
    return DomainReading(
        domain="regulatory_general",
        stability_score=0.80,
        raw_signals={
            "ftc_ai_guidance_status": "active",
            "sec_disclosure_changes": [],
            "state_ai_laws_passed_30d": [],
        },
        source="patch387_stub",
        fetched_at=_dt.now(_tz.utc).isoformat(),
        confidence=0.5,
    )


def fetch_construction_starts():
    """Construction starts — leading indicator for engineering tenant demand."""
    from src.world_state_engine import DomainReading
    from datetime import datetime as _dt, timezone as _tz
    return DomainReading(
        domain="construction_starts",
        stability_score=0.70,
        raw_signals={
            "ABI_index_latest": None,            # AIA Architecture Billings Index
            "housing_starts_yoy_pct": None,
            "nonres_construction_yoy_pct": None,
            "construction_sentiment": "stable",
        },
        source="patch387_stub",
        fetched_at=_dt.now(_tz.utc).isoformat(),
        confidence=0.4,
    )


def fetch_ashrae_nec_updates():
    """ASHRAE / NEC / IBC code updates — affects MEP engineering tenants."""
    from src.world_state_engine import DomainReading
    from datetime import datetime as _dt, timezone as _tz
    return DomainReading(
        domain="ashrae_nec_updates",
        stability_score=0.90,
        raw_signals={
            "ashrae_90_1_current": "2022",
            "ashrae_62_1_current": "2022",
            "nec_current_edition": "2023",
            "ibc_current_edition": "2024",
            "pending_revisions": [],
        },
        source="patch387_stub",
        fetched_at=_dt.now(_tz.utc).isoformat(),
        confidence=0.6,
    )


def _register_patch387_domains():
    """Register the 5 new business domains with the singleton WorldStateEngine."""
    try:
        from src.world_state_engine import world_state as _ws
        engine = _ws
        engine._fetchers["soc2_hipaa_changes"] = fetch_soc2_hipaa_changes
        engine._fetchers["competitive_saas"] = fetch_competitive_saas
        engine._fetchers["regulatory_general"] = fetch_regulatory_general
        engine._fetchers["construction_starts"] = fetch_construction_starts
        engine._fetchers["ashrae_nec_updates"] = fetch_ashrae_nec_updates
        return True
    except Exception:
        return False
'''


# ════════════════════════════════════════════════════════════════════════
# D) ROUTES inside create_app()
# ════════════════════════════════════════════════════════════════════════

ROUTES_CODE = '''

    # ═══ PATCH-387: Organizational Soul + WorldState wiring ═══
    @app.post("/api/org/soul/create")
    async def org_soul_create(payload: dict, request: Request = None):
        """Create or upsert an organizational soul."""
        try:
            import sqlite3 as _sql, json as _json, uuid as _uuid
            from datetime import datetime as _dt, timezone as _tz
            DB = "/var/lib/murphy-production/entity_graph.db"
            now = _dt.now(_tz.utc).isoformat()
            org_id = payload.get("org_id") or f"org-{_uuid.uuid4().hex[:8]}"
            with _sql.connect(DB) as c:
                c.execute("""INSERT OR REPLACE INTO organizational_souls
                    (org_id, org_name, org_type, parent_org_id, vision, mission,
                     market_position, business_plan_json, strategic_priorities,
                     competitive_landscape, constraints, kpis_org_json,
                     culture_values, risk_appetite, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                            COALESCE((SELECT created_at FROM organizational_souls WHERE org_id=?), ?),
                            ?)""", (
                    org_id, payload.get("org_name", ""), payload.get("org_type", "tenant"),
                    payload.get("parent_org_id"), payload.get("vision", ""),
                    payload.get("mission", ""), payload.get("market_position", ""),
                    _json.dumps(payload.get("business_plan_json", {})),
                    _json.dumps(payload.get("strategic_priorities", [])),
                    _json.dumps(payload.get("competitive_landscape", [])),
                    _json.dumps(payload.get("constraints", [])),
                    _json.dumps(payload.get("kpis_org_json", {})),
                    _json.dumps(payload.get("culture_values", [])),
                    payload.get("risk_appetite", "moderate"),
                    org_id, now, now,
                ))
                c.commit()
            return {"gate": "PATCH-387-ORG-SOUL-CREATE", "status": "OK", "org_id": org_id}
        except Exception as e:
            import traceback as _tb
            return {"gate": "PATCH-387-ORG-SOUL-CREATE", "status": "ERROR",
                    "error": str(e), "trace": _tb.format_exc()[:500]}


    @app.get("/api/org/soul/{org_id}")
    async def org_soul_read(org_id: str, request: Request = None):
        """Read an organizational soul."""
        try:
            import sqlite3 as _sql, json as _json
            DB = "/var/lib/murphy-production/entity_graph.db"
            with _sql.connect(DB) as c:
                c.row_factory = _sql.Row
                row = c.execute("SELECT * FROM organizational_souls WHERE org_id=?", (org_id,)).fetchone()
                if not row:
                    return {"gate": "PATCH-387-ORG-SOUL-READ", "status": "NOT_FOUND", "org_id": org_id}
                d = dict(row)
                # Parse JSON fields
                for f in ("business_plan_json", "strategic_priorities", "competitive_landscape",
                          "constraints", "kpis_org_json", "culture_values"):
                    if d.get(f):
                        try: d[f] = _json.loads(d[f])
                        except: pass
                # Subscriptions
                subs = [dict(s) for s in c.execute(
                    "SELECT domain, relevance_weight, auto_inject_to_l4 FROM worldstate_subscriptions WHERE org_id=?",
                    (org_id,)).fetchall()]
                d["worldstate_subscriptions"] = subs
            return {"gate": "PATCH-387-ORG-SOUL-READ", "status": "OK", "soul": d}
        except Exception as e:
            import traceback as _tb
            return {"gate": "PATCH-387-ORG-SOUL-READ", "status": "ERROR",
                    "error": str(e), "trace": _tb.format_exc()[:500]}


    @app.post("/api/org/soul/edit")
    async def org_soul_edit(payload: dict, request: Request = None):
        """HITL edit to an organizational soul field."""
        try:
            import sqlite3 as _sql, json as _json
            from datetime import datetime as _dt, timezone as _tz
            DB = "/var/lib/murphy-production/entity_graph.db"
            org_id = payload.get("org_id")
            field = payload.get("field")           # e.g. "vision", "strategic_priorities"
            new_value = payload.get("new_value")
            if not org_id or not field:
                return {"gate": "PATCH-387-ORG-SOUL-EDIT", "status": "ERROR",
                        "error": "org_id and field required"}
            allowed = {"vision","mission","market_position","business_plan_json",
                       "strategic_priorities","competitive_landscape","constraints",
                       "kpis_org_json","culture_values","risk_appetite","org_name"}
            if field not in allowed:
                return {"gate": "PATCH-387-ORG-SOUL-EDIT", "status": "ERROR",
                        "error": f"field {field} not editable"}
            value_str = _json.dumps(new_value) if not isinstance(new_value, str) else new_value
            with _sql.connect(DB) as c:
                c.execute(f"UPDATE organizational_souls SET {field}=?, updated_at=? WHERE org_id=?",
                          (value_str, _dt.now(_tz.utc).isoformat(), org_id))
                c.commit()
            return {"gate": "PATCH-387-ORG-SOUL-EDIT", "status": "OK",
                    "org_id": org_id, "field": field, "applied_at": _dt.now(_tz.utc).isoformat()}
        except Exception as e:
            import traceback as _tb
            return {"gate": "PATCH-387-ORG-SOUL-EDIT", "status": "ERROR",
                    "error": str(e), "trace": _tb.format_exc()[:500]}


    @app.get("/api/dispatch/contextualized-soul")
    async def dispatch_contextualized_soul(agent_id: str = "platform_ceo",
                                           task: str = "review priorities",
                                           domain: str = "platform_executive",
                                           request: Request = None):
        """
        The full assembled soul for an agent at dispatch time:
          agent L0-L4  ⊕  org soul  ⊕  worldstate_slice(task-relevant)
        """
        try:
            import sqlite3 as _sql, json as _json
            from src.deep_soul_engine import build_deep_soul
            DB = "/var/lib/murphy-production/entity_graph.db"

            # 1) Agent's own layered soul
            agent_soul = build_deep_soul(
                agent_id=agent_id, role_title=agent_id, domain=domain,
                include_gmail_context=False,
            )

            # 2) Find the agent's org
            org_id = None
            with _sql.connect(DB) as c:
                c.row_factory = _sql.Row
                # Strategy: platform agents → platform org; tenant agents (id starts with tenant_) → tenant org
                if agent_id.startswith("platform_") or agent_id in ("sales_director","customer_success","support_agent"):
                    org_id = "murphy_systems_platform"
                else:
                    # Tenant agent — strip _ceo/_cto etc to find parent tenant
                    parts = agent_id.rsplit("_", 1)
                    if len(parts) == 2:
                        possible_org = parts[0]
                        row = c.execute("SELECT org_id FROM organizational_souls WHERE org_id=?",
                                        (possible_org,)).fetchone()
                        if row: org_id = row["org_id"]

                # 3) Load org soul
                org_soul_text = ""
                org_subs = []
                if org_id:
                    row = c.execute("SELECT * FROM organizational_souls WHERE org_id=?", (org_id,)).fetchone()
                    if row:
                        s = dict(row)
                        org_soul_text = f"""# ORGANIZATIONAL SOUL — {s.get('org_name','')}
**Type:** {s.get('org_type','')}
**Vision:** {s.get('vision','')}
**Mission:** {s.get('mission','')}
**Market position:** {s.get('market_position','')}
**Risk appetite:** {s.get('risk_appetite','')}

## Strategic priorities
{s.get('strategic_priorities','')}

## Competitive landscape
{s.get('competitive_landscape','')}

## Constraints
{s.get('constraints','')}

## Culture / values
{s.get('culture_values','')}
"""
                    org_subs = [dict(r) for r in c.execute(
                        "SELECT domain, relevance_weight FROM worldstate_subscriptions WHERE org_id=? AND auto_inject_to_l4=1",
                        (org_id,)).fetchall()]

            # 4) Pull WorldState slice for subscribed domains
            worldstate_text = ""
            try:
                from src.world_state_engine import world_state as _ws
                ws_engine = _ws
                snapshot = ws_engine.current_snapshot() if hasattr(ws_engine, 'current_snapshot') else None
                if snapshot and org_subs:
                    parts = ["# WORLD STATE — domains your org subscribes to"]
                    domains_dict = getattr(snapshot, 'domains', {}) or {}
                    if not isinstance(domains_dict, dict):
                        domains_dict = snapshot.to_dict().get('domains', {}) if hasattr(snapshot, 'to_dict') else {}
                    for sub in org_subs:
                        dname = sub["domain"]
                        dval = domains_dict.get(dname)
                        if dval:
                            score = dval.get("stability_score") if isinstance(dval, dict) else getattr(dval, "stability_score", None)
                            signals = dval.get("raw_signals") if isinstance(dval, dict) else getattr(dval, "raw_signals", {})
                            parts.append(f"**{dname}** (relevance={sub['relevance_weight']}): score={score}")
                            if signals:
                                for k,v in list(signals.items())[:4]:
                                    parts.append(f"  - {k}: {v}")
                    worldstate_text = "\\n".join(parts)
            except Exception as we:
                worldstate_text = f"# WORLD STATE — (unavailable: {str(we)[:80]})"

            # 5) Assemble the full soul
            agent_text = agent_soul.get("full_soul", "") or "\\n\\n".join(
                agent_soul.get(k, "") for k in ("L0","L1","L2","L3","L4") if agent_soul.get(k))

            full = "\\n\\n".join(filter(None, [org_soul_text, agent_text, worldstate_text]))

            return {
                "gate": "PATCH-387-CONTEXTUALIZED-SOUL",
                "status": "OK",
                "agent_id": agent_id,
                "org_id": org_id,
                "task": task,
                "composition": {
                    "agent_layers_chars": sum(len(agent_soul.get(k,"")) for k in ("L0","L1","L2","L3","L4")),
                    "org_soul_chars": len(org_soul_text),
                    "worldstate_chars": len(worldstate_text),
                    "total_chars": len(full),
                    "subscribed_worldstate_domains": [s["domain"] for s in org_subs],
                },
                "full_soul": full,
            }
        except Exception as e:
            import traceback as _tb
            return {"gate": "PATCH-387-CONTEXTUALIZED-SOUL", "status": "ERROR",
                    "error": str(e), "trace": _tb.format_exc()[:500]}


    @app.get("/api/world/business-domains")
    async def world_business_domains_status(request: Request = None):
        """Show the 5 new PATCH-387 business-relevant WorldState domains."""
        try:
            from src.world_state_engine import world_state as _ws
            engine = _ws
            patch387_domains = ["soc2_hipaa_changes","competitive_saas","regulatory_general",
                                "construction_starts","ashrae_nec_updates"]
            registered = {d: (d in engine._fetchers) for d in patch387_domains}
            # Try a live fetch of each
            results = {}
            for d in patch387_domains:
                if registered.get(d):
                    try:
                        reading = engine._fetchers[d]()
                        results[d] = {
                            "registered": True,
                            "stability_score": reading.stability_score,
                            "confidence": reading.confidence,
                            "signal_keys": list((reading.raw_signals or {}).keys()),
                        }
                    except Exception as fe:
                        results[d] = {"registered": True, "fetch_error": str(fe)[:100]}
                else:
                    results[d] = {"registered": False}
            return {
                "gate": "PATCH-387-BUSINESS-DOMAINS",
                "status": "OK",
                "domains": results,
                "total_engine_domains": len(engine._fetchers),
            }
        except Exception as e:
            return {"gate": "PATCH-387-BUSINESS-DOMAINS", "status": "ERROR", "error": str(e)}
'''
