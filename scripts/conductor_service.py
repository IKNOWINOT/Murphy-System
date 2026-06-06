#!/usr/bin/env python3
"""R517+R518 — Conductor HTTP service with persistence."""
import os, sys, json, sqlite3, time
sys.path.insert(0, "/opt/Murphy-System/scripts")
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import conductor as _c

DB_PATH = "/var/lib/murphy-production/state/conductor_jobs.db"
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def _db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs(
            job_id TEXT PRIMARY KEY,
            ask TEXT NOT NULL,
            operator_id TEXT,
            psm_seq INTEGER,
            concepts TEXT,
            grep_hits INTEGER,
            plan TEXT,
            endpoint TEXT,
            result TEXT,
            error TEXT,
            created_at REAL,
            elapsed_sec REAL
        )
    """)
    return conn


def _save(job):
    conn = _db()
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO jobs(job_id, ask, operator_id, psm_seq, concepts,
                grep_hits, plan, endpoint, result, error, created_at, elapsed_sec)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job.job_id, job.ask, job.operator_id, job.psm_seq,
            json.dumps(job.keywords[:5]),
            len(job.grep_context),
            (job.murphy_plan or "")[:2000],
            json.dumps(job.execution_endpoint) if job.execution_endpoint else None,
            json.dumps(job.execution_result, default=str)[:4000] if job.execution_result else None,
            job.error,
            job.started_at,
            time.time() - job.started_at,
        ))
    conn.close()


app = FastAPI(title="Murphy Conductor", version="0.0.4")


class ConductReq(BaseModel):
    ask: str
    operator_id: Optional[str] = "corey@founder"


def _row_to_dict(r):
    d = dict(r)
    for k in ("concepts", "endpoint", "result"):
        if d.get(k):
            try: d[k] = json.loads(d[k])
            except: pass
    return d


@app.get("/health")
def health():
    return {"status": "ok", "service": "conductor", "version": "0.0.4"}


@app.post("/conduct")
def conduct(req: ConductReq):
    if not req.ask or len(req.ask) < 3:
        raise HTTPException(400, "ask too short")
    job = _c.conduct(req.ask, operator_id=req.operator_id)
    try:
        _save(job)
    except Exception as e:
        # never fail the response because of persistence
        pass
    return {
        "job_id": job.job_id, "ask": job.ask,
        "psm_seq": job.psm_seq,
        "concepts": job.keywords[:5],
        "grep_hits": len(job.grep_context),
        "plan": (job.murphy_plan or "")[:800],
        "endpoint": job.execution_endpoint,
        "result": job.execution_result,
        "error": job.error,
    }


@app.get("/conduct/job/{job_id}")
def get_job(job_id: str):
    conn = _db()
    r = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    conn.close()
    if not r:
        raise HTTPException(404, "job_not_found")
    return _row_to_dict(r)


@app.get("/conduct/jobs")
def list_jobs(limit: int = 20):
    conn = _db()
    rows = conn.execute(
        "SELECT job_id, ask, operator_id, psm_seq, grep_hits, error, created_at, elapsed_sec "
        "FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return {"count": len(rows), "jobs": [dict(r) for r in rows]}




class ConductReplyReq(BaseModel):
    message: str
    operator_id: Optional[str] = "corey@founder"


@app.post("/conduct-and-reply")
def conduct_and_reply(req: ConductReplyReq):
    """R23: unified bot interface.
    1) Ask Murphy chat-v2 for the user-facing reply (persona-aware)
    2) Run conductor on the same message (plan + execute or HITL-gate)
    3) Return both — chat surface shows the reply, debug pane shows the plan."""
    if not req.message or len(req.message) < 2:
        raise HTTPException(400, "message too short")
    # 1. Get Murphy's natural-language reply
    try:
        chat_resp = _c.ask_murphy(req.message)
        reply = chat_resp.get("reply", "")
    except Exception as e:
        reply = f"(chat-v2 unreachable: {e})"
    # 2. Run conductor in parallel-ish (sequential ok for now)
    job = _c.conduct(req.message, operator_id=req.operator_id)
    try:
        _save(job)
    except Exception:
        pass
    return {
        "reply": reply,
        "conductor": {
            "job_id": job.job_id,
            "psm_seq": job.psm_seq,
            "concepts": job.keywords[:5],
            "plan": (job.murphy_plan or "")[:400],
            "endpoint": job.execution_endpoint,
            "executed_result": job.execution_result,
            "error": job.error,
        }
    }



@app.get("/conduct/metrics")
def metrics():
    conn = _db()
    rows = conn.execute(
        "SELECT psm_seq, error, elapsed_sec FROM jobs"
    ).fetchall()
    conn.close()
    total = len(rows)
    success = sum(1 for r in rows if r["error"] is None)
    elapsed = sorted([r["elapsed_sec"] for r in rows if r["elapsed_sec"]])
    p50 = elapsed[len(elapsed)//2] if elapsed else None
    p95 = elapsed[int(len(elapsed)*0.95)] if elapsed else None
    return {
        "total_jobs": total,
        "success_rate": round(success/total, 3) if total else None,
        "latency_p50_sec": round(p50, 2) if p50 else None,
        "latency_p95_sec": round(p95, 2) if p95 else None,
        "rate_limited": sum(1 for r in rows if r["error"] and "429" in r["error"]),
        "psm_failed": sum(1 for r in rows if r["error"] and "psm_failed" in r["error"]),
        "execute_failed": sum(1 for r in rows if r["error"] and "execute_stage" in r["error"]),
    }



@app.get("/watchdog/events")
def watchdog_events(limit: int = 20):
    import sqlite3
    try:
        c = sqlite3.connect("/var/lib/murphy-production/state/watchdog_events.db", timeout=5)
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT * FROM watchdog_events ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        c.close()
        return {"count": len(rows), "events": [dict(r) for r in rows]}
    except Exception as e:
        return {"count": 0, "events": [], "note": str(e)}



@app.get("/vendor/list")
def vendor_list():
    import sys
    sys.path.insert(0, "/opt/Murphy-System/src")
    try:
        import vendor_protection as vp
        rows = vp.list_protected()
        return {"count": len(rows), "vendors": rows}
    except Exception as e:
        return {"count": 0, "vendors": [], "error": str(e)}

@app.get("/vendor/check")
def vendor_check(addr: str):
    import sys
    sys.path.insert(0, "/opt/Murphy-System/src")
    try:
        import vendor_protection as vp
        return {"addr": addr, "protected": vp.is_protected(addr)}
    except Exception as e:
        return {"addr": addr, "protected": None, "error": str(e)}



@app.get("/journey/status")
def journey_status():
    """R578: latest journey verifier result + last 24h trend."""
    import sqlite3, json
    try:
        c = sqlite3.connect("/var/lib/murphy-production/journey_history.db", timeout=5)
        latest = c.execute("SELECT payload FROM journey_runs ORDER BY ts DESC LIMIT 1").fetchone()
        if not latest:
            return {"ok": False, "error": "no journey runs yet"}
        latest_obj = json.loads(latest[0])
        # 24h trend
        trend = c.execute("""SELECT count(*), avg(passed*1.0/total)
                             FROM journey_runs
                             WHERE ts > datetime('now','-24 hours')""").fetchone()
        c.close()
        return {
            "ok": True,
            "latest": latest_obj,
            "trend_24h": {
                "runs": trend[0],
                "avg_pass_rate": round((trend[1] or 0) * 100, 1),
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8091, log_level="info")
