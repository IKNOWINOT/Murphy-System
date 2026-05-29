"""
PATCH-RECONCILE-R95 (2026-05-28) — reality vs ledger delta recorder

WHAT THIS IS:
  Records a single capture of (reality_value, ledger_value, captured_via)
  for some subject (bank_balance, inventory_count, etc.) along with the
  expected lag-note for natural gap closure.

WHY IT EXISTS:
  Corey R93.5 insight: "the movement of money won't always be exactly
  the same as the ledger based on external processing which will leave
  notes of how long it can take."

  Bank balance is the canonical example. Phone captures $4,231 from
  banking app. Ledger says $4,489. Gap of -$258 is real but explainable:
  ACH payment hit early. Note expected_resolve_at to 72h from now.
  Reconcile walker picks up the delta at expected_resolve_at to verify
  closure.

INPUT:
  record_delta(subject, subject_id, reality_value, ledger_value, ...)

OUTPUT:
  {"delta_id": "...", "ok": true, "gap": -258.0, "auto_tagged": [...]}

USAGE:
  >>> from src.reconcile_recorder import record_delta
  >>> r = record_delta(
  ...     subject="bank_balance",
  ...     subject_id="wells_fargo_chk_1234",
  ...     reality_value=4231.00,
  ...     ledger_value=4489.00,
  ...     expected_resolve_hours=72,
  ...     resolve_reason="ACH pending settlement",
  ...     captured_via="mobile_ocr",
  ...     source_hint="Wells Fargo iOS app",
  ... )

DEPENDS ON:
  src/tag_extractor.py + src/tag_writer.py (auto-tags the delta)
  hitl_provenance.db with reality_deltas table

LAST UPDATED: 2026-05-28 R95
"""

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

_DB_PATH = "/var/lib/murphy-production/hitl_provenance.db"


def _delta_id(subject: str, subject_id: str, captured_at: str) -> str:
    """Deterministic ID — same subject+capture-time = same delta."""
    key = "{}::{}::{}".format(subject, subject_id, captured_at)
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def record_delta(
    subject: str,
    subject_id: str,
    reality_value: float,
    ledger_value: float,
    expected_resolve_hours: Optional[float] = None,
    resolve_reason: str = "",
    captured_via: str = "manual_entry",
    captured_by: str = "system",
    source_hint: str = "",
    db_path: str = _DB_PATH,
) -> Dict[str, Any]:
    """Record one reality-vs-ledger delta."""
    try:
        rv = float(reality_value)
        lv = float(ledger_value)
        gap = rv - lv
    except (TypeError, ValueError) as e:
        return {"ok": False, "reason": "numeric_parse: {}".format(e)}

    now = datetime.now(timezone.utc)
    captured_at = now.strftime("%Y-%m-%d %H:%M:%S")
    expected_at = None
    if expected_resolve_hours is not None:
        expected_at = (now + timedelta(hours=float(expected_resolve_hours))).strftime("%Y-%m-%d %H:%M:%S")

    delta_id = _delta_id(subject, subject_id, captured_at)

    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.execute(
            "INSERT OR IGNORE INTO reality_deltas "
            "(delta_id, subject, subject_id, reality_value, ledger_value, gap, "
            " expected_resolve_at, resolve_reason, captured_via, captured_by, "
            " source_hint) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (delta_id, subject, subject_id, rv, lv, gap, expected_at,
             resolve_reason, captured_via, captured_by, source_hint),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        return {"ok": False, "reason": "db_write: {}: {}".format(type(e).__name__, e)}

    # Auto-tag the delta via facet_tags
    auto_tagged = []
    try:
        from src.tag_extractor import extract_tags as _ext
        from src.tag_writer import write_tags as _write
        payload = {
            "subject": subject,
            "subject_id": subject_id,
            "captured_at": captured_at,
            "source_kind": "reality_capture",
            "source_hint": source_hint or subject,
            "command_function": captured_via,
            "command_module": "reconcile_recorder",
            "hitl_status": "pending" if abs(gap) > 0.01 else "matched",
            "actor": captured_by,
        }
        tags = _ext({"entity_table": "reality_deltas",
                     "entity_id": delta_id,
                     "payload": payload})
        # Add domain-specific tags
        tags.append({"axis": "what", "tag_value": "#" + subject,
                     "confidence": 1.0, "source": "rule"})
        tags.append({"axis": "what", "tag_value": "#reality_capture",
                     "confidence": 1.0, "source": "rule"})
        if abs(gap) > 0.01:
            tags.append({"axis": "troubleshoot", "tag_value": "#delta_pending",
                         "confidence": 1.0, "source": "rule"})
        else:
            tags.append({"axis": "troubleshoot", "tag_value": "#delta_matched",
                         "confidence": 1.0, "source": "rule"})
        if expected_at:
            tags.append({"axis": "why", "tag_value": "#expects_resolve",
                         "confidence": 1.0, "source": "rule"})
        _write("reality_deltas", delta_id, tags)
        auto_tagged = [t["tag_value"] for t in tags]
    except Exception:
        pass  # tagging best-effort

    return {
        "ok": True,
        "delta_id": delta_id,
        "gap": gap,
        "expected_resolve_at": expected_at,
        "auto_tagged": auto_tagged,
    }


def list_pending_deltas(subject: Optional[str] = None,
                        db_path: str = _DB_PATH) -> list:
    """Show open deltas — for walker queue + management dashboard."""
    try:
        conn = sqlite3.connect(db_path, timeout=3)
        conn.row_factory = sqlite3.Row
        if subject:
            rows = conn.execute(
                "SELECT delta_id, subject, subject_id, reality_value, ledger_value, "
                "gap, expected_resolve_at, captured_at FROM reality_deltas "
                "WHERE status = 'pending' AND subject = ? ORDER BY captured_at DESC LIMIT 50",
                (subject,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT delta_id, subject, subject_id, reality_value, ledger_value, "
                "gap, expected_resolve_at, captured_at FROM reality_deltas "
                "WHERE status = 'pending' ORDER BY captured_at DESC LIMIT 50"
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": "{}: {}".format(type(e).__name__, e)}]


def overdue_deltas(db_path: str = _DB_PATH) -> list:
    """Deltas whose expected_resolve_at has passed but they're still pending."""
    try:
        conn = sqlite3.connect(db_path, timeout=3)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM reality_deltas "
            "WHERE status = 'pending' "
            "  AND expected_resolve_at IS NOT NULL "
            "  AND expected_resolve_at < datetime('now') "
            "ORDER BY expected_resolve_at LIMIT 50"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": "{}: {}".format(type(e).__name__, e)}]


if __name__ == "__main__":
    # Demo: bank balance capture per Corey's canonical example
    print("Recording bank balance delta (Corey's canonical example)...")
    r = record_delta(
        subject="bank_balance",
        subject_id="wells_fargo_chk_demo",
        reality_value=4231.00,
        ledger_value=4489.00,
        expected_resolve_hours=72,
        resolve_reason="ACH pending settlement",
        captured_via="mobile_ocr",
        captured_by="corey",
        source_hint="Wells Fargo iOS app",
    )
    print("Result:")
    for k, v in r.items():
        print("  {}: {}".format(k, v))

    print()
    print("Pending deltas:")
    for d in list_pending_deltas(subject="bank_balance"):
        print("  {} subject={} gap={} expected_resolve={}".format(
            d.get("delta_id", "?")[:12], d.get("subject"),
            d.get("gap"), d.get("expected_resolve_at")
        ))
