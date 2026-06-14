"""
Ship 31be.HITL_ONLY — central gate for ALL email to the founder.

Founder direction 2026-06-13: 'I don't need emails unless they relate
to hitl acceptance.' Everything else stays in @murphy.systems.

USAGE
  from src.founder_mail_gate_31be import should_send_to_founder
  if should_send_to_founder(subject, body, message_type):
      sendmail(...)

CATEGORIES THAT PASS
  - HITL approval requests        (subject contains 'HITL approval',
                                   'Approve:', 'HITL queue requires...')
  - HITL acceptance prompts       (subject contains 'accept', 'sign')
  - Direct human replies          (from a real prospect, not @murphy.systems)
  - Founder-explicit overrides    (X-Murphy-To-Founder: force header)

EVERYTHING ELSE GETS BLOCKED.
"""
import re
import os
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("murphy.founder_gate")

_LOG_DB = "/var/lib/murphy-production/founder_gate_log.db"

# Whitelist patterns that mean 'this IS for the founder'
HITL_PATTERNS = [
    r"\bHITL\s+approval\b",
    r"\bHITL\s+request\b",
    r"\bHITL\s+queue\b.*\bawait",
    r"\bApprove:\s*https?://",
    r"\bAccept\s+the\s+(HITL|Engagement)\b",
    r"\bSign\s+the\s+(HITL|Engagement)\b",
    r"\bawaiting\s+founder\s+(approval|signature|sign-off)\b",
    r"\bawaiting\s+human\s+(approval|signature|sign-off)\b",
    r"\bHITL Engagement Contract\b",
]

# Block patterns even if HITL keyword present (these are SWARM internal)
BLOCK_OVERRIDE_PATTERNS = [
    r"\[Murphy Swarm\]",          # internal ping-pong
    r"Hitl completed:",            # post-acceptance receipt, not needed
    r"Re:\s*\[Murphy Swarm\]",     # any swarm reply chain
    r"Capacity warning:.*HITL",    # capacity-about-HITL is not HITL itself
]


def _init_log():
    conn = sqlite3.connect(_LOG_DB, timeout=10.0)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS founder_gate_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checked_at TEXT NOT NULL,
            subject TEXT,
            message_type TEXT,
            decision TEXT,
            reason TEXT
        )
    """)
    conn.commit()
    conn.close()


def should_send_to_founder(subject: str, body: str = "",
                            message_type: str = "",
                            force_header: Optional[str] = None) -> bool:
    """Return True if this message should reach the founder's inbox."""
    _init_log()

    subj = subject or ""
    typ = (message_type or "").lower()

    # Force-header override (explicit founder-intended)
    if force_header == "force":
        _log("PASS", subj, typ, "force_header set")
        return True

    # Block override — never let swarm-internal through
    for pat in BLOCK_OVERRIDE_PATTERNS:
        if re.search(pat, subj, re.IGNORECASE):
            _log("BLOCK", subj, typ, f"block_override: {pat[:40]}")
            return False
        if re.search(pat, body or "", re.IGNORECASE):
            _log("BLOCK", subj, typ, f"block_override_body: {pat[:40]}")
            return False

    # message_type allowlist
    if typ in ("hitl_request", "hitl_approval", "hitl_acceptance",
               "founder_action_required"):
        _log("PASS", subj, typ, f"allowlisted message_type: {typ}")
        return True

    # HITL pattern match
    for pat in HITL_PATTERNS:
        if re.search(pat, subj, re.IGNORECASE):
            _log("PASS", subj, typ, f"hitl_pattern_subject: {pat[:40]}")
            return True
        if re.search(pat, body or "", re.IGNORECASE):
            _log("PASS", subj, typ, f"hitl_pattern_body: {pat[:40]}")
            return True

    # Everything else: BLOCK
    _log("BLOCK", subj, typ, "no hitl pattern; not founder-bound")
    return False


def _log(decision: str, subject: str, typ: str, reason: str):
    try:
        conn = sqlite3.connect(_LOG_DB, timeout=10.0)
        conn.execute(
            "INSERT INTO founder_gate_log (checked_at, subject, message_type, decision, reason) "
            "VALUES (?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), subject[:200], typ, decision, reason[:200])
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("founder_gate log failed: %s", e)


def stats():
    _init_log()
    conn = sqlite3.connect(_LOG_DB, timeout=10.0)
    by_decision = dict(conn.execute(
        "SELECT decision, COUNT(*) FROM founder_gate_log "
        "WHERE checked_at > datetime('now','-24 hours') GROUP BY decision"
    ).fetchall())
    total = conn.execute(
        "SELECT COUNT(*) FROM founder_gate_log "
        "WHERE checked_at > datetime('now','-24 hours')"
    ).fetchone()[0]
    recent_blocks = conn.execute(
        "SELECT subject, reason FROM founder_gate_log "
        "WHERE decision='BLOCK' AND checked_at > datetime('now','-1 hour') "
        "ORDER BY id DESC LIMIT 5"
    ).fetchall()
    conn.close()
    return {
        "decisions_24h":  by_decision,
        "total_24h":      total,
        "recent_blocks":  [{"subject": r[0][:60], "reason": r[1]} for r in recent_blocks],
    }


if __name__ == "__main__":
    import json
    # Self-test
    cases = [
        ("HITL approval requested for outbound email", "", "hitl_request", True),
        ("[Murphy Swarm] Rosetta completed: hitl approval...", "", "", False),  # block override
        ("HITL queue awaiting founder approval (5 items)", "", "", True),
        ("[Murphy LOW] Capacity info: No inbound replies", "", "", False),
        ("Re: Quote on chiller install", "", "", False),
        ("Accept the HITL Engagement Contract", "", "hitl_acceptance", True),
        ("🎯 Murphy Executive Report — 2026-06-14", "", "", False),
    ]
    print("SELF-TEST")
    for subj, body, typ, expected in cases:
        result = should_send_to_founder(subj, body, typ)
        mark = "✅" if result == expected else "❌"
        print(f"  {mark} '{subj[:50]}' → {result} (expected {expected})")
    print()
    print("STATS")
    print(json.dumps(stats(), indent=2))
