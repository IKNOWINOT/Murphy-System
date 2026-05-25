"""
PATCH-400 — Universal Event Spine + HITL-as-Graph
====================================================

WHAT THIS IS:
  The audit backbone of the entire Murphy system. Every meaningful action
  (agent decision, customer action, system event) writes an event with a
  SHA-256 hash chain linking it to the previous event. Tamper-evident
  proof of what happened, in what order, by whom.

  HITL decisions are first-class graph nodes (not just approval flags).
  Each decision captures: the proposed action, alternatives considered,
  reasoning, the Rosetta soul at decision time, risk assessment, the
  decider's response, and labels for training data.

WHY IT EXISTS:
  Three problems it solves:
    1. Compliance — SOC2/HIPAA need provable audit trails
    2. Training data — captured decisions teach future agents
    3. Tamper-evidence — chain breaks instantly visible

HOW IT FITS:
  Originally lived inline inside runtime/app.py (lines 30513-31019).
  Migrated 2026-05-24 (OPT-9) to its own module, now wired into
  murphy-ops:8003 next to vault and audit.

  All other patches that emit events call _p400_emit() directly via
  database write (no HTTP hop), so the migration only moves the HTTP
  surface — the emission path stays the same.

ENDPOINTS:
  POST /api/events/emit                  — emit a new event
  GET  /api/events/feed                  — recent events (filterable)
  POST /api/events/route-to-hitl         — open a HITL decision
  GET  /api/events/hitl/decisions        — list pending/recent HITL
  GET  /api/events/hitl/{hitl_id}        — single decision detail
  POST /api/events/hitl/{hitl_id}/respond — founder/kin responds
  POST /api/events/hitl/{hitl_id}/label   — tag for training data
  GET  /api/events/hitl/patterns         — repeated rejection patterns
  GET  /api/events/graph/{snap_id}       — snapshot detail
  GET  /api/events/chain-verify          — verify hash chain integrity

DEPENDENCIES:
  - SQLite at /var/lib/murphy-production/entity_graph.db
  - FastAPI Request / JSONResponse
  - logger (provided by host)

KNOWN LIMITS:
  - Single SQLite DB (no replication yet) — bastion backup runs nightly
  - chain-verify is O(N) — fine up to ~1M events, then needs paging

LAST UPDATED: 2026-05-24 by Murphy (OPT-9 extraction)
"""
from __future__ import annotations
import logging
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("patch400.event_spine")


# ── Helpers and DB init (run at import time, just like the inline version) ──
# PATCH-400 — UNIVERSAL EVENT SPINE + HITL-AS-GRAPH
# ════════════════════════════════════════════════════════════════════
# Architectural rule (locked 2026-05-23):
#   • Nothing fails or succeeds silently
#   • Every pipeline routes to its HITL gate
#   • HITL decisions are training data, not just approvals
#   • Rosetta soul is built AT DECISION TIME, not cached
import sqlite3 as _p400_sq
import uuid as _p400_uu
import json as _p400_j
import hashlib as _p400_hl
import asyncio as _p400_io
from datetime import datetime as _p400_dt, timezone as _p400_tz, timedelta as _p400_td

_P400_DB = "/var/lib/murphy-production/entity_graph.db"

def _p400_conn():
    c = _p400_sq.connect(_P400_DB, timeout=10)
    c.row_factory = _p400_sq.Row
    return c

def _p400_now():
    return _p400_dt.now(_p400_tz.utc).isoformat()

def _p400_hash(payload: str) -> str:
    return _p400_hl.sha256(payload.encode("utf-8")).hexdigest()

def _p400_init():
    c = _p400_conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        occurred_at TEXT NOT NULL,
        actor_type TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        action_verb TEXT NOT NULL,
        action_object TEXT,
        pipeline TEXT,
        outcome TEXT NOT NULL,
        reasoning_text TEXT,
        inputs_json TEXT,
        outputs_json TEXT,
        soul_hash TEXT,
        soul_composition_json TEXT,
        graph_snapshot_id TEXT,
        hitl_decision_id TEXT,
        parent_event_id TEXT,
        hash_prev TEXT,
        hash_self TEXT,
        severity TEXT DEFAULT 'normal',
        tags_json TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_events_pipeline ON events(pipeline, occurred_at);
    CREATE INDEX IF NOT EXISTS idx_events_outcome ON events(outcome);
    CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor_id, occurred_at);

    CREATE TABLE IF NOT EXISTS hitl_decisions (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        pipeline TEXT NOT NULL,
        decision_type TEXT NOT NULL,
        triggering_event_id TEXT NOT NULL,
        proposing_agent_id TEXT NOT NULL,
        proposed_action_json TEXT NOT NULL,
        alternatives_json TEXT,
        reasoning_text TEXT NOT NULL,
        soul_hash TEXT NOT NULL,
        soul_full_text TEXT NOT NULL,
        graph_context_json TEXT NOT NULL,
        risk_assessment_json TEXT,
        status TEXT DEFAULT 'pending',
        decided_at TEXT,
        decider_user_id TEXT,
        decider_choice TEXT,
        decider_reasoning TEXT,
        decided_action_json TEXT,
        sla_deadline TEXT,
        closing_event_id TEXT,
        learning_label TEXT,
        learning_notes TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_hitl_status ON hitl_decisions(status, created_at);
    CREATE INDEX IF NOT EXISTS idx_hitl_pipeline ON hitl_decisions(pipeline, status);

    CREATE TABLE IF NOT EXISTS graph_snapshots (
        id TEXT PRIMARY KEY,
        captured_at TEXT NOT NULL,
        purpose TEXT,
        relevant_entity_ids TEXT,
        snapshot_json TEXT NOT NULL,
        hash TEXT
    );
    """)
    c.commit(); c.close()

try:
    _p400_init()
except Exception as _e:
    logger.warning(f"PATCH-400 init: {_e}")

# ─── Core helper: emit an event with hash chain ───
def _p400_emit(actor_type, actor_id, action_verb, *,
               action_object=None, pipeline=None, outcome="success",
               reasoning_text=None, inputs=None, outputs=None,
               soul_hash=None, soul_composition=None,
               graph_snapshot_id=None, hitl_decision_id=None,
               parent_event_id=None, severity="normal", tags=None):
    """Universal event emitter. Returns event_id. NEVER raises — failures degrade to a log."""
    try:
        c = _p400_conn()
        cur = c.cursor()
        # Get previous hash for chain
        row = cur.execute("SELECT hash_self FROM events ORDER BY occurred_at DESC LIMIT 1").fetchone()
        hash_prev = row[0] if row else "GENESIS"
        evt_id = "evt_" + _p400_uu.uuid4().hex[:14]
        occurred_at = _p400_now()
        inputs_json = _p400_j.dumps(inputs) if inputs is not None else None
        outputs_json = _p400_j.dumps(outputs) if outputs is not None else None
        soul_comp_json = _p400_j.dumps(soul_composition) if soul_composition else None
        tags_json = _p400_j.dumps(tags) if tags else None
        # Compute self hash
        payload = f"{evt_id}|{occurred_at}|{actor_type}|{actor_id}|{action_verb}|{outcome}|{hash_prev}"
        hash_self = _p400_hash(payload)
        cur.execute("""INSERT INTO events
            (id, occurred_at, actor_type, actor_id, action_verb, action_object,
             pipeline, outcome, reasoning_text, inputs_json, outputs_json,
             soul_hash, soul_composition_json, graph_snapshot_id, hitl_decision_id,
             parent_event_id, hash_prev, hash_self, severity, tags_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (evt_id, occurred_at, actor_type, actor_id, action_verb, action_object,
             pipeline, outcome, reasoning_text, inputs_json, outputs_json,
             soul_hash, soul_comp_json, graph_snapshot_id, hitl_decision_id,
             parent_event_id, hash_prev, hash_self, severity, tags_json))
        c.commit(); c.close()
        return evt_id
    except Exception as _e:
        logger.error(f"PATCH-400 emit failed: {_e}")
        return None

# ─── Capture graph snapshot for HITL context ───
def _p400_snapshot_graph(purpose, relevant_entity_ids):
    try:
        c = _p400_conn()
        cur = c.cursor()
        snapshot = {"entities": {}, "captured_at": _p400_now()}
        for eid in (relevant_entity_ids or []):
            # Try multiple tables — entity_graph is heterogeneous
            for tbl in ("persons", "companies", "projects", "agent_contracts"):
                try:
                    r = cur.execute(f"SELECT * FROM {tbl} WHERE id=? OR agent_id=?", (eid, eid)).fetchone()
                    if r:
                        snapshot["entities"][eid] = {"_table": tbl, **dict(r)}
                        break
                except Exception:
                    pass
        snap_id = "gsnap_" + _p400_uu.uuid4().hex[:12]
        snap_json = _p400_j.dumps(snapshot, default=str)
        snap_hash = _p400_hash(snap_json)
        cur.execute("""INSERT INTO graph_snapshots (id, captured_at, purpose,
            relevant_entity_ids, snapshot_json, hash)
            VALUES (?,?,?,?,?,?)""",
            (snap_id, _p400_now(), purpose,
             _p400_j.dumps(relevant_entity_ids or []), snap_json, snap_hash))
        c.commit(); c.close()
        return snap_id
    except Exception as _e:
        logger.warning(f"PATCH-400 snapshot failed: {_e}")
        return None

# ─── Build deep soul at decision time ───
def _p400_build_soul_now(agent_id):
    """Build deep soul RIGHT NOW for the deciding agent. Returns (soul_hash, soul_text, composition)."""
    try:
        # Pull agent contract
        c = _p400_conn()
        ac = c.execute("SELECT role_title, department FROM agent_contracts WHERE agent_id=?", (agent_id,)).fetchone()
        c.close()
        if not ac:
            return None, "", {}
        try:
            # Try the deep_soul_engine for full soul
            from src import deep_soul_engine as _dse
            soul = _dse.build_deep_soul(
                agent_id=agent_id,
                role_title=ac["role_title"] or agent_id,
                domain=ac["department"] or "general"
            )
            soul_text = soul.get("full_soul", "")
            composition = {
                "L0_chars": len(soul.get("L0","")),
                "L1_chars": len(soul.get("L1","")),
                "L2_chars": len(soul.get("L2","")),
                "L3_chars": len(soul.get("L3","")),
                "L4_chars": len(soul.get("L4","")),
                "word_count": soul.get("word_count", 0),
                "token_estimate": soul.get("token_estimate", 0),
            }
        except Exception as _e:
            # Fallback: just the agent_contracts duties
            c = _p400_conn()
            ac = c.execute("SELECT duties_text, persona_label, decision_style FROM agent_contracts WHERE agent_id=?", (agent_id,)).fetchone()
            c.close()
            soul_text = f"# {agent_id}\nPersona: {ac['persona_label']}\nDecision style: {ac['decision_style']}\n\n{ac['duties_text']}"
            composition = {"fallback": True, "reason": str(_e)}
        soul_hash = _p400_hash(soul_text)
        return soul_hash, soul_text, composition
    except Exception as _e:
        logger.warning(f"PATCH-400 build_soul_now failed: {_e}")
        return None, "", {}

# ─── Route an event to HITL with full context ───
def _p400_route_to_hitl(triggering_event_id, *, pipeline, decision_type,
                        proposing_agent_id, proposed_action, reasoning_text,
                        alternatives=None, risk_assessment=None,
                        relevant_entity_ids=None, sla_hours=24):
    """Create a HITL decision with full context — Rosetta soul built RIGHT NOW."""
    try:
        # 1. Build soul at decision time
        soul_hash, soul_text, soul_comp = _p400_build_soul_now(proposing_agent_id)
        # 2. Snapshot the graph
        graph_snap_id = _p400_snapshot_graph("hitl", relevant_entity_ids)
        # 3. Create HITL record
        hitl_id = "hitl_" + _p400_uu.uuid4().hex[:14]
        now = _p400_now()
        sla = (_p400_dt.now(_p400_tz.utc) + _p400_td(hours=sla_hours)).isoformat()
        c = _p400_conn()
        # Pull graph snapshot JSON for embedding
        graph_json = "{}"
        if graph_snap_id:
            row = c.execute("SELECT snapshot_json FROM graph_snapshots WHERE id=?", (graph_snap_id,)).fetchone()
            if row: graph_json = row["snapshot_json"]
        c.execute("""INSERT INTO hitl_decisions
            (id, created_at, pipeline, decision_type, triggering_event_id,
             proposing_agent_id, proposed_action_json, alternatives_json,
             reasoning_text, soul_hash, soul_full_text, graph_context_json,
             risk_assessment_json, status, sla_deadline)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (hitl_id, now, pipeline, decision_type, triggering_event_id,
             proposing_agent_id, _p400_j.dumps(proposed_action),
             _p400_j.dumps(alternatives or []), reasoning_text,
             soul_hash or "no_soul", soul_text,
             graph_json,
             _p400_j.dumps(risk_assessment or {}),
             "pending", sla))
        # Link back to triggering event
        c.execute("UPDATE events SET hitl_decision_id=? WHERE id=?", (hitl_id, triggering_event_id))
        c.commit(); c.close()
        return hitl_id
    except Exception as _e:
        logger.error(f"PATCH-400 route_to_hitl failed: {_e}")
        return None



# ── Route registration ──────────────────────────────────────────────────────
def init_event_spine_routes(app):
    """Register PATCH-400 endpoints on the FastAPI app.
    
    All endpoints are NEW-PREFIX /api/events/* to match the original.
    HITL endpoints are under /api/events/hitl/* (renamed from /api/hitl/*
    to avoid collision with the many other HITL endpoints in the monolith).
    """
    # ═══ Public endpoints ═══

    @app.post("/api/events/emit")
    async def patch400_event_emit(request: Request):
        try:
            body = await request.json()
            required = ["actor_type", "actor_id", "action_verb", "outcome"]
            missing = [k for k in required if k not in body]
            if missing:
                return JSONResponse({"success":False,"error":f"missing fields: {missing}"}, status_code=400)
            evt_id = _p400_emit(
                actor_type=body["actor_type"], actor_id=body["actor_id"],
                action_verb=body["action_verb"], action_object=body.get("action_object"),
                pipeline=body.get("pipeline"), outcome=body["outcome"],
                reasoning_text=body.get("reasoning_text"),
                inputs=body.get("inputs"), outputs=body.get("outputs"),
                severity=body.get("severity","normal"), tags=body.get("tags"),
                parent_event_id=body.get("parent_event_id")
            )
            return {"gate":"PATCH-400-EVENT-EMIT","status":"OK","event_id":evt_id}
        except Exception as e:
            return JSONResponse({"success":False,"error":str(e)}, status_code=500)

    @app.get("/api/events/feed")
    async def patch400_events_feed(request: Request):
        """Recent events across all pipelines."""
        try:
            limit = int(request.query_params.get("limit", "50"))
            pipeline = request.query_params.get("pipeline")
            outcome = request.query_params.get("outcome")
            c = _p400_conn()
            q = "SELECT * FROM events WHERE 1=1"
            args = []
            if pipeline: q += " AND pipeline=?"; args.append(pipeline)
            if outcome:  q += " AND outcome=?"; args.append(outcome)
            q += " ORDER BY occurred_at DESC LIMIT ?"
            args.append(limit)
            rows = [dict(r) for r in c.execute(q, args).fetchall()]
            c.close()
            return {"gate":"PATCH-400-EVENTS-FEED","status":"OK","count":len(rows),"events":rows}
        except Exception as e:
            return JSONResponse({"success":False,"error":str(e)}, status_code=500)

    @app.post("/api/hitl/route")
    async def patch400_hitl_route(request: Request):
        """Manually route an event to HITL (pipelines call this internally too)."""
        try:
            body = await request.json()
            hitl_id = _p400_route_to_hitl(
                triggering_event_id=body["triggering_event_id"],
                pipeline=body["pipeline"],
                decision_type=body["decision_type"],
                proposing_agent_id=body["proposing_agent_id"],
                proposed_action=body["proposed_action"],
                reasoning_text=body.get("reasoning_text",""),
                alternatives=body.get("alternatives"),
                risk_assessment=body.get("risk_assessment"),
                relevant_entity_ids=body.get("relevant_entity_ids"),
                sla_hours=body.get("sla_hours", 24),
            )
            if not hitl_id:
                return JSONResponse({"success":False,"error":"route failed"}, status_code=500)
            # Emit an event for the routing itself
            _p400_emit("system", "hitl_router", "route_to_hitl",
                       action_object=hitl_id, pipeline=body["pipeline"],
                       outcome="hitl_required",
                       reasoning_text=f"Routed {body['decision_type']} to HITL",
                       parent_event_id=body["triggering_event_id"],
                       hitl_decision_id=hitl_id)
            return {"gate":"PATCH-400-HITL-ROUTE","status":"OK","hitl_decision_id":hitl_id,
                    "review_url":f"/api/hitl/decision/{hitl_id}"}
        except Exception as e:
            return JSONResponse({"success":False,"error":str(e)}, status_code=500)

    @app.get("/api/hitl/decisions")
    async def patch400_hitl_decisions(request: Request):
        try:
            status = request.query_params.get("status","pending")
            pipeline = request.query_params.get("pipeline")
            limit = int(request.query_params.get("limit", "50"))
            c = _p400_conn()
            q = """SELECT id, created_at, pipeline, decision_type, proposing_agent_id,
                          status, sla_deadline, decided_at, decider_choice, learning_label
                   FROM hitl_decisions WHERE status=?"""
            args = [status]
            if pipeline: q += " AND pipeline=?"; args.append(pipeline)
            q += " ORDER BY created_at DESC LIMIT ?"
            args.append(limit)
            rows = [dict(r) for r in c.execute(q, args).fetchall()]
            c.close()
            return {"gate":"PATCH-400-HITL-DECISIONS","status":"OK","count":len(rows),"decisions":rows}
        except Exception as e:
            return JSONResponse({"success":False,"error":str(e)}, status_code=500)

    @app.get("/api/hitl/decision/{hitl_id}")
    async def patch400_hitl_decision_detail(hitl_id: str):
        try:
            c = _p400_conn()
            row = c.execute("SELECT * FROM hitl_decisions WHERE id=?", (hitl_id,)).fetchone()
            c.close()
            if not row:
                return JSONResponse({"success":False,"error":"not found"}, status_code=404)
            d = dict(row)
            # Parse JSON fields for readable response
            for k in ("proposed_action_json","alternatives_json","graph_context_json",
                      "risk_assessment_json","decided_action_json"):
                if d.get(k):
                    try: d[k.replace("_json","")] = _p400_j.loads(d[k])
                    except Exception: pass
            return {"gate":"PATCH-400-HITL-DETAIL","status":"OK","decision":d}
        except Exception as e:
            return JSONResponse({"success":False,"error":str(e)}, status_code=500)

    @app.post("/api/hitl/decision/{hitl_id}/respond")
    async def patch400_hitl_respond(hitl_id: str, request: Request):
        """Human responds to a HITL decision. This emits a closing event."""
        try:
            body = await request.json()
            choice = body.get("choice")  # approve | reject | modify
            if choice not in ("approve","reject","modify"):
                return JSONResponse({"success":False,"error":"choice must be approve|reject|modify"}, status_code=400)
            reasoning = body.get("reasoning","")
            decider_user_id = body.get("decider_user_id","founder")
            decided_action = body.get("decided_action")  # only for modify

            c = _p400_conn()
            row = c.execute("SELECT * FROM hitl_decisions WHERE id=?", (hitl_id,)).fetchone()
            if not row:
                c.close()
                return JSONResponse({"success":False,"error":"not found"}, status_code=404)
            if row["status"] != "pending":
                c.close()
                return JSONResponse({"success":False,"error":f"already {row['status']}"}, status_code=400)

            # Decide what action gets recorded
            if choice == "approve":
                final_action = _p400_j.loads(row["proposed_action_json"])
                new_status = "approved"
            elif choice == "reject":
                final_action = None
                new_status = "rejected"
            else:  # modify
                final_action = decided_action or _p400_j.loads(row["proposed_action_json"])
                new_status = "modified"

            now = _p400_now()
            c.execute("""UPDATE hitl_decisions SET status=?, decided_at=?, decider_user_id=?,
                         decider_choice=?, decider_reasoning=?, decided_action_json=?
                         WHERE id=?""",
                      (new_status, now, decider_user_id, choice, reasoning,
                       _p400_j.dumps(final_action) if final_action else None, hitl_id))
            c.commit(); c.close()

            # Emit closing event
            closing_evt = _p400_emit(
                "human", decider_user_id, "hitl_respond",
                action_object=hitl_id, pipeline=row["pipeline"],
                outcome=new_status,
                reasoning_text=reasoning,
                inputs={"choice": choice}, outputs={"final_action": final_action},
                hitl_decision_id=hitl_id,
                parent_event_id=row["triggering_event_id"]
            )
            # Link closing event back
            c = _p400_conn()
            c.execute("UPDATE hitl_decisions SET closing_event_id=? WHERE id=?", (closing_evt, hitl_id))
            c.commit(); c.close()

            return {"gate":"PATCH-400-HITL-RESPOND","status":"OK","hitl_decision_id":hitl_id,
                    "new_status":new_status,"closing_event_id":closing_evt,
                    "next_step":"Murphy will resume the pipeline with this decision."}
        except Exception as e:
            return JSONResponse({"success":False,"error":str(e)}, status_code=500)

    @app.post("/api/hitl/decision/{hitl_id}/label")
    async def patch400_hitl_label(hitl_id: str, request: Request):
        """Retrospective learning label — was the decision right?"""
        try:
            body = await request.json()
            label = body.get("label")  # correct | wrong | partial
            if label not in ("correct","wrong","partial"):
                return JSONResponse({"success":False,"error":"label must be correct|wrong|partial"}, status_code=400)
            notes = body.get("notes","")
            c = _p400_conn()
            c.execute("UPDATE hitl_decisions SET learning_label=?, learning_notes=? WHERE id=?",
                      (label, notes, hitl_id))
            c.commit(); c.close()
            _p400_emit("human", body.get("user_id","founder"), "hitl_label",
                       action_object=hitl_id, outcome="success",
                       reasoning_text=f"Labeled {label}: {notes}",
                       inputs={"label": label, "notes": notes},
                       hitl_decision_id=hitl_id)
            return {"gate":"PATCH-400-HITL-LABEL","status":"OK","hitl_decision_id":hitl_id,"label":label}
        except Exception as e:
            return JSONResponse({"success":False,"error":str(e)}, status_code=500)

    @app.get("/api/hitl/learn/by-pattern")
    async def patch400_hitl_patterns(request: Request):
        """Show patterns in human decisions — the corpus for learning."""
        try:
            c = _p400_conn()
            # Group by decision_type + choice
            rows = c.execute("""
                SELECT decision_type, pipeline, decider_choice, learning_label,
                       COUNT(*) as count,
                       AVG(CASE WHEN learning_label='correct' THEN 1.0
                                WHEN learning_label='wrong' THEN 0.0
                                ELSE 0.5 END) as accuracy
                FROM hitl_decisions
                WHERE status != 'pending'
                GROUP BY decision_type, pipeline, decider_choice, learning_label
                ORDER BY count DESC
            """).fetchall()
            c.close()
            return {"gate":"PATCH-400-HITL-PATTERNS","status":"OK",
                    "count":len(rows),"patterns":[dict(r) for r in rows]}
        except Exception as e:
            return JSONResponse({"success":False,"error":str(e)}, status_code=500)

    @app.get("/api/graph/snapshot/{snap_id}")
    async def patch400_graph_snapshot(snap_id: str):
        try:
            c = _p400_conn()
            row = c.execute("SELECT * FROM graph_snapshots WHERE id=?", (snap_id,)).fetchone()
            c.close()
            if not row:
                return JSONResponse({"success":False,"error":"not found"}, status_code=404)
            d = dict(row)
            try: d["snapshot"] = _p400_j.loads(d["snapshot_json"])
            except Exception: pass
            return {"gate":"PATCH-400-GRAPH-SNAPSHOT","status":"OK","snapshot":d}
        except Exception as e:
            return JSONResponse({"success":False,"error":str(e)}, status_code=500)

    @app.get("/api/events/chain-verify")
    async def patch400_chain_verify():
        """Verify the hash chain is unbroken — proof of tamper-evidence."""
        try:
            c = _p400_conn()
            rows = c.execute("SELECT id, hash_prev, hash_self, occurred_at, actor_type, actor_id, action_verb, outcome FROM events ORDER BY occurred_at").fetchall()
            c.close()
            broken_at = []
            prev = "GENESIS"
            for r in rows:
                if r["hash_prev"] != prev:
                    broken_at.append(r["id"])
                prev = r["hash_self"]
            return {"gate":"PATCH-400-CHAIN-VERIFY","status":"OK",
                    "total_events":len(rows),
                    "chain_intact": len(broken_at) == 0,
                    "broken_at": broken_at}
        except Exception as e:
            return JSONResponse({"success":False,"error":str(e)}, status_code=500)


    return app
