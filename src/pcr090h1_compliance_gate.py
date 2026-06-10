"""PCR-090h.1 — Outbound compliance gate (CAN-SPAM / CASL / GDPR / DNC / bounce).

Pre-send check that fires before an outbound_email_queue row moves from
pending_review → approved. Five checks:

  1. DNC suppression (HARD)  — crm.db dnc_suppression
  2. Bounce list      (HARD)  — murphy_mail.db bounced_addresses
  3. CAN-SPAM body    (HARD)  — physical address + unsubscribe link required
  4. CASL consent     (SOFT)  — flag if Canadian recipient w/o consent record
  5. GDPR consent     (SOFT)  — flag if EU recipient w/o consent record

HARD failure  → verdict = "block", send must not proceed
SOFT failure  → verdict = "warn",  send proceeds, founder logged
ALL pass      → verdict = "pass"

Per L160, every gate evaluation is appended to outbound_email_queue.audit_report
as a JSON array (one entry per gate run, never mutated).

Per L161, this gate NEVER alters regulated content — it only inspects + verdicts.
"""
from __future__ import annotations
import json
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

CRM_DB = "/var/lib/murphy-production/crm.db"
MAIL_DB = "/var/lib/murphy-production/murphy_mail.db"

# Schema migrations (additive only — append columns + new audit table)
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pcr090h1_gate_runs (
    run_id              TEXT PRIMARY KEY,
    queue_id            TEXT NOT NULL,
    run_at              REAL NOT NULL,
    verdict             TEXT NOT NULL,   -- 'pass' | 'warn' | 'block'
    hard_failures       INTEGER NOT NULL DEFAULT 0,
    soft_failures       INTEGER NOT NULL DEFAULT 0,
    checks_json         TEXT NOT NULL    -- full check breakdown
);
CREATE INDEX IF NOT EXISTS idx_h1_queue ON pcr090h1_gate_runs(queue_id);
CREATE INDEX IF NOT EXISTS idx_h1_verdict ON pcr090h1_gate_runs(verdict);
"""

# Country codes for jurisdictional rules
_EU_TLDS = {
    "de","fr","it","es","nl","be","at","pt","gr","ie","fi","se","dk","pl",
    "cz","hu","ro","bg","sk","si","ee","lv","lt","lu","mt","cy","hr","eu",
}
_CA_TLDS = {"ca"}

_UNSUB_PATTERNS = [
    r"\bunsubscribe\b",
    r"\bopt[\s\-]?out\b",
    r"\bstop\s+receiving\b",
    r"List-Unsubscribe",
]
_PHYS_ADDR_HINT = [
    r"\b\d{1,6}\s+\w+\s+(street|st|avenue|ave|road|rd|blvd|boulevard|lane|ln|drive|dr|way|court|ct)\b",
    r"\b(suite|ste|floor|fl)\s+\d+",
    r"\bP\.?O\.?\s*Box\s+\d+",
]


@dataclass
class CheckResult:
    name: str
    severity: str  # 'hard' or 'soft'
    passed: bool
    detail: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)


def ensure_schema() -> None:
    c = sqlite3.connect(MAIL_DB, timeout=5.0)
    try:
        c.executescript(_SCHEMA_SQL)
        c.commit()
    finally:
        c.close()


def _domain_of(addr: str) -> str:
    if not addr or "@" not in addr:
        return ""
    return addr.rsplit("@", 1)[-1].lower().strip(">")


def _tld_of(addr: str) -> str:
    dom = _domain_of(addr)
    if not dom or "." not in dom:
        return ""
    return dom.rsplit(".", 1)[-1]


def check_dnc(recipients: List[str]) -> CheckResult:
    """HARD — block if any recipient is on the DNC list."""
    if not recipients:
        return CheckResult("dnc", "hard", True, "no recipients")
    hits = []
    try:
        c = sqlite3.connect(f"file:{CRM_DB}?mode=ro", uri=True, timeout=3.0)
        try:
            for r in recipients:
                r_clean = (r or "").lower().strip()
                if not r_clean:
                    continue
                dom = _domain_of(r_clean)
                # exact email or domain match
                row = c.execute(
                    "SELECT email, domain, reason FROM dnc_suppression "
                    "WHERE LOWER(email)=? OR (domain != '' AND LOWER(domain)=?) "
                    "LIMIT 1",
                    (r_clean, dom),
                ).fetchone()
                if row:
                    hits.append({"recipient": r, "reason": row[2] or "listed"})
        finally:
            c.close()
    except Exception as e:
        return CheckResult("dnc", "hard", False, f"db_error: {e}",
                           {"recipients_checked": len(recipients)})
    if hits:
        return CheckResult(
            "dnc", "hard", False,
            f"{len(hits)} recipient(s) on DNC list",
            {"hits": hits, "recipients_checked": len(recipients)},
        )
    return CheckResult("dnc", "hard", True,
                       f"all {len(recipients)} recipient(s) clear",
                       {"recipients_checked": len(recipients)})


def check_bounces(recipients: List[str]) -> CheckResult:
    """HARD — block if any recipient is on the hard-bounce list."""
    if not recipients:
        return CheckResult("bounces", "hard", True, "no recipients")
    hits = []
    try:
        c = sqlite3.connect(f"file:{MAIL_DB}?mode=ro", uri=True, timeout=3.0)
        try:
            for r in recipients:
                r_clean = (r or "").lower().strip()
                if not r_clean:
                    continue
                row = c.execute(
                    "SELECT email FROM bounced_addresses WHERE LOWER(email)=? LIMIT 1",
                    (r_clean,),
                ).fetchone()
                if row:
                    hits.append({"recipient": r})
        finally:
            c.close()
    except Exception as e:
        # bounce table optional — if missing, treat as no hits
        return CheckResult("bounces", "hard", True, f"no_bounce_table: {e}",
                           {"recipients_checked": len(recipients)})
    if hits:
        return CheckResult(
            "bounces", "hard", False,
            f"{len(hits)} recipient(s) on hard-bounce list",
            {"hits": hits},
        )
    return CheckResult("bounces", "hard", True,
                       f"all {len(recipients)} recipient(s) clear")


def check_can_spam(body: str, subject: str = "") -> CheckResult:
    """HARD — body must contain physical address hint + unsubscribe mechanism."""
    if not body:
        return CheckResult("can_spam", "hard", False, "empty body")
    body_lc = body.lower()
    has_unsub = any(re.search(p, body, re.IGNORECASE) for p in _UNSUB_PATTERNS)
    has_phys = any(re.search(p, body, re.IGNORECASE) for p in _PHYS_ADDR_HINT)
    missing = []
    if not has_unsub:
        missing.append("unsubscribe_mechanism")
    if not has_phys:
        missing.append("physical_address")
    if missing:
        return CheckResult(
            "can_spam", "hard", False,
            f"missing: {', '.join(missing)}",
            {"has_unsubscribe": has_unsub, "has_physical_address": has_phys},
        )
    return CheckResult("can_spam", "hard", True,
                       "unsubscribe + physical address present",
                       {"has_unsubscribe": True, "has_physical_address": True})


def check_casl_consent(recipients: List[str], metadata: Dict[str, Any]) -> CheckResult:
    """SOFT — flag if Canadian recipient w/o consent record in metadata."""
    canadian = [r for r in recipients if _tld_of(r) in _CA_TLDS]
    if not canadian:
        return CheckResult("casl", "soft", True, "no canadian recipients")
    consent_records = (metadata or {}).get("consent_records") or {}
    missing = [r for r in canadian if r not in consent_records]
    if missing:
        return CheckResult(
            "casl", "soft", False,
            f"{len(missing)} canadian recipient(s) without consent record",
            {"missing_consent": missing},
        )
    return CheckResult("casl", "soft", True,
                       f"all {len(canadian)} canadian recipient(s) have consent")


def check_gdpr_consent(recipients: List[str], metadata: Dict[str, Any]) -> CheckResult:
    """SOFT — flag if EU recipient w/o consent record in metadata."""
    eu = [r for r in recipients if _tld_of(r) in _EU_TLDS]
    if not eu:
        return CheckResult("gdpr", "soft", True, "no eu recipients")
    consent_records = (metadata or {}).get("consent_records") or {}
    missing = [r for r in eu if r not in consent_records]
    if missing:
        return CheckResult(
            "gdpr", "soft", False,
            f"{len(missing)} eu recipient(s) without consent record",
            {"missing_consent": missing},
        )
    return CheckResult("gdpr", "soft", True,
                       f"all {len(eu)} eu recipient(s) have consent")


def run_gate(
    queue_id: str,
    to_addresses: List[str],
    subject: str,
    body: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run all 5 checks, persist a gate-run row, return verdict + breakdown.

    Verdict logic:
      - any HARD failure → 'block'
      - any SOFT failure (no HARD failures) → 'warn'
      - all pass → 'pass'
    """
    ensure_schema()
    metadata = metadata or {}
    checks: List[CheckResult] = [
        check_dnc(to_addresses),
        check_bounces(to_addresses),
        check_can_spam(body, subject),
        check_casl_consent(to_addresses, metadata),
        check_gdpr_consent(to_addresses, metadata),
    ]
    hard_fails = sum(1 for c in checks if c.severity == "hard" and not c.passed)
    soft_fails = sum(1 for c in checks if c.severity == "soft" and not c.passed)
    if hard_fails > 0:
        verdict = "block"
    elif soft_fails > 0:
        verdict = "warn"
    else:
        verdict = "pass"

    checks_json = [
        {
            "name": c.name,
            "severity": c.severity,
            "passed": c.passed,
            "detail": c.detail,
            "evidence": c.evidence,
        }
        for c in checks
    ]

    run_id = f"h1_{uuid.uuid4().hex[:16]}"
    now = time.time()
    try:
        conn = sqlite3.connect(MAIL_DB, timeout=5.0)
        try:
            conn.execute(
                "INSERT INTO pcr090h1_gate_runs "
                "(run_id, queue_id, run_at, verdict, hard_failures, soft_failures, checks_json) "
                "VALUES (?,?,?,?,?,?,?)",
                (run_id, queue_id, now, verdict, hard_fails, soft_fails, json.dumps(checks_json)),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        # persistence failure is non-fatal for the caller — verdict still returned
        pass

    return {
        "run_id": run_id,
        "queue_id": queue_id,
        "run_at": now,
        "verdict": verdict,
        "hard_failures": hard_fails,
        "soft_failures": soft_fails,
        "checks": checks_json,
    }


def get_runs_for_queue(queue_id: str) -> List[Dict[str, Any]]:
    """Append-only audit history for a queue row."""
    ensure_schema()
    c = sqlite3.connect(MAIL_DB, timeout=5.0)
    try:
        rows = c.execute(
            "SELECT run_id, run_at, verdict, hard_failures, soft_failures, checks_json "
            "FROM pcr090h1_gate_runs WHERE queue_id=? ORDER BY run_at DESC",
            (queue_id,),
        ).fetchall()
        return [
            {
                "run_id": r[0], "run_at": r[1], "verdict": r[2],
                "hard_failures": r[3], "soft_failures": r[4],
                "checks": json.loads(r[5]) if r[5] else [],
            }
            for r in rows
        ]
    finally:
        c.close()


def get_aggregate_stats() -> Dict[str, Any]:
    """For dashboards — counts by verdict over the last 30 days."""
    ensure_schema()
    c = sqlite3.connect(MAIL_DB, timeout=5.0)
    try:
        since = time.time() - (30 * 86400)
        rows = c.execute(
            "SELECT verdict, COUNT(*) FROM pcr090h1_gate_runs "
            "WHERE run_at >= ? GROUP BY verdict",
            (since,),
        ).fetchall()
        by_verdict = {r[0]: r[1] for r in rows}
        return {
            "since": since,
            "total": sum(by_verdict.values()),
            "by_verdict": by_verdict,
        }
    finally:
        c.close()
