#!/usr/bin/env python3
"""
R609 — Living Loop (the orchestrator)
======================================

The thing that puts it together so Murphy gets better by working on itself.

Every 15 min:
  1. Read NEW wirer findings since last cycle (cursor in self_plan.db)
  2. Read latest agent reports, extract their escalations
  3. Classify each gap/escalation by domain
       architecture/code/wirer → platform_cto
       revenue/spend/runway    → platform_cfo
       sales/conversion/CRM    → platform_cro
       strategic/cross-cutting → platform_ceo
  4. Create ImprovementProposal rows in self_plan.proposals with owner_agent_id
  5. Each contracted agent's next cycle picks up its own slice via owner_agent_id

This is the "live business" loop — gaps surface, get owned, get worked,
get closed. Backlog visible at /api/self-plan (next: expose route).

Murphy approved R609 over a long-lived service. Cron is simpler + restart-safe.
"""
import os, sys, json, sqlite3, uuid, hashlib, logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/opt/Murphy-System/src")
from r608_contract_loader import load_contract, list_org_chart

AGENT_ID = "r609_living_loop"
NOW = datetime.now(timezone.utc)
WIRER_DB = "/var/lib/murphy-production/wirer_findings.db"
SELF_PLAN_DB = "/var/lib/murphy-production/self_plan.db"
ENTITY_DB = "/var/lib/murphy-production/entity_graph.db"
ARTIFACT_DIR = Path("/var/lib/murphy-production/artifacts")

log = logging.getLogger("r609")
logging.basicConfig(level=logging.INFO, format="  %(message)s")


def _ensure_cursor_table():
    """Track which wirer findings we've already processed."""
    c = sqlite3.connect(SELF_PLAN_DB)
    c.execute("""CREATE TABLE IF NOT EXISTS r609_cursor (
        name TEXT PRIMARY KEY, value TEXT, updated_at TEXT
    )""")
    c.commit(); c.close()


def get_cursor(name):
    c = sqlite3.connect(SELF_PLAN_DB)
    r = c.execute("SELECT value FROM r609_cursor WHERE name = ?", (name,)).fetchone()
    c.close()
    return r[0] if r else None


def set_cursor(name, value):
    c = sqlite3.connect(SELF_PLAN_DB)
    c.execute("INSERT OR REPLACE INTO r609_cursor VALUES (?, ?, ?)",
              (name, str(value), NOW.isoformat()))
    c.commit(); c.close()


def _q(db, sql, params=(), default=None):
    try:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        r = c.execute(sql, params).fetchall(); c.close(); return r
    except Exception as e:
        log.warning(f"  query failed on {db}: {e}")
        return default


def read_new_wirer_findings():
    """Find findings we haven't seen yet."""
    last_id = int(get_cursor("wirer_last_id") or "0")
    rows = _q(WIRER_DB,
        "SELECT id, cycle_ts, kind, path, details, severity FROM findings "
        "WHERE id > ? AND status='open' ORDER BY id ASC LIMIT 50",
        (last_id,), default=[])
    return rows or [], last_id


def classify_finding(kind, path, details):
    """Route finding to the right contracted exec by domain hints."""
    path_l = (path or "").lower()
    # money/spend/billing → CFO
    if any(k in path_l for k in ["bill", "treasury", "payment", "stripe", "nowpay",
                                  "invoice", "revenue", "capital", "spend", "ledger"]):
        return "platform_cfo", "financial"
    # sales/crm/outreach → CRO
    if any(k in path_l for k in ["crm", "sales", "outreach", "cadence", "pipeline",
                                  "prospect", "lead", "outbound", "campaign"]):
        return "platform_cro", "commercial"
    # most architecture/code gaps → CTO
    return "platform_cto", "technology"


def read_recent_escalations():
    """Pull the latest 4 agent reports, extract their explicit escalations."""
    rows = _q(ENTITY_DB,
        "SELECT id, title, file_url, notes, created_at FROM data_room_artifacts "
        "WHERE category='report' ORDER BY created_at DESC LIMIT 8", default=[])
    escalations = []
    for art_id, title, file_url, notes, created_at in (rows or []):
        if not file_url: continue
        p = Path(file_url)
        if not p.exists(): continue
        try:
            text = p.read_text(errors="replace")
        except Exception: continue
        # parse "Escalations I would raise to X" section
        in_esc = False; esc_lines = []
        for line in text.splitlines():
            if "escalation" in line.lower() and line.startswith("#"):
                in_esc = True; continue
            if in_esc and line.startswith("#"): break
            if in_esc and line.strip().startswith(("1.", "2.", "3.", "- ")):
                esc_lines.append(line.strip())
        # figure out which agent it came from
        owner = "platform_cto"
        for marker, role in [("R603v2", "platform_cto"), ("R603B", "platform_cfo"),
                              ("R603C", "platform_cro"), ("R603D", "platform_ceo")]:
            if marker in (notes or ""): owner = role; break
        for e in esc_lines:
            escalations.append({"from_agent": owner, "text": e[:300], "art_id": art_id, "title": title})
    return escalations


def fingerprint(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def create_proposal(title, description, owner_agent_id, source_kind, severity,
                     affected_module="", context=None):
    """Insert into self_plan.proposals with owner_agent_id attribution."""
    fp = fingerprint(title, owner_agent_id, affected_module)
    pid = str(uuid.uuid4())
    risk = {"urgent": "high", "warn": "low", "info": "low"}.get(severity, "low")
    score = {"urgent": 0.9, "warn": 0.5, "info": 0.2}.get(severity, 0.3)
    ctx = json.dumps({**(context or {}), "owner_agent_id": owner_agent_id,
                       "source_kind": source_kind, "discovered_at": NOW.isoformat()})
    c = sqlite3.connect(SELF_PLAN_DB)
    try:
        c.execute("""INSERT INTO proposals
            (proposal_id, trace_id, title, description, affected_module,
             change_type, risk_level, status, score, fingerprint, semver_intent,
             created_at, scheduled_at, context)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, 'patch', ?, ?, ?)""",
            (pid, f"r609_{NOW.strftime('%Y%m%dT%H%M%S')}", title, description,
             affected_module, "behaviour", risk, score, fp,
             NOW.isoformat(), NOW.isoformat(), ctx))
        c.commit()
        return pid, "created"
    except sqlite3.IntegrityError:
        return None, "duplicate_fingerprint"
    finally:
        c.close()


def main():
    print(f"R609 living-loop cycle — {NOW.isoformat()}")
    _ensure_cursor_table()

    # --- 1. Wirer findings ---
    findings, last_seen_id = read_new_wirer_findings()
    print(f"  new wirer findings since id={last_seen_id}: {len(findings)}")
    created = 0; dup = 0
    for fid, cycle_ts, kind, path, details, severity in findings:
        owner, domain = classify_finding(kind, path, details)
        title = f"[{domain}] {kind}: {path}"[:120]
        desc = f"Wirer finding #{fid} at {cycle_ts}\n\nDetails: {details or '(none)'}\n\nRouted to: {owner} (domain: {domain})"
        pid, status = create_proposal(
            title=title, description=desc, owner_agent_id=owner,
            source_kind=f"wirer.{kind}", severity=severity,
            affected_module=path,
            context={"finding_id": fid, "cycle_ts": cycle_ts}
        )
        if status == "created": created += 1
        else: dup += 1
    if findings:
        set_cursor("wirer_last_id", findings[-1][0])
    print(f"  proposals created from wirer: {created} (dup: {dup})")

    # --- 2. Agent escalations ---
    escalations = read_recent_escalations()
    print(f"  escalations from agent reports: {len(escalations)}")
    esc_created = 0; esc_dup = 0
    for e in escalations:
        owner_of_escalation_target = {
            "platform_cto": "platform_ceo", "platform_cfo": "platform_ceo",
            "platform_cro": "platform_ceo", "platform_ceo": "founder",
        }.get(e["from_agent"], "platform_ceo")
        title = f"[escalation] {e['from_agent']} → {owner_of_escalation_target}: {e['text'][:80]}"[:120]
        desc = f"Escalated by {e['from_agent']} in report '{e['title']}' ({e['art_id']}):\n\n{e['text']}"
        pid, status = create_proposal(
            title=title, description=desc, owner_agent_id=owner_of_escalation_target,
            source_kind="agent_escalation", severity="warn",
            affected_module=e["from_agent"],
            context={"source_artifact": e["art_id"], "from_agent": e["from_agent"]}
        )
        if status == "created": esc_created += 1
        else: esc_dup += 1
    print(f"  proposals created from escalations: {esc_created} (dup: {esc_dup})")

    # --- 3. Summary ---
    c = sqlite3.connect(SELF_PLAN_DB)
    tot = c.execute("SELECT count(*) FROM proposals").fetchone()[0]
    by_owner = c.execute(
        "SELECT json_extract(context, '$.owner_agent_id') AS owner, "
        "       status, count(*) FROM proposals GROUP BY 1, 2 ORDER BY 1, 2"
    ).fetchall()
    c.close()
    print(f"  TOTAL proposals in self_plan: {tot}")
    for owner, status, n in by_owner:
        print(f"    {owner or '(unowned)':18} {status:12} {n}")

    summary = {
        "ok": True, "cycle_ts": NOW.isoformat(),
        "wirer_new": len(findings), "proposals_from_wirer": created,
        "escalations_seen": len(escalations), "proposals_from_escalations": esc_created,
        "total_proposals": tot,
        "by_owner": [{"owner": o, "status": s, "n": n} for o, s, n in by_owner]
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
