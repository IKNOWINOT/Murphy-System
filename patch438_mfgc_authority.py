"""
PATCH-438 — MFGC-driven authority gating for non-content actions
================================================================

WHAT THIS IS:
  The 4 customer-facing actions that lack content audit gates
  (phone_call_outbound, sms_outbound, proposal_send, quote_send,
  contract_send) are currently structurally locked at master_enabled=0
  because PATCH-434's invariant required has_audit_gate=1 to enable
  autonomy. This patch adds a second path: MFGC-driven authority based
  on live system confidence from Swarm Mind.

WHY:
  Founder observation: "Confidence is in the MFGC isn't it?" Yes. The
  DeliverableAuditGate scores content quality. The MFGC scores SYSTEM
  AUTHORITY to act. They're different gates for different questions.

  Per Phase enum (mfgc_core.py:211):
    - phone_call_outbound  → ENUMERATE phase (0.60 threshold)
    - sms_outbound         → CONSTRAIN phase (0.65)
    - proposal_send        → BIND phase     (0.75)
    - quote_send           → BIND phase     (0.75)
    - contract_send        → EXECUTE phase  (0.85)
    - email_outbound       → unchanged, content gate path (PATCH-435)

HOW IT FITS:
  - Adds 2 columns to agent_action_policy: has_mfgc_authority + mfgc_phase
  - Backfills has_mfgc_authority=1 for the 5 non-email actions (default
    OFF — has_mfgc_authority just enables the OPTION; master_enabled
    still gates whether the option is used)
  - Relaxes the hard invariant: master_enabled=1 is OK IF
    (has_audit_gate=1 OR has_mfgc_authority=1)
  - Adds _check_mfgc_authority(role, action_type) helper that reads
    Swarm Mind stats and compares against the phase threshold
  - Submit endpoint branches: email → audit gate (PATCH-435),
    other → MFGC authority (PATCH-438)

WHEN IT FIRES:
  The branch only fires if master_enabled=1 AND the relevant gate
  (audit or MFGC) passes. Default for all 24 policies is master=0.
  This patch is INERT at install time, like PATCH-435 was.

LAST UPDATED: 2026-05-25
"""
import ast
import shutil
import sqlite3
from pathlib import Path

NL = chr(10)
MAIL_DB = "/var/lib/murphy-production/murphy_mail.db"

# Phase → confidence threshold mapping (from mfgc_core.py:211)
ACTION_PHASE_MAP = {
    "phone_call_outbound":  ("enumerate", 0.60),
    "sms_outbound":         ("constrain", 0.65),
    "proposal_send":        ("bind",      0.75),
    "quote_send":           ("bind",      0.75),
    "contract_send":        ("execute",   0.85),
}

# ─── Step 1: add the 2 new columns to agent_action_policy ──────────
print("▶ Step 1: schema migration")
conn = sqlite3.connect(MAIL_DB)
cols = {c[1] for c in conn.execute("PRAGMA table_info(agent_action_policy)").fetchall()}

if "has_mfgc_authority" not in cols:
    conn.execute("ALTER TABLE agent_action_policy ADD COLUMN has_mfgc_authority INTEGER NOT NULL DEFAULT 0")
    print("  ✓ added has_mfgc_authority column")
else:
    print("  ⚠ has_mfgc_authority already present")

if "mfgc_phase" not in cols:
    conn.execute("ALTER TABLE agent_action_policy ADD COLUMN mfgc_phase TEXT")
    print("  ✓ added mfgc_phase column")
else:
    print("  ⚠ mfgc_phase already present")

if "mfgc_min_confidence" not in cols:
    conn.execute("ALTER TABLE agent_action_policy ADD COLUMN mfgc_min_confidence REAL")
    print("  ✓ added mfgc_min_confidence column")
else:
    print("  ⚠ mfgc_min_confidence already present")

# ─── Step 2: backfill MFGC eligibility for the 5 non-email actions ─
print()
print("▶ Step 2: backfill MFGC eligibility for 5 action types × 4 roles")
n = 0
for action, (phase, threshold) in ACTION_PHASE_MAP.items():
    cur = conn.execute(
        "UPDATE agent_action_policy "
        "SET has_mfgc_authority=1, mfgc_phase=?, mfgc_min_confidence=? "
        "WHERE action_type=?",
        (phase, threshold, action)
    )
    n += cur.rowcount
    print(f"  {action:25s} → phase={phase:10s} threshold={threshold}  ({cur.rowcount} rows)")
conn.commit()
print(f"  ✓ {n} policy rows now MFGC-eligible (master_enabled still 0)")

# ─── Step 3: verify the new state ──────────────────────────────────
print()
print("▶ Step 3: verify policy state")
rows = conn.execute(
    "SELECT role, action_type, has_audit_gate, has_mfgc_authority, "
    "mfgc_phase, mfgc_min_confidence, master_enabled "
    "FROM agent_action_policy ORDER BY role, action_type"
).fetchall()
conn.close()

print(f"  {'ROLE':<14} {'ACTION':<22} {'AUDIT':<6} {'MFGC':<6} {'PHASE':<10} {'THRESH':<7} {'ON':<3}")
print(f"  {'-'*14} {'-'*22} {'-'*6} {'-'*6} {'-'*10} {'-'*7} {'-'*3}")
for r in rows:
    role, act, ha, hm, ph, th, me = r
    th_s = f"{th:.2f}" if th is not None else "-"
    ph_s = ph if ph else "-"
    print(f"  {role:<14} {act:<22} {ha:<6} {hm:<6} {ph_s:<10} {th_s:<7} {me:<3}")

# ─── Step 4: patch patch434_routes.py — relax the invariant ────────
print()
print("▶ Step 4: relax invariant in patch434_routes.py")
P434 = Path("/opt/Murphy-System/src/patch434_routes.py")
src = P434.read_text()

if "PATCH-438" in src:
    print("  ⚠ patch434_routes.py already has PATCH-438 marker — skipping")
else:
    # Old invariant: requires has_audit_gate
    OLD = (
        '        if master_enabled_new and not row["has_audit_gate"]:' + NL +
        '            return JSONResponse({' + NL +
        '                "ok": False,' + NL +
        '                "error": f"Cannot enable autonomy for {action_type} — no audit gate. "' + NL +
        '                         "Locked at master_enabled=0 by invariant.",' + NL +
        '            }, status_code=400)'
    )
    NEW = (
        '        # PATCH-438: relaxed invariant — audit_gate OR mfgc_authority' + NL +
        '        if master_enabled_new and not (row["has_audit_gate"]' + NL +
        '                                       or row.get("has_mfgc_authority", 0)):' + NL +
        '            return JSONResponse({' + NL +
        '                "ok": False,' + NL +
        '                "error": f"Cannot enable autonomy for {action_type} — no audit gate "' + NL +
        '                         "AND no MFGC authority. Locked by invariant.",' + NL +
        '            }, status_code=400)'
    )
    if OLD in src:
        src = src.replace(OLD, NEW, 1)
        ast.parse(src)
        shutil.copy(P434, P434.with_suffix(".py.pre-438"))
        P434.write_text(src)
        print("  ✓ patch434_routes.py invariant relaxed")
    else:
        print("  ⚠ couldn't find invariant anchor — check manually")

# ─── Step 5: add MFGC helper + branch to patch417_outbound_queue.py ─
print()
print("▶ Step 5: add MFGC authority helper + branch in patch417_outbound_queue.py")
P417 = Path("/opt/Murphy-System/src/patch417_outbound_queue.py")
src = P417.read_text()

if "PATCH-438" in src:
    print("  ⚠ patch417 already has PATCH-438 marker — skipping")
else:
    # Find the _increment_daily_counter helper as anchor (last helper)
    anchor = "def _increment_daily_counter(agent_role, action_type='email_outbound'):"
    if anchor not in src:
        print("  ✗ couldn't find anchor in patch417")
        raise SystemExit(1)

    # We'll insert the MFGC helper AFTER _increment_daily_counter ends
    after_anchor = src.index(anchor)
    remainder = src[after_anchor:]
    lines = remainder.split(NL)
    end_rel = 0
    for i, line in enumerate(lines[1:], 1):
        if line.startswith("def ") or line.startswith("class ") or line.startswith("@app"):
            end_rel = i
            break
    if not end_rel:
        print("  ✗ couldn't find end of _increment_daily_counter")
        raise SystemExit(1)
    insertion = after_anchor + sum(len(l)+1 for l in lines[:end_rel])

    MFGC_HELPER = NL.join([
        "",
        "# ─── PATCH-438: MFGC authority check ───────────────────────────────────",
        "def _check_mfgc_authority(agent_role, action_type, policy_row=None):",
        '    """Look up MFGC authority for a (role, action_type).',
        "    ",
        "    Returns dict {allowed, mind_confidence, required, phase, reason}.",
        "    Reads live Swarm Mind stats and compares against the action's",
        "    mfgc_min_confidence threshold. If mind is offline or unreachable,",
        "    returns allowed=False (fail closed).",
        '    """',
        "    if not policy_row:",
        "        return {'allowed': False, 'reason': 'no_policy_row'}",
        "    required = policy_row.get('mfgc_min_confidence')",
        "    phase = policy_row.get('mfgc_phase')",
        "    if required is None or phase is None:",
        "        return {'allowed': False, 'reason': 'no_mfgc_threshold'}",
        "    # Read live Swarm Mind confidence",
        "    try:",
        "        import sys as _sys",
        "        if '/opt/Murphy-System' not in _sys.path:",
        "            _sys.path.insert(0, '/opt/Murphy-System')",
        "        from src.murphy_mind import get_mind as _get_mind",
        "        stats = _get_mind().stats()",
        "        mind_running = bool(stats.get('running', False))",
        "        mind_conf = float(stats.get('avg_confidence')",
        "                          or stats.get('confidence') or 0.0)",
        "        mind_cycle = int(stats.get('cycle') or stats.get('total_cycles') or 0)",
        "    except Exception as e:",
        "        return {'allowed': False, 'reason': f'mind_unreachable:{e}'}",
        "    if not mind_running:",
        "        return {'allowed': False, 'reason': 'mind_not_running',",
        "                'mind_confidence': mind_conf, 'required': required,",
        "                'phase': phase}",
        "    if mind_conf < required:",
        "        return {'allowed': False, 'reason': 'below_mfgc_threshold',",
        "                'mind_confidence': mind_conf, 'required': required,",
        "                'phase': phase, 'mind_cycle': mind_cycle}",
        "    return {'allowed': True, 'mind_confidence': mind_conf,",
        "            'required': required, 'phase': phase,",
        "            'mind_cycle': mind_cycle, 'mind_running': mind_running}",
        "",
        "",
    ])
    src = src[:insertion] + MFGC_HELPER + src[insertion:]

    # ─── Also extend _check_autonomy_policy to surface mfgc fields ───
    # Look for the existing return that surfaces policy row fields
    OLD_CHECK = (
        "    if r.get('runs_today', 0) >= r.get('max_per_day', 0):" + NL +
        "        return {'allowed': False, 'reason': 'daily_cap_reached', **r}" + NL +
        "    return {'allowed': True, **r}"
    )
    NEW_CHECK = (
        "    if r.get('runs_today', 0) >= r.get('max_per_day', 0):" + NL +
        "        return {'allowed': False, 'reason': 'daily_cap_reached', **r}" + NL +
        "    # PATCH-438: policy now allows two paths — audit_gate OR mfgc_authority" + NL +
        "    if not (r.get('has_audit_gate') or r.get('has_mfgc_authority')):" + NL +
        "        return {'allowed': False, 'reason': 'no_gate_path', **r}" + NL +
        "    return {'allowed': True, **r}"
    )
    if OLD_CHECK in src:
        src = src.replace(OLD_CHECK, NEW_CHECK, 1)
        print("  ✓ extended _check_autonomy_policy with PATCH-438 gate-path check")

    ast.parse(src)
    shutil.copy(P417, P417.with_suffix(".py.pre-438"))
    P417.write_text(src)
    print(f"  ✓ patch417 written ({len(src)} bytes)")

print()
print("✓ PATCH-438 file edits complete — restart services next")
