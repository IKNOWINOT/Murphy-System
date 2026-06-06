"""
gate_auditor.py — Populates registry_routes gate columns by actually
checking each route's 5 gates (a:code / b:wired / c:deps / d:e2e / e:visible).

LOCKED 2026-05-27: stub version. Implements gate_b_wired (route reachable
via HTTP 200/204/404 = wired; 502/503/504/timeout = not wired) ONLY.
Gates a/c/d/e left for future work — see CORRECTED BELIEFS #1 in memory.

Usage:
  python3 -m src.gate_auditor              # audit all routes
  python3 -m src.gate_auditor --path /api/health   # audit one
"""
from __future__ import annotations
import sqlite3, time, sys, os
from urllib import request, error
from datetime import datetime, timezone

REG_DB = "/var/lib/murphy-production/murphy_registry.db"
APP = "http://127.0.0.1:8000"
KEY = os.environ.get("MURPHY_AUTH_KEY", "")
TIMEOUT = 60.0  # PATCH-GATE-AUDITOR-TIMEOUT 2026-05-27: swarm-call scale per locked rule O
PROBE_DELAY = 0.5  # PATCH-GATE-AUDITOR-RATELIMIT 2026-05-27: avoid overloading monolith during audit_all

def _probe(path: str, method: str = "GET") -> tuple[int, float]:
    """Return (status_code, latency_ms). 0 = connection failed."""
    url = APP + path
    t0 = time.monotonic()
    try:
        req = request.Request(url, method=method)
        if KEY:
            req.add_header("X-API-Key", KEY)
        with request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, (time.monotonic() - t0) * 1000
    except error.HTTPError as e:
        return e.code, (time.monotonic() - t0) * 1000
    except Exception:
        return 0, (time.monotonic() - t0) * 1000

def _gate_b(status: int) -> int:
    """gate_b_wired = 1 (green) if route responded at all (even with 4xx).
    0 = red (5xx, timeout, connection refused)."""
    if status == 0: return 0          # connection failed
    if 500 <= status < 600: return 0  # server-side fail
    return 1                          # 2xx / 3xx / 4xx all = wired

def audit_all(limit: int = None):
    con = sqlite3.connect(REG_DB, timeout=5)
    rows = con.execute(
        "SELECT id, path, method FROM registry_routes "
        "WHERE archived IS NOT 1 "
        + (f"LIMIT {int(limit)}" if limit else "")
    ).fetchall()
    print(f"auditing {len(rows)} routes...")
    now = datetime.now(timezone.utc).isoformat()
    green = red = 0
    for rid, path, method in rows:
        if not path.startswith("/"):
            continue
        status, ms = _probe(path, method or "GET")
        wired = _gate_b(status)
        green += wired; red += (1 - wired)
        time.sleep(PROBE_DELAY)  # PATCH-GATE-AUDITOR-RATELIMIT
        con.execute(
            "UPDATE registry_routes SET gate_b_wired=?, last_status=?, "
            "last_latency_ms=?, last_status_at=?, last_audited_at=? WHERE id=?",
            (wired, status, int(ms), now, now, rid),
        )
    con.commit(); con.close()
    print(f"done. wired={green} not_wired={red}")
    return green, red

if __name__ == "__main__":
    if "--path" in sys.argv:
        p = sys.argv[sys.argv.index("--path") + 1]
        s, ms = _probe(p)
        print(f"{p} → {s} in {ms:.0f}ms, gate_b={_gate_b(s)}")
    elif "--limit" in sys.argv:
        n = int(sys.argv[sys.argv.index("--limit") + 1])
        audit_all(limit=n)
    else:
        audit_all()
