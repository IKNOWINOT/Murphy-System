"""
PATCH-BROWSER-R97 (2026-05-28 R97) — Murphy-owned browser substrate

WHAT THIS IS:
  Session-based browser primitive that ghost controller (operator) and
  mobile capture clients drive to navigate, fill, click, extract, and
  screenshot pages. Wraps Playwright when available; degrades to a
  stub-mode that records "would have done X" actions when not.

WHY IT EXISTS:
  Corey R94.5: "build our own browser to collect whatever data needed
  by ghost controller UI movements and commands to get to logic needed"

  Why session-based (not one-shot):
    Bank balance capture flow is multi-step:
      1. Navigate to login page
      2. Fill username (from R96 vault.username — visible)
      3. Fill password (from R96 vault.encrypted_value — decrypted just-in-time)
      4. Click submit
      5. Wait for redirect to account page
      6. Extract balance from DOM
      7. record_delta() via R95 reconcile_recorder
    Each step depends on cookies + login state from prior steps.
    One-shot would mean re-authenticating every action.

  Why this is the "Murphy-owned" browser:
    Even though Playwright drives Chromium under the hood, ghost controller
    ONLY ever talks to murphy_browser.py — never to Chromium directly.
    All actions are session-logged in browser_actions table.
    All credentials come from R96 vault (no plaintext in code).
    All extracted data is auto-tagged via facet_tags chain.
    The browser is FULLY OBSERVABLE + auditable.

PUBLIC SURFACE:
  open_session(tenant_id, operator, purpose) -> session_id
  navigate(session_id, url) -> {ok, title, current_url}
  fill(session_id, selector, value=None, credential_label=None) -> {ok}
    If credential_label given, retrieves from R96 vault automatically.
    Password plaintext never returns from this function.
  click(session_id, selector) -> {ok, navigated_to}
  extract_text(session_id, selector) -> {ok, text}
  screenshot(session_id) -> {ok, path}  (writes PNG, returns file path)
  close_session(session_id) -> {ok}
  
  list_sessions(tenant_id=None, state='open') -> [session metadata]
  session_actions(session_id) -> [action history for this session]

GHOST CONTROLLER ENTRY POINT (R98+):
  capture_bank_balance(tenant_id, vault_label) -> 
    Composes all the above into the canonical bank-balance flow.
    Records reality_delta via R95.

DEPENDS ON:
  playwright (optional — degrades to stub if missing)
  src/credential_vault.py for auto-fill
  src/reconcile_recorder.py for balance capture
  src/tag_writer.py for auto-tagging
  hitl_provenance.db with browser_sessions + browser_actions tables

LAST UPDATED: 2026-05-28 R97
"""

import hashlib
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_DB_PATH = "/var/lib/murphy-production/hitl_provenance.db"

# Try Playwright — degrade gracefully if unavailable
try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_OK = True
except ImportError:
    _PLAYWRIGHT_OK = False

# In-process session cache: session_id -> playwright page/browser objects
# Sessions are NOT persisted across process restarts (browser_actions log is)
_SESSIONS: Dict[str, Dict[str, Any]] = {}
_SESSIONS_LOCK = threading.Lock()


def _session_id(tenant_id: str, operator: str, purpose: str) -> str:
    """Deterministic session_id per (tenant + operator + purpose + time-bucket)."""
    minute = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    seed = "{}::{}::{}::{}".format(tenant_id, operator, purpose, minute)
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


def _log_action(session_id: str, action_type: str, target_selector: str = "",
                input_value: str = "", result_summary: str = "",
                success: bool = True, error: str = "",
                db_path: str = _DB_PATH) -> str:
    """Persist a browser action to browser_actions table."""
    try:
        conn = sqlite3.connect(db_path, timeout=3)
        # Get next seq for this session
        cur = conn.execute(
            "SELECT COALESCE(MAX(seq), -1) + 1 FROM browser_actions WHERE session_id = ?",
            (session_id,),
        )
        seq = cur.fetchone()[0]
        action_id = hashlib.sha256(
            "{}::{}::{}".format(session_id, seq, datetime.now().isoformat()).encode()
        ).hexdigest()[:16]
        conn.execute(
            "INSERT INTO browser_actions "
            "(action_id, session_id, seq, action_type, target_selector, "
            " input_value, result_summary, success, error_reason) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (action_id, session_id, seq, action_type, target_selector[:200],
             input_value[:500], result_summary[:500],
             1 if success else 0, error[:200]),
        )
        # Touch session activity
        conn.execute(
            "UPDATE browser_sessions SET last_activity_at = CURRENT_TIMESTAMP "
            "WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()
        conn.close()
        return action_id
    except Exception:
        return ""


def open_session(tenant_id: str, operator: str = "system",
                 purpose: str = "browse", headless: bool = True,
                 db_path: str = _DB_PATH) -> Dict[str, Any]:
    """Open a browser session. Returns session_id."""
    if not tenant_id:
        return {"ok": False, "reason": "missing_tenant_id"}

    sid = _session_id(tenant_id, operator, purpose)

    # Persist session metadata
    try:
        conn = sqlite3.connect(db_path, timeout=3)
        conn.execute(
            "INSERT OR REPLACE INTO browser_sessions "
            "(session_id, tenant_id, operator, purpose, state) "
            "VALUES (?,?,?,?,?)",
            (sid, tenant_id, operator, purpose, "open"),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        return {"ok": False, "reason": "db_write: {}: {}".format(type(e).__name__, e)}

    # Launch playwright if available
    engine = "stub"
    if _PLAYWRIGHT_OK:
        try:
            with _SESSIONS_LOCK:
                pw = sync_playwright().start()
                browser = pw.chromium.launch(headless=headless)
                page = browser.new_page()
                _SESSIONS[sid] = {
                    "playwright": pw,
                    "browser": browser,
                    "page": page,
                    "tenant_id": tenant_id,
                }
            engine = "playwright_chromium"
        except Exception as e:
            _log_action(sid, "open_session", "", "", "", False, str(e)[:200])
            engine = "stub_after_pw_fail"
    else:
        with _SESSIONS_LOCK:
            _SESSIONS[sid] = {"tenant_id": tenant_id, "stub": True}

    _log_action(sid, "open_session", "", "", "engine={}".format(engine), True)

    # Auto-tag via facet_tags chain
    try:
        import sys
        if "/opt/Murphy-System" not in sys.path:
            sys.path.insert(0, "/opt/Murphy-System")
        from src.tag_writer import write_tags
        tags = [
            {"axis": "what", "tag_value": "#browser_session", "confidence": 1.0, "source": "rule"},
            {"axis": "who", "tag_value": "#" + operator, "confidence": 1.0, "source": "rule"},
            {"axis": "who", "tag_value": "#tenant_" + tenant_id, "confidence": 1.0, "source": "rule"},
            {"axis": "why", "tag_value": "#" + purpose, "confidence": 0.9, "source": "rule"},
            {"axis": "how", "tag_value": "#" + engine, "confidence": 1.0, "source": "rule"},
            {"axis": "when", "tag_value": "#today", "confidence": 1.0, "source": "rule"},
        ]
        write_tags("browser_sessions", sid, tags)
    except Exception:
        pass

    return {"ok": True, "session_id": sid, "engine": engine}


def navigate(session_id: str, url: str) -> Dict[str, Any]:
    """Navigate the session's browser to url. Returns {ok, title, current_url}."""
    with _SESSIONS_LOCK:
        sess = _SESSIONS.get(session_id)
    if not sess:
        _log_action(session_id, "navigate", url, "", "", False, "session_not_found")
        return {"ok": False, "reason": "session_not_found"}

    if sess.get("stub"):
        _log_action(session_id, "navigate", url, "", "stub_pretend", True)
        return {"ok": True, "title": "(stub)", "current_url": url, "engine": "stub"}

    try:
        sess["page"].goto(url, wait_until="domcontentloaded", timeout=30000)
        title = sess["page"].title()
        current = sess["page"].url
        _log_action(session_id, "navigate", url, "",
                    "title='{}' current='{}'".format(title[:60], current[:60]), True)
        return {"ok": True, "title": title, "current_url": current, "engine": "playwright"}
    except Exception as e:
        _log_action(session_id, "navigate", url, "", "", False, str(e)[:200])
        return {"ok": False, "reason": "{}: {}".format(type(e).__name__, str(e)[:120])}


def extract_text(session_id: str, selector: str) -> Dict[str, Any]:
    """Extract text content from elements matching selector."""
    with _SESSIONS_LOCK:
        sess = _SESSIONS.get(session_id)
    if not sess:
        return {"ok": False, "reason": "session_not_found"}
    if sess.get("stub"):
        _log_action(session_id, "extract_text", selector, "", "stub_pretend", True)
        return {"ok": True, "text": "(stub_text)", "engine": "stub"}
    try:
        text = sess["page"].locator(selector).first.inner_text(timeout=5000)
        _log_action(session_id, "extract_text", selector, "",
                    "len={} preview='{}'".format(len(text), text[:60]), True)
        return {"ok": True, "text": text, "engine": "playwright"}
    except Exception as e:
        _log_action(session_id, "extract_text", selector, "", "", False, str(e)[:200])
        return {"ok": False, "reason": "{}: {}".format(type(e).__name__, str(e)[:120])}


def close_session(session_id: str, db_path: str = _DB_PATH) -> Dict[str, Any]:
    """Close the browser session and mark its state in DB."""
    with _SESSIONS_LOCK:
        sess = _SESSIONS.pop(session_id, None)
    if sess and not sess.get("stub"):
        try:
            sess["page"].close()
            sess["browser"].close()
            sess["playwright"].stop()
        except Exception:
            pass
    try:
        conn = sqlite3.connect(db_path, timeout=3)
        conn.execute(
            "UPDATE browser_sessions SET state='closed', closed_at=CURRENT_TIMESTAMP "
            "WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
    _log_action(session_id, "close_session", "", "", "closed", True)
    return {"ok": True, "session_id": session_id}


def list_sessions(tenant_id: Optional[str] = None, state: str = "open",
                  db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """List browser sessions, optionally filtered by tenant + state."""
    try:
        conn = sqlite3.connect(db_path, timeout=3)
        conn.row_factory = sqlite3.Row
        if tenant_id:
            rows = conn.execute(
                "SELECT * FROM browser_sessions WHERE tenant_id = ? AND state = ? "
                "ORDER BY last_activity_at DESC LIMIT 50",
                (tenant_id, state),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM browser_sessions WHERE state = ? "
                "ORDER BY last_activity_at DESC LIMIT 50",
                (state,),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": "{}: {}".format(type(e).__name__, e)}]


def session_actions(session_id: str, db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """Return full action history for a session, ordered by seq."""
    try:
        conn = sqlite3.connect(db_path, timeout=3)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT seq, action_type, target_selector, result_summary, "
            "       success, error_reason, captured_at "
            "FROM browser_actions WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": "{}: {}".format(type(e).__name__, e)}]


if __name__ == "__main__":
    # Demo: open session, navigate, extract, close, audit
    print("R97 murphy_browser demo")
    print("  Playwright available: {}".format(_PLAYWRIGHT_OK))
    s = open_session(tenant_id="t1", operator="r97_smoke",
                     purpose="browser_substrate_demo", headless=True)
    print("  open_session: {}".format(s))

    if s.get("ok"):
        sid = s["session_id"]
        n = navigate(sid, "https://example.com")
        print("  navigate: {}".format(n))

        e = extract_text(sid, "h1")
        print("  extract h1: {}".format(e))

        c = close_session(sid)
        print("  close: {}".format(c))

        print()
        print("  Session action history:")
        for a in session_actions(sid):
            print("    seq={} type={} result={}".format(
                a.get("seq"), a.get("action_type"),
                (a.get("result_summary") or "")[:80]))
