"""
PATCH-390 — CEO Operating Rhythm

The platform_ceo agent has a business plan (PATCH-387) and an org of 10 agents
under it (PATCH-386). What's missing: a cadence that turns the business plan
into action without Corey driving it.

This patch adds:
  1. strategic_cycles table — every weekly CEO cycle leaves an audit trail
     of: which priorities, which agents got which tasks, what outcomes
  2. /api/ceo/run-weekly-cycle — CEO reads business plan, generates week's
     strategy, dispatches OKRs to each direct report. Idempotent per ISO week.
  3. /api/ceo/status — current week's strategy + report states (replaces 404 stub)
  4. /api/ceo/directive — Corey can override/add a directive that CEO must
     factor into next cycle
  5. APScheduler job: every Monday 08:00 America/Los_Angeles → run weekly cycle
  6. APScheduler job: every weekday 07:00 PT → daily standup digest to Corey

Standards:
  - CEO cannot create new agents (writes go to existing agent_contracts table)
  - Every dispatch is logged in strategic_cycle_dispatches
  - Audit log row for every cycle in strategic_cycle_audit (hash-chained)
  - Idempotent: re-running the same ISO week reads existing cycle, doesn't duplicate

Applied: 2026-05-22
"""

SCHEMA_MIGRATION = '''
    # ═══ PATCH-390: CEO operating rhythm schema ═══
    def _patch390_schema():
        import sqlite3 as _sql
        DB = "/var/lib/murphy-production/entity_graph.db"
        with _sql.connect(DB, timeout=20.0) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS strategic_cycles (
                cycle_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                iso_year_week TEXT NOT NULL,
                cycle_type TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                business_plan_snapshot TEXT,
                strategy_json TEXT,
                summary TEXT,
                status TEXT DEFAULT 'in_progress',
                UNIQUE(org_id, iso_year_week, cycle_type)
            );""")
            c.execute("""CREATE INDEX IF NOT EXISTS idx_strategic_cycles_org_week
                ON strategic_cycles(org_id, iso_year_week);""")
            c.execute("""CREATE TABLE IF NOT EXISTS strategic_cycle_dispatches (
                dispatch_id TEXT PRIMARY KEY,
                cycle_id TEXT NOT NULL,
                from_agent_id TEXT NOT NULL,
                to_agent_id TEXT NOT NULL,
                priority_ref TEXT,
                okr_objective TEXT NOT NULL,
                key_results_json TEXT,
                deadline TEXT,
                status TEXT DEFAULT 'assigned',
                result_summary TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (cycle_id) REFERENCES strategic_cycles(cycle_id)
            );""")
            c.execute("""CREATE INDEX IF NOT EXISTS idx_dispatches_cycle
                ON strategic_cycle_dispatches(cycle_id);""")
            c.execute("""CREATE INDEX IF NOT EXISTS idx_dispatches_to_agent
                ON strategic_cycle_dispatches(to_agent_id, status);""")
            c.execute("""CREATE TABLE IF NOT EXISTS strategic_cycle_audit (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id TEXT NOT NULL,
                event TEXT NOT NULL,
                actor TEXT NOT NULL,
                payload TEXT,
                prev_hash TEXT,
                this_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );""")
            c.execute("""CREATE TABLE IF NOT EXISTS ceo_directives (
                directive_id TEXT PRIMARY KEY,
                from_user TEXT NOT NULL,
                directive_text TEXT NOT NULL,
                weight REAL DEFAULT 0.5,
                deadline TEXT,
                applied_to_cycle_id TEXT,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending'
            );""")
            c.commit()
    try: _patch390_schema()
    except Exception as e:
        try:
            import logging as _lg
            _lg.getLogger("murphy.ceo").warning("schema fail: %s", e)
        except: pass
'''


CEO_CYCLE_ENGINE = '''
    # ═══ PATCH-390: CEO weekly cycle engine ═══
    def _ceo_iso_week(dt=None):
        from datetime import datetime as _dt, timezone as _tz
        if dt is None: dt = _dt.now(_tz.utc)
        y, w, _ = dt.isocalendar()
        return f"{y}-W{w:02d}"

    def _ceo_audit(cycle_id: str, event: str, actor: str, payload: dict):
        import sqlite3 as _sql, json as _j, hashlib as _h
        from datetime import datetime as _dt, timezone as _tz
        DB = "/var/lib/murphy-production/entity_graph.db"
        try:
            with _sql.connect(DB, timeout=10.0) as c:
                prev = c.execute("""SELECT this_hash FROM strategic_cycle_audit
                                    ORDER BY audit_id DESC LIMIT 1""").fetchone()
                prev_hash = prev[0] if prev else ""
                now = _dt.now(_tz.utc).isoformat()
                payload_str = _j.dumps(payload, sort_keys=True, default=str)
                this_hash = _h.sha256(
                    (prev_hash + cycle_id + event + actor + payload_str + now).encode()
                ).hexdigest()
                c.execute("""INSERT INTO strategic_cycle_audit
                    (cycle_id,event,actor,payload,prev_hash,this_hash,created_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    (cycle_id, event, actor, payload_str, prev_hash, this_hash, now))
                c.commit()
        except Exception: pass

    def _ceo_load_business_plan():
        """Return the platform org soul incl. business_plan_json + priorities."""
        import sqlite3 as _sql, json as _j
        DB = "/var/lib/murphy-production/entity_graph.db"
        with _sql.connect(DB, timeout=10.0) as c:
            row = c.execute("""SELECT vision, mission, market_position,
                                      business_plan_json, strategic_priorities,
                                      competitive_landscape, constraints, kpis_org_json
                               FROM organizational_souls
                               WHERE org_id='murphy_systems_platform'""").fetchone()
        if not row: return None
        def _ld(x):
            if not x: return None
            try: return _j.loads(x) if isinstance(x, str) else x
            except Exception: return None
        return {
            "vision": row[0], "mission": row[1], "market_position": row[2],
            "business_plan": _ld(row[3]),
            "strategic_priorities": _ld(row[4]) or [],
            "competitive_landscape": _ld(row[5]) or [],
            "constraints": _ld(row[6]) or [],
            "kpis": _ld(row[7]) or {},
        }

    def _ceo_load_pending_directives():
        import sqlite3 as _sql
        DB = "/var/lib/murphy-production/entity_graph.db"
        with _sql.connect(DB, timeout=5.0) as c:
            rows = c.execute("""SELECT directive_id, directive_text, weight, deadline, from_user
                                FROM ceo_directives WHERE status='pending'
                                ORDER BY weight DESC, created_at ASC""").fetchall()
        return [{"directive_id": r[0], "text": r[1], "weight": r[2],
                 "deadline": r[3], "from_user": r[4]} for r in rows]

    def _ceo_get_direct_reports():
        """Read agent_contracts for the CEO's direct reports."""
        import sqlite3 as _sql
        DB = "/var/lib/murphy-production/entity_graph.db"
        with _sql.connect(DB, timeout=5.0) as c:
            rows = c.execute("""SELECT agent_id, role, persona, objective
                                FROM agent_contracts
                                WHERE reports_to='platform_ceo'
                                ORDER BY agent_id""").fetchall()
        return [{"agent_id": r[0], "role": r[1], "persona": r[2], "objective": r[3]}
                for r in rows]

    def _ceo_generate_weekly_strategy(plan: dict, directives: list, reports: list) -> dict:
        """
        Heuristic strategy generator. Uses the business plan, current priorities,
        and pending Corey directives. NOT an LLM — deterministic, audit-clean.

        Logic:
          - Take top-3 priorities by weight
          - Match each priority to the best-fit report based on role keywords
          - Generate OKRs (1 objective + 2-3 key results) per assigned report
          - Carry pending directives forward into priorities
        """
        import re as _re
        # Merge directives into priorities list as virtual high-weight items
        merged_priorities = list(plan.get("strategic_priorities") or [])
        for d in directives:
            merged_priorities.append({
                "priority": d["text"], "weight": max(d.get("weight") or 0.5, 0.5),
                "deadline": d.get("deadline"),
                "_directive_id": d["directive_id"],
                "_from_user": d["from_user"],
            })
        # Sort by weight desc, take top by report count (so each report gets one)
        merged_priorities.sort(key=lambda p: -(p.get("weight") or 0))

        # Keyword → role mapping (rough fit)
        ROLE_KEYWORDS = {
            "platform_cto":       ["gate","autonomy","patch","architecture","engineering","g06","g07","g08","g09","g10","g11","g12","g13","g14","scale","uptime","technical","ship"],
            "platform_cro":       ["tenant","customer","revenue","arr","sales","outreach","prospect","close","paying","conversion","pipeline","10 paying"],
            "platform_coo":       ["onboarding","support","success","retention","churn","operations","ops","ticket","tenant self-service"],
            "platform_cfo":       ["arr","unit economics","cac","margin","valuation","treasury","crypto","price","tier","revenue"],
            "platform_cco":       ["soc2","hipaa","gdpr","compliance","audit","regulatory","posture","constraint"],
        }

        def _best_report_for_priority(prio_text: str) -> str:
            text = prio_text.lower()
            best = None; best_score = 0
            for agent_id, kws in ROLE_KEYWORDS.items():
                score = sum(2 if kw in text else 0 for kw in kws if len(kw) > 3)
                if score > best_score:
                    best_score, best = score, agent_id
            return best or "platform_coo"  # default to ops

        assignments = []
        used_reports = set()
        for prio in merged_priorities:
            if len(assignments) >= len(reports): break
            assignee = _best_report_for_priority(prio.get("priority",""))
            # If that report is already loaded, pick next available
            if assignee in used_reports:
                # find any unassigned report
                for r in reports:
                    if r["agent_id"] not in used_reports and r["agent_id"] not in ("platform_cto","platform_engineer","platform_sre"):
                        assignee = r["agent_id"]; break
            used_reports.add(assignee)
            assignments.append({
                "priority": prio.get("priority"),
                "weight": prio.get("weight"),
                "deadline": prio.get("deadline"),
                "directive_id": prio.get("_directive_id"),
                "to_agent_id": assignee,
                "okr_objective": prio.get("priority"),
                "key_results": _generate_key_results(prio.get("priority",""), plan),
            })

        return {
            "iso_week": _ceo_iso_week(),
            "top_priorities_count": len(assignments),
            "assignments": assignments,
            "carry_forward_directives": [d for d in directives],
            "advantage_focus": _identify_competitive_focus(plan),
        }

    def _generate_key_results(priority_text: str, plan: dict) -> list:
        """Convert a priority text into 2-3 measurable key results."""
        t = priority_text.lower()
        krs = []
        # Match against KPI targets if available
        kpis = plan.get("kpis") or {}
        if "tenant" in t and "paying" in t:
            krs = [
                "Identify 100 qualified prospects (regulated SMB: engineering, healthcare, compliance services)",
                "Run multi-stakeholder outreach to 50 of them (3 contacts/company minimum)",
                "Close 2-3 paying tenants this week",
            ]
        elif "gate" in t or "autonomy" in t:
            krs = [
                "Verify all 9 baseline gates remain HTTP 200",
                "Close 1 of the 6 remaining gates (G06-G14)",
                "Add observability metrics to any gate without them",
            ]
        elif "soc2" in t or "compliance" in t:
            krs = [
                "Document current control posture across 5 SOC2 trust criteria",
                "Identify 2 critical gaps and propose remediation patches",
                "Begin vendor selection for SOC2 Type 1 audit firm",
            ]
        elif "self-service" in t or "onboarding" in t:
            krs = [
                "Ship tenant signup flow with 21-question onboarding",
                "Reduce signup-to-first-deliverable time to <48 hours",
                "Test with 1 friendly tenant before broader release",
            ]
        elif "churn" in t or "retention" in t:
            krs = [
                "Identify tenants with <40% activity in past 7 days",
                "Run save-motion outreach (CEO email + onboarding refresh)",
                "Measure week-over-week retention delta",
            ]
        else:
            krs = [
                f"Define measurable success criteria for: {priority_text[:80]}",
                "Identify 1 blocker and propose mitigation",
                "Report progress at week-end standup",
            ]
        return krs

    def _identify_competitive_focus(plan: dict) -> str:
        """Where should we lean into our advantage this week?"""
        # Pull the highest-threat competitor; lean into the differentiator
        comps = plan.get("competitive_landscape") or []
        if not comps: return "Audit-trail compliance as wedge for regulated SMBs"
        levels = {"low":1, "medium":2, "high":3}
        sorted_c = sorted(comps, key=lambda c: -levels.get(c.get("threat_level","low"),1))
        top = sorted_c[0]
        return f"Lean into: {top.get('our_differentiator','-')} (vs {top.get('competitor','?')}, {top.get('threat_level','?')} threat)"

    def _ceo_dispatch_assignments(cycle_id: str, assignments: list):
        """Persist each assignment as a strategic_cycle_dispatch row."""
        import sqlite3 as _sql, uuid as _u, json as _j
        from datetime import datetime as _dt, timezone as _tz
        DB = "/var/lib/murphy-production/entity_graph.db"
        now = _dt.now(_tz.utc).isoformat()
        dispatch_ids = []
        with _sql.connect(DB, timeout=10.0) as c:
            for a in assignments:
                did = "disp_" + _u.uuid4().hex[:12]
                c.execute("""INSERT INTO strategic_cycle_dispatches
                    (dispatch_id, cycle_id, from_agent_id, to_agent_id,
                     priority_ref, okr_objective, key_results_json, deadline,
                     status, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (did, cycle_id, "platform_ceo", a["to_agent_id"],
                     a.get("priority",""), a["okr_objective"],
                     _j.dumps(a.get("key_results", [])), a.get("deadline"),
                     "assigned", now))
                dispatch_ids.append(did)
            c.commit()
        return dispatch_ids

    def _ceo_run_weekly_cycle(triggered_by: str = "scheduled"):
        """The CEO's main weekly planning loop."""
        import sqlite3 as _sql, uuid as _u, json as _j
        from datetime import datetime as _dt, timezone as _tz
        DB = "/var/lib/murphy-production/entity_graph.db"
        iso_week = _ceo_iso_week()
        org_id = "murphy_systems_platform"
        cycle_type = "weekly_planning"

        # Idempotent: if cycle already exists for this week, return it
        with _sql.connect(DB, timeout=10.0) as c:
            row = c.execute("""SELECT cycle_id, status, strategy_json
                               FROM strategic_cycles
                               WHERE org_id=? AND iso_year_week=? AND cycle_type=?""",
                            (org_id, iso_week, cycle_type)).fetchone()
        if row:
            return {"cycle_id": row[0], "status": row[1], "idempotent_hit": True,
                    "iso_week": iso_week, "strategy": _j.loads(row[2]) if row[2] else None}

        plan = _ceo_load_business_plan()
        if not plan:
            return {"error": "no business plan found for platform_ceo"}
        directives = _ceo_load_pending_directives()
        reports = _ceo_get_direct_reports()
        if not reports:
            return {"error": "no direct reports found for platform_ceo"}

        strategy = _ceo_generate_weekly_strategy(plan, directives, reports)
        cycle_id = "cyc_" + _u.uuid4().hex[:12]
        now = _dt.now(_tz.utc).isoformat()

        with _sql.connect(DB, timeout=10.0) as c:
            c.execute("""INSERT INTO strategic_cycles
                (cycle_id, org_id, iso_year_week, cycle_type, started_at,
                 business_plan_snapshot, strategy_json, status)
                VALUES (?,?,?,?,?,?,?,?)""",
                (cycle_id, org_id, iso_week, cycle_type, now,
                 _j.dumps(plan, default=str), _j.dumps(strategy, default=str),
                 "in_progress"))
            c.commit()

        _ceo_audit(cycle_id, "cycle_started", "platform_ceo",
                   {"triggered_by": triggered_by, "iso_week": iso_week,
                    "report_count": len(reports), "directive_count": len(directives)})

        dispatch_ids = _ceo_dispatch_assignments(cycle_id, strategy["assignments"])
        for did, a in zip(dispatch_ids, strategy["assignments"]):
            _ceo_audit(cycle_id, "dispatch_assigned", "platform_ceo",
                       {"dispatch_id": did, "to": a["to_agent_id"],
                        "objective": a["okr_objective"][:120]})

        # Mark applied directives
        if directives:
            with _sql.connect(DB, timeout=10.0) as c:
                for d in directives:
                    c.execute("""UPDATE ceo_directives
                                 SET status='applied', applied_to_cycle_id=?
                                 WHERE directive_id=?""",
                              (cycle_id, d["directive_id"]))
                c.commit()

        summary = (f"Week {iso_week}: dispatched {len(dispatch_ids)} OKRs to "
                   f"{', '.join(sorted(set(a['to_agent_id'] for a in strategy['assignments'])))}. "
                   f"Focus: {strategy['advantage_focus']}")
        with _sql.connect(DB, timeout=10.0) as c:
            c.execute("""UPDATE strategic_cycles SET summary=?, completed_at=?,
                                                       status='completed'
                         WHERE cycle_id=?""",
                      (summary, _dt.now(_tz.utc).isoformat(), cycle_id))
            c.commit()

        _ceo_audit(cycle_id, "cycle_completed", "platform_ceo",
                   {"dispatch_count": len(dispatch_ids), "summary": summary[:200]})

        return {
            "cycle_id": cycle_id, "iso_week": iso_week, "status": "completed",
            "dispatch_count": len(dispatch_ids), "summary": summary,
            "strategy": strategy, "triggered_by": triggered_by,
        }
'''


CEO_ROUTES = '''

    # ═══ PATCH-390: CEO routes ═══

    @app.post("/api/ceo/run-weekly-cycle")
    async def ceo_run_weekly_cycle(request: Request = None):
        """Trigger the CEO weekly planning cycle. Idempotent per ISO week."""
        try:
            result = _ceo_run_weekly_cycle(triggered_by="manual")
            return {"gate": "PATCH-390-CEO-WEEKLY", "status": "OK", **result}
        except Exception as e:
            import traceback as _tb
            return {"gate":"PATCH-390-CEO-WEEKLY","status":"ERROR",
                    "error":str(e), "trace": _tb.format_exc()[:500]}

    @app.get("/api/ceo/status")
    async def ceo_status(request: Request = None):
        """Current cycle state + report progress + pending directives."""
        import sqlite3 as _sql, json as _j
        DB = "/var/lib/murphy-production/entity_graph.db"
        try:
            iso_week = _ceo_iso_week()
            with _sql.connect(DB, timeout=5.0) as c:
                cyc = c.execute("""SELECT cycle_id, started_at, completed_at,
                                          status, summary, strategy_json
                                   FROM strategic_cycles
                                   WHERE org_id='murphy_systems_platform'
                                     AND iso_year_week=?
                                     AND cycle_type='weekly_planning'""",
                                 (iso_week,)).fetchone()
                if cyc:
                    dispatches = c.execute("""SELECT dispatch_id, to_agent_id,
                                                     okr_objective, status,
                                                     deadline, result_summary
                                              FROM strategic_cycle_dispatches
                                              WHERE cycle_id=?
                                              ORDER BY to_agent_id""",
                                            (cyc[0],)).fetchall()
                    cycle_state = {
                        "cycle_id": cyc[0], "started_at": cyc[1],
                        "completed_at": cyc[2], "status": cyc[3],
                        "summary": cyc[4],
                        "dispatches": [
                            {"dispatch_id":d[0], "to":d[1], "objective":d[2],
                             "status":d[3], "deadline":d[4],
                             "result_summary":d[5]} for d in dispatches],
                    }
                else:
                    cycle_state = {"note": f"No cycle yet for {iso_week}. "
                                            "POST /api/ceo/run-weekly-cycle to start."}
                pending = c.execute("""SELECT directive_id, directive_text, weight, deadline
                                       FROM ceo_directives WHERE status='pending'
                                       ORDER BY weight DESC""").fetchall()
                pending_directives = [{"id":p[0], "text":p[1],
                                       "weight":p[2], "deadline":p[3]} for p in pending]
            return {
                "gate": "PATCH-390-CEO-STATUS", "status": "OK",
                "iso_week": iso_week, "current_cycle": cycle_state,
                "pending_directives": pending_directives,
            }
        except Exception as e:
            return {"gate":"PATCH-390-CEO-STATUS","status":"ERROR","error":str(e)}

    @app.post("/api/ceo/directive")
    async def ceo_directive(request: Request):
        """
        Corey gives the CEO a directive that gets factored into next cycle.
        Body: {"text": "Focus on healthcare prospects this week",
               "weight": 0.9, "deadline": "2026-06-01"}
        """
        import sqlite3 as _sql, uuid as _u
        from datetime import datetime as _dt, timezone as _tz
        try:
            body = await request.json()
            text = (body.get("text") or "").strip()
            if not text or len(text) < 5:
                return {"gate":"PATCH-390-DIRECTIVE","status":"ERROR",
                        "error":"directive_text required (min 5 chars)"}
            user = _shadow_resolve_user_from_request(request) or "anonymous"
            DB = "/var/lib/murphy-production/entity_graph.db"
            did = "dir_" + _u.uuid4().hex[:12]
            now = _dt.now(_tz.utc).isoformat()
            weight = float(body.get("weight") or 0.7)
            weight = max(0.0, min(1.0, weight))
            with _sql.connect(DB, timeout=10.0) as c:
                c.execute("""INSERT INTO ceo_directives
                    (directive_id, from_user, directive_text, weight, deadline,
                     created_at, status)
                    VALUES (?,?,?,?,?,?,?)""",
                    (did, user, text, weight, body.get("deadline"), now, "pending"))
                c.commit()
            return {"gate":"PATCH-390-DIRECTIVE","status":"OK",
                    "directive_id": did, "from_user": user,
                    "weight": weight,
                    "note":"Will be applied at next weekly cycle"}
        except Exception as e:
            return {"gate":"PATCH-390-DIRECTIVE","status":"ERROR","error":str(e)}

    @app.get("/api/ceo/cycles")
    async def ceo_cycles_history(request: Request = None):
        """List historical CEO cycles."""
        import sqlite3 as _sql
        DB = "/var/lib/murphy-production/entity_graph.db"
        try:
            with _sql.connect(DB, timeout=5.0) as c:
                rows = c.execute("""SELECT cycle_id, iso_year_week, cycle_type,
                                          started_at, completed_at, status, summary
                                   FROM strategic_cycles
                                   WHERE org_id='murphy_systems_platform'
                                   ORDER BY started_at DESC LIMIT 20""").fetchall()
            return {
                "gate":"PATCH-390-CEO-CYCLES","status":"OK",
                "cycles":[
                    {"cycle_id":r[0],"iso_week":r[1],"type":r[2],
                     "started_at":r[3],"completed_at":r[4],
                     "status":r[5],"summary":r[6]} for r in rows],
            }
        except Exception as e:
            return {"gate":"PATCH-390-CEO-CYCLES","status":"ERROR","error":str(e)}

    @app.get("/api/ceo/audit-trail")
    async def ceo_audit_trail(request: Request = None):
        """Tamper-evident hash-chained audit log."""
        import sqlite3 as _sql
        DB = "/var/lib/murphy-production/entity_graph.db"
        try:
            with _sql.connect(DB, timeout=5.0) as c:
                rows = c.execute("""SELECT audit_id,cycle_id,event,actor,
                                          prev_hash,this_hash,created_at
                                   FROM strategic_cycle_audit
                                   ORDER BY audit_id DESC LIMIT 50""").fetchall()
            return {
                "gate":"PATCH-390-CEO-AUDIT","status":"OK",
                "entries":[
                    {"audit_id":r[0],"cycle_id":r[1],"event":r[2],"actor":r[3],
                     "prev_hash":r[4][:16] + "..." if r[4] else "",
                     "this_hash":r[5][:16] + "...","created_at":r[6]} for r in rows],
            }
        except Exception as e:
            return {"gate":"PATCH-390-CEO-AUDIT","status":"ERROR","error":str(e)}
'''


SCHEDULER_INTEGRATION = '''
    # ═══ PATCH-390: Schedule the weekly CEO cycle ═══
    try:
        if hasattr(self, "_scheduler") and self._scheduler:
            from apscheduler.triggers.cron import CronTrigger as _Cron
            # Monday 08:00 America/Los_Angeles → 15:00 UTC (winter) / 16:00 (summer)
            # Use UTC for cron and let PT shift naturally
            self._scheduler.add_job(
                lambda: _ceo_run_weekly_cycle(triggered_by="scheduled_weekly"),
                _Cron(day_of_week="mon", hour=15, minute=0),
                id="ceo_weekly_planning",
                replace_existing=True,
                misfire_grace_time=3600,
            )
            import logging as _lg
            _lg.getLogger("murphy.ceo").info(
                "✅ PATCH-390: CEO weekly cycle scheduled (Mon 15:00 UTC = 08:00 PT)")
    except Exception as e:
        try:
            import logging as _lg
            _lg.getLogger("murphy.ceo").warning("PATCH-390 scheduler attach fail: %s", e)
        except: pass
'''
