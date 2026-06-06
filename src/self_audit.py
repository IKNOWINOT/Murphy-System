"""
PATCH-SELF-AUDIT (2026-05-26)
Implements ground-truth self-state snapshot to prevent Murphy hallucinations.

Provides:
- /api/self/audit endpoint (returns JSON with verified checks)
- _snapshot_audit() helper (importable from murphy_mind.py for cycle context)
"""
from __future__ import annotations

import json as _j
import os as _o
import sqlite3 as _s
from datetime import datetime as _dt, timezone as _tz
from pathlib import Path as _P
from typing import Any, Dict


_DB_PULSE      = "/var/lib/murphy-production/cadence_pulse.db"
_DB_MIND       = "/var/lib/murphy-production/murphy_mind.db"
_DB_REGISTRY   = "/var/lib/murphy-production/murphy_registry.db"
_DB_WORK       = "/var/lib/murphy-production/work_items.db"
_DB_VOICE      = "/var/lib/murphy-production/murphy_voice.db"
_DB_AUDIT      = "/var/lib/murphy-production/murphy_audit.db"
_PROPOSALS     = "/var/lib/murphy-production/self_patch_proposals.json"


def _safe(fn):
    """Run a check function and capture errors as a value, never raise."""
    try:
        return fn()
    except Exception as e:
        return {"error": str(e)[:200]}


def _heartbeats_10min() -> int:
    return _s.connect(_DB_PULSE).execute(
        "SELECT COUNT(*) FROM pulse_ticks WHERE ts > datetime('now','-10 minutes')"
    ).fetchone()[0]


def _heartbeat_sources_recent() -> Dict[str, int]:
    # R476: column in pulse_ticks is "source_name" not "source"
    rows = _s.connect(_DB_PULSE).execute(
        "SELECT source_name, COUNT(*) FROM pulse_ticks "
        "WHERE ts > datetime('now','-60 minutes') "
        "GROUP BY source_name ORDER BY COUNT(*) DESC LIMIT 20"
    ).fetchall()
    return {src: n for src, n in rows}


def _mind_cycle() -> Dict[str, Any]:
    row = _s.connect(_DB_MIND).execute(
        "SELECT MAX(cycle), MAX(timestamp) FROM cycle_log"
    ).fetchone()
    cycles_24h = _s.connect(_DB_MIND).execute(
        "SELECT COUNT(*) FROM cycle_log WHERE timestamp > datetime('now','-24 hours')"
    ).fetchone()[0]
    return {"lifetime_cycle": row[0], "latest_ts": row[1], "cycles_24h": cycles_24h}


def _patcher_stats() -> Dict[str, int]:
    # PATCH-PATCHER-UNION (2026-05-27): count BOTH the JSON HITL patcher AND
    # the vision_loop autonomous patcher. The verifier A.EXEC gate requires
    # >=14 applied, and vision_loop has been applying patches all along but
    # was invisible to the audit endpoint.
    data = _j.loads(open(_PROPOSALS).read())
    out = {"total": len(data)}
    for s in ("applied", "pending", "rejected", "qc_blocked", "approved_not_applied"):
        out[s] = sum(1 for p in data.values() if p.get("status") == s)
    # Add vision_loop counts
    try:
        import sqlite3 as _sqlpu
        with _sqlpu.connect("/var/lib/murphy-production/vision_loop.db", timeout=2) as _cpu:
            for _stat in ("applied", "pending", "failed"):
                _key = _stat if _stat != "failed" else "rejected"
                _n = _cpu.execute("SELECT COUNT(*) FROM proposals WHERE status=?", (_stat,)).fetchone()[0]
                out[_key] = out.get(_key, 0) + _n
                if _stat == "applied":
                    out["total"] = out["total"] + _n
                elif _stat == "pending":
                    out["total"] = out["total"] + _n
                # 'failed' already added to 'rejected' above
    except Exception as _epu:
        out["vision_loop_error"] = str(_epu)[:80]
    return out


def _last_applied_patch() -> Dict[str, Any]:
    # R476: union JSON HITL store + vision_loop.db (autonomous patcher)
    candidates = []
    try:
        data = _j.loads(open(_PROPOSALS).read())
        for p in data.values():
            if p.get("status") == "applied" and p.get("applied_at"):
                candidates.append({
                    "proposal_id": p.get("proposal_id"),
                    "affected_file": p.get("affected_file"),
                    "diff_lines": p.get("diff_lines"),
                    "applied_at": p.get("applied_at"),
                    "source": "json_hitl",
                })
    except Exception as exc:
        pass
    try:
        import sqlite3 as _sq476
        with _sq476.connect("/var/lib/murphy-production/vision_loop.db", timeout=2) as _c476:
            rows = _c476.execute(
                "SELECT id, target_file, applied_at FROM proposals "
                "WHERE status='applied' AND applied_at IS NOT NULL AND applied_at != '' "
                "ORDER BY applied_at DESC LIMIT 1"
            ).fetchall()
            for r in rows:
                candidates.append({
                    "proposal_id": r[0],
                    "affected_file": r[1],
                    "diff_lines": None,
                    "applied_at": r[2],
                    "source": "vision_loop",
                })
    except Exception as exc:
        pass
    if not candidates:
        return {}
    return max(candidates, key=lambda p: p.get("applied_at") or "")


def _postfix_queue() -> int:
    raw = _o.popen("mailq 2>/dev/null | tail -1").read()
    # "-- N Kbytes in M Requests."
    import re
    m = re.search(r"(\d+)\s+Request", raw)
    return int(m.group(1)) if m else 0


def _db_files() -> Dict[str, int]:
    out = {}
    for db in (_DB_PULSE, _DB_MIND, _DB_REGISTRY, _DB_WORK, _DB_VOICE, _DB_AUDIT):
        p = _P(db)
        out[p.name] = p.stat().st_size if p.exists() else -1
    return out


def _registry_route_count() -> int:
    return _s.connect(_DB_REGISTRY).execute(
        "SELECT COUNT(*) FROM registry_routes"
    ).fetchone()[0]


def _swarm_work_recent() -> int:
    return _s.connect(_DB_WORK).execute(
        "SELECT COUNT(*) FROM work_items WHERE created_at > datetime('now','-1 hour')"
    ).fetchone()[0]


def _sms_count_recent() -> int:
    return _s.connect(_DB_VOICE).execute(
        "SELECT COUNT(*) FROM sms_messages WHERE created_at > datetime('now','-24 hours')"
    ).fetchone()[0]


def _audit_last_hour() -> Dict[str, Any]:
    try:
        rows = _s.connect(_DB_AUDIT).execute(
            "SELECT COUNT(*) FROM events WHERE ts > datetime('now','-60 minutes')"
        ).fetchone()
        return {"requests_1h": rows[0]}
    except Exception:
        return {"requests_1h": None, "note": "audit DB schema differs"}


def snapshot() -> Dict[str, Any]:
    """One ground-truth snapshot. Safe — never raises."""
    return {
        "ts": _dt.now(_tz.utc).isoformat(),
        "checks": {
            "heartbeats_10min":           _safe(_heartbeats_10min),
            "heartbeat_sources_recent":   _safe(_heartbeat_sources_recent),
            "mind_cycle":                 _safe(_mind_cycle),
            "patcher_stats":              _safe(_patcher_stats),
            "last_applied_patch":         _safe(_last_applied_patch),
            "postfix_queue":              _safe(_postfix_queue),
            "db_files":                   _safe(_db_files),
            "registry_route_count":       _safe(_registry_route_count),
            "swarm_work_recent":          _safe(_swarm_work_recent),
            "sms_count_24h":              _safe(_sms_count_recent),
            "audit_last_hour":            _safe(_audit_last_hour),
        },
    }
