"""
PATCH-390 — revised inline code (correct column names + scheduler pattern)
"""

# Use the org-chart endpoint as the source of truth for the tree.
# Use agent_contracts.duties_text for objective, role_title for role, persona_label for persona.
# The 10 platform agents are seeded in DB but tree relationships are constructed in code.

CEO_CYCLE_ENGINE_V2 = '''
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
        """The CEO's 5 direct reports — read from agent_contracts using
        the platform org structure (CTO/COO/CFO/CRO/CCO report to CEO)."""
        import sqlite3 as _sql
        DB = "/var/lib/murphy-production/entity_graph.db"
        DIRECT_REPORT_IDS = ["platform_cto","platform_coo","platform_cfo",
                             "platform_cro","platform_cco"]
        with _sql.connect(DB, timeout=5.0) as c:
            qmarks = ",".join("?" * len(DIRECT_REPORT_IDS))
            rows = c.execute(
                f"""SELECT agent_id, role_title, persona_label, duties_text
                    FROM agent_contracts
                    WHERE agent_id IN ({qmarks})""",
                DIRECT_REPORT_IDS).fetchall()
        return [{"agent_id": r[0], "role": r[1], "persona": r[2], "objective": r[3]}
                for r in rows]

    def _ceo_generate_weekly_strategy(plan: dict, directives: list, reports: list) -> dict:
        merged_priorities = list(plan.get("strategic_priorities") or [])
        for d in directives:
            merged_priorities.append({
                "priority": d["text"],
                "weight": max(d.get("weight") or 0.5, 0.5),
                "deadline": d.get("deadline"),
                "_directive_id": d["directive_id"],
                "_from_user": d["from_user"],
            })
        merged_priorities.sort(key=lambda p: -(p.get("weight") or 0))

        ROLE_KEYWORDS = {
            "platform_cto": ["gate","autonomy","patch","architecture","engineering","g06","g07","g08","g09","g10","g11","g12","g14","scale","uptime","technical","ship"],
            "platform_cro": ["tenant","customer","revenue","arr","sales","outreach","prospect","close","paying","conversion","pipeline","paying tenants"],
            "platform_coo": ["onboarding","support","success","retention","operations","ops","ticket","tenant self-service","first deliverable"],
            "platform_cfo": ["arr","unit economics","cac","margin","valuation","treasury","crypto","price","tier","cash"],
            "platform_cco": ["soc2","hipaa","gdpr","compliance","audit","regulatory","posture","constraint","control"],
        }

        def _best_report_for_priority(prio_text: str) -> str:
            text = prio_text.lower()
            best = None; best_score = 0
            for agent_id, kws in ROLE_KEYWORDS.items():
                score = sum(2 for kw in kws if kw in text)
                if score > best_score:
                    best_score, best = score, agent_id
            return best or "platform_coo"

        assignments = []
        used_reports = set()
        report_ids = set(r["agent_id"] for r in reports)
        for prio in merged_priorities:
            if len(assignments) >= len(reports): break
            assignee = _best_report_for_priority(prio.get("priority",""))
            if assignee in used_reports or assignee not in report_ids:
                for r in reports:
                    if r["agent_id"] not in used_reports:
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
            "carry_forward_directives": directives,
            "advantage_focus": _identify_competitive_focus(plan),
        }

    def _generate_key_results(priority_text: str, plan: dict) -> list:
        t = priority_text.lower()
        if "tenant" in t and "paying" in t:
            return [
                "Build qualified prospect list: 100 regulated SMBs (engineering, healthcare, compliance services, 5-50 employees)",
                "Run multi-stakeholder outreach to 50 companies (3 contacts each: owner + ops lead + compliance/finance)",
                "Book 10 demos this week; close 2-3 paying tenants by week-end",
            ]
        if "gate" in t or "autonomy" in t:
            return [
                "Verify all 9 baseline gates remain HTTP 200 daily",
                "Close 1 of the remaining gates (G06-G14)",
                "Document gate coverage in /api/observability/health",
            ]
        if "soc2" in t or "compliance" in t:
            return [
                "Map current controls to SOC2 Trust Services Criteria",
                "Identify top 2 gaps; propose remediation patches",
                "Get quotes from 3 SOC2 Type 1 audit firms",
            ]
        if "self-service" in t or "onboarding" in t:
            return [
                "Ship signup flow with 21-question onboarding live",
                "Reduce signup-to-first-deliverable to <48h",
                "Test with 1 friendly pilot tenant before broader release",
            ]
        if "cross-tenant" in t or "network" in t:
            return [
                "Design anonymized signal-sharing between tenants",
                "Build first benchmark: average response time per industry",
                "Privacy review with CCO before any data sharing",
            ]
        return [
            f"Define measurable success criteria for: {priority_text[:80]}",
            "Identify 1 critical blocker; propose mitigation",
            "Report progress at next weekly cycle",
        ]

    def _identify_competitive_focus(plan: dict) -> str:
        comps = plan.get("competitive_landscape") or []
        if not comps: return "Audit-trail compliance as wedge for regulated SMBs"
        levels = {"low":1, "medium":2, "high":3}
        sorted_c = sorted(comps, key=lambda c: -levels.get(c.get("threat_level","low"),1))
        top = sorted_c[0]
        return (f"Lean into: {top.get('our_differentiator','-')} "
                f"(vs {top.get('competitor','?')}, {top.get('threat_level','?')} threat)")

    def _ceo_dispatch_assignments(cycle_id: str, assignments: list):
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
        import sqlite3 as _sql, uuid as _u, json as _j
        from datetime import datetime as _dt, timezone as _tz
        DB = "/var/lib/murphy-production/entity_graph.db"
        iso_week = _ceo_iso_week()
        org_id = "murphy_systems_platform"
        cycle_type = "weekly_planning"

        with _sql.connect(DB, timeout=10.0) as c:
            row = c.execute("""SELECT cycle_id, status, strategy_json
                               FROM strategic_cycles
                               WHERE org_id=? AND iso_year_week=? AND cycle_type=?""",
                            (org_id, iso_week, cycle_type)).fetchone()
        if row:
            return {"cycle_id": row[0], "status": row[1],
                    "idempotent_hit": True, "iso_week": iso_week,
                    "strategy": _j.loads(row[2]) if row[2] else None}

        plan = _ceo_load_business_plan()
        if not plan: return {"error": "no business plan found"}
        directives = _ceo_load_pending_directives()
        reports = _ceo_get_direct_reports()
        if not reports: return {"error": "no direct reports found"}

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

# No scheduler attach in v1 — we'll trigger manually. Scheduler attach can come later
# once we know the exact reference path. Keeps the deploy minimal-risk.
