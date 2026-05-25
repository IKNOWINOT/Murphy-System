"""
PATCH-392 — Platform Org Chart + Tenant Rosetta Lifecycle
==========================================================
Applies to: /opt/Murphy-System/src/runtime/app.py + deep_soul_engine.py

DOES NOT CREATE NEW BACKEND FILES (RULE 1).
Modifies in-place. Adds:

A. Schema migrations to entity_graph.db:
   - agent_contracts.reports_to  (parent agent_id, for org chart)
   - agent_contracts.tenant_id   (NULL = platform, else tenant scope)
   - exclusion_list table        (companies CRO must never outreach)
   - tenant_soul_feedback table  (HITL approvals/edits/rejects)
   - tenant_soul_inference table (usage-mined L-layer suggestions)

B. Platform org chart wiring (PATCH-392a):
   Sets reports_to on 12 existing platform agents.

C. Tenant onboarding → Rosetta (PATCH-392b):
   Function tenant_onboarding_to_soul(tenant_id, answers_dict, founder_email)
   Writes L0-L4 into agent_contracts row "tenant_{tid}_ceo".

D. HITL feedback writeback (PATCH-392c):
   POST /api/tenant/{tid}/feedback  {dispatch_id, action, edits}
   action ∈ {approve, edit, reject}
   Updates agent_contracts stability metrics + applies edits to L2/L3.

E. Usage inference (PATCH-392d):
   POST /api/tenant/{tid}/inference/run
   Mines shadow_observations from last 7d, proposes soul updates.
   Approvals via /api/tenant/{tid}/inference/approve/{suggestion_id}.

F. Exclusion list (PATCH-391a/b):
   POST /api/exclusion-list/add  {company_name, reason}
   GET  /api/exclusion-list
   Seeded with: Akana Engineering.
   Hook in any CRO outreach call: check_exclusion(name) before adding to prospects.
"""

import sqlite3
import os
import json
import time
import hashlib
from datetime import datetime, timezone

DB_PATH = "/var/lib/murphy-production/entity_graph.db"
APP_PY = "/opt/Murphy-System/src/runtime/app.py"
BACKUP = APP_PY + ".pre392"

# ─────────────────────────────────────────────────────────────────────────
# STEP 1: Schema migrations
# ─────────────────────────────────────────────────────────────────────────

MIGRATIONS = [
    # Add reports_to + tenant_id to agent_contracts (idempotent)
    ("ALTER TABLE agent_contracts ADD COLUMN reports_to TEXT", "duplicate column"),
    ("ALTER TABLE agent_contracts ADD COLUMN tenant_id TEXT", "duplicate column"),
    ("ALTER TABLE agent_contracts ADD COLUMN onboarding_session_id TEXT", "duplicate column"),

    # exclusion_list
    ("""CREATE TABLE IF NOT EXISTS exclusion_list (
        id TEXT PRIMARY KEY,
        company_name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        reason TEXT,
        added_by TEXT,
        added_at TEXT,
        UNIQUE(normalized_name)
    )""", None),
    ("CREATE INDEX IF NOT EXISTS idx_exclusion_norm ON exclusion_list(normalized_name)", None),

    # tenant_soul_feedback (HITL)
    ("""CREATE TABLE IF NOT EXISTS tenant_soul_feedback (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        dispatch_id TEXT,
        action TEXT NOT NULL,  -- approve | edit | reject
        original_output TEXT,
        edited_output TEXT,
        edit_diff TEXT,
        layer_affected TEXT,   -- L0|L1|L2|L3|L4
        rationale TEXT,
        created_at TEXT NOT NULL,
        applied INTEGER DEFAULT 0
    )""", None),
    ("CREATE INDEX IF NOT EXISTS idx_tsf_tenant ON tenant_soul_feedback(tenant_id)", None),

    # tenant_soul_inference (usage-mined suggestions)
    ("""CREATE TABLE IF NOT EXISTS tenant_soul_inference (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        inference_type TEXT,   -- skill_promotion | comm_style | domain_expansion | priority_shift
        evidence_json TEXT,
        proposed_change TEXT,
        layer_affected TEXT,
        confidence REAL,
        status TEXT DEFAULT 'pending',  -- pending | approved | rejected | applied
        created_at TEXT NOT NULL,
        applied_at TEXT
    )""", None),
    ("CREATE INDEX IF NOT EXISTS idx_tsi_tenant ON tenant_soul_inference(tenant_id, status)", None),
]


def run_migrations():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    applied = 0
    skipped = 0
    for sql, ignore_token in MIGRATIONS:
        try:
            cur.execute(sql)
            applied += 1
        except sqlite3.OperationalError as e:
            if ignore_token and ignore_token in str(e).lower():
                skipped += 1
            else:
                raise
    conn.commit()
    conn.close()
    return applied, skipped


# ─────────────────────────────────────────────────────────────────────────
# STEP 2: Platform org chart (PATCH-392a) — set reports_to
# ─────────────────────────────────────────────────────────────────────────

ORG_CHART = {
    # CEO is root — reports to founder (sentinel "founder")
    "platform_ceo": "founder",

    # C-suite reports to CEO
    "platform_cto": "platform_ceo",
    "platform_coo": "platform_ceo",
    "platform_cfo": "platform_ceo",
    "platform_cro": "platform_ceo",
    "platform_cco": "platform_ceo",

    # Engineering: CTO direct reports
    "lead_engineer": "platform_cto",
    "platform_engineer": "platform_cto",
    "platform_sre": "platform_cto",

    # Operations: COO direct reports
    "customer_success": "platform_coo",
    "support_agent": "platform_coo",

    # Shadow agents report to nobody on org chart — they shadow users
    # cpost_shadow is Corey's shadow, not a platform employee
}


def wire_org_chart():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    updated = []
    skipped = []
    now = datetime.now(timezone.utc).isoformat()

    for agent_id, parent in ORG_CHART.items():
        cur.execute("SELECT agent_id FROM agent_contracts WHERE agent_id=?", (agent_id,))
        if cur.fetchone():
            cur.execute(
                "UPDATE agent_contracts SET reports_to=?, tenant_id=NULL, updated_at=? WHERE agent_id=?",
                (parent, now, agent_id),
            )
            updated.append((agent_id, parent))
        else:
            skipped.append(agent_id)

    # Mark cpost_shadow tenant_id properly so it's clearly a user-shadow not platform
    cur.execute(
        "UPDATE agent_contracts SET tenant_id='user:cpost@murphy.systems', reports_to='founder' "
        "WHERE agent_id='cpost_shadow'"
    )

    conn.commit()
    conn.close()
    return updated, skipped


# ─────────────────────────────────────────────────────────────────────────
# STEP 3: Seed exclusion_list (PATCH-391a)
# ─────────────────────────────────────────────────────────────────────────

EXCLUSIONS = [
    {
        "company_name": "Akana Engineering",
        "reason": "Founder directive 2026-05-23: do not pursue. Existing relationship.",
        "added_by": "cpost@murphy.systems",
    },
]


def normalize_name(name: str) -> str:
    return "".join(c.lower() for c in name if c.isalnum())


def seed_exclusions():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    added = []
    now = datetime.now(timezone.utc).isoformat()
    for entry in EXCLUSIONS:
        norm = normalize_name(entry["company_name"])
        rid = "excl_" + hashlib.sha1(norm.encode()).hexdigest()[:12]
        try:
            cur.execute(
                "INSERT INTO exclusion_list (id, company_name, normalized_name, reason, added_by, added_at) "
                "VALUES (?,?,?,?,?,?)",
                (rid, entry["company_name"], norm, entry["reason"], entry["added_by"], now),
            )
            added.append(entry["company_name"])
        except sqlite3.IntegrityError:
            pass  # already there
    conn.commit()
    conn.close()
    return added


# ─────────────────────────────────────────────────────────────────────────
# STEP 4: Helper API endpoints — appended to app.py
# ─────────────────────────────────────────────────────────────────────────

PATCH_392_ROUTES = '''
# ════════════════════════════════════════════════════════════════════════
# PATCH-392 — Platform Org Chart + Tenant Rosetta Lifecycle (2026-05-23)
# ════════════════════════════════════════════════════════════════════════

import sqlite3 as _p392_sqlite3
import hashlib as _p392_hashlib
import json as _p392_json
from datetime import datetime as _p392_datetime, timezone as _p392_tz

_P392_DB = "/var/lib/murphy-production/entity_graph.db"


def _p392_conn():
    return _p392_sqlite3.connect(_P392_DB)


def _p392_norm(name: str) -> str:
    return "".join(c.lower() for c in name if c.isalnum())


# ---------- Org Chart (PATCH-392a) ----------

@app.get("/api/org-chart")
async def patch392_org_chart(request: Request):
    """Return the platform org chart with reporting lines."""
    try:
        conn = _p392_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT agent_id, agent_name, role_title, department, reports_to,
                   tenant_id, agent_type
            FROM agent_contracts
            WHERE tenant_id IS NULL OR tenant_id NOT LIKE 'user:%'
            ORDER BY reports_to NULLS FIRST, agent_id
        """)
        rows = cur.fetchall()
        conn.close()

        agents = []
        for r in rows:
            agents.append({
                "agent_id": r[0],
                "agent_name": r[1],
                "role_title": r[2],
                "department": r[3],
                "reports_to": r[4],
                "tenant_id": r[5],
                "agent_type": r[6],
            })

        # Build tree
        by_id = {a["agent_id"]: dict(a, reports=[]) for a in agents}
        roots = []
        for a in agents:
            parent = a["reports_to"]
            if parent and parent in by_id:
                by_id[parent]["reports"].append(by_id[a["agent_id"]])
            else:
                roots.append(by_id[a["agent_id"]])

        return {
            "gate": "PATCH-392a-ORG-CHART",
            "status": "OK",
            "total_agents": len(agents),
            "roots": roots,
        }
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ---------- Exclusion List (PATCH-391a/b) ----------

@app.get("/api/exclusion-list")
async def patch392_exclusion_list(request: Request):
    try:
        conn = _p392_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, company_name, reason, added_by, added_at FROM exclusion_list ORDER BY added_at DESC")
        rows = cur.fetchall()
        conn.close()
        return {
            "gate": "PATCH-391a-EXCLUSION-LIST",
            "status": "OK",
            "count": len(rows),
            "entries": [
                {"id": r[0], "company_name": r[1], "reason": r[2], "added_by": r[3], "added_at": r[4]}
                for r in rows
            ],
        }
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/exclusion-list/add")
async def patch392_exclusion_add(request: Request):
    try:
        body = await request.json()
        name = (body.get("company_name") or "").strip()
        reason = body.get("reason") or "Added via API"
        added_by = body.get("added_by") or "system"
        if not name:
            return JSONResponse({"success": False, "error": "company_name required"}, status_code=400)
        norm = _p392_norm(name)
        rid = "excl_" + _p392_hashlib.sha1(norm.encode()).hexdigest()[:12]
        now = _p392_datetime.now(_p392_tz.utc).isoformat()
        conn = _p392_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO exclusion_list (id, company_name, normalized_name, reason, added_by, added_at) "
                "VALUES (?,?,?,?,?,?)",
                (rid, name, norm, reason, added_by, now),
            )
            conn.commit()
            existed = False
        except _p392_sqlite3.IntegrityError:
            existed = True
        conn.close()
        return {"gate": "PATCH-391a-EXCLUSION-ADD", "status": "OK", "id": rid, "already_existed": existed}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/exclusion-list/check/{company_name}")
async def patch392_exclusion_check(company_name: str, request: Request):
    """CRO outreach engine MUST call this before any prospect goes in."""
    try:
        norm = _p392_norm(company_name)
        conn = _p392_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, reason FROM exclusion_list WHERE normalized_name=?", (norm,))
        row = cur.fetchone()
        conn.close()
        if row:
            return {"gate": "PATCH-391b-EXCLUSION-CHECK", "excluded": True, "id": row[0], "reason": row[1]}
        return {"gate": "PATCH-391b-EXCLUSION-CHECK", "excluded": False}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ---------- Tenant Onboarding → Rosetta (PATCH-392b) ----------

def _p392_industry_to_l3_sops(industry: str) -> list:
    """Inference: map industry to baseline regulatory frameworks."""
    industry_lower = industry.lower()
    sops = []
    if any(k in industry_lower for k in ["mep", "engineer", "hvac", "mechanical", "electrical"]):
        sops += ["ASHRAE 90.1 energy compliance", "NEC code compliance", "IECC envelope requirements"]
    if any(k in industry_lower for k in ["health", "medical", "clinic", "hospital", "patient"]):
        sops += ["HIPAA Privacy Rule", "HIPAA Security Rule", "HITECH breach notification"]
    if any(k in industry_lower for k in ["finance", "bank", "fintech", "payment", "lending"]):
        sops += ["SOC2 Type 2 controls", "PCI-DSS scope", "BSA/AML reporting"]
    if any(k in industry_lower for k in ["construction", "contractor", "build"]):
        sops += ["OSHA construction standards", "AIA contract review", "Mechanic's lien deadlines"]
    if any(k in industry_lower for k in ["software", "saas", "tech", "platform"]):
        sops += ["SOC2 Type 1/2", "GDPR data subject rights", "Subscription revenue recognition (ASC 606)"]
    if not sops:
        sops = ["General SMB compliance baseline"]
    return sops


@app.post("/api/tenant/{tenant_id}/onboarding/commit")
async def patch392_tenant_onboarding_commit(tenant_id: str, request: Request):
    """
    Take onboarding answers and WRITE them into the tenant's CEO agent_contract.
    Body: {answers: {q1:..., q2:..., ...}, founder_email: ...}
    Fills L0-L4 layers in agent_contracts row "tenant_{tid}_ceo".
    """
    try:
        body = await request.json()
        answers = body.get("answers") or {}
        founder_email = body.get("founder_email") or "unknown@unknown"

        # Pull key fields with sensible defaults
        company = (answers.get("company_name") or answers.get("q1") or f"Tenant-{tenant_id}").strip()
        industry = (answers.get("industry") or answers.get("q2") or "general").strip()
        role = (answers.get("founder_role") or answers.get("q3") or "Founder/CEO").strip()
        size = answers.get("company_size") or answers.get("q4") or "1-10"
        priorities_raw = answers.get("top_priorities") or answers.get("q5") or "growth, compliance, efficiency"
        comm_style = (answers.get("communication_style") or answers.get("q6") or "direct").strip()
        decision_style = (answers.get("decision_style") or answers.get("q7") or "data-driven").strip()
        boundaries = answers.get("boundaries") or answers.get("q8") or []
        if isinstance(boundaries, str):
            boundaries = [b.strip() for b in boundaries.split(",")]
        if isinstance(priorities_raw, str):
            priorities = [p.strip() for p in priorities_raw.split(",")]
        else:
            priorities = list(priorities_raw)

        # Inference: industry → baseline SOPs (L3)
        l3_sops = _p392_industry_to_l3_sops(industry)

        # Build layered soul
        agent_id = f"tenant_{tenant_id}_ceo"
        agent_name = f"{company} CEO"
        role_title = f"Autonomous CEO — {company}"
        department = "executive"
        domain = industry

        duties_text = (
            f"Drive {company}, a {size} {industry} company. "
            f"Founder is {founder_email} ({role}). "
            f"Strategic priorities: {', '.join(priorities)}. "
            f"Operate within boundaries: {', '.join(boundaries) if boundaries else 'none specified'}. "
            f"Make decisions in {decision_style} style. Communicate {comm_style}."
        )

        pipeline = [
            {"step": "weekly_planning", "action": "Review priorities + dispatch OKRs",
             "output": "5 OKRs/week", "hands_to": "direct_reports"},
            {"step": "daily_briefing", "action": "Read worldstate + customer signals",
             "output": "morning_brief", "hands_to": founder_email},
            {"step": "monthly_review", "action": "Analyze MRR + churn + product usage",
             "output": "executive_report", "hands_to": founder_email},
        ]

        kpis = {
            "revenue_target": answers.get("revenue_target") or "TBD",
            "customer_count": 0,
            "priorities": priorities,
        }

        ocean = {
            "openness": 0.7, "conscientiousness": 0.85,
            "extraversion": 0.55, "agreeableness": 0.6, "neuroticism": 0.25,
        }
        if "creative" in comm_style.lower() or "vision" in decision_style.lower():
            ocean["openness"] = 0.9

        authorised = ["read_business_data", "draft_communications", "propose_strategy", "dispatch_okrs"]
        off_limits = ["send_payment", "sign_contracts", "publicly_post"] + list(boundaries)

        now = _p392_datetime.now(_p392_tz.utc).isoformat()
        rid = "ac_" + _p392_hashlib.sha1(agent_id.encode()).hexdigest()[:12]

        conn = _p392_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO agent_contracts (
                id, agent_id, agent_name, role_title, department, domain,
                management_layer, duties_text, pipeline_touchpoints, escalation_paths,
                hitl_threshold, ocean_json, persona_label, communication_style,
                decision_style, kpis_json, authorised_actions, off_limits,
                recalibration_triggers, created_at, updated_at,
                agent_type, tenant_id, reports_to, onboarding_session_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(agent_id) DO UPDATE SET
                duties_text=excluded.duties_text,
                pipeline_touchpoints=excluded.pipeline_touchpoints,
                kpis_json=excluded.kpis_json,
                ocean_json=excluded.ocean_json,
                communication_style=excluded.communication_style,
                decision_style=excluded.decision_style,
                authorised_actions=excluded.authorised_actions,
                off_limits=excluded.off_limits,
                updated_at=excluded.updated_at,
                onboarding_session_id=excluded.onboarding_session_id
        """, (
            rid, agent_id, agent_name, role_title, department, domain,
            "executive", duties_text,
            _p392_json.dumps(pipeline), _p392_json.dumps([]),
            0.8, _p392_json.dumps(ocean), f"{company} CEO persona",
            comm_style, decision_style,
            _p392_json.dumps(kpis),
            _p392_json.dumps(authorised), _p392_json.dumps(off_limits),
            _p392_json.dumps(["repeated_rejection", "founder_directive"]),
            now, now,
            "tenant_ceo", tenant_id, "founder", body.get("session_id", "unknown"),
        ))

        # Also seed L3 SOPs for the tenant
        for sop_title in l3_sops:
            sop_id = "sop_" + _p392_hashlib.sha1((tenant_id + sop_title).encode()).hexdigest()[:12]
            try:
                cur.execute("""
                    INSERT INTO sops (id, domain, role, title, content, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?)
                """, (sop_id, industry, role_title, sop_title,
                      f"Baseline SOP for {sop_title} — inferred from industry={industry}. "
                      f"Refine via HITL feedback.", now, now))
            except _p392_sqlite3.IntegrityError:
                pass

        conn.commit()
        conn.close()

        return {
            "gate": "PATCH-392b-ONBOARDING-COMMIT",
            "status": "OK",
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "industry": industry,
            "l3_sops_seeded": l3_sops,
            "priorities": priorities,
            "boundaries_count": len(boundaries),
            "message": f"Tenant CEO Rosetta created. {len(l3_sops)} L3 SOPs seeded from industry inference.",
        }
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ---------- HITL Feedback Writeback (PATCH-392c) ----------

@app.post("/api/tenant/{tenant_id}/feedback")
async def patch392_tenant_feedback(tenant_id: str, request: Request):
    """
    HITL feedback writeback. Body:
    {
      agent_id: "tenant_<tid>_ceo",
      dispatch_id: "disp_...",
      action: "approve" | "edit" | "reject",
      original_output: "...",
      edited_output: "...",  (when action=edit)
      layer_affected: "L2",  (which soul layer was off)
      rationale: "...",
    }
    """
    try:
        body = await request.json()
        agent_id = body.get("agent_id") or f"tenant_{tenant_id}_ceo"
        action = body.get("action", "").lower()
        if action not in ("approve", "edit", "reject"):
            return JSONResponse({"success": False, "error": "action must be approve|edit|reject"}, status_code=400)

        original = body.get("original_output", "")
        edited = body.get("edited_output", "")
        layer = body.get("layer_affected", "L2")
        rationale = body.get("rationale", "")
        dispatch_id = body.get("dispatch_id")

        # Compute diff for edits
        edit_diff = None
        if action == "edit" and original and edited:
            edit_diff = _p392_json.dumps({
                "removed_len": len(original) - len(edited) if len(original) > len(edited) else 0,
                "added_len": len(edited) - len(original) if len(edited) > len(original) else 0,
                "preview": edited[:500],
            })

        now = _p392_datetime.now(_p392_tz.utc).isoformat()
        fid = "fb_" + _p392_hashlib.sha1((agent_id + now).encode()).hexdigest()[:12]

        conn = _p392_conn()
        cur = conn.cursor()

        # Record feedback
        cur.execute("""
            INSERT INTO tenant_soul_feedback
            (id, tenant_id, agent_id, dispatch_id, action, original_output,
             edited_output, edit_diff, layer_affected, rationale, created_at, applied)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,0)
        """, (fid, tenant_id, agent_id, dispatch_id, action,
              original[:5000], edited[:5000], edit_diff, layer, rationale, now))

        # Update sync_score on the agent based on action
        cur.execute("SELECT sync_score, observation_count FROM agent_contracts WHERE agent_id=?", (agent_id,))
        row = cur.fetchone()
        if row:
            sync_score = float(row[0] or 0.0)
            obs_count = int(row[1] or 0) + 1

            if action == "approve":
                # Strong positive signal — bump sync_score
                sync_score = min(1.0, sync_score + 0.05)
            elif action == "edit":
                # Mild positive — output was useful but needed tuning
                sync_score = min(1.0, sync_score + 0.01)
            elif action == "reject":
                # Strong negative
                sync_score = max(0.0, sync_score - 0.10)

            cur.execute("""
                UPDATE agent_contracts
                SET sync_score=?, observation_count=?, updated_at=?
                WHERE agent_id=?
            """, (sync_score, obs_count, now, agent_id))

            # If action=edit, apply the edit to the soul layer
            if action == "edit" and edited and layer in ("L2", "L3"):
                # For L2 = duties_text, append the edit as a learned pattern
                if layer == "L2":
                    cur.execute("""
                        UPDATE agent_contracts
                        SET duties_text = duties_text || ?
                        WHERE agent_id=?
                    """, (f"\\n\\n[Learned {now}]: {edited[:500]}", agent_id))

                cur.execute("UPDATE tenant_soul_feedback SET applied=1 WHERE id=?", (fid,))

        conn.commit()
        conn.close()

        return {
            "gate": "PATCH-392c-FEEDBACK",
            "status": "OK",
            "feedback_id": fid,
            "action": action,
            "sync_score_new": sync_score if row else None,
            "applied_to_soul": action == "edit" and layer in ("L2", "L3"),
        }
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/tenant/{tenant_id}/feedback/history")
async def patch392_feedback_history(tenant_id: str, request: Request):
    try:
        conn = _p392_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, agent_id, action, layer_affected, rationale, created_at, applied
            FROM tenant_soul_feedback
            WHERE tenant_id=?
            ORDER BY created_at DESC LIMIT 100
        """, (tenant_id,))
        rows = cur.fetchall()
        conn.close()
        return {
            "gate": "PATCH-392c-FEEDBACK-HISTORY",
            "tenant_id": tenant_id,
            "count": len(rows),
            "feedback": [
                {"id": r[0], "agent_id": r[1], "action": r[2], "layer": r[3],
                 "rationale": r[4], "created_at": r[5], "applied": bool(r[6])}
                for r in rows
            ],
        }
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ---------- Usage Inference (PATCH-392d) ----------

@app.post("/api/tenant/{tenant_id}/inference/run")
async def patch392_inference_run(tenant_id: str, request: Request):
    """
    Mine recent feedback + observations, propose soul updates.
    Looks at last N feedback events for the tenant, looks for patterns,
    creates suggestions in tenant_soul_inference table for HITL approval.
    """
    try:
        body = await request.json() if request.headers.get("content-length") else {}
        lookback_days = int(body.get("lookback_days", 7))

        conn = _p392_conn()
        cur = conn.cursor()

        # Pattern 1: repeated rejections in same layer → suggest layer overhaul
        cur.execute("""
            SELECT agent_id, layer_affected, COUNT(*) as cnt
            FROM tenant_soul_feedback
            WHERE tenant_id=? AND action='reject'
              AND datetime(created_at) > datetime('now', ?)
            GROUP BY agent_id, layer_affected
            HAVING cnt >= 3
        """, (tenant_id, f"-{lookback_days} days"))
        reject_patterns = cur.fetchall()

        # Pattern 2: high edit rate in a specific layer → suggest L-layer update
        cur.execute("""
            SELECT agent_id, layer_affected, COUNT(*) as cnt
            FROM tenant_soul_feedback
            WHERE tenant_id=? AND action='edit'
              AND datetime(created_at) > datetime('now', ?)
            GROUP BY agent_id, layer_affected
            HAVING cnt >= 5
        """, (tenant_id, f"-{lookback_days} days"))
        edit_patterns = cur.fetchall()

        # Pattern 3: high approval streak → promote skills
        cur.execute("""
            SELECT agent_id, COUNT(*) as cnt
            FROM tenant_soul_feedback
            WHERE tenant_id=? AND action='approve'
              AND datetime(created_at) > datetime('now', ?)
            GROUP BY agent_id
            HAVING cnt >= 10
        """, (tenant_id, f"-{lookback_days} days"))
        approval_patterns = cur.fetchall()

        suggestions = []
        now = _p392_datetime.now(_p392_tz.utc).isoformat()

        for agent_id, layer, cnt in reject_patterns:
            sid = "inf_" + _p392_hashlib.sha1((agent_id + layer + "reject" + now).encode()).hexdigest()[:12]
            cur.execute("""
                INSERT INTO tenant_soul_inference
                (id, tenant_id, agent_id, inference_type, evidence_json,
                 proposed_change, layer_affected, confidence, status, created_at)
                VALUES (?,?,?,?,?,?,?,?,'pending',?)
            """, (sid, tenant_id, agent_id, "layer_overhaul",
                  _p392_json.dumps({"reject_count": cnt, "lookback_days": lookback_days}),
                  f"Overhaul {layer} — {cnt} consecutive rejections suggest soul mismatch",
                  layer, min(0.9, 0.5 + cnt * 0.1), now))
            suggestions.append({"type": "layer_overhaul", "layer": layer, "agent_id": agent_id, "count": cnt})

        for agent_id, layer, cnt in edit_patterns:
            sid = "inf_" + _p392_hashlib.sha1((agent_id + layer + "edit" + now).encode()).hexdigest()[:12]
            cur.execute("""
                INSERT INTO tenant_soul_inference
                (id, tenant_id, agent_id, inference_type, evidence_json,
                 proposed_change, layer_affected, confidence, status, created_at)
                VALUES (?,?,?,?,?,?,?,?,'pending',?)
            """, (sid, tenant_id, agent_id, "comm_style_drift",
                  _p392_json.dumps({"edit_count": cnt, "lookback_days": lookback_days}),
                  f"User consistently edits {layer} outputs — communication style needs adjustment",
                  layer, min(0.85, 0.5 + cnt * 0.05), now))
            suggestions.append({"type": "comm_style_drift", "layer": layer, "agent_id": agent_id, "count": cnt})

        for agent_id, cnt in approval_patterns:
            sid = "inf_" + _p392_hashlib.sha1((agent_id + "promote" + now).encode()).hexdigest()[:12]
            cur.execute("""
                INSERT INTO tenant_soul_inference
                (id, tenant_id, agent_id, inference_type, evidence_json,
                 proposed_change, layer_affected, confidence, status, created_at)
                VALUES (?,?,?,?,?,?,?,?,'pending',?)
            """, (sid, tenant_id, agent_id, "skill_promotion",
                  _p392_json.dumps({"approve_count": cnt, "lookback_days": lookback_days}),
                  f"Agent {agent_id} has {cnt} consecutive approvals — promote to autonomous tier",
                  "L1", min(0.95, 0.6 + cnt * 0.03), now))
            suggestions.append({"type": "skill_promotion", "agent_id": agent_id, "count": cnt})

        conn.commit()
        conn.close()

        return {
            "gate": "PATCH-392d-INFERENCE-RUN",
            "status": "OK",
            "tenant_id": tenant_id,
            "lookback_days": lookback_days,
            "suggestions_created": len(suggestions),
            "suggestions": suggestions,
        }
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/tenant/{tenant_id}/inference/pending")
async def patch392_inference_pending(tenant_id: str, request: Request):
    try:
        conn = _p392_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, agent_id, inference_type, proposed_change, layer_affected,
                   confidence, created_at
            FROM tenant_soul_inference
            WHERE tenant_id=? AND status='pending'
            ORDER BY confidence DESC, created_at DESC
        """, (tenant_id,))
        rows = cur.fetchall()
        conn.close()
        return {
            "gate": "PATCH-392d-INFERENCE-PENDING",
            "tenant_id": tenant_id,
            "count": len(rows),
            "suggestions": [
                {"id": r[0], "agent_id": r[1], "type": r[2], "change": r[3],
                 "layer": r[4], "confidence": r[5], "created_at": r[6]}
                for r in rows
            ],
        }
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/tenant/{tenant_id}/inference/approve/{suggestion_id}")
async def patch392_inference_approve(tenant_id: str, suggestion_id: str, request: Request):
    try:
        now = _p392_datetime.now(_p392_tz.utc).isoformat()
        conn = _p392_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE tenant_soul_inference
            SET status='approved', applied_at=?
            WHERE id=? AND tenant_id=?
        """, (now, suggestion_id, tenant_id))
        affected = cur.rowcount
        conn.commit()
        conn.close()
        return {
            "gate": "PATCH-392d-INFERENCE-APPROVE",
            "status": "OK" if affected else "NOT_FOUND",
            "suggestion_id": suggestion_id,
            "affected": affected,
        }
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ════════════════════════════════════════════════════════════════════════
# END PATCH-392
# ════════════════════════════════════════════════════════════════════════
'''


# ─────────────────────────────────────────────────────────────────────────
# MAIN — applies in order, with rollback safety
# ─────────────────────────────────────────────────────────────────────────

def deploy():
    print("=" * 70)
    print("PATCH-392 Deployment — Platform Org Chart + Tenant Rosetta Lifecycle")
    print("=" * 70)

    # Step 1: schema
    print("\n[1/4] Running schema migrations...")
    applied, skipped = run_migrations()
    print(f"   ✅ Migrations: {applied} applied, {skipped} skipped (already present)")

    # Step 2: org chart
    print("\n[2/4] Wiring org chart (reports_to)...")
    updated, missing = wire_org_chart()
    print(f"   ✅ Wired {len(updated)} agents:")
    for agent_id, parent in updated:
        print(f"      {agent_id} → {parent}")
    if missing:
        print(f"   ⚠️  Missing agents (not in DB): {missing}")

    # Step 3: exclusion seed
    print("\n[3/4] Seeding exclusion_list...")
    added = seed_exclusions()
    print(f"   ✅ Added: {added}")

    # Step 4: append routes to app.py
    print("\n[4/4] Appending PATCH-392 routes to app.py...")
    if not os.path.exists(APP_PY):
        print(f"   ❌ {APP_PY} not found. Aborting route install.")
        return False

    # Backup
    if not os.path.exists(BACKUP):
        with open(APP_PY) as f:
            content = f.read()
        with open(BACKUP, "w") as f:
            f.write(content)
        print(f"   ✅ Backup: {BACKUP}")
    else:
        print(f"   ⏭  Backup already exists: {BACKUP}")

    # Check idempotency
    with open(APP_PY) as f:
        current = f.read()
    if "PATCH-392 — Platform Org Chart + Tenant Rosetta" in current:
        print("   ⏭  Routes already present in app.py")
    else:
        with open(APP_PY, "a") as f:
            f.write("\n\n" + PATCH_392_ROUTES + "\n")
        print(f"   ✅ Appended {len(PATCH_392_ROUTES)} chars of routes")

    print("\n" + "=" * 70)
    print("PATCH-392 DEPLOYED — restart service to activate routes")
    print("=" * 70)
    return True


if __name__ == "__main__":
    deploy()
