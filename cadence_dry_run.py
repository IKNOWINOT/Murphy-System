#!/usr/bin/env python3
"""
cadence_dry_run.py — Show what _run_followup_cadence WOULD do without sending.
LOCKED 2026-05-27 — PATCH-CADENCE-DRY-RUN

Replicates the filter and per-lead decision logic of run_followup_cadence
in lead_prospector.py:649, but stops short of actually invoking _send_*.
Safe to run any time. Produces JSON.

Usage:
    sudo -u murphy /opt/Murphy-System/venv/bin/python3 \\
        /opt/Murphy-System/cadence_dry_run.py
"""
import json, sqlite3, sys
sys.path.insert(0, '/opt/Murphy-System')

from src.lead_prospector import (
    _follow_up_count, _days_since_last_contact, _dnc_blocked,
    MAX_TOUCHES, CRM_DB
)

def run():
    with sqlite3.connect(CRM_DB, timeout=8) as db:
        rows = db.execute(
            "SELECT c.id, c.name, c.email, c.company, c.contact_type, "
            "       c.tags, c.created_at "
            "FROM contacts c "
            "WHERE c.tags LIKE '%auto-prospected%' "
            "AND c.contact_type='lead'"
        ).fetchall()

    results = []
    actions = {"opener":0, "followup_1":0, "followup_2":0, "archive_max":0,
               "dnc_blocked":0, "skipped_recent":0, "no_email":0}
    for cid, name, email, company, ctype, tags_raw, created_at in rows:
        if not email:
            actions["no_email"] += 1; continue
        blocked, reason = _dnc_blocked(email)
        if blocked:
            actions["dnc_blocked"] += 1
            results.append({"id":cid,"email":email,"action":"dnc_blocked","reason":reason})
            continue
        touches = _follow_up_count(email)
        days_ago = _days_since_last_contact(email)
        if touches >= MAX_TOUCHES:
            actions["archive_max"] += 1; continue
        if touches == 0:
            actions["opener"] += 1
            results.append({"id":cid,"email":email,"action":"WOULD_SEND_OPENER",
                          "company":company,"days_since_contact":days_ago})
        elif touches == 1 and (days_ago is None or days_ago >= 3):
            actions["followup_1"] += 1
            results.append({"id":cid,"email":email,"action":"WOULD_SEND_FOLLOWUP_1",
                          "company":company,"days_since_contact":days_ago})
        elif touches == 2 and (days_ago is None or days_ago >= 7):
            actions["followup_2"] += 1
            results.append({"id":cid,"email":email,"action":"WOULD_SEND_FOLLOWUP_2",
                          "company":company,"days_since_contact":days_ago})
        else:
            actions["skipped_recent"] += 1
            results.append({"id":cid,"email":email,"action":"skipped_recent",
                          "touches":touches,"days_since_contact":days_ago})

    return {"summary": actions, "total": len(rows), "per_lead": results}

if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
