#!/usr/bin/env python3
"""R603C — CSO Agent (Phase C). Reads crm/sales_pipeline/outreach → sales report."""
import os, sys, json, sqlite3, subprocess, uuid
from datetime import datetime, timezone
from pathlib import Path

NOW = datetime.now(timezone.utc)
ARTIFACT_DIR = Path("/var/lib/murphy-production/artifacts")
ARTIFACT_ID = f"r603c_cso_sales_report_{NOW.strftime('%Y%m%dT%H%M%SZ')}"
CRM_DB = "/var/lib/murphy-production/crm.db"
PIPELINE_DB = "/var/lib/murphy-production/sales_pipeline.db"
OUTREACH_DB = "/var/lib/murphy-production/outreach_drafts.db"
OUTBOUND_DB = "/var/lib/murphy-production/email_outbound.db"
RECIPIENT = "cpost@murphy.systems"
SENDER = "cso-agent@murphy.systems"

def _q(db, sql, default=None):
    try:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        r = c.execute(sql).fetchall(); c.close(); return r
    except Exception: return default

def read_crm():
    contacts = _q(CRM_DB, "SELECT count(*) FROM contacts", [(0,)])
    activities = _q(CRM_DB, "SELECT count(*) FROM activities", [(0,)])
    activities_7d = _q(CRM_DB,
        "SELECT count(*) FROM activities WHERE created_at > datetime('now', '-7 days')",
        [(0,)])
    # try to find recent activity types
    types = _q(CRM_DB,
        "SELECT type, count(*) FROM activities WHERE created_at > datetime('now', '-7 days') "
        "GROUP BY type ORDER BY 2 DESC LIMIT 5", [])
    return {
        "contacts": contacts[0][0] if contacts else 0,
        "activities_total": activities[0][0] if activities else 0,
        "activities_7d": activities_7d[0][0] if activities_7d else 0,
        "activity_types_7d": types or [],
    }

def read_pipeline():
    deals = _q(PIPELINE_DB, "SELECT count(*) FROM pipeline", [(0,)])
    contracts = _q(PIPELINE_DB, "SELECT count(*) FROM contracts", [(0,)])
    return {
        "pipeline_rows": deals[0][0] if deals else 0,
        "contracts": contracts[0][0] if contracts else 0,
    }

def read_outreach():
    drafts = _q(OUTREACH_DB,
        "SELECT count(*) FROM (SELECT name FROM sqlite_master WHERE type='table')",
        [(0,)])
    # try common table names
    drafts_total = 0
    drafts_pending = 0
    for tname in ['outreach_drafts', 'drafts', 'outbound_drafts']:
        r = _q(OUTREACH_DB, f"SELECT count(*), COUNT(CASE WHEN status='pending' THEN 1 END) FROM {tname}")
        if r and r[0]:
            drafts_total, drafts_pending = r[0][0], (r[0][1] or 0)
            break
    # outbound mail counts
    sent_7d = 0
    for tname in ['outbound', 'sent', 'email_log']:
        r = _q(OUTBOUND_DB, f"SELECT count(*) FROM {tname} WHERE created_at > datetime('now', '-7 days')")
        if r and r[0]:
            sent_7d = r[0][0]
            break
    return {
        "drafts_total": drafts_total,
        "drafts_pending": drafts_pending,
        "emails_sent_7d": sent_7d,
    }

def synthesize(crm, pipeline, outreach):
    em = lambda b: "🟢" if b else "🔴"
    has_activity = crm["activities_7d"] > 0
    has_pipeline = pipeline["pipeline_rows"] > 0
    has_outreach = outreach["emails_sent_7d"] > 0 or outreach["drafts_pending"] > 0

    md = f"""# Murphy Sales Report

**Reporter:** CSO Agent (R603C — first CSO deliverable)
**Generated:** {NOW.isoformat()}
**Period:** trailing 7 days
**For:** Corey Post (cpost@murphy.systems)

---

## Headline

| Signal | Status | Value |
|---|---|---|
| Contacts in CRM | {em(crm['contacts'] > 0)} | {crm['contacts']:,} total |
| CRM activity (7d) | {em(has_activity)} | {crm['activities_7d']} actions |
| Pipeline | {em(has_pipeline)} | {pipeline['pipeline_rows']} deals · {pipeline['contracts']} contracts |
| Outreach (7d) | {em(has_outreach)} | {outreach['emails_sent_7d']} sent · {outreach['drafts_pending']} pending |

## CRM state

- Total contacts: {crm['contacts']:,}
- Total activities (lifetime): {crm['activities_total']:,}
- Activities (7d): {crm['activities_7d']}
"""
    if crm["activity_types_7d"]:
        md += "\n### Recent activity breakdown\n\n"
        for t, n in crm["activity_types_7d"]:
            md += f"- **{t}**: {n}\n"

    md += f"""
## Pipeline

- Open deals: {pipeline['pipeline_rows']}
- Contracts: {pipeline['contracts']}

## Outreach engine

- Emails sent (7d): {outreach['emails_sent_7d']}
- Pending drafts: {outreach['drafts_pending']}
- Total drafts (lifetime): {outreach['drafts_total']}

## Recommended next actions

"""
    actions = []
    if crm["contacts"] > 0 and crm["activities_7d"] == 0:
        actions.append(f"{crm['contacts']} contacts in CRM but ZERO activity in 7 days — pipeline is dormant.")
    if pipeline["pipeline_rows"] == 0 and pipeline["contracts"] == 0:
        actions.append("Pipeline is empty. Per founder canon, sales prospecting is STOPPED pending ≥1 real reply.")
    if outreach["drafts_pending"] > 0:
        actions.append(f"{outreach['drafts_pending']} outbound drafts pending HITL approval — review in queue.")
    if not actions:
        actions.append("No urgent sales action items. Pipeline static — by design until founder unpauses prospecting.")
    for i, a in enumerate(actions[:5], 1):
        md += f"{i}. {a}\n"

    md += """

---

## About this report

Third agent in Murphy's history (CTO → CFO → CSO). Reads four DBs read-only,
synthesizes a one-page summary, emails the founder, posts to data_room_artifacts.

Same R603 pattern. Tomorrow: CEO agent (synthesis of all three).
"""
    return md


def email_report(subject, body):
    msg = (f"From: CSO Agent <{SENDER}>\nTo: {RECIPIENT}\nSubject: {subject}\n"
           f"Content-Type: text/plain; charset=utf-8\nX-Murphy-Agent: cso\n"
           f"X-Murphy-Pilot: R603C\nX-Murphy-Artifact: {ARTIFACT_ID}\n\n{body}\n")
    r = subprocess.run(["/usr/sbin/sendmail", "-f", SENDER, RECIPIENT],
                       input=msg.encode(), capture_output=True, timeout=20)
    return r.returncode == 0


def main():
    print(f"R603C CSO agent — {NOW.isoformat()}")
    crm = read_crm(); print(f"  crm: {crm['contacts']} contacts, {crm['activities_7d']} acts 7d")
    pipe = read_pipeline(); print(f"  pipeline: {pipe['pipeline_rows']} deals, {pipe['contracts']} contracts")
    out = read_outreach(); print(f"  outreach: {out['emails_sent_7d']} sent 7d, {out['drafts_pending']} pending")

    md = synthesize(crm, pipe, out)
    d = ARTIFACT_DIR / ARTIFACT_ID; d.mkdir(parents=True, exist_ok=True)
    p = d / "sales_report.md"
    with open(p, "w") as f: f.write(md)
    with open(d/"raw_data.json", "w") as f:
        json.dump({"crm": crm, "pipeline": pipe, "outreach": out}, f, indent=2, default=str)
    print(f"  artifact: {p}")

    ok = email_report(f"Murphy CSO Report — {NOW.strftime('%b %d %H:%M UTC')}", md)
    print(f"  email: {'✓' if ok else '✗'}")

    try:
        c = sqlite3.connect("/var/lib/murphy-production/entity_graph.db")
        c.execute("INSERT INTO data_room_artifacts VALUES (?,?,?,?,?,?,?,?,?)",
                  (f"art_{uuid.uuid4().hex[:12]}", "report",
                   f"CSO Sales Report {NOW.strftime('%Y-%m-%d %H:%M')}",
                   str(p), 1, 1, "R603C CSO pilot — Phase C", NOW.isoformat(), NOW.isoformat()))
        c.commit(); c.close()
        print("  ✓ data_room")
    except Exception as e:
        print(f"  ⚠ {e}")
    print(json.dumps({"ok": True, "artifact_id": ARTIFACT_ID}, indent=2))


if __name__ == "__main__":
    main()
