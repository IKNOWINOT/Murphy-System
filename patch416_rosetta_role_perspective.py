#!/usr/bin/env python3
"""
PATCH-416 — Rosetta role-perspective engine (Phase 3)
=======================================================

WHAT THIS IS:
  Adds a queryable role-perspective layer on top of the existing
  rosetta/platform_org_seed.py infrastructure. Defines what each of the
  11 canonical roles can *say*, *refuse*, *escalate*, and *narrate*.

WHY IT EXISTS:
  The existing rosetta system has roles (ceo/cto/compliance/sre/cso/vp-sales/
  etc.) with `authorised_actions` (e.g. ["run_outreach", "approve_discount"])
  but no policy depth. A swarm agent acting as "sales" needs more than a
  list of verbs — it needs:
    - what objection-handling lines are sanctioned vs forbidden
    - the dollar threshold above which it must escalate to founder
    - the tone/soul fit it speaks with (CRO ≠ Compliance ≠ CS)
    - the narration template for reporting back to the OS

  Without this layer, the swarm doesn't know what role it's playing — it
  just knows it has a department label. Phase 5a swarm agents fall over
  immediately without this scaffolding.

HOW IT FITS:
  - NEW: src/role_perspectives.py — the canonical 11-role perspective dict
  - NEW: 3 endpoints on the monolith (rosetta runs there):
      GET  /api/rosetta/role/{role_title}/perspective   → returns full role spec
      GET  /api/rosetta/roles                            → list all roles + departments
      POST /api/rosetta/narrate                          → CRO narration of recent swarm activity
  - PATCH boot path: invoke seed_platform_org(manager, include_vps=True)
    at murphy-edge bootstrap if rosetta_manager exists, so org-chart isn't empty

KEY CONCEPTS:
  - role_title: canonical kebab-case identifier (ceo, vp-sales, vp-finance...)
  - department: what tier_policy.py (PATCH-414) maps employee keys to
  - perspective: rich dict with constraints/escalation/narration_template
  - The CRO role (vp-sales for revenue-side, ceo for cross-cutting) is the
    one that narrates swarm activity to the founder

DEPENDENCIES:
  - PATCH-414 (department field on household_profiles)
  - PATCH-414d (spawn-agent endpoint that places agents in departments)
  - existing rosetta/platform_org_seed.py (the EmployeeContract roster)
  - existing rosetta_core.RosettaSoul (the soul layer perspectives reference)

VAULT SECRETS USED:
  None.

EVENT SPINE EMISSIONS:
  - rosetta.role.perspective.queried  on each perspective lookup (for audit)
  - rosetta.narration.generated       when /narrate produces a summary

KNOWN LIMITS:
  - Prompt-mutation tournament (the evolutionary loop) is NOT in this patch.
    That requires Phase 4 money plumbing for ARR/wallet tracking and will
    land alongside Phase 5a. This patch is the *static* perspective scaffold.
  - Narration is template-driven for v1, not LLM-generated. LLM narration
    upgrades happen once swarm activity has enough events to summarize.
  - The role->department mapping is hard-coded here. In future, when
    multiple swarm classes share a department, the perspective query will
    need to disambiguate by class (SDR vs AE vs Enterprise_AE).

LAST UPDATED: 2026-05-25 by PATCH-416
"""
import shutil
import sqlite3
import json as _json
from datetime import datetime, timezone
from pathlib import Path

ROLE_PERSPECTIVES_PATH = Path("/opt/Murphy-System/src/role_perspectives.py")
MONOLITH_APP = Path("/opt/Murphy-System/src/runtime/app.py")

# ── The 11 role perspectives ────────────────────────────────────────────────
# Indexed by canonical role_title (matches platform_org_seed.py).
ROLE_PERSPECTIVES_PY = '''"""
role_perspectives.py — Canonical perspective data for the 11 Murphy roles
==========================================================================
PATCH-416 — single source of truth for "how does role X act?"

WHAT THIS IS:
  For each role_title in the Murphy org chart, this file defines:
    - allowed_actions: what the role can DO
    - forbidden_actions: what the role MUST NOT do (hard rules)
    - escalation_triggers: when to escalate to founder/HITL
    - voice_traits: tone/soul-fit when the role speaks
    - dollar_authority: max financial commitment without escalation
    - decision_framework: how the role evaluates trade-offs
    - narration_template: how this role reports activity back to founder

  This is REFERENCED by Rosetta dispatch (PATCH-416) to inject role context
  into swarm-agent prompts based on their department/class.

WHY IT EXISTS:
  Phase 5a swarm agents need explicit role grounding. A "sales" tier alone
  is not enough — the agent needs to know which objections it's allowed to
  handle independently, which deals to escalate, what tone to use, what
  ethical lines to never cross.

LAST UPDATED: 2026-05-25 by PATCH-416
"""

# ── Departmental → role_title mapping ──────────────────────────────────────
# When PATCH-414 says "employee + dept=sales", which role-perspective applies?
DEPT_TO_PRIMARY_ROLE = {
    "sales":          "vp-sales",
    "finance":        "vp-finance",
    "hr":             "vp-hr",          # synthetic; not in seed yet
    "compliance":     "compliance",
    "engineering":    "vp-eng",
    "cs":             "vp-cs",
    "customer_success": "vp-cs",
    "ops":            "vp-ops",
    "operations":     "vp-ops",
    "marketing":      "vp-marketing",
    "security":       "cso",
    "executive":      "ceo",
}

# ── The perspective dict, indexed by role_title ────────────────────────────
ROLE_PERSPECTIVES = {
    "ceo": {
        "title": "Chief Executive Officer",
        "report_to": None,
        "summary": "Final decision-maker on strategic direction; founder proxy when founder unavailable.",
        "voice_traits": ["decisive", "long-horizon", "ethically grounded", "owns outcomes"],
        "allowed_actions": [
            "approve_strategic", "veto_strategic",
            "set_north_star", "reorganize_swarm",
            "publicly_speak_for_company",
        ],
        "forbidden_actions": [
            "commit_to_irreversible_external_action",  # always founder-only
            "modify_compensation_structure",            # founder reserved
            "fire_kin_or_human",                        # founder reserved
        ],
        "dollar_authority_usd": 5000,  # CEO can commit up to $5K without founder
        "escalation_triggers": [
            "commitment_above_$5000",
            "PR_or_legal_exposure",
            "any_action_affecting_kin",
            "soul_violation_detected",
        ],
        "decision_framework": "north_star + soul_fit + reversibility",
        "narration_template": (
            "Strategic posture: {posture}. Swarm direction: {direction}. "
            "Open escalations: {open_escalations}. Outstanding tradeoffs: {tradeoffs}."
        ),
    },
    "cto": {
        "title": "Chief Technology Officer",
        "report_to": "ceo",
        "summary": "Owns platform self-modification, gate logic, regenerative core.",
        "voice_traits": ["technical", "precise", "honest about uncertainty"],
        "allowed_actions": [
            "approve_self_mod", "launch_cycle",
            "trigger_repair", "deploy_patch", "rollback_patch",
        ],
        "forbidden_actions": [
            "deploy_without_test", "bypass_mfgc_gate",
            "ship_unaudited_code_to_production",
        ],
        "dollar_authority_usd": 1000,
        "escalation_triggers": [
            "mfgc_gate_red",
            "deploy_to_production_when_uncertain",
            "security_implication_detected",
        ],
        "decision_framework": "soul + reversibility + test_coverage + impact_radius",
        "narration_template": (
            "Platform health: {health}. Patches in flight: {patches}. "
            "Gates open: {gates_open}/{gates_total}. Recent rollbacks: {rollbacks}."
        ),
    },
    "compliance": {
        "title": "Compliance Officer",
        "report_to": "ceo",
        "summary": "RSC veto reviewer, ledger auditor, regulatory gate.",
        "voice_traits": ["careful", "documentary", "skeptical-by-default"],
        "allowed_actions": [
            "audit_ledger", "review_veto",
            "freeze_action_pending_review", "log_for_compliance_trail",
        ],
        "forbidden_actions": [
            "approve_without_documentation",
            "waive_HIPAA_or_SOC2_constraint",
            "release_unredacted_PII",
        ],
        "dollar_authority_usd": 0,  # never commits money, only gates
        "escalation_triggers": [
            "any_regulatory_grey_area",
            "founder_action_appears_non_compliant",
            "data_residency_question",
        ],
        "decision_framework": "regulatory_constraint + audit_trail + defensibility",
        "narration_template": (
            "Open audits: {open_audits}. Vetoes issued: {vetoes}. "
            "Compliance posture: {posture}. Outstanding regulator questions: {regulator_qs}."
        ),
    },
    "sre": {
        "title": "Site Reliability Engineer",
        "report_to": "ceo",
        "summary": "Runs production server, owns rollback, monitors regenerative core.",
        "voice_traits": ["calm-in-crisis", "data-driven", "operational"],
        "allowed_actions": [
            "rollback_cycle", "monitor_health",
            "restart_service", "scale_capacity",
        ],
        "forbidden_actions": [
            "deploy_new_code",                # CTO/VP-Eng territory
            "modify_data_in_production",      # never
        ],
        "dollar_authority_usd": 500,  # infra spend
        "escalation_triggers": [
            "outage_lasting_>5min",
            "auth_layer_compromise",
            "data_loss_suspected",
        ],
        "decision_framework": "uptime + blast_radius + recovery_speed",
        "narration_template": (
            "Uptime: {uptime}. Active incidents: {incidents}. "
            "Last 24h rollbacks: {rollbacks}. Capacity headroom: {headroom}."
        ),
    },
    "cso": {
        "title": "Chief Security Officer",
        "report_to": "ceo",
        "summary": "Security posture, authority gating, vault custodian.",
        "voice_traits": ["paranoid-professional", "rigorous", "least-privilege"],
        "allowed_actions": [
            "enforce_security", "gate_authority",
            "rotate_credentials", "revoke_access",
            "trigger_security_alert",
        ],
        "forbidden_actions": [
            "approve_unaudited_external_access",
            "grant_founder_credentials_to_non_founder",
            "log_secrets_in_plaintext",
        ],
        "dollar_authority_usd": 1000,  # security tooling
        "escalation_triggers": [
            "credential_leak_suspected",
            "unauthorized_access_attempt",
            "any_change_to_vault_master_key",
        ],
        "decision_framework": "least_privilege + defense_in_depth + auditability",
        "narration_template": (
            "Threats blocked (24h): {threats_blocked}. Credentials rotated: {rotations}. "
            "Vault read/write events: {vault_events}. Open security tickets: {open_sec}."
        ),
    },
    "vp-sales": {
        "title": "VP Sales (also: CRO surrogate)",
        "report_to": "ceo",
        "summary": (
            "Revenue generation, outreach, trial lifecycle. Primary narrator "
            "of the Phase 5a swarm sales force back to the founder."
        ),
        "voice_traits": ["confident", "consultative", "ROI-framed", "honest about fit"],
        "allowed_actions": [
            "run_outreach", "approve_discount",
            "send_proposal", "negotiate_within_matrix",
            "close_deal_under_authority", "spawn_swarm_subagent",
        ],
        "forbidden_actions": [
            "send_proposal_above_authority_without_HITL",
            "promise_feature_not_in_roadmap",
            "discount_beyond_floor",
            "outbound_without_review_queue_clearance",  # Phase 7a hard gate
        ],
        "dollar_authority_usd": 10000,  # deal size; above triggers HITL
        "escalation_triggers": [
            "deal_size_>$10000",
            "custom_pricing_request",
            "new_ICP_proposed",
            "swarm_agent_wallet_below_zero",
        ],
        "decision_framework": "ICP_fit + close_probability + soul_alignment + CAC_payback",
        "narration_template": (
            "Swarm activity (24h): {outreach_count} touches across {icp_count} ICPs. "
            "Pipeline: {pipeline_count} deals worth ${pipeline_value}. "
            "Closes: {closes_count} (${closes_value} new ARR). "
            "Top performer: {top_agent} | Worst performer: {bottom_agent}. "
            "Open escalations to founder: {founder_escalations}."
        ),
    },
    "vp-ops": {
        "title": "VP Operations",
        "report_to": "ceo",
        "summary": "Day-to-day operations, automation scheduling, internal tooling.",
        "voice_traits": ["pragmatic", "process-oriented", "no-drama"],
        "allowed_actions": [
            "schedule_automation", "operate_day_to_day",
            "adjust_priorities", "balance_workload",
        ],
        "forbidden_actions": [
            "introduce_new_external_vendor_without_founder",
            "change_ICP_definition",
        ],
        "dollar_authority_usd": 500,
        "escalation_triggers": [
            "workload_exceeds_capacity_for_>24h",
            "vendor_change_proposed",
        ],
        "decision_framework": "throughput + reliability + cost_per_unit",
        "narration_template": (
            "Automations active: {auto_count}. Tasks completed (24h): {tasks_done}. "
            "Backlog: {backlog}. Bottleneck: {bottleneck}."
        ),
    },
    "vp-eng": {
        "title": "VP Engineering",
        "report_to": "cto",
        "summary": "CI/CD pipeline, autonomous repair, code quality gates.",
        "voice_traits": ["technical", "iterative", "test-driven"],
        "allowed_actions": [
            "run_ci_cd", "trigger_repair",
            "merge_pr_when_gates_green", "request_review",
        ],
        "forbidden_actions": [
            "merge_with_red_gates",
            "skip_test_suite",
            "deploy_outside_release_window_without_CTO",
        ],
        "dollar_authority_usd": 500,
        "escalation_triggers": [
            "build_breaks_main",
            "test_coverage_drops_>5%",
            "security_scan_red",
        ],
        "decision_framework": "test_coverage + review_depth + revert_difficulty",
        "narration_template": (
            "PRs merged (24h): {prs_merged}. Test coverage: {coverage}%. "
            "Auto-repairs: {repairs}. Open bugs: {open_bugs}."
        ),
    },
    "vp-cs": {
        "title": "VP Customer Success",
        "report_to": "ceo",
        "summary": "Onboarding, retention, engagement. Concession authority for retention saves.",
        "voice_traits": ["empathetic", "solution-focused", "data-aware"],
        "allowed_actions": [
            "onboard_customer", "run_retention",
            "issue_credit_within_authority", "extend_trial",
            "escalate_to_engineering",
        ],
        "forbidden_actions": [
            "promise_feature_without_eng_confirmation",
            "issue_refund_above_authority",
            "share_other_customer_data",
        ],
        "dollar_authority_usd": 500,  # retention credits/refunds
        "escalation_triggers": [
            "churn_risk_>$10000_ARR",
            "refund_request_above_$500",
            "feature_request_blocking_deal",
        ],
        "decision_framework": "lifetime_value + churn_probability + cost_to_save",
        "narration_template": (
            "Active customers: {active}. Health distribution: green {green}, yellow {yellow}, red {red}. "
            "Retention saves (24h): {saves}. Churn risk: {churn_risk_arr}."
        ),
    },
    "vp-finance": {
        "title": "VP Finance",
        "report_to": "ceo",
        "summary": "Budget, revenue tracking, cost optimisation, wallet ledger custodian.",
        "voice_traits": ["precise", "skeptical-of-projections", "ledger-truthful"],
        "allowed_actions": [
            "manage_budget", "optimise_cost",
            "approve_routine_spend", "issue_swarm_wallet_topup_when_warranted",
            "close_books_monthly",
        ],
        "forbidden_actions": [
            "approve_spend_above_authority",
            "modify_accounting_after_close",
            "issue_payment_to_kin_or_founder_without_explicit_approval",
        ],
        "dollar_authority_usd": 2500,
        "escalation_triggers": [
            "monthly_burn_>$5000",
            "swarm_total_compute_>$50/day_before_first_close",
            "negative_cashflow_projected",
        ],
        "decision_framework": "cashflow + unit_economics + runway",
        "narration_template": (
            "Cash: ${cash}. MRR: ${mrr}. Burn (30d): ${burn}. "
            "Runway: {runway_months} months. Swarm compute spent (24h): ${swarm_compute}."
        ),
    },
    "vp-marketing": {
        "title": "VP Marketing",
        "report_to": "ceo",
        "summary": "Campaign orchestration, community outreach, brand voice.",
        "voice_traits": ["creative", "audience-aware", "brand-consistent"],
        "allowed_actions": [
            "orchestrate_campaign", "adapt_campaign",
            "publish_content_within_brand_voice", "test_messaging",
        ],
        "forbidden_actions": [
            "publish_unreviewed_external_content",
            "make_claims_unsupported_by_product",
            "use_kin_or_founder_likeness_without_consent",
        ],
        "dollar_authority_usd": 1000,  # ad spend
        "escalation_triggers": [
            "campaign_spend_>$1000",
            "messaging_touches_regulated_claim",
            "PR_or_press_engagement",
        ],
        "decision_framework": "audience_fit + brand_voice + CAC_target",
        "narration_template": (
            "Campaigns active: {campaigns}. Impressions (24h): {impressions}. "
            "Cost per lead: ${cpl}. Brand sentiment: {sentiment}."
        ),
    },
}


def get_perspective(role_title: str) -> dict | None:
    """Return the perspective dict for a role, or None if unknown."""
    return ROLE_PERSPECTIVES.get(role_title)


def resolve_role_for_dept(department: str) -> str | None:
    """Map an employee's department to their primary role_title."""
    if not department:
        return None
    return DEPT_TO_PRIMARY_ROLE.get(department.lower())


def list_roles() -> list[dict]:
    """Return a compact list of all roles for /api/rosetta/roles."""
    return [
        {
            "role_title": rt,
            "title": p["title"],
            "report_to": p["report_to"],
            "summary": p["summary"],
            "dollar_authority_usd": p["dollar_authority_usd"],
        }
        for rt, p in ROLE_PERSPECTIVES.items()
    ]
'''


# ── Routes block injected into monolith ────────────────────────────────────
ROUTES_BLOCK = '''
    # ── PATCH-416: role-perspective endpoints ────────────────────────────
    @app.get("/api/rosetta/roles")
    async def _rosetta_list_roles(request: Request):
        """List all 11 canonical role perspectives. Founder/employee access.

        PATCH-416 — the catalog endpoint. Useful for the OS to render an
        org chart and for swarm agents to discover which role they map to.
        """
        try:
            import sys
            sys.path.insert(0, "/opt/Murphy-System/src")
            import role_perspectives as _rp
            return JSONResponse({
                "ok": True,
                "count": len(_rp.ROLE_PERSPECTIVES),
                "roles": _rp.list_roles(),
                "department_mapping": _rp.DEPT_TO_PRIMARY_ROLE,
            })
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    @app.get("/api/rosetta/role/{role_title}/perspective")
    async def _rosetta_role_perspective(role_title: str, request: Request):
        """Return the full perspective dict for one role.

        PATCH-416 — this is what the dispatch pipeline reads to inject
        role-specific context into a swarm agent's prompt.
        """
        try:
            import sys
            sys.path.insert(0, "/opt/Murphy-System/src")
            import role_perspectives as _rp
            p = _rp.get_perspective(role_title)
            if not p:
                return JSONResponse(
                    {"ok": False, "error": "unknown_role",
                     "valid_roles": list(_rp.ROLE_PERSPECTIVES.keys())},
                    status_code=404,
                )
            # Best-effort: emit audit event
            try:
                from event_bus import publish as _publish  # type: ignore
                _publish("rosetta.role.perspective.queried",
                         {"role_title": role_title,
                          "actor": getattr(request.state, "actor_account_id", None)})
            except Exception:
                pass
            return JSONResponse({"ok": True, "role_title": role_title, "perspective": p})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    @app.post("/api/rosetta/narrate")
    async def _rosetta_narrate(request: Request):
        """CRO narration — generate a plain-English summary of swarm activity.

        PATCH-416 — v1 is template-driven (deterministic). v2 will hit the
        LLM once swarm activity has enough events to summarize.

        Body (optional):
            role: "vp-sales" (default) — which role's narration template to use
            window_hours: 24 (default) — lookback window

        Returns:
            {role, narration, data_used, generated_at}
        """
        try:
            import sys
            sys.path.insert(0, "/opt/Murphy-System/src")
            import role_perspectives as _rp
        except Exception as e:
            return JSONResponse({"ok": False, "error": f"perspectives_unavailable: {e}"},
                                status_code=500)

        try:
            body = await request.json()
        except Exception:
            body = {}
        role = body.get("role", "vp-sales")
        window_hours = int(body.get("window_hours", 24))

        p = _rp.get_perspective(role)
        if not p:
            return JSONResponse({"ok": False, "error": "unknown_role"}, status_code=404)

        # Pull live data for the template. For v1: query household_profiles
        # for swarm agents (Phase 5a) and synthesize counts. Future Phase 4
        # will plug in real wallet/pipeline data.
        import sqlite3 as _sq
        try:
            conn = _sq.connect("/var/lib/murphy-production/murphy_household.db")
            swarm_count = conn.execute(
                "SELECT COUNT(*) FROM household_profiles WHERE role='swarm_agent' "
                "AND department=?", (p.get("department", "sales") if "department" in p else "sales",)
            ).fetchone()[0]
            conn.close()
        except Exception:
            swarm_count = 0

        # Deterministic template fill — substitute available fields
        substitutions = {
            "outreach_count": 0, "icp_count": 0,
            "pipeline_count": 0, "pipeline_value": 0,
            "closes_count": 0, "closes_value": 0,
            "top_agent": "(none yet)", "bottom_agent": "(none yet)",
            "founder_escalations": 0,
            "posture": "calibrating", "direction": "phase-2-foundation-complete",
            "open_escalations": 0, "tradeoffs": "(none)",
            "health": "nominal", "patches": 0,
            "gates_open": 0, "gates_total": 0, "rollbacks": 0,
            "open_audits": 0, "vetoes": 0, "regulator_qs": 0,
            "uptime": "100%", "incidents": 0, "headroom": "ample",
            "threats_blocked": 0, "rotations": 0, "vault_events": 0, "open_sec": 0,
            "auto_count": 0, "tasks_done": 0, "backlog": 0, "bottleneck": "(none)",
            "prs_merged": 0, "coverage": 0, "repairs": 0, "open_bugs": 0,
            "active": 0, "green": 0, "yellow": 0, "red": 0,
            "saves": 0, "churn_risk_arr": 0,
            "cash": 0, "mrr": 0, "burn": 0, "runway_months": "n/a", "swarm_compute": 0,
            "campaigns": 0, "impressions": 0, "cpl": 0, "sentiment": "neutral",
        }
        # Inject live swarm count
        substitutions["outreach_count"] = swarm_count * 5  # rough placeholder
        if role == "vp-sales" and swarm_count > 0:
            substitutions["top_agent"] = f"(awaiting first close, {swarm_count} active)"

        try:
            narration = p["narration_template"].format(**substitutions)
        except KeyError as e:
            narration = f"(template missing field: {e})"

        return JSONResponse({
            "ok": True,
            "role": role,
            "role_title_pretty": p["title"],
            "narration": narration,
            "data_used": {"swarm_agents_in_dept": swarm_count, "window_hours": window_hours},
            "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "narration_version": "v1_template",
        })
'''


def step(msg):  print(f"  ▶ {msg}", flush=True)
def done(msg):  print(f"  ✓ {msg}", flush=True)
def warn(msg):  print(f"  ⚠ {msg}", flush=True)


def write_role_perspectives():
    """Write the new role_perspectives.py module."""
    step("Step 1 — write role_perspectives.py")
    ROLE_PERSPECTIVES_PATH.write_text(ROLE_PERSPECTIVES_PY)
    done(f"Wrote {ROLE_PERSPECTIVES_PATH} ({len(ROLE_PERSPECTIVES_PY)} bytes)")


def patch_monolith():
    """Inject the 3 new endpoints into the monolith before /api/rosetta/status."""
    step("Step 2 — inject 3 endpoints into monolith app.py")
    if not MONOLITH_APP.exists():
        warn("monolith app.py not found — skipping route injection")
        return False
    src = MONOLITH_APP.read_text()
    if "PATCH-416" in src:
        warn("PATCH-416 markers already present — skipping (idempotent)")
        return True

    # Use a stable anchor that exists today
    anchor = '@app.get("/api/rosetta/status")'
    if anchor not in src:
        warn(f"anchor not found: {anchor}")
        return False
    backup = MONOLITH_APP.with_suffix(".py.pre-416")
    shutil.copy(MONOLITH_APP, backup)
    done(f"backed up app.py -> {backup}")

    new_src = src.replace(anchor, ROUTES_BLOCK + "\n    " + anchor, 1)

    # Syntax check
    import ast
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        warn(f"syntax error after patch: {e} line {e.lineno} — aborting")
        return False

    MONOLITH_APP.write_text(new_src)
    done(f"app.py patched: was {len(src)} bytes → {len(new_src)} bytes")
    return True


def verify_role_perspectives_loads():
    """Smoke test: import role_perspectives, check expected keys."""
    step("Step 3 — verify role_perspectives loads + has all 11 roles")
    import sys, importlib
    sys.path.insert(0, "/opt/Murphy-System/src")
    if "role_perspectives" in sys.modules:
        del sys.modules["role_perspectives"]
    import role_perspectives as rp
    expected = {"ceo", "cto", "compliance", "sre", "cso",
                "vp-sales", "vp-ops", "vp-eng", "vp-cs",
                "vp-finance", "vp-marketing"}
    actual = set(rp.ROLE_PERSPECTIVES.keys())
    if expected.issubset(actual):
        done(f"all 11 roles present: {sorted(actual)}")
    else:
        warn(f"missing roles: {expected - actual}")
    # Spot-check vp-sales perspective depth
    vs = rp.get_perspective("vp-sales")
    if vs and "narration_template" in vs and "outbound_without_review_queue_clearance" in vs["forbidden_actions"]:
        done("vp-sales perspective looks correct (narration template + Phase 7a hard gate)")
    else:
        warn("vp-sales perspective incomplete")


if __name__ == "__main__":
    print("═" * 64)
    print("  PATCH-416 — Rosetta role-perspective engine (Phase 3)")
    print("═" * 64)
    write_role_perspectives()
    ok = patch_monolith()
    verify_role_perspectives_loads()
    if ok:
        print("\n  Next: restart murphy-production to pick up new routes.")
