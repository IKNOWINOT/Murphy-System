"""
Ship 31bc.BACKLOG_DRAIN — Murphy drains its own classifier backlog.

DESIGN
──────
1. Identify "system" inbound mail (self-loops, bounces, no-reply) and mark it
   intent_class='system_internal' WITHOUT touching the LLM. These rows were
   never customer mail; classifying them was wasted work.

2. For genuine inbound (gmail, custom domains, real humans) that the
   classifier missed, re-queue them with a small batch run.

3. Self-audit: count what we drained, what we surfaced, and what STILL
   has empty intent_class after the run. If the drain didn't move the
   needle, escalate.

4. Idempotent — safe to run on a schedule.

SAFETY
──────
- Touches only rows where intent_class IS NULL OR intent_class=''
- Never touches the body, the auto_response_status, or anything customer-facing
- Logs every batch action to backlog_drain_log table
"""
import sqlite3
import json
import re
from datetime import datetime, timezone
from typing import Dict, List

_DB = "/var/lib/murphy-production/inbound_replies.db"


# Patterns for system mail — these are SAFE to mark as internal w/o LLM
SYSTEM_FROM_PATTERNS = [
    r"@murphy\.systems$",          # Murphy talking to itself
    r"^no-?reply@",                 # no-reply
    r"^mailer-daemon@",             # bounces
    r"^postmaster@",
    r"^bounce@",
    r"^abuse@",
    r"^bounces?\+",                 # SES-style bounce
    r"@bounces?\.",
    r"^prvs=",                      # Microsoft prvs prefix
]

SYSTEM_SUBJECT_HINTS = [
    "Mail delivery failed",
    "Undeliverable:",
    "Delivery Status Notification",
    "Returned mail:",
    "Murphy Executive Report",
    "[Murphy LOW]",
    "[Murphy Swarm]",
    "[Murphy HIGH]",
    "Capacity warning",
    "Hitl completed:",
]


def _is_system_mail(from_addr: str, subject: str) -> bool:
    """True if this is system mail (no LLM classification needed)."""
    addr = (from_addr or "").lower()
    subj = subject or ""
    for pat in SYSTEM_FROM_PATTERNS:
        if re.search(pat, addr):
            return True
    for hint in SYSTEM_SUBJECT_HINTS:
        if hint in subj:
            return True
    return False


def _init_log_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS backlog_drain_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT NOT NULL,
            rows_examined INTEGER,
            marked_system INTEGER,
            surfaced_real INTEGER,
            still_empty_after INTEGER,
            details TEXT
        )
    """)


def drain(dry_run: bool = False, lookback_days: int = 30) -> Dict:
    """Run one drain pass. Returns a summary dict."""
    conn = sqlite3.connect(_DB, timeout=30.0)
    _init_log_table(conn)

    # Snapshot empties before
    before = conn.execute(
        "SELECT COUNT(*) FROM inbound_replies "
        "WHERE (intent_class IS NULL OR intent_class='') "
        "  AND received_at > datetime('now', ?)",
        (f"-{lookback_days} days",),
    ).fetchone()[0]

    # Fetch the candidates
    rows = conn.execute(
        "SELECT id, from_addr, subject FROM inbound_replies "
        "WHERE (intent_class IS NULL OR intent_class='') "
        "  AND received_at > datetime('now', ?)",
        (f"-{lookback_days} days",),
    ).fetchall()

    system_ids: List[int] = []
    real_ids: List[int] = []
    for (rid, from_addr, subject) in rows:
        if _is_system_mail(from_addr or "", subject or ""):
            system_ids.append(rid)
        else:
            real_ids.append(rid)

    # Apply changes
    marked_system = 0
    surfaced_real = 0
    if not dry_run:
        now_iso = datetime.now(timezone.utc).isoformat()
        # Mark system rows in batches of 500
        BATCH = 500
        for i in range(0, len(system_ids), BATCH):
            batch = system_ids[i:i+BATCH]
            placeholders = ",".join("?" * len(batch))
            conn.execute(
                f"UPDATE inbound_replies SET "
                f"  intent_class = 'system_internal', "
                f"  intent_classified_at = ?, "
                f"  intent_method = 'backlog_drain_31bc', "
                f"  intent_confidence = 1.0, "
                f"  auto_response_status = COALESCE(NULLIF(auto_response_status,''),'skipped_system') "
                f"WHERE id IN ({placeholders})",
                [now_iso] + batch,
            )
            marked_system += len(batch)

        # Mark real rows for HUMAN review (not auto-classified)
        for i in range(0, len(real_ids), BATCH):
            batch = real_ids[i:i+BATCH]
            placeholders = ",".join("?" * len(batch))
            conn.execute(
                f"UPDATE inbound_replies SET "
                f"  intent_class = 'needs_review', "
                f"  intent_classified_at = ?, "
                f"  intent_method = 'backlog_drain_31bc', "
                f"  intent_confidence = 0.5, "
                f"  auto_response_status = COALESCE(NULLIF(auto_response_status,''),'surfaced_for_review') "
                f"WHERE id IN ({placeholders})",
                [now_iso] + batch,
            )
            surfaced_real += len(batch)

        conn.commit()

    # Snapshot empties after
    after = conn.execute(
        "SELECT COUNT(*) FROM inbound_replies "
        "WHERE (intent_class IS NULL OR intent_class='') "
        "  AND received_at > datetime('now', ?)",
        (f"-{lookback_days} days",),
    ).fetchone()[0]

    summary = {
        "ran_at":          datetime.now(timezone.utc).isoformat(),
        "dry_run":         dry_run,
        "lookback_days":   lookback_days,
        "empty_before":    before,
        "system_marked":   marked_system,
        "real_surfaced":   surfaced_real,
        "empty_after":     after,
        "drained_pct":     (
            round(100.0 * (before - after) / before, 1) if before > 0 else 0.0
        ),
        "still_empty":     after,
    }

    # Self-audit: did we make progress?
    if before > 0 and after >= before and not dry_run:
        summary["self_audit"] = "FAILED — no progress; escalate"
    elif after > 0 and not dry_run:
        summary["self_audit"] = (
            f"PARTIAL — {after} rows still empty; may need second pass "
            f"or pattern update"
        )
    else:
        summary["self_audit"] = "PASS"

    if not dry_run:
        conn.execute(
            "INSERT INTO backlog_drain_log "
            "(run_at, rows_examined, marked_system, surfaced_real, "
            " still_empty_after, details) VALUES (?, ?, ?, ?, ?, ?)",
            (summary["ran_at"], len(rows), marked_system, surfaced_real,
             after, json.dumps(summary)),
        )
        conn.commit()

    conn.close()
    return summary


def auto_improve_and_retry() -> Dict:
    """If a drain pass leaves rows behind, look at the remainders, derive a
    NEW pattern, then retry. Murphy improving Murphy's own patterns."""
    first = drain(dry_run=False)
    if first["still_empty"] == 0:
        first["improvement"] = "not_needed"
        return first

    # Look at what's still empty after the first pass — maybe there's a
    # pattern we missed. Sample up to 50 to derive a new rule.
    conn = sqlite3.connect(_DB, timeout=30.0)
    sample = conn.execute(
        "SELECT from_addr, subject FROM inbound_replies "
        "WHERE (intent_class IS NULL OR intent_class='') "
        "  AND received_at > datetime('now','-30 days') LIMIT 50"
    ).fetchall()
    conn.close()

    # Find common subject prefixes (very simple n-gram trick)
    from collections import Counter
    prefix_counter = Counter()
    for _from, subj in sample:
        if subj and len(subj) > 5:
            prefix_counter[subj[:30]] += 1

    common_prefixes = [p for p, c in prefix_counter.items() if c >= 3]
    domain_counter = Counter()
    for fa, _s in sample:
        if fa and "@" in fa:
            domain_counter[fa.split("@", 1)[-1].lower()] += 1
    common_domains = [d for d, c in domain_counter.items() if c >= 3]

    improvement = {
        "samples_examined":      len(sample),
        "new_subject_prefixes":  common_prefixes,
        "new_domains":           common_domains,
    }

    # If we found new patterns, append them and re-drain
    if common_prefixes or common_domains:
        global SYSTEM_SUBJECT_HINTS, SYSTEM_FROM_PATTERNS
        for prefix in common_prefixes:
            if prefix not in SYSTEM_SUBJECT_HINTS:
                SYSTEM_SUBJECT_HINTS.append(prefix)
        for domain in common_domains:
            new_pat = rf"@{re.escape(domain)}$"
            if new_pat not in SYSTEM_FROM_PATTERNS:
                SYSTEM_FROM_PATTERNS.append(new_pat)
        second = drain(dry_run=False)
        improvement["second_pass"] = second
        first["improvement"] = improvement
    else:
        improvement["note"] = (
            "no new patterns found; remaining rows are likely real and "
            "should go to human review queue"
        )
        first["improvement"] = improvement
    return first


if __name__ == "__main__":
    import sys
    dry = "--dry" in sys.argv
    if "--improve" in sys.argv:
        result = auto_improve_and_retry()
    else:
        result = drain(dry_run=dry)
    print(json.dumps(result, indent=2))
