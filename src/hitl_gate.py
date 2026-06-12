"""
Ship 31an.HITL — HITL gate for outbound replies.

Single source of truth: /var/lib/murphy-production/hitl_mode.json
Default: "off_for_email" (founder request 2026-06-12).
"""
from __future__ import annotations
import json, os, threading
from typing import Literal

HitlMode = Literal["off_for_email", "on", "off"]
DEFAULT_MODE: HitlMode = "off_for_email"
_STATE_PATH = "/var/lib/murphy-production/hitl_mode.json"
_LOCK = threading.Lock()

# Allowed action types that the "off_for_email" mode auto-sends.
# Everything else stays HITL-gated even in this mode.
EMAIL_AUTO_ACTIONS = {
    "stranger_responder",
    "auto_responder",
    "inbound_email_reply",
    "drill_rosetta_reply",
}


def _read_state() -> dict:
    try:
        with open(_STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {"mode": DEFAULT_MODE, "set_by": "default", "set_at": ""}


def _write_state(state: dict) -> None:
    os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
    tmp = _STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, _STATE_PATH)


def get_mode() -> HitlMode:
    """Current HITL mode. Defaults to off_for_email if state missing."""
    s = _read_state()
    m = s.get("mode", DEFAULT_MODE)
    return m if m in ("off_for_email", "on", "off") else DEFAULT_MODE


def set_mode(mode: HitlMode, set_by: str = "system") -> dict:
    """Set the HITL mode. Returns the new state."""
    if mode not in ("off_for_email", "on", "off"):
        raise ValueError(f"invalid mode: {mode}")
    from datetime import datetime, timezone
    with _LOCK:
        state = {
            "mode": mode,
            "set_by": set_by,
            "set_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_state(state)
    return state


def should_auto_send(action_type: str) -> bool:
    """Should this outbound action skip HITL and auto-send?

    Rules:
      mode == "off"            → always auto-send
      mode == "off_for_email"  → auto-send if action_type in EMAIL_AUTO_ACTIONS
      mode == "on"             → never auto-send (everything HITL)
    """
    mode = get_mode()
    if mode == "off":
        return True
    if mode == "on":
        return False
    # off_for_email
    return (action_type or "").lower() in EMAIL_AUTO_ACTIONS


def describe() -> dict:
    """Full state + counts for the admin UI."""
    s = _read_state()
    return {
        "mode": s.get("mode", DEFAULT_MODE),
        "set_by": s.get("set_by", "default"),
        "set_at": s.get("set_at", ""),
        "auto_actions_when_off_for_email": sorted(EMAIL_AUTO_ACTIONS),
        "state_file": _STATE_PATH,
    }
