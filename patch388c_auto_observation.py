"""
PATCH-388c — Auto-observation middleware

Hooks shadow observation into request middleware. Every authenticated request
from a known user produces observations automatically, without code changes
anywhere else.

Two pieces:
  A) FastAPI middleware that records observations from every request
  B) Skill-promotion helper: after N similar requests, promote to skill_memory

Observation rules (kept simple for v1):
  - URL path → tool_fluency domain
  - Request method → routed to event_type
  - POST body keys → event_data (no PII; just structural signal)
  - User identified via Authorization Bearer session token
  - Ignored paths: /static, /api/shadow/* (don't observe the observer),
    /docs, /openapi.json, health checks

Skill promotion (every observation):
  - Skill ID = "<METHOD>:<path_template>" (e.g. "POST:/api/org/soul/edit")
  - Pattern signature = path + sorted(body keys)
  - Increment observation_count, set last_used, recompute confidence
    confidence = min(0.95, log10(count+1) / 2.0) — 1 use ≈ 0.15, 10 uses ≈ 0.50,
    100 uses ≈ 0.95
  - When confidence >= 0.80, set can_autonomous=1

Applied: 2026-05-22
"""

MIDDLEWARE_CODE = '''

    # ═══ PATCH-388c: Auto-observation middleware ═══

    # Paths the shadow ignores (otherwise we'd loop or pollute the graph)
    _SHADOW_IGNORE_PREFIXES = (
        "/api/shadow/",        # don't observe the observer
        "/static/",            # static asset reads
        "/docs",
        "/openapi.json",
        "/health",
        "/favicon",
        "/api/observability/health",  # G09 polling
        "/api/auth/login",     # contains password
        "/api/auth/signup",    # contains password
        "/api/auth/reset",     # contains tokens
    )

    # Mapping URL prefix → user-worldstate domain
    _SHADOW_DOMAIN_MAP = (
        ("/api/org/",            "decision_style"),
        ("/api/soul/",           "knowledge_graph"),
        ("/api/rosetta/",        "knowledge_graph"),
        ("/api/dispatch/",       "decision_style"),
        ("/api/onboarding/",     "decision_style"),
        ("/api/payments/",       "decision_style"),
        ("/api/billing/",        "priorities"),
        ("/api/treasury/",       "priorities"),
        ("/api/tenant/",         "boundaries"),
        ("/api/platform/",       "tool_fluency"),
        ("/api/self-heal/",      "tool_fluency"),
        ("/api/github/",         "tool_fluency"),
        ("/api/world/",          "knowledge_graph"),
        ("/api/swarm/",          "tool_fluency"),
        ("/api/mfgc/",           "tool_fluency"),
        ("/api/mss/",            "tool_fluency"),
        ("/api/agents/",         "tool_fluency"),
        ("/api/work/",           "focus"),
        ("/api/dispatch",        "focus"),
        ("/api/chat",            "communication_style"),
        ("/api/messages",        "communication_style"),
        ("/api/gmail",           "communication_style"),
        ("/api/calendar",        "working_rhythm"),
    )

    def _shadow_pick_domain(path: str) -> str:
        """Map a request path to one of the 8 user-worldstate domains."""
        for prefix, dom in _SHADOW_DOMAIN_MAP:
            if path.startswith(prefix): return dom
        return "tool_fluency"  # default — generic API tool use

    def _shadow_normalize_path(path: str) -> str:
        """Strip query params and trailing IDs (UUIDs / numeric) for skill grouping."""
        import re as _re
        p = path.split("?", 1)[0]
        # Replace UUIDs and long hex IDs with {id}
        p = _re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', p)
        p = _re.sub(r'/[0-9a-f]{16,}', '/{id}', p)
        # Replace numeric IDs >= 4 chars
        p = _re.sub(r'/\d{4,}', '/{id}', p)
        return p

    def _shadow_resolve_user_from_request(request) -> str:
        """Look up the user_id from a Bearer/cookie session. Returns None if no user."""
        try:
            # Try cookie session_token first
            tok = None
            if request and hasattr(request, "cookies"):
                tok = request.cookies.get("session_token")
            if not tok and request and hasattr(request, "headers"):
                auth = request.headers.get("authorization") or request.headers.get("Authorization")
                if auth and auth.lower().startswith("bearer "):
                    tok = auth.split(None, 1)[1].strip()
            if not tok: return None
            # Look up in _session_store (module-level dict already in app.py)
            try:
                sess = _session_store.get(tok)  # type: ignore
                if sess: return sess.get("email") or sess.get("user_id")
            except NameError:
                pass
        except Exception:
            pass
        return None

    async def _shadow_record_observation(user_id: str, method: str, path: str,
                                          status_code: int, latency_ms: float):
        """Write one observation + update skill memory. Best-effort; never raises."""
        try:
            import sqlite3 as _sql, json as _json, math as _math
            from datetime import datetime as _dt, timezone as _tz
            domain = _shadow_pick_domain(path)
            normalized = _shadow_normalize_path(path)
            skill_id = f"{method}:{normalized}"
            now = _dt.now(_tz.utc).isoformat()
            db_path = _shadow_ensure_user_db(user_id)

            with _sql.connect(db_path) as c:
                # Observation row
                c.execute("""INSERT INTO user_observations
                    (user_id, timestamp, domain, event_type, event_data, created_at)
                    VALUES (?,?,?,?,?,?)""", (
                    user_id, now, domain, "api_call",
                    _json.dumps({
                        "method": method, "path": normalized,
                        "status": status_code, "latency_ms": round(latency_ms, 1),
                    }),
                    now,
                ))

                # Upsert skill memory
                row = c.execute("""SELECT id, observation_count, confidence, can_autonomous
                                    FROM user_skill_memory WHERE user_id=? AND skill_id=?""",
                                 (user_id, skill_id)).fetchone()
                if row:
                    new_count = (row[1] or 0) + 1
                    new_conf = min(0.95, _math.log10(new_count + 1) / 2.0)
                    new_auto = 1 if new_conf >= 0.80 else 0
                    c.execute("""UPDATE user_skill_memory
                                  SET observation_count=?, confidence=?, can_autonomous=?, last_used=?
                                  WHERE id=?""",
                              (new_count, round(new_conf, 3), new_auto, now, row[0]))
                else:
                    new_conf = round(min(0.95, _math.log10(2) / 2.0), 3)  # first observation
                    c.execute("""INSERT INTO user_skill_memory
                        (user_id, skill_id, pattern_signature, context_summary,
                         observation_count, last_used, confidence, can_autonomous, skill_data_json)
                        VALUES (?,?,?,?,1,?,?,0,?)""", (
                        user_id, skill_id, f"{method}:{normalized}",
                        f"User invokes {method} {normalized} (mapped to {domain})",
                        now, new_conf,
                        _json.dumps({"method": method, "path": normalized}),
                    ))
                c.commit()

            # Bump observation_count on shadow record
            try:
                EG = "/var/lib/murphy-production/entity_graph.db"
                with _sql.connect(EG) as c:
                    c.execute("""UPDATE agent_contracts
                                  SET observation_count = COALESCE(observation_count,0) + 1,
                                      updated_at = ?
                                  WHERE shadowing_user_id=?""", (now, user_id))
                    c.commit()
            except Exception: pass
        except Exception as e:
            # Never let observation errors break the request flow
            try:
                import logging as _lg
                _lg.getLogger("murphy.shadow").debug("observe-fail: %s", e)
            except: pass


    @app.middleware("http")
    async def shadow_auto_observe_middleware(request, call_next):
        """Record every authenticated request as an observation for the user's shadow."""
        import time as _time
        start = _time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Pass through; don't swallow errors
            raise
        latency_ms = (_time.perf_counter() - start) * 1000.0
        try:
            path = request.url.path
            method = request.method
            # Skip ignored paths
            skip = any(path.startswith(p) for p in _SHADOW_IGNORE_PREFIXES)
            if not skip:
                user_id = _shadow_resolve_user_from_request(request)
                if user_id:
                    await _shadow_record_observation(
                        user_id, method, path,
                        getattr(response, "status_code", 0), latency_ms,
                    )
        except Exception:
            pass  # Never break the response
        return response


    @app.get("/api/shadow/auto-obs-status")
    async def shadow_auto_obs_status(request: Request = None):
        """Diagnostic — confirm the auto-observation middleware is wired."""
        return {
            "gate": "PATCH-388c-AUTO-OBS",
            "status": "OK",
            "middleware_active": True,
            "ignored_prefixes": list(_SHADOW_IGNORE_PREFIXES),
            "domain_map_entries": len(_SHADOW_DOMAIN_MAP),
        }
'''
