"""
tenant_inbox_31at — Ship 31at.TENANT_INBOX_UI

Backend for the tenant's "what did I send Murphy" dashboard.

Reads from:
  • inbound_replies.db (every email Murphy received)
  • thread_situation.db (auto-classified domain/vertical & role)
  • license_registry.db (any Murphy responses that went back out)

Surfaces three axes per row:
  • WHO copied/forwarded it       — from_addr + cc_addrs + delivery_mode
  • DOMAIN of the conversation    — from thread_situation.vertical
  • SURFACE (work type requested) — from inbound_replies.intent_class

Tenants see their own data only (tenant_id filter).
Founder sees everything (platform_legacy and per-tenant).
"""
from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("murphy.tenant_inbox_31at")

INBOUND_DB = "/var/lib/murphy-production/inbound_replies.db"
THREAD_DB  = "/var/lib/murphy-production/thread_situation.db"


def _decode_subject(subj: str) -> str:
    """Decode RFC2047 =?utf-8?q?...?= subjects for display."""
    if not subj:
        return ""
    try:
        from email.header import decode_header
        decoded = decode_header(subj)
        parts = []
        for text, enc in decoded:
            if isinstance(text, bytes):
                parts.append(text.decode(enc or "utf-8", errors="replace"))
            else:
                parts.append(text)
        return " ".join(parts).strip()
    except Exception:
        return subj


def _normalize_delivery_mode(row: Dict[str, Any]) -> str:
    """Derive 'how did this reach Murphy' bucket.

    Buckets: direct / cc / forward / ambient
    cc_addrs presence overrides delivery_mode when delivery_mode is direct
    but the message included a CC to a Murphy address.
    """
    mode = (row.get("delivery_mode") or "direct").lower()
    if mode in ("cc", "forward", "ambient", "direct"):
        cc = row.get("cc_addrs") or ""
        subject = (row.get("subject") or "").lower()
        # If forward marker in subject and not explicitly classified, mark
        if mode == "direct" and re.match(r"^(fwd?|fw):\s", subject):
            return "forward"
        if mode == "direct" and "murphy@" in cc.lower():
            return "cc"
        return mode
    return "direct"


def _humanize_intent(intent: Optional[str]) -> str:
    """Make raw intent_class friendly for the UI surface column."""
    if not intent:
        return "—"
    pretty = {
        "noise":            "Noise / Auto",
        "inquiry":          "Inquiry",
        "report_request":   "Report Request",
        "reply_to_outreach":"Reply (to outreach)",
        "meeting":          "Meeting",
        "general_query":    "General Question",
        "other":            "Other",
    }
    return pretty.get(intent, intent.replace("_", " ").title())


def stats(tenant_id: str = "") -> Dict[str, Any]:
    """Return aggregate stats for the inbox dashboard heading.

    If tenant_id is empty, returns platform-wide stats (founder view).
    """
    where = ""
    params: List[Any] = []
    if tenant_id and tenant_id != "*":
        where = "WHERE tenant_id = ?"
        params = [tenant_id]

    out: Dict[str, Any] = {
        "tenant_id": tenant_id or "platform_legacy",
        "total":          0,
        "by_delivery":    {},
        "by_intent":      {},
        "by_domain":      {},
        "recent_count":   0,
        "asof":           datetime.now(timezone.utc).isoformat(),
    }
    try:
        c = sqlite3.connect(f"file:{INBOUND_DB}?mode=ro", uri=True, timeout=5.0)
        out["total"] = c.execute(f"SELECT COUNT(*) FROM inbound_replies {where}", params).fetchone()[0]

        for mode, n in c.execute(
            f"SELECT COALESCE(delivery_mode,'direct'), COUNT(*) "
            f"FROM inbound_replies {where} GROUP BY 1 ORDER BY 2 DESC", params):
            out["by_delivery"][mode] = n

        for cls, n in c.execute(
            f"SELECT COALESCE(intent_class,'—'), COUNT(*) "
            f"FROM inbound_replies {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 12", params):
            out["by_intent"][_humanize_intent(cls if cls != "—" else None)] = n

        recent_where = where + (" AND " if where else "WHERE ") + \
            "received_at > datetime('now','-7 days')"
        out["recent_count"] = c.execute(
            f"SELECT COUNT(*) FROM inbound_replies {recent_where}", params
        ).fetchone()[0]
        c.close()
    except Exception as e:
        logger.warning("31at stats inbound failed: %s", e)

    try:
        c = sqlite3.connect(f"file:{THREAD_DB}?mode=ro", uri=True, timeout=5.0)
        # thread_situation has no tenant_id; show all domains as global signal
        for vertical, n in c.execute(
            "SELECT COALESCE(vertical,'general'), COUNT(*) "
            "FROM thread_situation GROUP BY 1 ORDER BY 2 DESC LIMIT 12"):
            out["by_domain"][vertical] = n
        c.close()
    except Exception as e:
        logger.warning("31at stats threads failed: %s", e)

    return out


def list_messages(
    tenant_id: str = "",
    limit: int = 50,
    offset: int = 0,
    delivery_mode: str = "",
    intent_class: str = "",
    search: str = "",
) -> Dict[str, Any]:
    """List recent inbound messages for the tenant inbox.

    Joins thread_situation by from_addr to augment with vertical/role.
    """
    conds: List[str] = []
    params: List[Any] = []
    if tenant_id and tenant_id != "*":
        conds.append("tenant_id = ?")
        params.append(tenant_id)
    if delivery_mode:
        conds.append("COALESCE(delivery_mode,'direct') = ?")
        params.append(delivery_mode)
    if intent_class:
        conds.append("COALESCE(intent_class,'—') = ?")
        params.append(intent_class)
    if search:
        conds.append("(subject LIKE ? OR body_preview LIKE ? OR from_addr LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    where = ("WHERE " + " AND ".join(conds)) if conds else ""

    out: Dict[str, Any] = {
        "items": [], "total": 0, "limit": limit, "offset": offset,
    }
    try:
        c = sqlite3.connect(f"file:{INBOUND_DB}?mode=ro", uri=True, timeout=5.0)
        c.row_factory = sqlite3.Row
        total = c.execute(f"SELECT COUNT(*) FROM inbound_replies {where}", params).fetchone()[0]
        out["total"] = total
        rows = c.execute(
            f"SELECT id, received_at, from_addr, from_domain, to_addr, subject, "
            f"cc_addrs, delivery_mode, intent_class, intent_confidence, "
            f"intent_method, tenant_id, source_type, body_preview "
            f"FROM inbound_replies {where} "
            f"ORDER BY received_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        c.close()
    except Exception as e:
        logger.warning("31at list_messages inbound failed: %s", e)
        return out

    # Augment with thread_situation
    thread_map: Dict[str, Dict[str, Any]] = {}
    try:
        c = sqlite3.connect(f"file:{THREAD_DB}?mode=ro", uri=True, timeout=5.0)
        c.row_factory = sqlite3.Row
        for tr in c.execute(
            "SELECT from_addr, vertical, role, subject_root FROM thread_situation"):
            thread_map[(tr["from_addr"] or "").lower()] = dict(tr)
        c.close()
    except Exception as e:
        logger.warning("31at list_messages threads failed: %s", e)

    for r in rows:
        tinfo = thread_map.get((r["from_addr"] or "").lower(), {})
        item = {
            "id":               r["id"],
            "received_at":      r["received_at"],
            "from":             r["from_addr"],
            "from_domain":      r["from_domain"],
            "to":               r["to_addr"],
            "cc":               r["cc_addrs"] or "",
            "subject":          _decode_subject(r["subject"] or ""),
            "delivery_mode":    _normalize_delivery_mode(dict(r)),
            "surface":          _humanize_intent(r["intent_class"]),
            "surface_raw":      r["intent_class"] or "",
            "surface_conf":     r["intent_confidence"] or 0.0,
            "domain":           tinfo.get("vertical") or "—",
            "role":             tinfo.get("role") or "—",
            "tenant_id":        r["tenant_id"],
            "preview":          (r["body_preview"] or "")[:280],
        }
        out["items"].append(item)
    return out


def message_detail(msg_id: int) -> Optional[Dict[str, Any]]:
    """Drill-down view of a single inbound message."""
    try:
        c = sqlite3.connect(f"file:{INBOUND_DB}?mode=ro", uri=True, timeout=5.0)
        c.row_factory = sqlite3.Row
        r = c.execute(
            "SELECT * FROM inbound_replies WHERE id = ?", (msg_id,)
        ).fetchone()
        c.close()
        if not r:
            return None
        d = dict(r)
        d["subject"] = _decode_subject(d.get("subject") or "")
        d["surface"] = _humanize_intent(d.get("intent_class"))
        d["delivery_mode_normalized"] = _normalize_delivery_mode(d)
    except Exception as e:
        logger.warning("31at message_detail failed: %s", e)
        return None

    # Find related thread_situation
    try:
        c = sqlite3.connect(f"file:{THREAD_DB}?mode=ro", uri=True, timeout=5.0)
        c.row_factory = sqlite3.Row
        tr = c.execute(
            "SELECT * FROM thread_situation WHERE lower(from_addr) = ?",
            ((d.get("from_addr") or "").lower(),)
        ).fetchone()
        c.close()
        d["thread_situation"] = dict(tr) if tr else None
    except Exception as e:
        logger.warning("31at message_detail thread join failed: %s", e)
        d["thread_situation"] = None
    return d
