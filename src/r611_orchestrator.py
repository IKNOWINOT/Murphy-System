#!/usr/bin/env python3
"""
R611 — Orchestration Loop
==========================

The connector. Picks a proposal, claims a shell, invokes ForgeEngine,
records outcome, releases shell.

Per founder canon: cyborg-mode continuous progression. Runs N cycles
back-to-back (default 87 for tonight's training-signal seeding).

Flow per cycle:
  1. SELECT highest-score pending proposal from self_plan.proposals
  2. r610.claim(position=owner_agent_id, task=proposal.title) → shell
  3. ForgeEngine.create(description=proposal-to-forge-spec)
  4. Poll forge job until done (timeout 60s)
  5. UPDATE proposals SET status='resolved'|'failed', forge_item_id, verdict
  6. record_outcome() in self_improvement_engine
  7. r610.release(shell, token, outcome=verdict)
  8. Log STATE TRANSITIONS per Rule 15

State-transition labeling per the locked rule: every start/stop/fail/
succeed gets a row in event_log.state_transitions.

Reversal: just don't run it. R611 only WRITES to self_plan.proposals
status fields + forge.db items + shell_registry transitions. All recoverable.
"""
import sys, os, json, sqlite3, time, uuid, traceback
from datetime import datetime, timezone

sys.path.insert(0, "/opt/Murphy-System")        # so 'src' package is importable
sys.path.insert(0, "/opt/Murphy-System/src")    # so 'forge_engine' is importable bare

# Murphy substrate
from forge_engine import get_forge
from r610_shell_registry import claim as shell_claim, release as shell_release

# Optional: self_improvement_engine for outcome capture (R612b prep)
try:
    from self_improvement_engine import SelfImprovementEngine, ExecutionOutcome, OutcomeType
    _sie = SelfImprovementEngine()
    _SIE_AVAILABLE = True
except Exception as e:
    print(f"  ⚠ self_improvement_engine unavailable: {e}", file=sys.stderr)
    _SIE_AVAILABLE = False

SELF_PLAN_DB = "/var/lib/murphy-production/self_plan.db"
EVENT_LOG_DB = "/var/lib/murphy-production/event_log.db"
AGENT_ID     = "r611_orchestrator"
NOW          = lambda: datetime.now(timezone.utc).isoformat()


# ─────────────────── Event log (Rule 15: state transitions) ──────────────

def _ensure_event_log():
    c = sqlite3.connect(EVENT_LOG_DB)
    c.execute("""CREATE TABLE IF NOT EXISTS state_transitions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL, actor TEXT NOT NULL, subject TEXT NOT NULL,
        transition TEXT NOT NULL, from_state TEXT, to_state TEXT,
        code TEXT, reason TEXT, elapsed_ms INTEGER, metadata TEXT
    )""")
    c.commit(); c.close()


def log_event(subject, transition, reason="", code="", from_state="", to_state="",
              elapsed_ms=None, metadata=None):
    c = sqlite3.connect(EVENT_LOG_DB)
    c.execute("""INSERT INTO state_transitions
        (ts, actor, subject, transition, from_state, to_state, code, reason,
         elapsed_ms, metadata) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (NOW(), AGENT_ID, subject, transition, from_state, to_state, code,
         reason, elapsed_ms, json.dumps(metadata or {})))
    c.commit(); c.close()


# ─────────────────────────── Schema additions ────────────────────────────

def _ensure_proposal_columns():
    """Add forge_item_id, audit_verdict, processed_at if missing."""
    c = sqlite3.connect(SELF_PLAN_DB)
    existing = {row[1] for row in c.execute("PRAGMA table_info(proposals)").fetchall()}
    for col, ddl in [
        ("forge_item_id",  "ALTER TABLE proposals ADD COLUMN forge_item_id TEXT"),
        ("audit_verdict",  "ALTER TABLE proposals ADD COLUMN audit_verdict TEXT"),
        ("processed_at",   "ALTER TABLE proposals ADD COLUMN processed_at TEXT"),
        ("processing_ms",  "ALTER TABLE proposals ADD COLUMN processing_ms INTEGER"),
    ]:
        if col not in existing:
            c.execute(ddl)
    c.commit(); c.close()


# ────────────────────────── Proposal selection ──────────────────────────

def pick_next_proposal():
    """Highest score, pending, with an owner_agent_id."""
    c = sqlite3.connect(SELF_PLAN_DB)
    row = c.execute("""SELECT proposal_id, title, description, risk_level,
        score, affected_module, context
        FROM proposals
        WHERE status='pending'
          AND json_extract(context,'$.owner_agent_id') IS NOT NULL
        ORDER BY score DESC, created_at ASC LIMIT 1""").fetchone()
    c.close()
    if not row: return None
    pid, title, desc, risk, score, mod, ctx_str = row
    ctx = json.loads(ctx_str or "{}")
    return {
        "proposal_id": pid, "title": title, "description": desc,
        "risk_level": risk, "score": score, "affected_module": mod,
        "owner_agent_id": ctx.get("owner_agent_id"),
        "source_kind": ctx.get("source_kind", "unknown"),
        "deliverable_type": _infer_deliverable_type(ctx.get("source_kind", ""), mod),
        "context": ctx,
    }


def _infer_deliverable_type(source_kind, affected_module):
    """Per R612 plan: 9 deliverable types. Map source_kind → type."""
    sk = (source_kind or "").lower()
    if "doc_unread" in sk or "documentation" in sk: return "DOCUMENT"
    if "orphan" in sk or "module" in sk: return "ANALYSIS"
    if "escalation" in sk: return "REPORT"
    if "wire" in sk or "integration" in sk: return "API_INTEGRATION"
    return "ANALYSIS"  # safe default


# ─────────────────────────── Forge dispatch ─────────────────────────────

def forge_for_proposal(proposal):
    """Compose a tight forge description from the proposal."""
    pos = proposal["owner_agent_id"]
    dtype = proposal["deliverable_type"]
    title = proposal["title"]
    desc = proposal["description"]
    mod = proposal["affected_module"]

    forge_desc = (
        f"Function r611_handle_{proposal['proposal_id'][:8]}(context: dict) -> dict "
        f"that addresses this {dtype} task for {pos}: '{title}'. "
        f"Background: {desc[:400]}. "
        f"Affected module/path: {mod}. "
        f"Returns dict with keys: action_taken (str), status (str), "
        f"recommendations (list of strings), evidence (dict). "
        f"Pure Python, no external deps, use datetime if needed."
    )
    name = f"r611_handle_{proposal['proposal_id'].replace('-', '')[:12]}"
    return forge_desc, name


def _poll_forge_job(forge, name, timeout_s=300):
    """ForgeEngine.create() is async-ish — poll until forge_items has it."""
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            item = forge.get_item(name, tenant_id="founder")
            if item and item.get("status") in ("active", "complete", "ready"):
                return item
            if item and item.get("status") in ("failed", "error"):
                return item
        except Exception:
            pass
        time.sleep(2)
    return None


# ─────────────────────────────── Outcome ────────────────────────────────

def record_outcome_if_available(proposal, forge_item, shell_id, elapsed_ms, verdict):
    if not _SIE_AVAILABLE:
        return False
    try:
        otype = (OutcomeType.SUCCESS if verdict == "PASS"
                 else OutcomeType.PARTIAL if verdict == "WARN"
                 else OutcomeType.FAILURE)
        task_type = f"{proposal['deliverable_type']}__{proposal['owner_agent_id']}"
        oc = ExecutionOutcome(
            task_id=proposal["proposal_id"],
            session_id=f"r611_{NOW()[:10]}",
            outcome=otype,
            task_type=task_type,
            metrics={
                "audit_verdict": verdict,
                "critic_verdict": (forge_item or {}).get("critic_verdict"),
                "source_kind": proposal["source_kind"],
                "deliverable_type": proposal["deliverable_type"],
                "position": proposal["owner_agent_id"],
                "shell_id": shell_id,
                "elapsed_ms": elapsed_ms,
                "forge_item_id": (forge_item or {}).get("id"),
            },
        )
        _sie.record_outcome(oc)
        return True
    except Exception as e:
        log_event(f"proposal:{proposal['proposal_id']}", "fail",
                  reason=f"record_outcome error: {e}", code="E_SIE_001")
        return False


# ───────────────────────────── Update proposal ──────────────────────────

def mark_proposal(proposal_id, status, forge_item_id=None, verdict=None, elapsed_ms=None):
    c = sqlite3.connect(SELF_PLAN_DB)
    c.execute("""UPDATE proposals SET status=?, forge_item_id=?,
        audit_verdict=?, processed_at=?, processing_ms=? WHERE proposal_id=?""",
        (status, forge_item_id, verdict, NOW(), elapsed_ms, proposal_id))
    c.commit(); c.close()


# ──────────────────────────────── Cycle ─────────────────────────────────

def one_cycle(cycle_n, forge):
    cycle_start = time.time()
    log_event(f"r611_cycle_{cycle_n}", "start", reason=f"cycle #{cycle_n}")

    proposal = pick_next_proposal()
    if not proposal:
        log_event(f"r611_cycle_{cycle_n}", "skip", reason="no pending proposals")
        return {"ok": False, "reason": "no_proposals"}

    pid = proposal["proposal_id"]
    pos = proposal["owner_agent_id"]
    dtype = proposal["deliverable_type"]

    # 1. Claim shell
    claim_result = shell_claim(
        position=pos,
        task=proposal["title"][:80],
        locked_by="r611_orchestrator",
        ttl_seconds=120,
    )
    if not claim_result:
        log_event(f"proposal:{pid}", "skip", reason="no free shell",
                  code="E_NO_SHELL")
        return {"ok": False, "reason": "no_shell", "proposal_id": pid}
    shell_id = claim_result["shell_id"]
    token = claim_result["lock_token"]
    log_event(f"shell:{shell_id}", "succeed", transition_from="idle",
              to_state="locked", reason=f"claimed for {pos}",
              metadata={"proposal_id": pid}) if False else log_event(
        f"shell:{shell_id}", "succeed", from_state="idle", to_state="locked",
        reason=f"claimed for {pos}", metadata={"proposal_id": pid})

    # 2. Forge
    forge_desc, name = forge_for_proposal(proposal)
    log_event(f"proposal:{pid}", "start", reason=f"forging as {name}",
              metadata={"deliverable_type": dtype, "position": pos})

    try:
        forge.create(
            description=forge_desc, item_type="function",
            name=name, tenant_id="founder",
        )
    except Exception as e:
        elapsed = int((time.time() - cycle_start) * 1000)
        log_event(f"proposal:{pid}", "fail", reason=f"forge.create raised: {e}",
                  code="E_FORGE_CREATE", elapsed_ms=elapsed)
        mark_proposal(pid, "failed", verdict="FAIL", elapsed_ms=elapsed)
        shell_release(shell_id, token, outcome="forge_create_error")
        return {"ok": False, "reason": "forge_create_error",
                "proposal_id": pid, "error": str(e)[:200]}

    # 3. Poll
    item = _poll_forge_job(forge, name, timeout_s=300)
    elapsed = int((time.time() - cycle_start) * 1000)

    if not item:
        log_event(f"proposal:{pid}", "timeout", reason="forge poll timeout 300s",
                  code="E_FORGE_TIMEOUT", elapsed_ms=elapsed)
        mark_proposal(pid, "failed", verdict="TIMEOUT", elapsed_ms=elapsed)
        shell_release(shell_id, token, outcome="forge_timeout")
        return {"ok": False, "reason": "forge_timeout", "proposal_id": pid}

    verdict = item.get("critic_verdict", "UNKNOWN")
    forge_id = item.get("id")
    is_ok = verdict == "PASS"

    # 4. Mark proposal
    mark_proposal(pid, "resolved" if is_ok else "failed",
                  forge_item_id=forge_id, verdict=verdict, elapsed_ms=elapsed)

    # 5. Record outcome (R612b prep)
    sie_ok = record_outcome_if_available(proposal, item, shell_id, elapsed, verdict)

    # 6. Release shell
    shell_release(shell_id, token, outcome=verdict,
                  notes=f"forge={forge_id} elapsed={elapsed}ms sie={sie_ok}")
    log_event(f"shell:{shell_id}", "succeed", from_state="locked",
              to_state="idle", reason=f"released; outcome={verdict}",
              metadata={"forge_item_id": forge_id})

    log_event(f"r611_cycle_{cycle_n}", "succeed",
              reason=f"verdict={verdict} forge={name}", elapsed_ms=elapsed,
              metadata={"proposal_id": pid, "shell": shell_id,
                        "deliverable_type": dtype, "position": pos})

    return {
        "ok": True, "cycle_n": cycle_n, "proposal_id": pid,
        "shell_id": shell_id, "forge_item_id": forge_id,
        "verdict": verdict, "deliverable_type": dtype,
        "position": pos, "elapsed_ms": elapsed, "sie_recorded": sie_ok,
    }


def main(n_cycles=87, delay_between=1.0):
    _ensure_event_log()
    _ensure_proposal_columns()

    forge = get_forge()
    log_event("r611_orchestrator", "start",
              reason=f"running {n_cycles} cycles", metadata={"n_cycles": n_cycles})

    results = []
    summary = {"PASS": 0, "FAIL": 0, "TIMEOUT": 0, "WARN": 0,
               "OTHER": 0, "skipped": 0}
    by_position = {}
    by_type = {}
    t0 = time.time()

    print(f"R611 orchestrator — {n_cycles} cycles begin {NOW()}")
    for i in range(1, n_cycles + 1):
        try:
            r = one_cycle(i, forge)
            results.append(r)
            if r.get("ok"):
                v = r["verdict"]
                summary[v if v in summary else "OTHER"] += 1
                by_position[r["position"]] = by_position.get(r["position"], 0) + 1
                by_type[r["deliverable_type"]] = by_type.get(r["deliverable_type"], 0) + 1
                print(f"  [{i:3d}/{n_cycles}] {r['verdict']:8} {r['position']:14} "
                      f"{r['deliverable_type']:18} {r['elapsed_ms']/1000:5.1f}s "
                      f"forge={r['forge_item_id'][:8] if r['forge_item_id'] else '?':8}")
            else:
                summary["skipped"] += 1
                print(f"  [{i:3d}/{n_cycles}] SKIP     {r.get('reason')}")
                if r.get("reason") == "no_proposals":
                    break  # nothing to do — stop
        except Exception as e:
            print(f"  [{i:3d}/{n_cycles}] EXC      {e}")
            traceback.print_exc()
            log_event(f"r611_cycle_{i}", "fail", reason=str(e)[:300],
                      code="E_CYCLE_UNCAUGHT")
        time.sleep(delay_between)

    total = time.time() - t0
    log_event("r611_orchestrator", "succeed",
              reason=f"completed; PASS={summary['PASS']} FAIL={summary['FAIL']}",
              elapsed_ms=int(total * 1000), metadata=summary)

    print(f"\n══════════ R611 batch complete ══════════")
    print(f"  Wall time: {total/60:.1f} min")
    print(f"  Verdicts: {summary}")
    print(f"  By position: {by_position}")
    print(f"  By deliverable_type: {by_type}")
    print(json.dumps({"summary": summary, "by_position": by_position,
                      "by_type": by_type, "total_seconds": int(total)}, indent=2))


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--cycles", type=int, default=87)
    p.add_argument("--delay", type=float, default=1.0)
    args = p.parse_args()
    main(n_cycles=args.cycles, delay_between=args.delay)
