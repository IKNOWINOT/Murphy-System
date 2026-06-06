"""Caps C.4 + C.5 + C.6 + C.7 — Browserbase-style browser control.

Wraps Murphy's existing `murphy_browser` module (sync Playwright +
session DB) with an active-session model that matches Base44's
Browserbase tool shape (no session_id arg per call — uses the
currently-open session).

Surfaces:
  C.4   browserbase_navigate(url)        — go to URL in active session
  C.4s  browserbase_screenshot()         — PNG of current page
  C.5   browserbase_click(selector)      — click element by CSS
  C.6   browserbase_type(text, selector) — type into focused / selector
  C.7   browserbase_get_content(selector=None)
                                         — full page text or element text
  bonus browserbase_get_session()        — status + URL of active session
  bonus browserbase_stop_session()       — close and clear

Active session model:
  Module-global single session per process. First navigate() auto-opens
  if none exists. stop_session clears. Matches Base44's stateful model.

Screenshots:
  PNG bytes uploaded via A.7 upload_file → public URL returned.
"""
from __future__ import annotations
import base64
import logging
import threading
import time
from typing import Any, Dict, Optional

import murphy_browser as _mb
from .cap_a7_upload_file import upload_file as _upload_file

log = logging.getLogger(__name__)

_ACTIVE: Dict[str, Any] = {"session_id": None, "opened_at": None}
_LOCK = threading.Lock()


def _ensure_session(purpose: str = "superagent_browser") -> str:
    """Return active session_id, opening one if needed."""
    with _LOCK:
        sid = _ACTIVE["session_id"]
        if sid and sid in _mb._SESSIONS:
            return sid
        # Open new
        s = _mb.open_session(
            tenant_id="superagent",
            operator="superagent",
            purpose=purpose,
            headless=True,
        )
        if not s.get("ok"):
            raise RuntimeError(f"open_session failed: {s.get('reason')}")
        _ACTIVE["session_id"] = s["session_id"]
        _ACTIVE["opened_at"] = time.time()
        return s["session_id"]


def _page(sid: str):
    """Get the live Playwright Page object."""
    sess = _mb._SESSIONS.get(sid)
    if not sess or sess.get("stub"):
        return None
    return sess.get("page")


# ── C.4 navigate ──────────────────────────────────────────────────────────

def browserbase_navigate(url: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "url": url, "error": None}
    try:
        if not url or not url.strip():
            out["error"] = "empty url"; return out
        if not url.startswith(("http://", "https://")):
            out["error"] = "url must be http(s)://"; return out
        sid = _ensure_session()
        r = _mb.navigate(sid, url)
        if not r.get("ok"):
            out["error"] = f"navigate failed: {r.get('reason')}"
            return out
        out["session_id"] = sid
        out["title"] = r.get("title")
        out["current_url"] = r.get("current_url")
        out["engine"] = r.get("engine")
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── C.4s screenshot ───────────────────────────────────────────────────────

def browserbase_screenshot(*, full_page: bool = False,
                           upload: bool = True) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "error": None}
    try:
        sid = _ACTIVE["session_id"]
        if not sid:
            out["error"] = "no active session (navigate first)"; return out
        page = _page(sid)
        if not page:
            out["error"] = "session is stub mode (no real Playwright)"; return out
        png_bytes = page.screenshot(full_page=bool(full_page))
        out["session_id"] = sid
        out["bytes"] = len(png_bytes)
        out["full_page"] = full_page

        if upload:
            # Write to temp file then A.7 upload
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                tf.write(png_bytes)
                tmp_path = tf.name
            try:
                up = _upload_file(file_path=tmp_path)
                if up.get("ok"):
                    out["url"] = up.get("file_url") or up.get("url")
                else:
                    out["upload_error"] = up.get("error")
            finally:
                try: os.unlink(tmp_path)
                except Exception: pass
        else:
            out["b64"] = base64.b64encode(png_bytes).decode()
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── C.5 click ─────────────────────────────────────────────────────────────

def browserbase_click(selector: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "selector": selector, "error": None}
    try:
        if not selector or not selector.strip():
            out["error"] = "empty selector"; return out
        sid = _ACTIVE["session_id"]
        if not sid:
            out["error"] = "no active session (navigate first)"; return out
        r = _mb.click(sid, selector)
        if not r.get("ok"):
            out["error"] = f"click failed: {r.get('reason')}"
            return out
        out["session_id"] = sid
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── C.6 type ──────────────────────────────────────────────────────────────

def browserbase_type(text: str, selector: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "error": None}
    try:
        if text is None:
            out["error"] = "text is None"; return out
        sid = _ACTIVE["session_id"]
        if not sid:
            out["error"] = "no active session (navigate first)"; return out
        page = _page(sid)
        if not page:
            out["error"] = "session is stub mode"; return out
        if selector:
            # Use murphy_browser.fill for selector-targeted typing
            r = _mb.fill(sid, selector, text)
            if not r.get("ok"):
                out["error"] = f"fill failed: {r.get('reason')}"
                return out
        else:
            # Type into whatever is focused
            page.keyboard.type(text)
        out["session_id"] = sid
        out["chars_typed"] = len(text)
        out["selector"] = selector
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── C.7 get_content ───────────────────────────────────────────────────────

def browserbase_get_content(selector: Optional[str] = None,
                            *, max_chars: int = 50_000) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "error": None}
    try:
        sid = _ACTIVE["session_id"]
        if not sid:
            out["error"] = "no active session (navigate first)"; return out
        if selector:
            r = _mb.extract_text(sid, selector)
            if not r.get("ok"):
                out["error"] = f"extract failed: {r.get('reason')}"
                return out
            text = r.get("text", "")
        else:
            page = _page(sid)
            if not page:
                out["error"] = "session is stub mode"; return out
            text = page.locator("body").inner_text(timeout=5000)
        truncated = False
        if len(text) > max_chars:
            text = text[:max_chars]
            truncated = True
        out["session_id"] = sid
        out["selector"] = selector or "body"
        out["text"] = text
        out["chars"] = len(text)
        out["truncated"] = truncated
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── session lifecycle bonuses ─────────────────────────────────────────────

def browserbase_get_session() -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": True}
    sid = _ACTIVE["session_id"]
    if not sid:
        out["active"] = False
        return out
    out["active"] = sid in _mb._SESSIONS
    out["session_id"] = sid
    out["opened_at"] = _ACTIVE.get("opened_at")
    if out["active"]:
        page = _page(sid)
        if page:
            try:
                out["current_url"] = page.url
                out["title"] = page.title()
            except Exception:
                pass
    return out


def browserbase_stop_session() -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "error": None}
    try:
        sid = _ACTIVE["session_id"]
        if not sid:
            out["ok"] = True; out["was_active"] = False
            return out
        try:
            _mb.close_session(sid)
        except Exception as e:
            out["close_warning"] = f"{type(e).__name__}: {e}"
        _ACTIVE["session_id"] = None
        _ACTIVE["opened_at"] = None
        out["was_active"] = True
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── Executor wrappers ─────────────────────────────────────────────────────

def execute_browserbase_navigate(**kwargs) -> Dict[str, Any]:
    return browserbase_navigate(url=kwargs.get("url", ""))

def execute_browserbase_screenshot(**kwargs) -> Dict[str, Any]:
    return browserbase_screenshot(
        full_page=bool(kwargs.get("full_page", False)),
        upload=bool(kwargs.get("upload", True)),
    )

def execute_browserbase_click(**kwargs) -> Dict[str, Any]:
    return browserbase_click(selector=kwargs.get("selector", ""))

def execute_browserbase_type(**kwargs) -> Dict[str, Any]:
    return browserbase_type(
        text=kwargs.get("text", ""),
        selector=kwargs.get("selector"),
    )

def execute_browserbase_get_content(**kwargs) -> Dict[str, Any]:
    return browserbase_get_content(
        selector=kwargs.get("selector"),
        max_chars=int(kwargs.get("max_chars", 50_000)),
    )

def execute_browserbase_get_session(**kwargs) -> Dict[str, Any]:
    return browserbase_get_session()

def execute_browserbase_stop_session(**kwargs) -> Dict[str, Any]:
    return browserbase_stop_session()
