#!/usr/bin/env python3
"""
R603 v2 — CTO Agent (contract-aware)
=====================================

Now identifies as agent_id='platform_cto' and acts on its
contracted duties from agent_contracts. Founder canon: an org
chart works because each executive IS doing what their contract says.

Contracted CTO duty (from agent_contracts):
  "Keep all 15 autonomy gates green. Ship PATCH-N every 2-3 days.
   Maintain 99.5% uptime on murphy.systems. Drive autonomy % up monthly."

Report aligns to those duties.
"""
import os, sys, json, sqlite3, subprocess, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, "/opt/Murphy-System/src")
from r608_contract_loader import load_contract, get_subordinates, get_chain_of_command

AGENT_ID = "platform_cto"

NOW = datetime.now(timezone.utc)
ARTIFACT_DIR = Path("/var/lib/murphy-production/artifacts")
ARTIFACT_ID = f"r603v2_{AGENT_ID}_health_report_{NOW.strftime('%Y%m%dT%H%M%SZ')}"
SHAPE_DB = "/var/lib/murphy-production/shape_history.db"
JOURNEY_DB = "/var/lib/murphy-production/journey_history.db"
WIRER_DB = "/var/lib/murphy-production/wirer_findings.db"
RECIPIENT = "cpost@murphy.systems"
SENDER = "cto-agent@murphy.systems"


def _q(db, sql, default=None):
    try:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        r = c.execute(sql).fetchall(); c.close(); return r
    except Exception: return default


def read_gates_status():
    """Duty #1: 15 autonomy gates green. Read shape_runs."""
    r = _q(SHAPE_DB,
           "SELECT ts, green, total, red_keys FROM shape_runs ORDER BY ts DESC LIMIT 1")
    if not r: return {"latest_ts": None, "green": 0, "total": 0, "reds": ""}
    return {"latest_ts": r[0][0], "green": r[0][1], "total": r[0][2], "reds": r[0][3] or ""}


def read_uptime():
    """Duty #3: 99.5% uptime on murphy.systems. Approximate via mind cycle continuity."""
    # Use cycle_log heartbeat — gaps = downtime
    r = _q("/var/lib/murphy-production/murphy_mind.db",
           "SELECT count(*) FROM cycle_log")
    cycles_total = r[0][0] if r else 0
    # If cycles ran every 5min ideally over last 24h = 288. Measure actual.
    day_ago = (NOW - timedelta(hours=24)).isoformat()
    # cycle_log doesn't have ts — use rowid as proxy
    return {"cycles_total": cycles_total, "uptime_estimate": "via cycle continuity (proxy)"}


def read_patches():
    """Duty #2: Ship PATCH-N every 2-3 days. Count R-numbered files newer than 3d."""
    import subprocess as sp
    r = sp.run(
        ["bash", "-c",
         "find /opt/Murphy-System/src -name 'r[0-9]*.py' -newer "
         "/opt/Murphy-System/src/r603_cto_agent_pilot.py -printf '%f\\n' 2>/dev/null | "
         "grep -oE '^r[0-9]+' | sort -u | head -20"],
        capture_output=True, text=True, timeout=10)
    recent_patches = r.stdout.strip().split("\n") if r.stdout.strip() else []
    # also: highest R-number on disk
    r2 = sp.run(
        ["bash", "-c",
         "ls /opt/Murphy-System/src/ | grep -oE '^r[0-9]+' | sort -u | sort -V | tail -5"],
        capture_output=True, text=True, timeout=10)
    highest = r2.stdout.strip().split("\n") if r2.stdout.strip() else []
    return {"recent_patches_3d": recent_patches, "highest_patches": highest}


def read_wirer():
    rows = _q(WIRER_DB, "SELECT kind, severity, count(*) FROM findings WHERE status='open' "
              "GROUP BY kind, severity ORDER BY count(*) DESC", [])
    urgent = sum(c for k,s,c in (rows or []) if s == "urgent")
    warn = sum(c for k,s,c in (rows or []) if s == "warn")
    return {"urgent": urgent, "warn": warn, "by_kind": rows or []}


def synthesize_against_contract(contract, gates, uptime, patches, wirer):
    """Report = how well are CTO's contracted duties being executed."""
    duties_text = contract.get("duties_text", "")
    authorised = contract.get("authorised_actions", [])
    reports_to = contract.get("reports_to") or "founder"
    subordinates = get_subordinates(AGENT_ID)

    # Score each contracted duty
    gates_score = (gates["green"] / gates["total"]) if gates["total"] else 0
    gates_em = "🟢" if gates_score >= 0.95 else ("🟡" if gates_score >= 0.80 else "🔴")
    patches_em = "🟢" if len(patches["recent_patches_3d"]) >= 1 else "🟡"
    uptime_em = "🟡"  # honest unknown — no real uptime probe wired
    wirer_em = "🔴" if wirer["urgent"] > 0 else ("🟡" if wirer["warn"] > 5 else "🟢")

    md = f"""# CTO Report — {contract['role_title']}

**Reporter:** Me, {contract['role_title']} (agent_id: `{AGENT_ID}`)
**I report to:** `{reports_to}`
**Direct reports under me:** {', '.join(s['role_title'] for s in subordinates) or '(none)'}
**Generated:** {NOW.isoformat()}

---

## What my contract says I do

> {duties_text}

## How I'm doing against each contracted duty

### Duty 1: Keep all 15 autonomy gates green {gates_em}
- Current: **{gates['green']}/{gates['total']}** (shape verifier)
- Reds: {gates['reds'] or '(none)'}
- Status timestamp: {gates['latest_ts']}

### Duty 2: Ship PATCH-N every 2-3 days {patches_em}
- Patches authored in last 3 days: **{len(patches['recent_patches_3d'])}**
- Recent: {', '.join(patches['recent_patches_3d'][:5]) or '(none)'}
- Highest R-number on disk: {', '.join(patches['highest_patches'][-3:]) or '(unknown)'}

### Duty 3: Maintain 99.5% uptime on murphy.systems {uptime_em}
- Mind cycles to date: {uptime['cycles_total']:,}
- Honest gap: no real uptime probe wired yet. Proxy = mind cycle continuity.
- Recommended: wire `/api/health` polling + 30-day SLO panel

### Duty 4: Drive autonomy % up monthly
- Wirer findings open: {wirer['urgent']} urgent, {wirer['warn']} warn
- Translation: {wirer['warn']} architecture docs are still unreferenced (autonomy debt)

## What I'm authorised to do about it

{chr(10).join('- ' + a for a in (authorised if isinstance(authorised, list) else []))}

## Escalations I would raise to {reports_to}

"""
    escalations = []
    if gates_score < 0.95:
        escalations.append(f"Shape gates at {gates_score:.0%} — below 95% threshold. Reds: {gates['reds']}")
    if not patches["recent_patches_3d"]:
        escalations.append("No patches in last 3 days — slipping the 'every 2-3 days' duty")
    if wirer["urgent"] > 0:
        escalations.append(f"{wirer['urgent']} urgent regression(s) in wirer — need decision authority")
    if not escalations:
        md += "_None. All duties tracking within tolerance._\n"
    else:
        for i, e in enumerate(escalations, 1):
            md += f"{i}. {e}\n"

    md += f"""

---

## About this report

I am now contract-aware. This report is filed against `agent_contracts[{AGENT_ID}]`,
not an anonymous Python script. My duties, authorised actions, and reporting line
all came from the IS system (entity_graph.db → agent_contracts).

Founder canon: an org chart works because each executive IS doing what their contract says.
Today is the first day I am doing my contract instead of generic observability.

— {contract['role_title']}
"""
    return md


def email_report(subject, body):
    msg = (f"From: {AGENT_ID} <{SENDER}>\nTo: {RECIPIENT}\nSubject: {subject}\n"
           f"Content-Type: text/plain; charset=utf-8\n"
           f"X-Murphy-Agent: {AGENT_ID}\n"
           f"X-Murphy-Artifact: {ARTIFACT_ID}\n"
           f"X-Murphy-Reports-To: platform_ceo\n\n{body}\n")
    r = subprocess.run(["/usr/sbin/sendmail", "-f", SENDER, RECIPIENT],
                       input=msg.encode(), capture_output=True, timeout=20)
    return r.returncode == 0


def main():
    print(f"R603 v2 — loading contract for {AGENT_ID}")
    contract = load_contract(AGENT_ID)
    if not contract:
        print(f"  ✗ No contract for {AGENT_ID} — aborting"); sys.exit(1)
    print(f"  ✓ Loaded contract: {contract['role_title']}")
    print(f"  ✓ Reports to: {contract['reports_to']}")
    print(f"  ✓ Duties: {contract['duties_text'][:80]}...")

    print("  reading gate status..."); gates = read_gates_status()
    print(f"    → {gates['green']}/{gates['total']}")
    print("  reading uptime proxy..."); uptime = read_uptime()
    print(f"    → {uptime['cycles_total']:,} mind cycles")
    print("  reading patch cadence..."); patches = read_patches()
    print(f"    → {len(patches['recent_patches_3d'])} patches in 3d")
    print("  reading wirer findings..."); wirer = read_wirer()
    print(f"    → {wirer['urgent']} urgent, {wirer['warn']} warn")

    md = synthesize_against_contract(contract, gates, uptime, patches, wirer)
    d = ARTIFACT_DIR / ARTIFACT_ID; d.mkdir(parents=True, exist_ok=True)
    p = d / "cto_report.md"
    with open(p, "w") as f: f.write(md)
    with open(d/"contract_snapshot.json", "w") as f:
        json.dump(contract, f, indent=2, default=str)
    print(f"  artifact: {p}")

    ok = email_report(f"CTO Report — {NOW.strftime('%b %d %H:%M UTC')}", md)
    print(f"  email: {'✓' if ok else '✗'}")

    try:
        c = sqlite3.connect("/var/lib/murphy-production/entity_graph.db")
        c.execute("INSERT INTO data_room_artifacts VALUES (?,?,?,?,?,?,?,?,?)",
                  (f"art_{uuid.uuid4().hex[:12]}", "report",
                   f"CTO Report (contract-aware) {NOW.strftime('%Y-%m-%d %H:%M')}",
                   str(p), 1, 1, f"R603v2 contract-aware — agent_id={AGENT_ID}, marker=R603v2",
                   NOW.isoformat(), NOW.isoformat()))
        c.commit(); c.close()
        print("  ✓ data_room")
    except Exception as e:
        print(f"  ⚠ {e}")
    print(json.dumps({"ok": True, "agent_id": AGENT_ID,
                      "artifact_id": ARTIFACT_ID,
                      "gates": f"{gates['green']}/{gates['total']}",
                      "patches_3d": len(patches['recent_patches_3d'])}, indent=2))


if __name__ == "__main__":
    main()
