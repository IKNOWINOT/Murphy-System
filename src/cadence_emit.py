"""
BLOCK-A.4.1 — Cadence Emit Helper
=================================

WHAT THIS IS:
  Single function `emit_heartbeat()` that every cadence source calls to
  prove it's alive. Writes one row to cadence_pulse.pulse_ticks AND
  updates rolling state in murphy_registry.cadence_registry.

WHY:
  The 18 cadence sources cataloged in BLOCK-A.2.5 all currently show
  health_status='never_ticked' because no source has yet announced
  itself. This helper is the missing API.

DESIGN:
  - PUSH model: each source calls emit_heartbeat(source_name) itself.
    Murphy CTO recommends this over pull because (a) sources know their
    own state best, (b) async sources can't be polled cheaply, (c) only
    the source knows duration/success/error.

  - Telemetry never breaks the source: all writes wrapped in try/except,
    failures logged but do not propagate.

  - Reuses swarm_bus.publish (already in use by 8+ modules) when
    publish_to_bus=True. Keeps event spine consistent.

USAGE:

  # systemd .service ExecStartPost line:
  /opt/Murphy-System/venv/bin/python3 -c "from src.cadence_emit import emit_heartbeat; emit_heartbeat('murphy-watchdog.timer')"

  # In-code (Python):
  from src.cadence_emit import emit_heartbeat
  start = time.monotonic()
  try:
      do_work()
      emit_heartbeat('my_source.tick', duration_ms=int((time.monotonic()-start)*1000))
  except Exception as e:
      emit_heartbeat('my_source.tick', success=False, error_text=str(e))
      raise

DEPENDENCIES:
  - /var/lib/murphy-production/cadence_pulse.db (created by BLOCK-A.4.1 migration)
  - /var/lib/murphy-production/murphy_registry.db (cadence_registry from A.2.5)
  - Optional: src.swarm_bus (for publish_to_bus=True path)

LAST UPDATED: 2026-05-25 by Murphy/Inoni LLC (BLOCK-A.4.1)
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

PULSE_DB    = "/var/lib/murphy-production/cadence_pulse.db"
REGISTRY_DB = "/var/lib/murphy-production/murphy_registry.db"

log = logging.getLogger("murphy.cadence_emit")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_heartbeat(
    source_name: str,
    drift_ms: int = 0,
    duration_ms: int = 0,
    success: bool = True,
    error_text: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    publish_to_bus: bool = False,
) -> bool:
    """
    Record one heartbeat tick for a cadence source.

    Returns True if at least the pulse_ticks write succeeded.
    Never raises — telemetry must not break the source it measures.
    """
    ok_tick = False
    ok_state = False

    # Truncate long errors to keep rows small
    if error_text and len(error_text) > 500:
        error_text = error_text[:497] + "..."

    payload_str = json.dumps(payload or {}, default=str)
    ts = _now()
    success_int = 1 if success else 0

    # ── Write 1: append-only tick to cadence_pulse.db ─────────────────────
    try:
        c = sqlite3.connect(PULSE_DB, timeout=2)
        c.execute(
            "INSERT INTO pulse_ticks "
            "(source_name, ts, drift_ms, duration_ms, success, error_text, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (source_name, ts, drift_ms, duration_ms, success_int, error_text, payload_str),
        )
        c.commit()
        c.close()
        ok_tick = True
    except Exception as e:
        log.warning("emit_heartbeat tick write failed for %s: %s", source_name, e)

    # ── Write 2: update rolling state in cadence_registry ─────────────────
    try:
        c = sqlite3.connect(REGISTRY_DB, timeout=2)
        # Check the source exists (we want to know about orphans)
        row = c.execute(
            "SELECT id, consecutive_failures, total_ticks, total_failures "
            "FROM cadence_registry WHERE source_name = ?",
            (source_name,),
        ).fetchone()

        if row is None:
            log.warning(
                "emit_heartbeat: source '%s' not in cadence_registry — "
                "orphan tick recorded only",
                source_name,
            )
        else:
            cad_id, cur_cf, cur_tt, cur_tf = row
            new_cf = 0 if success else (cur_cf or 0) + 1
            new_tt = (cur_tt or 0) + 1
            new_tf = (cur_tf or 0) + (0 if success else 1)
            c.execute(
                "UPDATE cadence_registry SET "
                "  last_tick_at = ?, "
                "  last_drift_ms = ?, "
                "  last_duration_ms = ?, "
                "  last_success = ?, "
                "  last_error = ?, "
                "  consecutive_failures = ?, "
                "  total_ticks = ?, "
                "  total_failures = ?, "
                "  updated_at = ? "
                "WHERE id = ?",
                (ts, drift_ms, duration_ms, success_int, error_text,
                 new_cf, new_tt, new_tf, ts, cad_id),
            )
            c.commit()
            ok_state = True
        c.close()
    except Exception as e:
        log.warning("emit_heartbeat state write failed for %s: %s", source_name, e)

    # ── Optional Write 3: echo to swarm bus ───────────────────────────────
    if publish_to_bus:
        try:
            sys.path.insert(0, "/opt/Murphy-System")
            from src.swarm_bus import publish  # type: ignore
            publish(
                event_type="cadence.heartbeat",
                payload={
                    "source_name": source_name,
                    "ts": ts,
                    "drift_ms": drift_ms,
                    "duration_ms": duration_ms,
                    "success": success,
                    "error": error_text,
                    "extra": payload or {},
                },
            )
        except Exception as e:
            log.debug("emit_heartbeat bus publish failed for %s: %s", source_name, e)

    return ok_tick


# ── CLI entry point (for systemd ExecStartPost) ────────────────────────────
if __name__ == "__main__":
    """
    CLI:  python3 -m src.cadence_emit <source_name> [--drift_ms N] [--duration_ms N]
                                                    [--fail] [--error "msg"]
                                                    [--payload '{"k":"v"}']
                                                    [--publish-to-bus]
    """
    import argparse
    parser = argparse.ArgumentParser(description="Emit a cadence heartbeat tick")
    parser.add_argument("source_name", help="Matches cadence_registry.source_name")
    parser.add_argument("--drift_ms", type=int, default=0)
    parser.add_argument("--duration_ms", type=int, default=0)
    parser.add_argument("--fail", action="store_true",
                        help="Mark this tick as a failure")
    parser.add_argument("--error", default=None)
    parser.add_argument("--payload", default=None,
                        help="JSON object string for extra context")
    parser.add_argument("--publish-to-bus", action="store_true")
    args = parser.parse_args()

    payload_dict = None
    if args.payload:
        try:
            payload_dict = json.loads(args.payload)
        except Exception as e:
            print(f"WARN: payload not valid JSON: {e}", file=sys.stderr)

    ok = emit_heartbeat(
        source_name=args.source_name,
        drift_ms=args.drift_ms,
        duration_ms=args.duration_ms,
        success=not args.fail,
        error_text=args.error,
        payload=payload_dict,
        publish_to_bus=args.publish_to_bus,
    )
    print("ok" if ok else "fail")
    sys.exit(0 if ok else 1)
