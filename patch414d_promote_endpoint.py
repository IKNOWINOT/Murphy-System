#!/usr/bin/env python3
"""
PATCH-414d — Identity promote/spawn endpoint
==============================================

WHAT THIS IS:
  Adds POST /api/identity/promote and POST /api/identity/spawn-agent to
  patch410_unified_identity.py. Both mint API keys for the household_profiles
  table; both are founder-only.

WHY IT EXISTS:
  After PATCH-414/414b/414c, the tier system enforces dept-scoped access — but
  there was no way to actually MAKE an employee except by raw SQL. That works
  for testing; it doesn't work for the Phase 5a swarm spawner that needs to
  create dozens of agents programmatically.

HOW IT FITS:
  - /api/identity/spawn-agent  → primary caller, Phase 5a swarm spawn loop
  - /api/identity/promote      → secondary, for the rare day a human is added
  - /api/identity/employees    → founder-only list view (GET)
  - /api/identity/revoke       → founder-only kill switch (POST)

  All four routes live in patch410_unified_identity.py alongside the existing
  /api/identity/me, registered through the same init_identity_routes(app) call
  the murphy-edge bootstrap already runs.

KEY CONCEPTS:
  - Each call mints a raw API key (returned ONCE to the caller) and stores
    only SHA-256(key) in employee_key_hash. Caller must capture it or lose it.
  - spawn-agent vs promote: same DB row, different defaults
      spawn-agent → role='swarm_agent', auto-naming, starting wallet seed
      promote     → role='human_employee', requires explicit name/email
  - Revoke clears employee_key_hash (key no longer authenticates) but keeps
    the profile row so audit history survives.

ENDPOINTS / PUBLIC SURFACE:
  POST /api/identity/spawn-agent  body: {class: "SDR"|"AE"|"Enterprise_AE",
                                          department: "sales", territory?: str,
                                          name_hint?: str}
                                  returns: {profile_id, api_key, class, wallet_seed_usd}
  POST /api/identity/promote      body: {full_name, email, department,
                                          commission_rate?, territory?}
                                  returns: {profile_id, api_key}
  GET  /api/identity/employees    returns: [{profile_id, name, tier, dept,
                                              hire_date, has_key, role}]
  POST /api/identity/revoke       body: {profile_id}
                                  returns: {ok, profile_id, revoked_at}

DEPENDENCIES:
  - PATCH-414  (schema columns: department, employee_key_hash, hire_date,
                commission_rate, territory, manager_id)
  - PATCH-414b (modular_auth populates request.state.tier for founder check)
  - PATCH-414c (/api/identity/me as reference for request.state usage)

VAULT SECRETS USED:
  None. Keys are minted with secrets.token_urlsafe(32) and the raw key is
  returned to the caller exactly once. The hash is what we persist.

EVENT SPINE EMISSIONS:
  - identity.agent.spawned    when /spawn-agent succeeds
  - identity.human.promoted   when /promote succeeds
  - identity.key.revoked      when /revoke succeeds

KNOWN LIMITS:
  - Wallet seed is recorded on the profile (commission_rate field repurposed
    temporarily) but the actual wallet ledger doesn't exist yet — that's
    Phase 4 money plumbing. For now, spawn-agent emits the event so when the
    ledger lands, replaying events backfills the wallet balance.
  - No rate-limit on /spawn-agent yet — relies on founder-key gate as proxy.
    Will add per-day spawn cap once the swarm is actually running.

LAST UPDATED: 2026-05-25 by PATCH-414d
"""
import shutil
from pathlib import Path

TARGET = Path("/opt/Murphy-System/src/patch410_unified_identity.py")
BACKUP = TARGET.with_suffix(".py.pre-414d")

src = TARGET.read_text()

# ── Idempotency ────────────────────────────────────────────────────────────
if "PATCH-414d" in src:
    print("  ⚠ PATCH-414d already applied — skipping")
    raise SystemExit(0)

shutil.copy(TARGET, BACKUP)
print(f"  ✓ Backed up to {BACKUP}")


# ── The new routes block — injected just before /api/identity/health ───────
NEW_ROUTES = '''
    # ── PATCH-414d: spawn / promote / list / revoke ──────────────────────
    @app.post("/api/identity/spawn-agent")
    async def api_spawn_agent(request: Request):
        """Mint a new swarm-agent employee profile + API key.

        Founder-only. Primary caller is the Phase 5a swarm spawner.

        Body:
            class       — "SDR" | "AE" | "Enterprise_AE"  (default "SDR")
            department  — defaults to "sales"
            territory   — optional string (geo or vertical)
            name_hint   — optional; otherwise auto-generated like SDR-a7f2

        Returns:
            {profile_id, api_key, class, wallet_seed_usd, full_name}
            api_key is shown EXACTLY ONCE — caller must capture it.
        """
        if getattr(request.state, "tier", None) != "founder":
            return JSONResponse({"ok": False, "error": "founder_only"}, status_code=403)

        import secrets as _secrets
        import hashlib as _hl
        import sqlite3 as _sq
        import json as _json
        from datetime import datetime as _dt, timezone as _tz

        body = {}
        try:
            body = await request.json()
        except Exception:
            pass

        agent_class = (body.get("class") or "SDR").upper().replace("-", "_")
        if agent_class not in ("SDR", "AE", "ENTERPRISE_AE"):
            return JSONResponse({"ok": False, "error": "invalid_class",
                                 "valid": ["SDR", "AE", "Enterprise_AE"]}, status_code=400)

        department = body.get("department") or "sales"
        territory = body.get("territory")
        name_hint = body.get("name_hint")

        # Phase 5a compute-budget model: starting wallet seed in USD
        wallet_seed = {"SDR": 5.00, "AE": 15.00, "ENTERPRISE_AE": 50.00}[agent_class]

        # Mint key
        api_key = "swarm_" + _secrets.token_urlsafe(32)
        key_hash = _hl.sha256(api_key.encode()).hexdigest()
        profile_id = "prof_swarm_" + _secrets.token_hex(8)
        short_id = profile_id.split("_")[-1][:6]
        full_name = name_hint or f"{agent_class.replace('_', ' ')}-{short_id}"
        now = _dt.now(_tz.utc).isoformat()

        try:
            conn = _sq.connect("/var/lib/murphy-production/murphy_household.db")
            conn.execute("""
                INSERT INTO household_profiles
                    (profile_id, full_name, permission_tier, role, department,
                     email, employee_key_hash, hire_date, commission_rate,
                     territory, notes, created_at, updated_at)
                VALUES (?, ?, 'employee', 'swarm_agent', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (profile_id, full_name, department,
                  f"{profile_id}@swarm.murphy.systems", key_hash, now[:10],
                  wallet_seed,
                  territory,
                  _json.dumps({"class": agent_class, "wallet_seed_usd": wallet_seed,
                               "spawned_by": "founder", "spawn_method": "api"}),
                  now, now))
            conn.commit()
            conn.close()
        except Exception as e:
            return JSONResponse({"ok": False, "error": f"db_insert_failed: {e}"},
                                status_code=500)

        # Emit to Event Spine (best-effort, don't fail the call if bus down)
        try:
            from event_bus import publish as _publish  # type: ignore
            _publish("identity.agent.spawned", {
                "profile_id": profile_id, "full_name": full_name,
                "class": agent_class, "department": department,
                "territory": territory, "wallet_seed_usd": wallet_seed,
            })
        except Exception:
            pass

        return JSONResponse({
            "ok": True,
            "profile_id": profile_id,
            "full_name": full_name,
            "api_key": api_key,  # RETURNED ONCE
            "class": agent_class,
            "department": department,
            "territory": territory,
            "wallet_seed_usd": wallet_seed,
            "warning": "api_key is shown ONCE — store it now",
        })

    @app.post("/api/identity/promote")
    async def api_promote(request: Request):
        """Promote an existing kin profile (or create new) to employee tier.

        Founder-only. Reserved for the unlikely day a real human is added.

        Body:
            full_name        — required
            email            — required
            department       — required (sales|finance|hr|compliance|ops|cs|...)
            commission_rate  — optional float 0.0-1.0
            territory        — optional
            promote_existing — optional profile_id; if set, upgrade not create

        Returns:
            {profile_id, api_key, ...}
        """
        if getattr(request.state, "tier", None) != "founder":
            return JSONResponse({"ok": False, "error": "founder_only"}, status_code=403)

        import secrets as _secrets
        import hashlib as _hl
        import sqlite3 as _sq
        from datetime import datetime as _dt, timezone as _tz

        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

        full_name = body.get("full_name")
        email = body.get("email")
        department = body.get("department")
        if not all([full_name, email, department]):
            return JSONResponse({"ok": False,
                "error": "missing_required",
                "required": ["full_name", "email", "department"]}, status_code=400)

        api_key = "emp_" + _secrets.token_urlsafe(32)
        key_hash = _hl.sha256(api_key.encode()).hexdigest()
        now = _dt.now(_tz.utc).isoformat()
        promote_existing = body.get("promote_existing")

        conn = _sq.connect("/var/lib/murphy-production/murphy_household.db")
        try:
            if promote_existing:
                cur = conn.execute("""
                    UPDATE household_profiles SET
                        permission_tier = 'employee',
                        role            = COALESCE(role, 'human_employee'),
                        department      = ?,
                        employee_key_hash = ?,
                        hire_date       = COALESCE(hire_date, ?),
                        commission_rate = COALESCE(?, commission_rate),
                        territory       = COALESCE(?, territory),
                        updated_at      = ?
                    WHERE profile_id = ?
                """, (department, key_hash, now[:10],
                      body.get("commission_rate"), body.get("territory"),
                      now, promote_existing))
                if cur.rowcount == 0:
                    conn.close()
                    return JSONResponse({"ok": False, "error": "profile_not_found"},
                                        status_code=404)
                profile_id = promote_existing
            else:
                profile_id = "prof_emp_" + _secrets.token_hex(8)
                conn.execute("""
                    INSERT INTO household_profiles
                        (profile_id, full_name, permission_tier, role, department,
                         email, employee_key_hash, hire_date, commission_rate,
                         territory, created_at, updated_at)
                    VALUES (?, ?, 'employee', 'human_employee', ?, ?, ?, ?, ?, ?, ?, ?)
                """, (profile_id, full_name, department, email, key_hash, now[:10],
                      body.get("commission_rate"), body.get("territory"), now, now))
            conn.commit()
        except Exception as e:
            conn.close()
            return JSONResponse({"ok": False, "error": f"db_op_failed: {e}"},
                                status_code=500)
        conn.close()

        try:
            from event_bus import publish as _publish  # type: ignore
            _publish("identity.human.promoted", {
                "profile_id": profile_id, "full_name": full_name,
                "email": email, "department": department,
            })
        except Exception:
            pass

        return JSONResponse({
            "ok": True,
            "profile_id": profile_id,
            "full_name": full_name,
            "email": email,
            "department": department,
            "api_key": api_key,
            "warning": "api_key is shown ONCE — store it now",
        })

    @app.get("/api/identity/employees")
    async def api_list_employees(request: Request):
        """List all employee-tier profiles. Founder-only."""
        if getattr(request.state, "tier", None) != "founder":
            return JSONResponse({"ok": False, "error": "founder_only"}, status_code=403)

        import sqlite3 as _sq
        conn = _sq.connect("/var/lib/murphy-production/murphy_household.db")
        rows = conn.execute("""
            SELECT profile_id, full_name, role, department, hire_date,
                   commission_rate, territory,
                   CASE WHEN employee_key_hash IS NOT NULL AND employee_key_hash != ''
                        THEN 1 ELSE 0 END AS has_key
            FROM household_profiles
            WHERE permission_tier = 'employee'
            ORDER BY hire_date DESC, full_name
        """).fetchall()
        conn.close()

        employees = [{
            "profile_id":      r[0],
            "full_name":       r[1],
            "role":            r[2],          # swarm_agent | human_employee
            "department":      r[3],
            "hire_date":       r[4],
            "commission_rate": r[5],
            "territory":       r[6],
            "has_active_key":  bool(r[7]),
        } for r in rows]

        # Quick aggregate: count by class for swarm awareness
        by_role = {}
        for e in employees:
            by_role[e["role"] or "unknown"] = by_role.get(e["role"] or "unknown", 0) + 1

        return JSONResponse({
            "ok": True,
            "count": len(employees),
            "by_role": by_role,
            "employees": employees,
        })

    @app.post("/api/identity/revoke")
    async def api_revoke(request: Request):
        """Revoke an employee's API key (kill switch). Founder-only.

        Clears employee_key_hash but keeps the profile row for audit.
        """
        if getattr(request.state, "tier", None) != "founder":
            return JSONResponse({"ok": False, "error": "founder_only"}, status_code=403)

        import sqlite3 as _sq
        from datetime import datetime as _dt, timezone as _tz

        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)
        profile_id = body.get("profile_id")
        if not profile_id:
            return JSONResponse({"ok": False, "error": "profile_id_required"}, status_code=400)

        now = _dt.now(_tz.utc).isoformat()
        conn = _sq.connect("/var/lib/murphy-production/murphy_household.db")
        cur = conn.execute("""
            UPDATE household_profiles SET employee_key_hash = NULL, updated_at = ?
            WHERE profile_id = ? AND permission_tier = 'employee'
        """, (now, profile_id))
        conn.commit()
        conn.close()
        if cur.rowcount == 0:
            return JSONResponse({"ok": False, "error": "not_found_or_not_employee"},
                                status_code=404)

        try:
            from event_bus import publish as _publish  # type: ignore
            _publish("identity.key.revoked", {"profile_id": profile_id, "at": now})
        except Exception:
            pass

        return JSONResponse({"ok": True, "profile_id": profile_id, "revoked_at": now})
'''

# ── Inject the routes block right before the existing /api/identity/health ──
anchor = '    @app.get("/api/identity/health")'
if anchor not in src:
    print("  ✗ couldn't find /api/identity/health anchor — aborting")
    raise SystemExit(1)
src = src.replace(anchor, NEW_ROUTES + "\n" + anchor, 1)

# Syntax check before writing
import ast
try:
    ast.parse(src)
except SyntaxError as e:
    print(f"  ✗ syntax error after patch: {e} (line {e.lineno})")
    raise SystemExit(1)

TARGET.write_text(src)
print(f"  ✓ Wrote {TARGET} ({len(src)} bytes)")
print("  ✓ Syntax check passed")
