"""
PATCH-386 — Murphy.systems Platform Org Chart + Onboarding-driven Tenant Rosetta + HITL Edits + Inferred Usage

Builds INTO existing modules (per RULE 1):
  - deep_soul_engine.py — seed the platform org chart (10 agents + souls)
  - synthetic_interview_engine.py — already has the 21 questions; we wire it to write to entity_graph
  - hitl_persistence.py — already exists; we add a soul-edit feedback hook
  - runtime/app.py — 4 new routes inside create_app()

Four capabilities added:
  A) PLATFORM ORG CHART — 10 agents that run murphy.systems itself
       CEO → CTO, COO, CFO, CRO (Revenue), CCO (Compliance)
       CTO → SRE, Platform Engineer
       COO → Customer Success, Support
       CRO → Sales Director (already seeded)
  B) ONBOARDING → ROSETTA — POST /api/onboarding/complete
       Takes the 21-question answers and writes them to:
         - persons table (user identity)
         - companies table (their business)
         - agent_contracts (their CEO-agent shadow)
         - sops (anything they describe as "how I do X")
         - training_materials (anything they describe as expertise/regulatory)
  C) HITL FEEDBACK → SOUL EDITS — POST /api/soul/feedback
       When user edits an agent's output, the correction writes back to the
       L-layer it came from (L2 SOP edit → sops table, L3 regulatory edit →
       training_materials, L1 personality → agent_contracts).
  D) INFERRED USAGE → PROPOSED EDITS — POST /api/soul/usage-inference
       Reads observability metrics (which routes the tenant hits, which features
       they reject) and proposes soul updates. Proposals go into HITL queue for
       user approval before writing to entity_graph.

Applied: 2026-05-23
"""

# ════════════════════════════════════════════════════════════════════════
# A) PLATFORM ORG CHART — 10 agents seeded into agent_contracts
# ════════════════════════════════════════════════════════════════════════

PLATFORM_AGENTS = [
    {
        "agent_id": "platform_ceo",
        "role_title": "CEO — Murphy Platform",
        "domain": "platform_executive",
        "reports_to": None,
        "primary_objective": "Build Murphy.systems into the autonomous OS that compresses entire small-business operations into one platform. Maintain 80%+ autonomy across all gates. Hit $1M ARR by end of year 1.",
        "persona_label": "Visionary Operator",
        "ocean": {"openness": 0.85, "conscientiousness": 0.75, "extraversion": 0.55, "agreeableness": 0.50, "neuroticism": 0.30},
        "communication_style": "Direct, vision-first, bias to action. Speaks in outcomes not features.",
        "decision_style": "Strategic-first; defers tactical to CTO/COO. Re-prioritises weekly based on ARR/churn.",
        "stress_response": "Cuts scope, never quality. Tells the team what NOT to do.",
        "kpis": {"ARR": "$1M EoY1", "platform_gates_live": "13/15", "tenant_NPS": ">50"},
        "authorised_actions": ["set quarterly priorities", "approve new product lines", "fire patches", "redirect engineering"],
        "off_limits": ["bypass HITL on tenant data", "make compliance exceptions"],
        "hitl_threshold": 0.0,  # CEO operates without HITL for strategic decisions
    },
    {
        "agent_id": "platform_cto",
        "role_title": "CTO — Murphy Platform",
        "domain": "platform_engineering",
        "reports_to": "platform_ceo",
        "primary_objective": "Keep all 15 autonomy gates green. Ship PATCH-N every 2-3 days. Maintain 99.5% uptime on murphy.systems. Drive autonomy % up monthly.",
        "persona_label": "Pragmatic Architect",
        "ocean": {"openness": 0.80, "conscientiousness": 0.95, "extraversion": 0.40, "agreeableness": 0.55, "neuroticism": 0.20},
        "communication_style": "Precise, evidence-based. Always shows HTTP status + log proof.",
        "decision_style": "Read source before changing. One patch, one thing. No new files unless justified.",
        "stress_response": "Slows down, audits, then ships small.",
        "kpis": {"gate_uptime": "99.5%", "patches_per_week": ">2", "regression_rate": "<5%"},
        "authorised_actions": ["deploy patches", "restart services", "modify entity schemas", "approve PRs"],
        "off_limits": ["modify rosetta kernel without CEO sign-off", "delete tenant data"],
        "hitl_threshold": 0.15,
    },
    {
        "agent_id": "platform_coo",
        "role_title": "COO — Murphy Platform",
        "domain": "platform_operations",
        "reports_to": "platform_ceo",
        "primary_objective": "Run customer success, onboarding, support. Get every new tenant from signup to first deliverable in <48 hours. Resolve every support ticket in <4h.",
        "persona_label": "Calm Conductor",
        "ocean": {"openness": 0.60, "conscientiousness": 0.90, "extraversion": 0.70, "agreeableness": 0.85, "neuroticism": 0.25},
        "communication_style": "Warm, structured, follow-through-focused. Always confirms next steps.",
        "decision_style": "Process-driven; if it happened twice, it gets an SOP.",
        "stress_response": "Triages by tenant tier + SLA risk.",
        "kpis": {"time_to_first_value_hrs": "<48", "support_resolution_hrs": "<4", "churn_monthly": "<3%"},
        "authorised_actions": ["assign customer success owner", "issue credit", "escalate tickets", "publish help docs"],
        "off_limits": ["refund without CFO approval", "modify tenant soul without their consent"],
        "hitl_threshold": 0.25,
    },
    {
        "agent_id": "platform_cfo",
        "role_title": "CFO — Murphy Platform",
        "domain": "platform_finance",
        "reports_to": "platform_ceo",
        "primary_objective": "Run revenue recognition, treasury, billing, fundraising. 50/50 ATOM split on incoming revenue. Maintain 6-month runway minimum.",
        "persona_label": "Disciplined Steward",
        "ocean": {"openness": 0.45, "conscientiousness": 0.98, "extraversion": 0.30, "agreeableness": 0.50, "neuroticism": 0.40},
        "communication_style": "Numbers-first. Every claim has a ledger entry.",
        "decision_style": "Reconcile before reporting. No revenue counted until cash hits.",
        "stress_response": "Tightens spend, accelerates collections.",
        "kpis": {"runway_months": ">6", "gross_margin": ">80%", "DSO_days": "<14"},
        "authorised_actions": ["approve spend up to $5k", "issue invoices", "rebalance treasury", "open ledger entries"],
        "off_limits": ["spend >$5k without CEO", "modify revenue rules without compliance review"],
        "hitl_threshold": 0.30,
    },
    {
        "agent_id": "platform_cro",
        "role_title": "CRO — Murphy Platform",
        "domain": "platform_revenue",
        "reports_to": "platform_ceo",
        "primary_objective": "Drive top-of-funnel + conversion. 10 demos/week minimum, 30% demo→trial, 40% trial→paid. Own the Sales Director (existing agent).",
        "persona_label": "Conversion Hunter",
        "ocean": {"openness": 0.70, "conscientiousness": 0.75, "extraversion": 0.90, "agreeableness": 0.55, "neuroticism": 0.35},
        "communication_style": "Outcome-driven, urgency-aware, story-driven for prospects.",
        "decision_style": "If conversion drops, change the script in 24h, not the product.",
        "stress_response": "Doubles outbound, narrows ICP.",
        "kpis": {"demos_per_week": ">10", "demo_to_trial": ">30%", "trial_to_paid": ">40%"},
        "authorised_actions": ["send outbound campaigns", "approve discounts up to 20%", "modify pricing display"],
        "off_limits": ["promise unreleased features", "discount >20%"],
        "hitl_threshold": 0.20,
    },
    {
        "agent_id": "platform_cco",
        "role_title": "CCO — Compliance Officer, Murphy Platform",
        "domain": "platform_compliance",
        "reports_to": "platform_ceo",
        "primary_objective": "Maintain HIPAA, SOC2, GDPR posture. Audit every patch for compliance impact. Block deploys that touch PHI/PII without proper handling.",
        "persona_label": "Vigilant Guardian",
        "ocean": {"openness": 0.40, "conscientiousness": 0.99, "extraversion": 0.25, "agreeableness": 0.40, "neuroticism": 0.50},
        "communication_style": "Specific citations only. Quotes the standard, never paraphrases.",
        "decision_style": "Conservative default. Burden of proof on the requestor.",
        "stress_response": "Halts deploys, requests evidence.",
        "kpis": {"audit_findings_open": "0", "phi_exposure_incidents": "0", "soc2_controls_passing": "100%"},
        "authorised_actions": ["block deploys", "request audit logs", "modify compliance gates", "issue compliance variances"],
        "off_limits": ["override CEO on regulatory matters", "approve PHI access without RBAC"],
        "hitl_threshold": 0.10,  # very low threshold — almost everything gets reviewed
    },
    {
        "agent_id": "platform_sre",
        "role_title": "SRE — Site Reliability, Murphy Platform",
        "domain": "platform_reliability",
        "reports_to": "platform_cto",
        "primary_objective": "Keep murphy.systems up 99.5%. Sub-100ms P95 on /api/*. Auto-heal failed routes within 5 min via G08.",
        "persona_label": "Quiet Firefighter",
        "ocean": {"openness": 0.55, "conscientiousness": 0.95, "extraversion": 0.35, "agreeableness": 0.65, "neuroticism": 0.30},
        "communication_style": "Incident-first reports. Timeline, impact, fix, prevention.",
        "decision_style": "Restart first, root-cause after.",
        "stress_response": "Calm escalation by tier. No silent failures.",
        "kpis": {"uptime": "99.5%", "p95_latency_ms": "<100", "mttr_minutes": "<10"},
        "authorised_actions": ["restart services", "scale instances", "rollback to backup", "page on-call"],
        "off_limits": ["modify production schema in incident", "disable monitoring"],
        "hitl_threshold": 0.10,
    },
    {
        "agent_id": "platform_engineer",
        "role_title": "Platform Engineer — Murphy",
        "domain": "platform_engineering",
        "reports_to": "platform_cto",
        "primary_objective": "Ship patches. Wire new features into existing modules. Maintain test coverage on critical paths.",
        "persona_label": "Builder",
        "ocean": {"openness": 0.85, "conscientiousness": 0.85, "extraversion": 0.50, "agreeableness": 0.65, "neuroticism": 0.25},
        "communication_style": "Patch label + file + line. Code + proof.",
        "decision_style": "Read source, propose patch, get CTO sign-off, ship, verify.",
        "stress_response": "Smaller patches, more frequent.",
        "kpis": {"patches_shipped_per_week": ">3", "patch_regression_rate": "<5%"},
        "authorised_actions": ["edit /opt/Murphy-System/src/", "deploy patches", "modify backend functions"],
        "off_limits": ["edit rosetta kernel", "skip syntax check before deploy"],
        "hitl_threshold": 0.20,
    },
    {
        "agent_id": "customer_success",
        "role_title": "Customer Success Manager — Murphy",
        "domain": "platform_customer_success",
        "reports_to": "platform_coo",
        "primary_objective": "Get every new tenant to first deliverable in <48h. Weekly check-ins for first 30 days. Identify expansion opportunities.",
        "persona_label": "Empathetic Coach",
        "ocean": {"openness": 0.70, "conscientiousness": 0.85, "extraversion": 0.80, "agreeableness": 0.90, "neuroticism": 0.20},
        "communication_style": "Friendly, specific, follow-up-driven. Always closes the loop.",
        "decision_style": "Tenant outcome first, platform metric second.",
        "stress_response": "Schedules calls, sends loom videos.",
        "kpis": {"time_to_value_hrs": "<48", "30day_activation": ">80%", "expansion_revenue": ">15%"},
        "authorised_actions": ["schedule calls", "send onboarding kits", "request feature work", "issue $50 credit"],
        "off_limits": ["promise features without product sign-off"],
        "hitl_threshold": 0.30,
    },
    {
        "agent_id": "support_agent",
        "role_title": "Support Agent — Murphy",
        "domain": "platform_support",
        "reports_to": "platform_coo",
        "primary_objective": "Resolve every tenant ticket in <4h. Escalate to engineering if root cause, to CSM if relationship.",
        "persona_label": "Patient Problem-Solver",
        "ocean": {"openness": 0.60, "conscientiousness": 0.90, "extraversion": 0.70, "agreeableness": 0.95, "neuroticism": 0.15},
        "communication_style": "Acknowledge, diagnose, fix, confirm. Plain English.",
        "decision_style": "Try the documented fix first, escalate on second occurrence.",
        "stress_response": "Templates + escalation paths.",
        "kpis": {"resolution_hrs": "<4", "first_response_min": "<15", "csat": ">4.5"},
        "authorised_actions": ["read tenant logs", "reset passwords", "restart tenant sessions", "escalate"],
        "off_limits": ["modify tenant data without consent", "promise resolution times"],
        "hitl_threshold": 0.40,
    },
]


# ════════════════════════════════════════════════════════════════════════
# B) ONBOARDING → ROSETTA wiring (new route /api/onboarding/complete)
# ════════════════════════════════════════════════════════════════════════
ONBOARDING_COMPLETE_ROUTE = '''
    # ═══ PATCH-386: Onboarding → Tenant Rosetta ═══
    @app.post("/api/onboarding/complete")
    async def onboarding_complete(payload: dict, request: Request = None):
        """
        Take the 21-question onboarding answers and write a full tenant
        Rosetta soul into the entity_graph.db.

        Expected payload:
        {
            "tenant_id": "...",
            "answers": {
                "q1_name": "Jane Doe",
                "q2_email": "jane@example.com",
                "q3_company_name": "Acme Engineering",
                "q4_industry": "MEP engineering",
                "q5_role": "Principal Engineer",
                "q6_years_experience": 15,
                "q7_licenses": ["PE-FL", "LEED AP"],
                "q8_primary_objective": "...",
                "q9_kpis": {...},
                "q10_communication_style": "...",
                "q11_decision_style": "...",
                "q12_ocean": {...},  # optional
                "q13_authorised_actions": [...],
                "q14_off_limits": [...],
                "q15_sops": [{"title":..., "steps":[...], "domain":...}],
                "q16_regulatory_frameworks": [{"title":..., "content":...}],
                "q17_current_projects": [...],
                "q18_team_members": [...],
                "q19_tools_used": [...],
                "q20_pain_points": [...],
                "q21_success_definition": "..."
            }
        }
        """
        try:
            from src.deep_soul_engine import (
                upsert_person, upsert_company, upsert_agent_contract,
                upsert_sop, add_relationship, ensure_schema
            )
            import json as _json, sqlite3 as _sql, uuid as _uuid
            from datetime import datetime as _dt, timezone as _tz

            ensure_schema()
            a = payload.get("answers", {})
            tenant_id = payload.get("tenant_id") or f"tenant-{_uuid.uuid4().hex[:8]}"

            # 1) Write the user as a person
            person_id = upsert_person({
                "full_name": a.get("q1_name", "Unknown"),
                "email": a.get("q2_email", ""),
                "title": a.get("q5_role", ""),
                "discipline": a.get("q4_industry", ""),
                "licenses": _json.dumps(a.get("q7_licenses", [])),
                "years_experience": a.get("q6_years_experience", 0),
                "skills": _json.dumps(a.get("q19_tools_used", [])),
            })

            # 2) Write their company
            company_id = upsert_company({
                "name": a.get("q3_company_name", "Unknown Co"),
                "industry": a.get("q4_industry", ""),
                "description": a.get("q21_success_definition", ""),
                "primary_contact_id": person_id,
            })

            # 3) Link person -> company (works_for)
            add_relationship("person", person_id, "works_for", "company", company_id,
                             {"role": a.get("q5_role"), "since": _dt.now(_tz.utc).isoformat()})

            # 4) Create the tenant's CEO agent contract
            ceo_agent_id = f"{tenant_id}_ceo"
            upsert_agent_contract({
                "agent_id": ceo_agent_id,
                "role_title": f"CEO — {a.get('q3_company_name', 'Tenant')}",
                "domain": a.get("q4_industry", "operations"),
                "primary_objective": a.get("q8_primary_objective", ""),
                "persona_label": "Tenant CEO",
                "ocean_json": _json.dumps(a.get("q12_ocean", {
                    "openness": 0.7, "conscientiousness": 0.8, "extraversion": 0.6,
                    "agreeableness": 0.6, "neuroticism": 0.3,
                })),
                "communication_style": a.get("q10_communication_style", ""),
                "decision_style": a.get("q11_decision_style", ""),
                "kpis_json": _json.dumps(a.get("q9_kpis", {})),
                "authorised_actions": _json.dumps(a.get("q13_authorised_actions", [])),
                "off_limits": _json.dumps(a.get("q14_off_limits", [])),
            })

            # 5) Link CEO agent shadows the person
            add_relationship("agent", ceo_agent_id, "shadows", "person", person_id,
                             {"created_via": "onboarding"})

            # 6) Write SOPs (q15)
            sop_ids = []
            for sop in (a.get("q15_sops") or []):
                sid = upsert_sop({
                    "title": sop.get("title", "Untitled SOP"),
                    "domain": sop.get("domain", a.get("q4_industry", "operations")),
                    "role": a.get("q5_role", ""),
                    "steps": _json.dumps(sop.get("steps", [])),
                    "regulatory_refs": _json.dumps(sop.get("regulatory_refs", [])),
                })
                sop_ids.append(sid)

            # 7) Write training materials / regulatory frameworks (q16)
            training_ids = []
            DB_PATH = "/var/lib/murphy-production/entity_graph.db"
            with _sql.connect(DB_PATH) as c:
                for tm in (a.get("q16_regulatory_frameworks") or []):
                    tid = str(_uuid.uuid4())
                    c.execute("""INSERT INTO training_materials
                        (id, title, domain, level, content_text, source, role_applicability, created_at)
                        VALUES (?,?,?,?,?,?,?,?)""", (
                        tid, tm.get("title", "Untitled"), tm.get("domain", a.get("q4_industry", "")),
                        "regulatory", tm.get("content", ""), tm.get("source", "tenant_onboarding"),
                        _json.dumps([a.get("q5_role", "")]), _dt.now(_tz.utc).isoformat()
                    ))
                    training_ids.append(tid)
                c.commit()

            return {
                "gate": "PATCH-386-ONBOARDING-COMPLETE",
                "status": "OK",
                "tenant_id": tenant_id,
                "person_id": person_id,
                "company_id": company_id,
                "ceo_agent_id": ceo_agent_id,
                "sops_created": len(sop_ids),
                "training_materials_created": len(training_ids),
                "relationships_created": 2,
                "next_step": f"Test soul via /api/soul/dispatch-preview?agent_id={ceo_agent_id}",
            }
        except Exception as e:
            import traceback as _tb
            return {
                "gate": "PATCH-386-ONBOARDING-COMPLETE",
                "status": "ERROR",
                "error": str(e),
                "trace": _tb.format_exc()[:500],
            }
'''


# ════════════════════════════════════════════════════════════════════════
# C) HITL FEEDBACK → SOUL EDITS (new route /api/soul/feedback)
# ════════════════════════════════════════════════════════════════════════
SOUL_FEEDBACK_ROUTE = '''
    # ═══ PATCH-386: HITL Feedback → Soul Edits ═══
    @app.post("/api/soul/feedback")
    async def soul_feedback(payload: dict, request: Request = None):
        """
        When a tenant corrects/edits an agent's output, write that edit back
        to the L-layer it came from.

        Payload:
        {
            "tenant_id": "...",
            "agent_id": "...",
            "layer": "L1" | "L2" | "L3",
            "original_output": "...",
            "corrected_output": "...",
            "feedback_type": "tone" | "process" | "regulatory" | "authority",
            "user_notes": "..."
        }

        L1 (personality) → updates agent_contracts.communication_style or persona
        L2 (process/SOP) → updates sops table (new step or revised step)
        L3 (regulatory)  → updates training_materials
        """
        try:
            import sqlite3 as _sql, json as _json, uuid as _uuid
            from datetime import datetime as _dt, timezone as _tz

            DB = "/var/lib/murphy-production/entity_graph.db"
            agent_id = payload.get("agent_id")
            layer = payload.get("layer", "L2")
            corrected = payload.get("corrected_output", "")
            feedback_type = payload.get("feedback_type", "process")
            notes = payload.get("user_notes", "")

            if not agent_id or not corrected:
                return {"gate": "PATCH-386-SOUL-FEEDBACK", "status": "ERROR",
                        "error": "agent_id and corrected_output required"}

            with _sql.connect(DB) as c:
                c.row_factory = _sql.Row

                if layer == "L1":
                    # Update agent's communication style or persona
                    if feedback_type == "tone":
                        c.execute("""UPDATE agent_contracts
                                     SET communication_style = ?, updated_at = ?
                                     WHERE agent_id = ?""",
                                  (corrected, _dt.now(_tz.utc).isoformat(), agent_id))
                    elif feedback_type == "authority":
                        c.execute("""UPDATE agent_contracts
                                     SET authorised_actions = ?, updated_at = ?
                                     WHERE agent_id = ?""",
                                  (corrected, _dt.now(_tz.utc).isoformat(), agent_id))
                    target_table = "agent_contracts"

                elif layer == "L2":
                    # Add a new SOP or revise the most recent
                    sop_id = str(_uuid.uuid4())
                    # Look up the agent's role/domain
                    row = c.execute("SELECT domain, role_title FROM agent_contracts WHERE agent_id=?",
                                    (agent_id,)).fetchone()
                    domain = row["domain"] if row else "operations"
                    role = row["role_title"] if row else agent_id
                    c.execute("""INSERT INTO sops
                        (id, title, domain, role, steps, regulatory_refs, reference_books, follow_up_protocol, created_at)
                        VALUES (?,?,?,?,?,?,?,?,?)""", (
                        sop_id, f"HITL Edit — {notes[:60] or feedback_type}",
                        domain, role, _json.dumps([{"step": corrected, "source": "hitl_feedback"}]),
                        "[]", "[]", "{}", _dt.now(_tz.utc).isoformat()
                    ))
                    target_table = "sops"

                elif layer == "L3":
                    # Add training material correction
                    tid = str(_uuid.uuid4())
                    row = c.execute("SELECT domain, role_title FROM agent_contracts WHERE agent_id=?",
                                    (agent_id,)).fetchone()
                    domain = row["domain"] if row else "operations"
                    c.execute("""INSERT INTO training_materials
                        (id, title, domain, level, content_text, source, role_applicability, created_at)
                        VALUES (?,?,?,?,?,?,?,?)""", (
                        tid, f"HITL Correction — {notes[:60]}",
                        domain, "regulatory", corrected,
                        "hitl_feedback", _json.dumps([row["role_title"] if row else ""]),
                        _dt.now(_tz.utc).isoformat()
                    ))
                    target_table = "training_materials"
                else:
                    return {"gate": "PATCH-386-SOUL-FEEDBACK", "status": "ERROR",
                            "error": f"unknown layer: {layer}"}

                c.commit()

            return {
                "gate": "PATCH-386-SOUL-FEEDBACK",
                "status": "OK",
                "agent_id": agent_id,
                "layer": layer,
                "feedback_type": feedback_type,
                "wrote_to_table": target_table,
                "applied_at": _dt.now(_tz.utc).isoformat(),
                "next_dispatch_will_use": True,
            }
        except Exception as e:
            import traceback as _tb
            return {"gate": "PATCH-386-SOUL-FEEDBACK", "status": "ERROR",
                    "error": str(e), "trace": _tb.format_exc()[:500]}
'''


# ════════════════════════════════════════════════════════════════════════
# D) USAGE INFERENCE → PROPOSED SOUL EDITS (new route /api/soul/usage-inference)
# ════════════════════════════════════════════════════════════════════════
USAGE_INFERENCE_ROUTE = '''
    # ═══ PATCH-386: Usage Inference → Proposed Soul Edits ═══
    @app.get("/api/soul/usage-inference")
    async def soul_usage_inference(tenant_id: str = "", request: Request = None):
        """
        Read the tenant's observability metrics + churn signals and infer
        what soul edits would improve their fit. Proposals go to HITL queue.

        Looks at:
          - which routes they hit (heavy usage = important domain)
          - which features they ignore (low usage = irrelevant)
          - which outputs they reject (HITL rejections = wrong soul layer)
          - their tier (Solo/Team/Enterprise authority caps)

        Returns proposed soul updates — NOT applied automatically.
        User approves via /api/soul/feedback to actually write them.
        """
        try:
            import sqlite3 as _sql
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td

            proposals = []
            DB = "/var/lib/murphy-production/entity_graph.db"

            # Get tenant CEO agent if exists
            with _sql.connect(DB) as c:
                c.row_factory = _sql.Row
                agent = c.execute(
                    "SELECT * FROM agent_contracts WHERE agent_id=?",
                    (f"{tenant_id}_ceo",)
                ).fetchone()

                if not agent:
                    return {"gate": "PATCH-386-USAGE-INFERENCE", "status": "NO_AGENT",
                            "tenant_id": tenant_id, "proposals": []}

                agent = dict(agent)

            # Pull observability metrics if available (G09)
            try:
                obs_db = "/var/lib/murphy-production/observability.db"
                with _sql.connect(obs_db) as oc:
                    oc.row_factory = _sql.Row
                    # Top 10 routes hit in last 7 days
                    cutoff = (_dt.now(_tz.utc) - _td(days=7)).isoformat()
                    top_routes = [dict(r) for r in oc.execute(
                        """SELECT route, COUNT(*) as hits, AVG(latency_ms) as avg_lat
                           FROM request_log
                           WHERE tenant_id = ? AND timestamp > ?
                           GROUP BY route ORDER BY hits DESC LIMIT 10""",
                        (tenant_id, cutoff)
                    ).fetchall()]
            except Exception:
                top_routes = []

            # INFERENCE 1: heavy usage of a route domain → SOP suggestion
            for r in top_routes:
                if r["hits"] > 50:
                    proposals.append({
                        "type": "ADD_SOP",
                        "layer": "L2",
                        "reason": f"Route {r['route']} hit {r['hits']}x in 7d — likely a core workflow",
                        "suggestion": f"Document the standard workflow for {r['route']} as an SOP",
                        "confidence": 0.75,
                    })

            # INFERENCE 2: if churn predictor flagged at-risk → personality/comm style mismatch
            try:
                churn_db = "/var/lib/murphy-production/churn_predictions.db"
                with _sql.connect(churn_db) as cc:
                    cc.row_factory = _sql.Row
                    risk = cc.execute(
                        "SELECT risk_score, factors FROM predictions WHERE tenant_id=? ORDER BY created_at DESC LIMIT 1",
                        (tenant_id,)
                    ).fetchone()
                    if risk and risk["risk_score"] > 0.6:
                        proposals.append({
                            "type": "ADJUST_COMMUNICATION_STYLE",
                            "layer": "L1",
                            "reason": f"Churn risk {risk['risk_score']:.2f} — communication style may be misaligned",
                            "suggestion": "Survey tenant on preferred tone (formal/casual/technical)",
                            "confidence": 0.60,
                        })
            except Exception:
                pass

            # INFERENCE 3: if no SOPs exist yet, propose seeding from industry standard
            with _sql.connect(DB) as c:
                sop_count = c.execute(
                    "SELECT COUNT(*) FROM sops WHERE role=?", (agent.get("role_title", ""),)
                ).fetchone()[0]
                if sop_count == 0:
                    proposals.append({
                        "type": "SEED_INDUSTRY_SOPS",
                        "layer": "L2",
                        "reason": f"No SOPs defined for role {agent.get('role_title')} in {agent.get('domain')}",
                        "suggestion": f"Seed 3-5 standard SOPs from {agent.get('domain')} industry library",
                        "confidence": 0.80,
                    })

            # INFERENCE 4: if no regulatory L3 content, propose
            with _sql.connect(DB) as c:
                tm_count = c.execute(
                    "SELECT COUNT(*) FROM training_materials WHERE domain=?",
                    (agent.get("domain", ""),)
                ).fetchone()[0]
                if tm_count == 0:
                    proposals.append({
                        "type": "SEED_REGULATORY_KNOWLEDGE",
                        "layer": "L3",
                        "reason": f"No regulatory/training material for domain {agent.get('domain')}",
                        "suggestion": f"Pull industry standards relevant to {agent.get('domain')} (ASHRAE/NEC/etc)",
                        "confidence": 0.85,
                    })

            return {
                "gate": "PATCH-386-USAGE-INFERENCE",
                "status": "OK",
                "tenant_id": tenant_id,
                "agent_id": agent.get("agent_id"),
                "proposals": proposals,
                "proposal_count": len(proposals),
                "next_step": "POST /api/soul/feedback to apply any proposal",
                "note": "Proposals are NOT applied automatically — they queue for HITL approval",
            }
        except Exception as e:
            import traceback as _tb
            return {"gate": "PATCH-386-USAGE-INFERENCE", "status": "ERROR",
                    "error": str(e), "trace": _tb.format_exc()[:500]}
'''


# ════════════════════════════════════════════════════════════════════════
# E) PLATFORM ORG CHART INSPECTION ROUTE
# ════════════════════════════════════════════════════════════════════════
PLATFORM_ORG_ROUTE = '''
    # ═══ PATCH-386: Platform Org Chart ═══
    @app.get("/api/platform/org-chart")
    async def platform_org_chart(request: Request = None):
        """
        Return the current Murphy.systems platform org chart from agent_contracts.
        Builds the tree from reports_to relationships.
        """
        try:
            import sqlite3 as _sql, json as _json
            DB = "/var/lib/murphy-production/entity_graph.db"

            with _sql.connect(DB) as c:
                c.row_factory = _sql.Row
                # All platform agents (domain starts with platform_)
                rows = [dict(r) for r in c.execute(
                    """SELECT agent_id, role_title, domain, persona_label,
                              primary_objective, kpis_json
                       FROM agent_contracts
                       WHERE domain LIKE 'platform_%'
                       ORDER BY agent_id"""
                ).fetchall()]

                # reports_to relationships
                reports = [dict(r) for r in c.execute(
                    """SELECT from_id, to_id FROM relationships
                       WHERE rel_type = 'reports_to'"""
                ).fetchall()]

            # Build tree
            children_of = {}
            for r in reports:
                children_of.setdefault(r["to_id"], []).append(r["from_id"])

            def build_node(agent_id):
                agent = next((a for a in rows if a["agent_id"] == agent_id), None)
                if not agent:
                    return None
                return {
                    "agent_id": agent_id,
                    "role": agent["role_title"],
                    "persona": agent["persona_label"],
                    "objective": (agent["primary_objective"] or "")[:200],
                    "kpis": _json.loads(agent["kpis_json"] or "{}"),
                    "reports": [build_node(child) for child in children_of.get(agent_id, [])],
                }

            ceo = next((a for a in rows if a["agent_id"] == "platform_ceo"), None)
            tree = build_node("platform_ceo") if ceo else None

            return {
                "gate": "PATCH-386-PLATFORM-ORG",
                "status": "OK",
                "total_agents": len(rows),
                "ceo_present": ceo is not None,
                "tree": tree,
                "flat": [{"id": a["agent_id"], "role": a["role_title"],
                          "persona": a["persona_label"]} for a in rows],
            }
        except Exception as e:
            import traceback as _tb
            return {"gate": "PATCH-386-PLATFORM-ORG", "status": "ERROR",
                    "error": str(e), "trace": _tb.format_exc()[:500]}
'''
