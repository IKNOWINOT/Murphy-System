"""
Ship 31cx — Forward-email ambient gathering + verification + transcript flow.

Per reply protocol Rule 6: a forwarded email is a NEW SESSION that needs:
  a. Collect info (who/what/when/why)
  b. Send a verification email to confirm facts
  c. Build a per-participant checklist of what each person said
  d. Ask the user: "Want me to email everyone a session transcript +
     action items + dates with direct-add calendar buttons?"
  e. Only proceed on user yes.

This module is COMPLEMENTARY to Ship 31g (forward-with-attachment role-lens
analysis): 31g handles single-document analysis through a role lens; 31cx
handles multi-participant chains where the goal is to organize and coordinate.

Detection priority:
  1. If 31g attachment-context says is_forward AND has attachment → 31g handles
  2. Else if subject starts with Fwd:/Fw:/FWD: AND body contains
     forward markers → 31cx ambient-gather

Module is graceful-degraded: any failure falls back to existing pipeline.
"""
from __future__ import annotations

import re
import json
import sqlite3
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from email.utils import parseaddr

logger = logging.getLogger(__name__)

_DB = "/var/lib/murphy-production/forward_sessions_31cx.db"

# ─────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────
def _init_db():
    c = sqlite3.connect(_DB, timeout=10.0)
    c.execute("""
        CREATE TABLE IF NOT EXISTS forward_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            forwarder_addr TEXT NOT NULL,
            inbound_id INTEGER,
            subject TEXT,
            participants_json TEXT,
            checklist_json TEXT,
            dates_json TEXT,
            action_items_json TEXT,
            verification_sent_at TEXT,
            verification_confirmed_at TEXT,
            user_prompt_status TEXT DEFAULT 'pending',
            user_prompt_response TEXT,
            transcript_sent_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_fwd_session ON forward_sessions(session_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_fwd_forwarder ON forward_sessions(forwarder_addr)")
    c.commit()
    c.close()


# ─────────────────────────────────────────────────────────────────────
# Detection
# ─────────────────────────────────────────────────────────────────────
_FWD_PREFIX = re.compile(r"^\s*(fwd|fw|forwarded message)[:\s]", re.IGNORECASE)
_FWD_MARKERS = (
    "---------- Forwarded message ---------",
    "Begin forwarded message",
    "-------- Original Message --------",
    "----- Original Message -----",
    "From: ", "Sent: ", "To: ",
)


def is_forward(subject: str, body: str) -> bool:
    """Cheap heuristic. Subject starts with Fwd/Fw and body has forward markers."""
    if not subject:
        return False
    if not _FWD_PREFIX.match(subject):
        return False
    if not body:
        return False
    # Count distinct forward markers
    hits = sum(1 for m in _FWD_MARKERS if m in body)
    return hits >= 2


# ─────────────────────────────────────────────────────────────────────
# Participant + date + action-item extraction
# ─────────────────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_DATE_RE = re.compile(
    r"\b(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\s*,?\s*)?"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?"
    r"(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?)?",
    re.IGNORECASE,
)
_ACTION_VERBS = (
    "need to", "should", "will", "must", "let's", "please", "can you",
    "could you", "would you", "action item", "todo", "follow up", "deadline",
    "by next", "by tomorrow", "by friday", "by monday",
)


def extract_participants(body: str, forwarder_addr: str = "") -> List[Dict]:
    """Return list of distinct participants with what they said.

    Each entry: {addr, mentions: int, said: [str, ...]}.
    Excludes the forwarder.
    """
    addrs = {}
    for m in _EMAIL_RE.finditer(body or ""):
        addr = m.group(0).lower()
        if addr == (forwarder_addr or "").lower():
            continue
        addrs[addr] = addrs.get(addr, 0) + 1

    # Find what each participant said: look for "From: <addr>" or "<addr> wrote:"
    # blocks and capture the next few lines.
    said_map = {a: [] for a in addrs}
    lines = (body or "").splitlines()
    for i, ln in enumerate(lines):
        for addr in addrs:
            if addr in ln.lower() and ("from:" in ln.lower() or "wrote:" in ln.lower()):
                # Capture next 3-5 non-empty lines
                captured = []
                for nx in lines[i+1:i+15]:
                    s = nx.strip()
                    if not s:
                        continue
                    if s.startswith(">") or s.startswith("From:") or s.startswith("To:"):
                        break
                    captured.append(s)
                    if len(captured) >= 3:
                        break
                if captured:
                    said_map[addr].append(" ".join(captured)[:300])

    out = []
    for addr, n in sorted(addrs.items(), key=lambda x: -x[1]):
        out.append({
            "addr": addr,
            "mentions": n,
            "said": said_map.get(addr, [])[:3],
        })
    return out


def extract_dates(body: str) -> List[Dict]:
    """Return list of {raw, ical_safe} date mentions."""
    dates = []
    seen = set()
    for m in _DATE_RE.finditer(body or ""):
        raw = m.group(0).strip()
        if raw.lower() in seen:
            continue
        seen.add(raw.lower())
        dates.append({"raw": raw, "ical_safe": _to_ical_safe(raw)})
        if len(dates) >= 10:
            break
    return dates


def _to_ical_safe(raw: str) -> Optional[str]:
    """Best-effort parse of a date string to ISO 8601. Returns None if can't."""
    # We use the dateutil parser if available; otherwise None
    try:
        from dateutil import parser as _dp
        dt = _dp.parse(raw, fuzzy=True, default=datetime(2026, 6, 17, 9, 0))
        return dt.isoformat()
    except Exception:
        return None


def extract_action_items(body: str) -> List[str]:
    """Pull sentences that look like action items."""
    items = []
    for sent in re.split(r"(?<=[.!?])\s+", body or ""):
        s = sent.strip()
        if len(s) < 15 or len(s) > 300:
            continue
        low = s.lower()
        if any(v in low for v in _ACTION_VERBS):
            items.append(s)
        if len(items) >= 12:
            break
    return items


# ─────────────────────────────────────────────────────────────────────
# Session lifecycle
# ─────────────────────────────────────────────────────────────────────
def begin_session(
    *, forwarder_addr: str, inbound_id: Optional[int],
    subject: str, body: str,
) -> Dict:
    """Open a forward session. Returns the full session dict."""
    _init_db()
    session_id = "fwd_" + hashlib.sha1(
        f"{forwarder_addr}|{subject}|{inbound_id}|{datetime.now().isoformat()}".encode()
    ).hexdigest()[:14]

    participants  = extract_participants(body, forwarder_addr=forwarder_addr)
    dates         = extract_dates(body)
    action_items  = extract_action_items(body)
    checklist     = {p["addr"]: p["said"] for p in participants}

    now = datetime.now(timezone.utc).isoformat()
    c = sqlite3.connect(_DB, timeout=10.0)
    c.execute(
        "INSERT INTO forward_sessions (session_id, forwarder_addr, inbound_id, "
        "subject, participants_json, checklist_json, dates_json, action_items_json, "
        "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (session_id, forwarder_addr, inbound_id, subject[:300],
         json.dumps(participants), json.dumps(checklist),
         json.dumps(dates), json.dumps(action_items), now, now),
    )
    c.commit(); c.close()

    logger.info(
        "Ship 31cx session %s opened: %d participants, %d dates, %d action items",
        session_id, len(participants), len(dates), len(action_items),
    )
    return {
        "session_id": session_id,
        "participants": participants,
        "dates": dates,
        "action_items": action_items,
        "checklist": checklist,
    }


def build_verification_email(session: Dict, forwarder_addr: str) -> Dict:
    """Build the verification email Murphy sends back to the forwarder.

    Returns {to, subject, body}. Caller queues to outbound.
    """
    parts = session["participants"]
    dates = session["dates"]
    items = session["action_items"]

    lines = [
        "Got the forward — let me make sure I have this right before doing anything.",
        "",
        "Here's what I extracted:",
        "",
    ]
    if parts:
        lines.append(f"People in the chain ({len(parts)}):")
        for p in parts[:8]:
            said_snip = f' — said: "{p["said"][0][:80]}"' if p["said"] else ""
            lines.append(f"  • {p['addr']}{said_snip}")
        lines.append("")
    if items:
        lines.append(f"Action items I picked up ({len(items)}):")
        for it in items[:8]:
            lines.append(f"  • {it}")
        lines.append("")
    if dates:
        lines.append(f"Dates mentioned ({len(dates)}):")
        for d in dates[:6]:
            lines.append(f"  • {d['raw']}")
        lines.append("")
    lines.append("Two questions:")
    lines.append("  1. Did I miss anyone or anything important?")
    lines.append("  2. Want me to email everyone a session transcript with")
    lines.append("     action items + calendar buttons for the dates?")
    lines.append("")
    lines.append("Just reply yes/no/edit and I'll move.")

    return {
        "to": forwarder_addr,
        "subject": f"Re: {session.get('subject','your forward')[:80]} — verification",
        "body": "\n".join(lines),
        "session_id": session["session_id"],
    }


def mark_verification_sent(session_id: str) -> None:
    _init_db()
    c = sqlite3.connect(_DB, timeout=10.0)
    c.execute(
        "UPDATE forward_sessions SET verification_sent_at=?, updated_at=? "
        "WHERE session_id=?",
        (datetime.now(timezone.utc).isoformat(),
         datetime.now(timezone.utc).isoformat(), session_id),
    )
    c.commit(); c.close()


def confirm_verification(session_id: str, response: str) -> Dict:
    """Forwarder responded yes/no/edit. Returns the updated session."""
    _init_db()
    now = datetime.now(timezone.utc).isoformat()
    user_status = "pending"
    low = (response or "").strip().lower()
    if low.startswith("y"):
        user_status = "yes_broadcast"
    elif low.startswith("n"):
        user_status = "no_broadcast"
    elif "edit" in low or "wait" in low or "hold" in low:
        user_status = "edit_requested"

    c = sqlite3.connect(_DB, timeout=10.0)
    c.execute(
        "UPDATE forward_sessions SET verification_confirmed_at=?, "
        "user_prompt_status=?, user_prompt_response=?, updated_at=? "
        "WHERE session_id=?",
        (now, user_status, (response or "")[:500], now, session_id),
    )
    c.commit()
    row = c.execute(
        "SELECT session_id, forwarder_addr, subject, participants_json, "
        "dates_json, action_items_json, user_prompt_status "
        "FROM forward_sessions WHERE session_id=?", (session_id,)
    ).fetchone()
    c.close()
    if not row:
        return {}
    return {
        "session_id":      row[0],
        "forwarder_addr":  row[1],
        "subject":         row[2],
        "participants":    json.loads(row[3] or "[]"),
        "dates":           json.loads(row[4] or "[]"),
        "action_items":    json.loads(row[5] or "[]"),
        "user_status":     row[6],
    }


def build_transcript_email(session: Dict) -> Dict:
    """Build the final transcript broadcast email. One per participant.

    Returns {to_list, subject, body, ics_attachments}.
    """
    parts = session.get("participants", [])
    dates = session.get("dates", [])
    items = session.get("action_items", [])

    to_list = [p["addr"] for p in parts]

    lines = [
        f"Session transcript for: {session.get('subject','')[:120]}",
        "",
        "Action items (optimal order):",
    ]
    for i, it in enumerate(items, 1):
        lines.append(f"  {i}. {it}")
    if dates:
        lines.append("")
        lines.append("Dates (add to calendar):")
        for d in dates:
            ics_url = build_calendar_link(d, session.get("subject", "Session"))
            lines.append(f"  • {d['raw']}  →  {ics_url}")
    lines.append("")
    lines.append("Reply to this thread if anything's wrong; I'll re-broadcast.")

    return {
        "to_list": to_list,
        "subject": f"Re: {session.get('subject','')[:80]} — transcript + action items",
        "body": "\n".join(lines),
    }


def build_calendar_link(date_entry: Dict, title: str) -> str:
    """Build a Google Calendar add-event link from a parsed date."""
    iso = date_entry.get("ical_safe")
    if not iso:
        return f"(unparsed: {date_entry.get('raw','')})"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        end = dt + timedelta(hours=1)
        fmt = "%Y%m%dT%H%M%S"
        from urllib.parse import quote
        base = "https://calendar.google.com/calendar/render?action=TEMPLATE"
        return (
            f"{base}"
            f"&text={quote(title[:80])}"
            f"&dates={dt.strftime(fmt)}/{end.strftime(fmt)}"
            f"&details={quote('Auto-extracted from forwarded email by Murphy')}"
        )
    except Exception:
        return f"(unparsed: {date_entry.get('raw','')})"


def mark_transcript_sent(session_id: str) -> None:
    _init_db()
    c = sqlite3.connect(_DB, timeout=10.0)
    c.execute(
        "UPDATE forward_sessions SET transcript_sent_at=?, updated_at=? "
        "WHERE session_id=?",
        (datetime.now(timezone.utc).isoformat(),
         datetime.now(timezone.utc).isoformat(), session_id),
    )
    c.commit(); c.close()
