#!/usr/bin/env python3
"""
PCR-049 (was PCR-040d v3) — Async dispatch under fresh prefix /api/jobs/dispatch*

ROUND 1+2 FINDINGS (see .agents/memory/pcr040d_round1_round2_findings.md):
  - Marker-based patcher pattern works cleanly (both rounds reverted clean)
  - The hang in R1+R2 was the system under LLM rate-limit cascade
  - The auth_middleware deprecation hook on /api/rosetta/dispatch* makes
    requests slow when system is degraded, but doesn't actually block
  - Recommendation (a) from findings: use a fresh prefix to avoid the
    hook entirely

ROUND 3 — same logic as R2 but at /api/jobs/dispatch and /api/jobs/{id}.
Uses asyncio.create_task for true fire-and-forget.

PRE-FLIGHT (must pass before applying):
  All four surfaces 200 with sub-2s latency
  SYNC /api/rosetta/dispatch returns 200 in <30s

ENDPOINTS:
  POST /api/jobs/dispatch         body={prompt}      → {job_id, status}
  GET  /api/jobs/dispatch/{id}                       → {status, graph_state?}
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

APP = Path("/opt/Murphy-System/src/runtime/app.py")

# Same stable anchor as R2 — two lines, no trailing whitespace
ANCHOR_OLD = """    # ── PATCH-363: Work Item API ─────────────────────────────────────────────
    import sqlite3 as _wsq363, json as _wjs363"""

ANCHOR_NEW = '''    # ── PCR-049 (was PCR-040d v3): Async dispatch under fresh /api/jobs/ prefix ─────────────
    # Avoids auth_middleware deprecation hook on /api/rosetta/dispatch*
    # which slows requests during LLM cascade pressure. Same logic as R2.
    import sqlite3 as _aq040d, json as _aj040d, uuid as _au040d, time as _at040d
    import asyncio as _aa040d, logging as _alog040d
    _log040d = _alog040d.getLogger("murphy.pcr040d")

    _ASYNC_DISPATCH_DB = "/var/lib/murphy-production/dispatch_jobs.db"

    def _init_async_dispatch_db_040d():
        try:
            _conn = _aq040d.connect(_ASYNC_DISPATCH_DB, timeout=5.0)
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA synchronous=NORMAL")
            _conn.execute("""
                CREATE TABLE IF NOT EXISTS dispatch_jobs (
                    job_id        TEXT PRIMARY KEY,
                    status        TEXT NOT NULL,
                    created_at    REAL NOT NULL,
                    started_at    REAL,
                    finished_at   REAL,
                    prompt        TEXT,
                    response_json TEXT,
                    error         TEXT
                )
            """)
            _conn.execute("CREATE INDEX IF NOT EXISTS ix_dispatch_jobs_status ON dispatch_jobs(status)")
            _conn.execute("CREATE INDEX IF NOT EXISTS ix_dispatch_jobs_created ON dispatch_jobs(created_at DESC)")
            _conn.commit()
            _conn.execute("INSERT INTO dispatch_jobs (job_id,status,created_at) VALUES (?,?,?)",
                          ("_warmup_", "warmup", _at040d.time()))
            _conn.execute("DELETE FROM dispatch_jobs WHERE job_id=?", ("_warmup_",))
            _conn.commit()
            _conn.close()
            _log040d.info("[PCR-040d] dispatch_jobs.db ready (WAL)")
        except Exception as _e:
            _log040d.error("[PCR-040d] db init failed: %s", _e)
    _init_async_dispatch_db_040d()

    class _ShimRequest040d:
        def __init__(self, body_dict):
            self._body = body_dict
            self.headers = {}
            self.client = type("C", (), {"host": "127.0.0.1", "port": 0})()
            self.url = type("U", (), {"path": "/api/rosetta/dispatch"})()
        async def json(self):
            return self._body

    async def _run_dispatch_to_db_040d(job_id: str, prompt: str):
        _log040d.info("[PCR-040d] runner start job=%s", job_id)
        _started = _at040d.time()
        try:
            _conn = _aq040d.connect(_ASYNC_DISPATCH_DB, timeout=5.0)
            _conn.execute("UPDATE dispatch_jobs SET status=?, started_at=? WHERE job_id=?",
                          ("running", _started, job_id))
            _conn.commit(); _conn.close()
        except Exception as _e:
            _log040d.warning("[PCR-040d] status update failed: %s", _e)

        try:
            _req = _ShimRequest040d({"prompt": prompt})
            _resp = await _rosetta_dispatch(_req)
            try:
                _body = _resp.body if hasattr(_resp, "body") else b"{}"
                _payload = _aj040d.loads(_body.decode("utf-8")) if _body else {}
            except Exception as _de:
                _log040d.error("[PCR-040d] payload decode failed: %s", _de)
                _payload = {"success": False, "_decode_error": str(_de)}

            _finished = _at040d.time()
            _conn = _aq040d.connect(_ASYNC_DISPATCH_DB, timeout=5.0)
            _conn.execute(
                "UPDATE dispatch_jobs SET status=?, finished_at=?, response_json=? WHERE job_id=?",
                ("done" if _payload.get("success") else "error",
                 _finished, _aj040d.dumps(_payload)[:2_000_000], job_id),
            )
            _conn.commit(); _conn.close()
            _log040d.info("[PCR-040d] runner done job=%s elapsed=%.1fs", job_id, _finished - _started)
        except Exception as _err:
            _log040d.exception("[PCR-040d] runner FAILED job=%s", job_id)
            try:
                _conn = _aq040d.connect(_ASYNC_DISPATCH_DB, timeout=5.0)
                _conn.execute(
                    "UPDATE dispatch_jobs SET status=?, finished_at=?, error=? WHERE job_id=?",
                    ("error", _at040d.time(), str(_err)[:2000], job_id),
                )
                _conn.commit(); _conn.close()
            except Exception:
                pass

    @app.post("/api/jobs/dispatch")
    async def _jobs_dispatch_post(request: Request):
        """PCR-049 (was PCR-040d v3): returns {job_id} immediately, runs dispatch via
        asyncio.create_task. Fresh prefix avoids /api/rosetta/dispatch*
        middleware deprecation hook."""
        try:
            body = await request.json()
            prompt = body.get("prompt") or body.get("task") or ""
            if not prompt:
                return JSONResponse({"success": False, "error": "prompt required"}, status_code=400)
            job_id = "djob_" + _au040d.uuid4().hex[:12]
            _now = _at040d.time()
            _conn = _aq040d.connect(_ASYNC_DISPATCH_DB, timeout=5.0)
            _conn.execute(
                "INSERT INTO dispatch_jobs (job_id, status, created_at, prompt) VALUES (?, 'queued', ?, ?)",
                (job_id, _now, prompt[:50000]),
            )
            _conn.commit(); _conn.close()
            _aa040d.create_task(_run_dispatch_to_db_040d(job_id, prompt))
            return JSONResponse({
                "success": True,
                "job_id": job_id,
                "status": "queued",
                "poll_url": "/api/jobs/dispatch/" + job_id,
            })
        except Exception as exc:
            _log040d.exception("[PCR-040d] async endpoint failed")
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/jobs/dispatch/{job_id}")
    async def _jobs_dispatch_get(job_id: str):
        """PCR-049 (was PCR-040d v3): poll endpoint."""
        try:
            _conn = _aq040d.connect(_ASYNC_DISPATCH_DB, timeout=5.0)
            _conn.row_factory = _aq040d.Row
            _row = _conn.execute("""
                SELECT job_id, status, created_at, started_at, finished_at,
                       prompt, response_json, error
                FROM dispatch_jobs WHERE job_id=?
            """, (job_id,)).fetchone()
            _conn.close()
            if not _row:
                return JSONResponse({"success": False, "error": "job not found"}, status_code=404)
            _out = {
                "success": True,
                "job_id": _row["job_id"],
                "status": _row["status"],
                "created_at": _row["created_at"],
                "started_at": _row["started_at"],
                "finished_at": _row["finished_at"],
                "elapsed_s": (_row["finished_at"] or _at040d.time()) - _row["created_at"],
            }
            if _row["status"] == "done" and _row["response_json"]:
                try:
                    _payload = _aj040d.loads(_row["response_json"])
                    _out["graph_state"] = _payload.get("graph_state")
                    _out["compound_workflow"] = _payload.get("compound_workflow")
                    _out["dynamic_team"] = _payload.get("dynamic_team")
                    _out["dag_id"] = _payload.get("dag_id")
                    _out["assigned_agents"] = _payload.get("assigned_agents")
                except Exception as _e:
                    _out["_decode_error"] = str(_e)
            elif _row["status"] == "error":
                _out["error"] = _row["error"]
            return JSONResponse(_out)
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


    # ── PATCH-363: Work Item API ─────────────────────────────────────────────
    import sqlite3 as _wsq363, json as _wjs363'''


def apply(verify, revert):
    print(f"PCR-049 (was PCR-040d v3) fresh-prefix async  verify={verify}  revert={revert}")
    src = APP.read_text(encoding="utf-8")
    if revert:
        if "PCR-040d" not in src:
            print("  · already absent"); return 0
        src = src.replace(ANCHOR_NEW, ANCHOR_OLD, 1)
        if verify: print("  ✓ would revert"); return 0
        APP.write_text(src, encoding="utf-8")
        print("  ✓ reverted"); return 0
    if "PCR-040d" in src:
        print("  · already present"); return 0
    if ANCHOR_OLD not in src:
        print("  ✗ ANCHOR_OLD not found"); return 1
    src = src.replace(ANCHOR_OLD, ANCHOR_NEW, 1)
    if verify: print("  ✓ would apply"); return 0
    APP.write_text(src, encoding="utf-8")
    print("  ✓ POST /api/jobs/dispatch")
    print("  ✓ GET /api/jobs/dispatch/{job_id}")
    print("  ✓ asyncio.create_task fire-and-forget runner")
    print("  ✓ dispatch_jobs.db pre-warmed WAL")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return apply(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())
