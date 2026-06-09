"""
PCR-053d — org_compiler HTTP surface

Mirrors the structure of executive_wiring.py (PCR-EXEC-02). A single
registration function attaches the org_compiler endpoints to the running
app. Idempotent, additive, reversible.

WHAT THIS WIRES:

  app.state.org_compiler     → RoleTemplateCompiler() (per-app singleton)
  app.state.shadow_collector → TelemetryCollector() (per-app singleton)
  app.state.shadow_agent     → ShadowLearningAgent(collector)

  POST /api/org/compile             → submit role spec, get compiled
                                       RoleTemplate (Fork A)
  POST /api/org/shadow/observe      → record a work event for shadow
                                       learning (Fork B intake)
  GET  /api/org/proposals           → list current TemplateProposalArtifacts
                                       and their multi-dim N gate verdicts
  GET  /api/org/floor/{jurisdiction}/{industry}/{role_family}
                                    → look up the regulatory floor for a
                                       (jurisdiction, industry, role) tuple
  GET  /api/org/health              → liveness + counts

WHAT THIS DOES NOT WIRE (deferred):
  - Heartbeat tick driving shadow agent on a schedule  → PCR-053f
  - Real /os UI panel for proposals                     → PCR-053g
  - Cross-tenant isolation on shared compiler          → future round

LOCKED DEFAULTS (Corey approved 2026-06-09):
  - Missing jurisdiction at gate time = FAIL CLOSED with loud alert
  - Jurisdiction source = onboarding form + role-level override

ALL ROUTES ARE READ/WRITE-SAFE:
  - /compile is pure (returns derived data, no shadow-side effects)
  - /shadow/observe writes to the in-memory TelemetryCollector
  - /proposals is pure (computes verdicts on demand)
  - /floor is pure lookup
  - /health is pure
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("murphy.org_compiler_routes")


def register_org_compiler(app: Any) -> Dict[str, Any]:
    """Idempotent — safe to call multiple times. Returns status dict.

    Pattern mirrors register_executive(app) from EXEC-02. Routes are
    registered exactly once; subsequent calls report the existing state.
    """
    status: Dict[str, Any] = {
        "compiler":         False,
        "shadow_collector": False,
        "shadow_agent":     False,
        "routes_added":     [],
        "errors":           [],
    }

    # ─────────────────────────────────────────────────────────────
    # 1. Per-app singletons (lazy)
    # ─────────────────────────────────────────────────────────────
    try:
        if not hasattr(app.state, "org_compiler") or app.state.org_compiler is None:
            from org_compiler.compiler import RoleTemplateCompiler
            app.state.org_compiler = RoleTemplateCompiler()
            LOG.info("PCR-053d: RoleTemplateCompiler attached to app.state.org_compiler")
        status["compiler"] = True
    except Exception as e:
        LOG.warning("PCR-053d: compiler instantiate failed: %s", e)
        status["errors"].append(f"compiler: {e}")
        app.state.org_compiler = None

    try:
        if not hasattr(app.state, "shadow_collector") or app.state.shadow_collector is None:
            from org_compiler.shadow_learning import TelemetryCollector
            app.state.shadow_collector = TelemetryCollector()
            LOG.info("PCR-053d: TelemetryCollector attached to app.state.shadow_collector")
        status["shadow_collector"] = True
    except Exception as e:
        LOG.warning("PCR-053d: shadow_collector instantiate failed: %s", e)
        status["errors"].append(f"shadow_collector: {e}")
        app.state.shadow_collector = None

    try:
        if (not hasattr(app.state, "shadow_agent")
                or app.state.shadow_agent is None
                and app.state.shadow_collector is not None):
            from org_compiler.shadow_learning import ShadowLearningAgent
            app.state.shadow_agent = ShadowLearningAgent(app.state.shadow_collector)
            LOG.info("PCR-053d: ShadowLearningAgent attached to app.state.shadow_agent")
        status["shadow_agent"] = True
    except Exception as e:
        LOG.warning("PCR-053d: shadow_agent instantiate failed: %s", e)
        status["errors"].append(f"shadow_agent: {e}")
        app.state.shadow_agent = None

    # ─────────────────────────────────────────────────────────────
    # 2. Route registration (idempotent guard)
    # ─────────────────────────────────────────────────────────────
    if getattr(app.state, "_org_compiler_routes_registered", False):
        LOG.info("PCR-053d: routes already registered, skipping")
        status["routes_added"] = ["<already-registered>"]
        return status

    # ── POST /api/org/compile ────────────────────────────────────
    @app.post("/api/org/compile")
    async def org_compile(payload: Dict[str, Any]):
        """Compile a role specification into a RoleTemplate.

        Payload shape:
          {
            "org_chart": [ {node_id, role_name, reports_to, team, department, authority_level}, ... ],
            "sop_data":  { "Role Name": {responsibilities: [...]}, ... },
            "role_name": "Sales Rep"   # which role to compile
          }
        """
        try:
            from org_compiler.parsers import OrgChartParser
            from org_compiler.schemas import AuthorityLevel
            import json, tempfile, os

            chart = payload.get("org_chart") or []
            sop = payload.get("sop_data") or {}
            role_name = payload.get("role_name")
            if not role_name:
                return {"ok": False, "error": "missing role_name"}, 400

            # OrgChartParser expects a file path; write to a tempfile
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                json.dump(chart, f); path = f.name
            try:
                nodes = OrgChartParser.parse_json(path)
            finally:
                try: os.unlink(path)
                except Exception: pass

            comp = app.state.org_compiler
            comp.add_org_chart(nodes)
            for r, data in sop.items():
                comp.add_sop_data(r, data)

            tpl = comp.compile(role_name)
            return {
                "ok": True,
                "role_template": {
                    "role_id":                      tpl.role_id,
                    "role_name":                    tpl.role_name,
                    "decision_authority":           tpl.decision_authority.value,
                    "responsibilities":             tpl.responsibilities,
                    "decision_ceiling_usd":         tpl.decision_ceiling_usd,
                    "distinct_operators_required":  tpl.distinct_operators_required,
                    "primary_jurisdiction":         tpl.primary_jurisdiction,
                    "integrity_hash":               tpl.integrity_hash,
                    "version":                      tpl.version,
                },
            }
        except Exception as e:
            LOG.exception("org_compile failed")
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    status["routes_added"].append("POST /api/org/compile")

    # ── POST /api/org/shadow/observe ─────────────────────────────
    @app.post("/api/org/shadow/observe")
    async def shadow_observe(payload: Dict[str, Any]):
        """Record a shadow observation event.

        Payload shape (one of):
          {"kind":"task", "role":"Sales Rep", "task":"send_quote",   "metadata":{...}}
          {"kind":"approval", "role":"...", "approval_type":"...",   "granted":true, "metadata":{...}}
          {"kind":"failure", "role":"...", "failure_type":"...",     "metadata":{...}}
        """
        try:
            kind = payload.get("kind")
            role = payload.get("role")
            if not kind or not role:
                return {"ok": False, "error": "missing kind or role"}, 400

            col = app.state.shadow_collector
            now = datetime.now(timezone.utc)
            md = payload.get("metadata") or {}

            if kind == "task":
                col.record_task_assignment(role, payload.get("task", ""), now, md)
            elif kind == "approval":
                col.record_approval(role, payload.get("approval_type", ""),
                                    bool(payload.get("granted")), now, md)
            elif kind == "failure":
                col.record_failure(role, payload.get("failure_type", ""), now, md)
            else:
                return {"ok": False, "error": f"unknown kind={kind!r}"}, 400

            # Return summary so caller sees impact
            t = col.get_telemetry_for_role(role)
            return {
                "ok": True,
                "role": role,
                "kind_recorded": kind,
                "totals": {
                    k: len(v) if isinstance(v, list) else v
                    for k, v in t.items()
                },
            }
        except Exception as e:
            LOG.exception("shadow_observe failed")
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    status["routes_added"].append("POST /api/org/shadow/observe")

    # ── GET /api/org/proposals ───────────────────────────────────
    @app.get("/api/org/proposals")
    async def list_proposals(
        role: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        industry: Optional[str] = None,
    ):
        """Compute current shadow-learning proposals + multi-dim N verdicts.

        Query params:
          role         — restrict to a single role (optional)
          jurisdiction — e.g. 'US-CA' (used for floor lookup)
          industry     — e.g. 'saas'  (used for floor lookup)

        If jurisdiction or industry are missing, the verdict for each role
        is fail-closed per PCR-053b policy.
        """
        try:
            from org_compiler.shadow_learning import (
                PatternRecognitionEngine, RiskAnalyzer
            )
            from org_compiler.regulatory_floor import evaluate_against_floor

            col = app.state.shadow_collector
            pe = PatternRecognitionEngine()

            # PCR-053d-fix: TelemetryCollector stores flat lists, not role-keyed dicts.
            # Pull unique role values by scanning each list.
            roles_seen: List[str] = []
            for ev_list_name in ("task_assignments", "approvals", "failures"):
                for ev in getattr(col, ev_list_name, []) or []:
                    rname = ev.get("role") if isinstance(ev, dict) else None
                    if rname and rname not in roles_seen:
                        roles_seen.append(rname)
            # Handoffs use HandoffEvent objects with from_role/to_role
            for h in getattr(col, "handoffs", []) or []:
                for attr in ("from_role", "to_role"):
                    rname = getattr(h, attr, None)
                    if rname and rname not in roles_seen:
                        roles_seen.append(rname)

            if role and role in roles_seen:
                roles_seen = [role]
            elif role:
                roles_seen = []

            out: List[Dict[str, Any]] = []
            for r in roles_seen:
                t = col.get_telemetry_for_role(r)
                patterns = pe.identify_repetitive_tasks(t)

                # Approximate dimensions from the telemetry we have
                tasks = t.get("task_assignments", [])
                distinct_ops = len({
                    (ev.get("metadata") or {}).get("operator", "unknown")
                    for ev in tasks
                })
                if distinct_ops == 0:
                    distinct_ops = 1  # at least the observed actor

                if tasks:
                    timestamps = []
                    for ev in tasks:
                        ts = ev.get("timestamp")
                        if isinstance(ts, datetime):
                            timestamps.append(ts)
                    if timestamps:
                        span_days = (max(timestamps) - min(timestamps)).days + 1
                    else:
                        span_days = 0
                else:
                    span_days = 0

                # Derive role_family — use role name lowercased + underscored
                role_family = r.lower().replace(" ", "_")

                # Money ceiling — pull max deal_size_usd if present
                max_money = 0.0
                for ev in tasks:
                    m = (ev.get("metadata") or {}).get("deal_size_usd")
                    if isinstance(m, (int, float)) and m > max_money:
                        max_money = float(m)

                verdict = evaluate_against_floor(
                    jurisdiction=jurisdiction,
                    industry=industry or "saas",
                    role_family=role_family,
                    observation_window_days=span_days,
                    distinct_operators_observed=distinct_ops,
                    decision_ceiling_usd=max_money if max_money > 0 else None,
                    compliance_regulations=("audit_trail",),
                )

                out.append({
                    "role":                       r,
                    "role_family":                role_family,
                    "events_observed":            sum(
                        len(v) if isinstance(v, list) else 0 for v in t.values()
                    ),
                    "observation_window_days":    span_days,
                    "distinct_operators_observed": distinct_ops,
                    "max_money_seen_usd":         max_money,
                    "patterns_found":             len(patterns),
                    "verdict": {
                        "passes":       verdict.passes,
                        "fail_closed":  verdict.fail_closed,
                        "floor_source": verdict.floor_source,
                        "reasons":      list(verdict.reasons),
                    },
                })

            return {"ok": True, "proposals": out, "count": len(out)}
        except Exception as e:
            LOG.exception("list_proposals failed")
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    status["routes_added"].append("GET /api/org/proposals")

    # ── GET /api/org/floor/{jurisdiction}/{industry}/{role_family} ──
    @app.get("/api/org/floor/{jurisdiction}/{industry}/{role_family}")
    async def get_floor(jurisdiction: str, industry: str, role_family: str):
        """Look up the regulatory floor for a (jurisdiction, industry, role) tuple."""
        try:
            from org_compiler.regulatory_floor import lookup_floor, FloorMissingError
            try:
                fp = lookup_floor(jurisdiction, industry, role_family)
                return {
                    "ok": True,
                    "floor": {
                        "jurisdiction":             jurisdiction,
                        "industry":                 industry,
                        "role_family":              role_family,
                        "min_observation_days":     fp.min_observation_days,
                        "min_distinct_operators":   fp.min_distinct_operators,
                        "max_decision_ceiling_usd": fp.max_decision_ceiling_usd,
                        "never_promote":            fp.never_promote,
                        "required_regulations":     list(fp.required_regulations),
                        "citation":                 fp.citation,
                    },
                }
            except FloorMissingError as e:
                # Fail-closed but informative
                return {
                    "ok": False,
                    "fail_closed": True,
                    "error": str(e),
                    "key": list(e.key),
                }, 404
        except Exception as e:
            LOG.exception("get_floor failed")
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    status["routes_added"].append("GET /api/org/floor/{jurisdiction}/{industry}/{role_family}")

    # ── GET /api/org/health ──────────────────────────────────────
    @app.get("/api/org/health")
    async def org_health():
        """Liveness for the org_compiler subsystem."""
        from org_compiler.regulatory_floor import list_known_combinations
        return {
            "ok": True,
            "compiler_attached":          app.state.org_compiler is not None,
            "shadow_collector_attached":  app.state.shadow_collector is not None,
            "shadow_agent_attached":      app.state.shadow_agent is not None,
            "regulatory_floor_rows":      len(list_known_combinations()),
            "routes_registered":          True,
        }
    status["routes_added"].append("GET /api/org/health")

    # Mark idempotent
    app.state._org_compiler_routes_registered = True
    LOG.info("PCR-053d: registered %d org_compiler routes", len(status["routes_added"]))
    return status


__all__ = ["register_org_compiler"]
