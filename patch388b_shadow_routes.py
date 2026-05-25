"""
PATCH-388b — Shadow Agent Routes

Adds 5 routes inside create_app(). Foundation (388a) already in place:
  - agent_contracts has agent_type / shadowing_user_id columns
  - user_worldstate/ DB infrastructure exists
  - Corey's Shadow seeded

Routes:
  POST /api/shadow/observe              record an observation event
  GET  /api/shadow/user-worldstate      current snapshot of user's graph
  GET  /api/shadow/predict              shadow predicts what user would do
  GET  /api/shadow/sync-status          overall + per-domain sync metrics
  GET  /api/shadow/skill-memory         learned skill patterns + confidence

Applied: 2026-05-22
"""

ROUTES_CODE = '''

    # ═══ PATCH-388b: Shadow Agent Routes ═══

    def _shadow_user_db_path(user_id: str) -> str:
        """Map user_id to its per-user worldstate DB path."""
        import re as _re, os as _os
        safe = _re.sub(r'[^a-zA-Z0-9_]', '_', user_id or 'anonymous')
        base = "/var/lib/murphy-production/user_worldstate"
        _os.makedirs(base, exist_ok=True)
        return f"{base}/{safe}.db"

    def _shadow_ensure_user_db(user_id: str) -> str:
        """Ensure a user_worldstate DB exists for this user, return its path."""
        import sqlite3 as _sql
        path = _shadow_user_db_path(user_id)
        SCHEMA = """
        CREATE TABLE IF NOT EXISTS user_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL, timestamp TEXT NOT NULL, domain TEXT NOT NULL,
            event_type TEXT NOT NULL, event_data TEXT,
            predicted TEXT, actual TEXT, sync_delta REAL, created_at TEXT);
        CREATE TABLE IF NOT EXISTS user_worldstate_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL, timestamp TEXT NOT NULL,
            domains_json TEXT NOT NULL, overall_sync REAL, snapshot_summary TEXT);
        CREATE TABLE IF NOT EXISTS user_skill_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL, skill_id TEXT NOT NULL, pattern_signature TEXT,
            context_summary TEXT, observation_count INTEGER DEFAULT 1,
            last_used TEXT, confidence REAL DEFAULT 0.1,
            can_autonomous INTEGER DEFAULT 0, skill_data_json TEXT);
        CREATE INDEX IF NOT EXISTS idx_obs_user_domain ON user_observations(user_id, domain);
        CREATE INDEX IF NOT EXISTS idx_skill_user ON user_skill_memory(user_id, skill_id);
        """
        with _sql.connect(path) as c:
            c.executescript(SCHEMA)
            c.commit()
        return path


    @app.post("/api/shadow/observe")
    async def shadow_observe(payload: dict, request: Request = None):
        """Record an observation event into the user's worldstate graph."""
        try:
            import sqlite3 as _sql, json as _json
            from datetime import datetime as _dt, timezone as _tz
            user_id = payload.get("user_id")
            domain = payload.get("domain")
            event_type = payload.get("event_type")
            if not (user_id and domain and event_type):
                return {"gate":"PATCH-388b-OBSERVE","status":"ERROR",
                        "error":"user_id, domain, event_type required"}
            VALID_DOMAINS = {"focus","decision_style","knowledge_graph","tool_fluency",
                             "working_rhythm","communication_style","priorities","boundaries"}
            if domain not in VALID_DOMAINS:
                return {"gate":"PATCH-388b-OBSERVE","status":"ERROR",
                        "error":f"domain must be one of {sorted(VALID_DOMAINS)}"}

            now = _dt.now(_tz.utc).isoformat()
            event_data = payload.get("event_data")
            predicted = payload.get("predicted")
            actual = payload.get("actual")

            # Compute sync_delta if both prediction and actual present
            sync_delta = None
            if predicted is not None and actual is not None:
                # Simple delta — 0 if matches exactly, else 1; future patches refine
                try:
                    sync_delta = 0.0 if (
                        _json.dumps(predicted, sort_keys=True) ==
                        _json.dumps(actual, sort_keys=True)
                    ) else 1.0
                except Exception:
                    sync_delta = 1.0

            path = _shadow_ensure_user_db(user_id)
            with _sql.connect(path) as c:
                cur = c.execute("""INSERT INTO user_observations
                    (user_id, timestamp, domain, event_type, event_data,
                     predicted, actual, sync_delta, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""", (
                    user_id, now, domain, event_type,
                    _json.dumps(event_data) if event_data is not None else None,
                    _json.dumps(predicted) if predicted is not None else None,
                    _json.dumps(actual) if actual is not None else None,
                    sync_delta, now,
                ))
                obs_id = cur.lastrowid
                c.commit()

            # Also bump observation_count on the shadow agent record
            try:
                EG = "/var/lib/murphy-production/entity_graph.db"
                with _sql.connect(EG) as c:
                    c.execute("""UPDATE agent_contracts
                                 SET observation_count = COALESCE(observation_count,0) + 1,
                                     updated_at = ?
                                 WHERE shadowing_user_id = ?""", (now, user_id))
                    c.commit()
            except Exception:
                pass

            return {"gate":"PATCH-388b-OBSERVE","status":"OK",
                    "observation_id": obs_id, "user_id": user_id,
                    "domain": domain, "sync_delta": sync_delta,
                    "timestamp": now}
        except Exception as e:
            import traceback as _tb
            return {"gate":"PATCH-388b-OBSERVE","status":"ERROR",
                    "error":str(e),"trace":_tb.format_exc()[:500]}


    @app.get("/api/shadow/user-worldstate")
    async def shadow_user_worldstate(user_id: str = "cpost@murphy.systems",
                                     request: Request = None):
        """Return current WorldState snapshot of the user's graph."""
        try:
            import sqlite3 as _sql, json as _json
            from datetime import datetime as _dt, timezone as _tz
            DOMAINS = ["focus","decision_style","knowledge_graph","tool_fluency",
                       "working_rhythm","communication_style","priorities","boundaries"]
            path = _shadow_ensure_user_db(user_id)
            with _sql.connect(path) as c:
                c.row_factory = _sql.Row
                # Latest snapshot
                snap_row = c.execute("""SELECT timestamp, domains_json, overall_sync, snapshot_summary
                                        FROM user_worldstate_snapshots
                                        WHERE user_id=? ORDER BY timestamp DESC LIMIT 1""",
                                     (user_id,)).fetchone()
                snap = dict(snap_row) if snap_row else None
                if snap and snap.get("domains_json"):
                    try: snap["domains"] = _json.loads(snap["domains_json"])
                    except: snap["domains"] = {}
                    snap.pop("domains_json", None)

                # Per-domain observation counts (live)
                domain_obs = {}
                for d in DOMAINS:
                    cnt = c.execute("SELECT COUNT(*) FROM user_observations WHERE user_id=? AND domain=?",
                                    (user_id, d)).fetchone()[0]
                    domain_obs[d] = cnt

                total_obs = c.execute("SELECT COUNT(*) FROM user_observations WHERE user_id=?",
                                      (user_id,)).fetchone()[0]

            return {"gate":"PATCH-388b-USER-WORLDSTATE","status":"OK",
                    "user_id": user_id,
                    "snapshot": snap,
                    "live_observation_counts": domain_obs,
                    "total_observations": total_obs}
        except Exception as e:
            import traceback as _tb
            return {"gate":"PATCH-388b-USER-WORLDSTATE","status":"ERROR",
                    "error":str(e),"trace":_tb.format_exc()[:500]}


    @app.get("/api/shadow/predict")
    async def shadow_predict(user_id: str = "cpost@murphy.systems",
                             task: str = "",
                             request: Request = None):
        """
        Shadow predicts what user would do for a given task.
        Pulls from observation history + skill memory + current snapshot.
        v1: heuristic-based prediction; v2 will use LLM with full user worldstate.
        """
        try:
            import sqlite3 as _sql, json as _json
            from datetime import datetime as _dt, timezone as _tz
            path = _shadow_ensure_user_db(user_id)
            now = _dt.now(_tz.utc).isoformat()

            with _sql.connect(path) as c:
                c.row_factory = _sql.Row
                # Pull recent observations (last 20)
                recent = [dict(r) for r in c.execute("""
                    SELECT timestamp, domain, event_type, event_data
                    FROM user_observations WHERE user_id=?
                    ORDER BY timestamp DESC LIMIT 20""", (user_id,)).fetchall()]

                # Pull skill memory by relevance to task
                skills = [dict(r) for r in c.execute("""
                    SELECT skill_id, pattern_signature, context_summary, observation_count,
                           confidence, can_autonomous, last_used
                    FROM user_skill_memory WHERE user_id=?
                    ORDER BY confidence DESC LIMIT 10""", (user_id,)).fetchall()]

                # Total observations across all domains
                total_obs = c.execute("SELECT COUNT(*) FROM user_observations WHERE user_id=?",
                                      (user_id,)).fetchone()[0]

            # Pull shadow's sync_score
            sync_score = 0.0
            try:
                EG = "/var/lib/murphy-production/entity_graph.db"
                with _sql.connect(EG) as c:
                    row = c.execute("SELECT sync_score FROM agent_contracts WHERE shadowing_user_id=?",
                                    (user_id,)).fetchone()
                    if row: sync_score = float(row[0] or 0.0)
            except Exception: pass

            # Find most relevant skills (simple keyword match for v1)
            task_lower = (task or "").lower()
            matching_skills = [s for s in skills
                               if task_lower and any(w in (s.get("context_summary") or "").lower()
                                                     for w in task_lower.split() if len(w) > 3)]

            if total_obs < 5:
                prediction = {
                    "prediction": "INSUFFICIENT_DATA",
                    "confidence": 0.0,
                    "reasoning": f"Only {total_obs} observations recorded — shadow needs more data to predict reliably",
                    "source_domains": [],
                    "recommendation": "Observe more before predicting"
                }
            elif matching_skills:
                top = matching_skills[0]
                prediction = {
                    "prediction": f"Apply skill: {top['skill_id']}",
                    "confidence": float(top.get("confidence") or 0.1),
                    "reasoning": f"Matched skill pattern used {top.get('observation_count')} times in similar contexts",
                    "source_domains": ["tool_fluency", "knowledge_graph"],
                    "matched_skill": top,
                    "can_autonomous": bool(top.get("can_autonomous")),
                }
            else:
                # Fallback — heuristic from recent observations
                domain_counts = {}
                for r in recent:
                    domain_counts[r["domain"]] = domain_counts.get(r["domain"], 0) + 1
                top_domain = max(domain_counts, key=domain_counts.get) if domain_counts else "focus"
                prediction = {
                    "prediction": f"User likely engages via {top_domain} domain",
                    "confidence": min(0.4, sync_score),
                    "reasoning": f"No skill match; defaulting to user's most active recent domain ({top_domain}: {domain_counts.get(top_domain, 0)} obs)",
                    "source_domains": [top_domain],
                }

            # Record the prediction for later sync measurement
            try:
                with _sql.connect(path) as c:
                    c.execute("""INSERT INTO user_observations
                        (user_id, timestamp, domain, event_type, event_data,
                         predicted, actual, sync_delta, created_at)
                        VALUES (?,?,?,?,?,?,NULL,NULL,?)""", (
                        user_id, now, "knowledge_graph", "shadow_prediction",
                        _json.dumps({"task": task}),
                        _json.dumps(prediction), now,
                    ))
                    c.commit()
            except Exception: pass

            return {"gate":"PATCH-388b-PREDICT","status":"OK",
                    "user_id": user_id, "task": task,
                    "shadow_sync_score": sync_score,
                    "observation_pool_size": total_obs,
                    **prediction}
        except Exception as e:
            import traceback as _tb
            return {"gate":"PATCH-388b-PREDICT","status":"ERROR",
                    "error":str(e),"trace":_tb.format_exc()[:500]}


    @app.get("/api/shadow/sync-status")
    async def shadow_sync_status(user_id: str = "cpost@murphy.systems",
                                 request: Request = None):
        """Per-domain + overall sync metrics. Shows calibration progress."""
        try:
            import sqlite3 as _sql
            DOMAINS = ["focus","decision_style","knowledge_graph","tool_fluency",
                       "working_rhythm","communication_style","priorities","boundaries"]
            path = _shadow_ensure_user_db(user_id)

            per_domain = {}
            with _sql.connect(path) as c:
                for d in DOMAINS:
                    obs_n = c.execute("SELECT COUNT(*) FROM user_observations WHERE user_id=? AND domain=?",
                                      (user_id, d)).fetchone()[0]
                    measured = c.execute("""SELECT AVG(sync_delta), COUNT(*)
                                            FROM user_observations
                                            WHERE user_id=? AND domain=? AND sync_delta IS NOT NULL""",
                                          (user_id, d)).fetchone()
                    avg_delta = measured[0]
                    measured_n = measured[1] or 0
                    # stability = inverse of avg delta; need at least 5 measurements
                    stability = 0.0
                    if measured_n >= 5 and avg_delta is not None:
                        stability = max(0.0, 1.0 - float(avg_delta))
                    per_domain[d] = {
                        "observation_count": obs_n,
                        "measured_predictions": measured_n,
                        "avg_sync_delta": float(avg_delta) if avg_delta is not None else None,
                        "stability_score": round(stability, 3),
                        "calibrated": stability >= 0.70,
                    }

            calibrated_count = sum(1 for d in per_domain.values() if d["calibrated"])
            overall_sync = round(
                sum(d["stability_score"] for d in per_domain.values()) / len(DOMAINS),
                3
            )

            # Update shadow's sync_score in entity_graph
            try:
                EG = "/var/lib/murphy-production/entity_graph.db"
                from datetime import datetime as _dt, timezone as _tz
                with _sql.connect(EG) as c:
                    c.execute("""UPDATE agent_contracts SET sync_score=?, updated_at=?
                                 WHERE shadowing_user_id=?""",
                              (overall_sync, _dt.now(_tz.utc).isoformat(), user_id))
                    c.commit()
            except Exception: pass

            return {"gate":"PATCH-388b-SYNC-STATUS","status":"OK",
                    "user_id": user_id,
                    "overall_sync": overall_sync,
                    "calibrated_domains_count": calibrated_count,
                    "calibrated_target": 6,
                    "domains": per_domain}
        except Exception as e:
            import traceback as _tb
            return {"gate":"PATCH-388b-SYNC-STATUS","status":"ERROR",
                    "error":str(e),"trace":_tb.format_exc()[:500]}


    @app.get("/api/shadow/skill-memory")
    async def shadow_skill_memory(user_id: str = "cpost@murphy.systems",
                                  min_confidence: float = 0.0,
                                  request: Request = None):
        """Learned skill patterns + confidence levels."""
        try:
            import sqlite3 as _sql, json as _json
            path = _shadow_ensure_user_db(user_id)
            with _sql.connect(path) as c:
                c.row_factory = _sql.Row
                rows = [dict(r) for r in c.execute("""
                    SELECT skill_id, pattern_signature, context_summary,
                           observation_count, last_used, confidence,
                           can_autonomous, skill_data_json
                    FROM user_skill_memory WHERE user_id=? AND confidence >= ?
                    ORDER BY confidence DESC, observation_count DESC""",
                    (user_id, float(min_confidence))).fetchall()]
                for r in rows:
                    if r.get("skill_data_json"):
                        try: r["skill_data"] = _json.loads(r["skill_data_json"])
                        except: pass
                        r.pop("skill_data_json", None)
                total = c.execute("SELECT COUNT(*) FROM user_skill_memory WHERE user_id=?",
                                  (user_id,)).fetchone()[0]
                autonomous = c.execute("SELECT COUNT(*) FROM user_skill_memory WHERE user_id=? AND can_autonomous=1",
                                       (user_id,)).fetchone()[0]
            return {"gate":"PATCH-388b-SKILL-MEMORY","status":"OK",
                    "user_id": user_id,
                    "total_skills": total,
                    "autonomous_skills": autonomous,
                    "skills_returned": len(rows),
                    "skills": rows}
        except Exception as e:
            import traceback as _tb
            return {"gate":"PATCH-388b-SKILL-MEMORY","status":"ERROR",
                    "error":str(e),"trace":_tb.format_exc()[:500]}
'''
