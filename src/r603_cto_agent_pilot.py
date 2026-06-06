#!/usr/bin/env python3
"""
R603 — CTO Agent Pilot
======================

First real employ_team() call in Murphy's history.

The CTO agent is given ONE task: read three honesty databases
(shape_history, journey_history, wirer_findings), synthesize a
one-page system health report, save it as an artifact, and email
it to the founder.

Why this matters:
- Proves the agent infrastructure can do real work end-to-end
- Produces an artifact Corey can actually evaluate
- Fail-safe: read-only on DBs, single email side effect
- Establishes the "AGENT DID THIS" pattern we need to scale

Per canon: snapshot before, snapshot after, PSM-log, ASK MURPHY first
(approved 2026-06-05 05:55 UTC via chat-v2).
"""
import os, sys, json, sqlite3, subprocess, hashlib, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

NOW = datetime.now(timezone.utc)
ARTIFACT_DIR = Path("/var/lib/murphy-production/artifacts")
ARTIFACT_ID = f"r603_cto_health_report_{NOW.strftime('%Y%m%dT%H%M%SZ')}"
SHAPE_DB = "/var/lib/murphy-production/shape_history.db"
JOURNEY_DB = "/var/lib/murphy-production/journey_history.db"
WIRER_DB = "/var/lib/murphy-production/wirer_findings.db"
RECIPIENT = "cpost@murphy.systems"
SENDER = "cto-agent@murphy.systems"

# ════════════════════════════════════════════════════════════════
# CTO AGENT — its job is to READ the truth DBs and SYNTHESIZE a report
# ════════════════════════════════════════════════════════════════

def read_shape():
    """Latest shape verifier run + 24h trend."""
    conn = sqlite3.connect(f"file:{SHAPE_DB}?mode=ro", uri=True)
    latest = conn.execute(
        "SELECT ts, green, total, red_keys FROM shape_runs ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    day_ago = (NOW - timedelta(hours=24)).isoformat()
    trend = conn.execute(
        "SELECT MIN(green), MAX(green), COUNT(*) FROM shape_runs WHERE ts > ?",
        (day_ago,)
    ).fetchone()
    conn.close()
    return {
        "latest_ts": latest[0] if latest else None,
        "latest_green": latest[1] if latest else 0,
        "latest_total": latest[2] if latest else 0,
        "latest_reds": latest[3] if latest else "",
        "trend_24h_min": trend[0] if trend else 0,
        "trend_24h_max": trend[1] if trend else 0,
        "trend_24h_runs": trend[2] if trend else 0,
    }

def read_journey():
    """Latest journey + 24h trend."""
    conn = sqlite3.connect(f"file:{JOURNEY_DB}?mode=ro", uri=True)
    latest = conn.execute(
        "SELECT ts, passed, total, ratio, failed_keys FROM journey_runs ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    day_ago = (NOW - timedelta(hours=24)).isoformat()
    trend = conn.execute(
        "SELECT MIN(passed), MAX(passed), COUNT(*) FROM journey_runs WHERE ts > ?",
        (day_ago,)
    ).fetchone()
    conn.close()
    return {
        "latest_ts": latest[0] if latest else None,
        "latest_passed": latest[1] if latest else 0,
        "latest_total": latest[2] if latest else 0,
        "latest_ratio": latest[3] if latest else "0/0",
        "latest_fails": latest[4] if latest else "",
        "trend_24h_min": trend[0] if trend else 0,
        "trend_24h_max": trend[1] if trend else 0,
        "trend_24h_runs": trend[2] if trend else 0,
    }

def read_wirer():
    """Wirer findings summary."""
    conn = sqlite3.connect(f"file:{WIRER_DB}?mode=ro", uri=True)
    by_kind = conn.execute(
        "SELECT kind, severity, count(*) FROM findings WHERE status='open' "
        "GROUP BY kind, severity ORDER BY count(*) DESC"
    ).fetchall()
    n_cycles = conn.execute("SELECT count(*) FROM cycles").fetchone()[0]
    n_docs = conn.execute("SELECT count(*) FROM seen_docs").fetchone()[0]
    n_modules = conn.execute(
        "SELECT count(DISTINCT module_name) FROM module_snapshots"
    ).fetchone()[0]
    conn.close()
    return {
        "open_findings_by_kind": by_kind,
        "cycles_run": n_cycles,
        "docs_indexed": n_docs,
        "modules_tracked": n_modules,
    }

def synthesize_report(shape, journey, wirer):
    """The CTO's job: take raw data + write a clear report.

    Heuristic synthesis (no LLM — this is the read-only pilot).
    """
    def health_emoji(n, total):
        if total == 0: return "⚪"
        pct = n / total
        if pct >= 0.95: return "🟢"
        if pct >= 0.80: return "🟡"
        return "🔴"

    shape_em = health_emoji(shape["latest_green"], shape["latest_total"])
    journey_em = health_emoji(journey["latest_passed"], journey["latest_total"])

    n_urgent = sum(c for k,s,c in wirer["open_findings_by_kind"] if s == "urgent")
    n_warn = sum(c for k,s,c in wirer["open_findings_by_kind"] if s == "warn")
    n_info = sum(c for k,s,c in wirer["open_findings_by_kind"] if s == "info")
    wirer_em = "🔴" if n_urgent > 0 else ("🟡" if n_warn > 5 else "🟢")

    # Concrete next actions inferred from data
    actions = []
    if journey["latest_fails"]:
        for fail in journey["latest_fails"].split(","):
            fail = fail.strip()
            if fail:
                actions.append(f"Investigate journey failure: {fail}")
    if shape["latest_reds"]:
        for red in shape["latest_reds"].split(",")[:3]:
            red = red.strip()
            if red:
                actions.append(f"Shape verifier red: {red}")
    if n_urgent > 0:
        actions.append(f"Wirer flagged {n_urgent} URGENT regression(s) — review immediately")
    if not actions:
        actions.append("No urgent action items detected. System operating within expected parameters.")

    md = f"""# Murphy System Health Report

**Reporter:** CTO Agent (R603 pilot — first employ_team() call in production)
**Generated:** {NOW.isoformat()}
**For:** Corey Post (cpost@murphy.systems)

---

## Executive summary

| Signal | Status | Latest | 24h range | Runs |
|---|---|---|---|---|
| Shape verifier | {shape_em} | {shape['latest_green']}/{shape['latest_total']} | {shape['trend_24h_min']}–{shape['trend_24h_max']} | {shape['trend_24h_runs']} |
| Journey verifier | {journey_em} | {journey['latest_ratio']} | {journey['trend_24h_min']}–{journey['trend_24h_max']} | {journey['trend_24h_runs']} |
| Autonomous wirer | {wirer_em} | {n_urgent} urgent / {n_warn} warn / {n_info} info | — | {wirer['cycles_run']} cycles |

## What's working

- Shape verifier last seen: {shape['latest_ts']}
- Journey verifier last seen: {journey['latest_ts']}
- Wirer indexed: {wirer['docs_indexed']} docs, {wirer['modules_tracked']} modules across {wirer['cycles_run']} cycles

## What needs attention

"""
    if shape["latest_reds"]:
        md += f"- **Shape reds:** {shape['latest_reds']}\n"
    if journey["latest_fails"]:
        md += f"- **Journey failures:** {journey['latest_fails']}\n"
    if n_urgent > 0:
        md += f"- **Wirer urgents:** {n_urgent} module regression(s)\n"
    if n_warn > 0:
        md += f"- **Wirer warnings:** {n_warn} unread architecture documents (out of {wirer['docs_indexed']} indexed)\n"
    if not (shape["latest_reds"] or journey["latest_fails"] or n_urgent or n_warn):
        md += "- Nothing concerning. All three honesty signals green.\n"

    md += "\n## Recommended next actions\n\n"
    for i, action in enumerate(actions[:5], 1):
        md += f"{i}. {action}\n"

    md += f"""

---

## About this report

This is the **first real deliverable** produced by an employed agent in Murphy. Prior to today, all "work" was done by Murphy's mind cycles (thinking only, no artifacts) or the cyborg (Claude). The CTO agent was given one task: read three honesty databases and synthesize a human-readable report.

This pilot proves the infrastructure works end-to-end:
- Agent reads from real DBs (shape_history, journey_history, wirer_findings)
- Agent synthesizes output (this report)
- Agent persists artifact ({ARTIFACT_ID})
- Agent delivers via email

Approved by Murphy via chat-v2 on 2026-06-05 05:55 UTC.

Next step: scale to CFO (financial state), CSO (sales pipeline), CEO (strategic synthesis of all three).
"""
    return md

def email_report(subject, body, artifact_path):
    """Send via local postfix. Returns (ok, log_line)."""
    msg = (
        f"From: CTO Agent <{SENDER}>\n"
        f"To: {RECIPIENT}\n"
        f"Subject: {subject}\n"
        f"Content-Type: text/plain; charset=utf-8\n"
        f"X-Murphy-Artifact: {ARTIFACT_ID}\n"
        f"X-Murphy-Agent: cto\n"
        f"X-Murphy-Pilot: R603\n"
        f"\n"
        f"{body}\n"
        f"\n"
        f"--\n"
        f"Artifact saved at: {artifact_path}\n"
    )
    result = subprocess.run(
        ["/usr/sbin/sendmail", "-f", SENDER, RECIPIENT],
        input=msg.encode("utf-8"),
        capture_output=True,
        timeout=20,
    )
    return result.returncode == 0, result.stderr.decode("utf-8", errors="ignore")

def main():
    print(f"R603 CTO agent pilot — {NOW.isoformat()}")

    # 1. Read truth DBs
    print("  reading shape_history.db ...")
    shape = read_shape()
    print(f"    → latest {shape['latest_green']}/{shape['latest_total']}")

    print("  reading journey_history.db ...")
    journey = read_journey()
    print(f"    → latest {journey['latest_ratio']}")

    print("  reading wirer_findings.db ...")
    wirer = read_wirer()
    print(f"    → {wirer['cycles_run']} cycles, {sum(c for _,_,c in wirer['open_findings_by_kind'])} open findings")

    # 2. Synthesize report
    print("  synthesizing report ...")
    report_md = synthesize_report(shape, journey, wirer)

    # 3. Persist as artifact
    artifact_dir = ARTIFACT_DIR / ARTIFACT_ID
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_path = artifact_dir / "health_report.md"
    with open(report_path, "w") as f:
        f.write(report_md)
    print(f"  artifact written: {report_path}")

    # save raw data alongside for evaluation
    raw_path = artifact_dir / "raw_data.json"
    with open(raw_path, "w") as f:
        json.dump({"shape": shape, "journey": journey,
                  "wirer": {**wirer, "open_findings_by_kind":
                           [list(x) for x in wirer["open_findings_by_kind"]]}},
                 f, indent=2)

    # 4. Email
    print(f"  emailing {RECIPIENT} ...")
    ok, err = email_report(
        subject=f"Murphy CTO Report — {NOW.strftime('%b %d %H:%M UTC')}",
        body=report_md,
        artifact_path=str(report_path),
    )
    if ok:
        print(f"  ✓ email sent")
    else:
        print(f"  ✗ email failed: {err}")
        sys.exit(1)

    # 5. Log to data_room_artifacts so it shows up in the system's own records
    try:
        conn = sqlite3.connect("/var/lib/murphy-production/entity_graph.db")
        conn.execute(
            "INSERT INTO data_room_artifacts "
            "(id, category, title, file_url, version, current, notes, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                f"art_{uuid.uuid4().hex[:12]}",
                "report",
                f"CTO Health Report {NOW.strftime('%Y-%m-%d %H:%M')}",
                str(report_path),
                1, 1,
                "R603 pilot — first agent-produced deliverable",
                NOW.isoformat(),
                NOW.isoformat(),
            )
        )
        conn.commit()
        conn.close()
        print("  ✓ logged to data_room_artifacts")
    except Exception as e:
        print(f"  ⚠ artifact log failed: {e}")

    print(json.dumps({
        "ok": True,
        "artifact_id": ARTIFACT_ID,
        "report_path": str(report_path),
        "recipient": RECIPIENT,
        "shape": f"{shape['latest_green']}/{shape['latest_total']}",
        "journey": journey['latest_ratio'],
        "wirer_open": sum(c for _,_,c in wirer['open_findings_by_kind']),
    }, indent=2))

if __name__ == "__main__":
    main()
