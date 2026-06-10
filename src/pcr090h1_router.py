"""PCR-090h.1 — HTTP surface for the outbound compliance gate.

Endpoints:
  POST /api/compliance/check         — run the gate against ad-hoc content
  GET  /api/compliance/runs/{q_id}   — audit history for a queue row
  GET  /api/compliance/stats         — 30-day aggregate

Pre-send integration is via the gate module's run_gate() — outbound queue
handlers can call it directly inside their /approve flow.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pcr090h1_compliance_gate import run_gate, get_runs_for_queue, get_aggregate_stats

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


class CheckRequest(BaseModel):
    queue_id: Optional[str] = None
    to_addresses: List[str]
    subject: str = ""
    body: str
    metadata: Optional[Dict[str, Any]] = None


@router.post("/check")
async def check(req: CheckRequest):
    """Run gate against ad-hoc content (queue_id auto-assigned if absent)."""
    import uuid as _u
    qid = req.queue_id or f"adhoc_{_u.uuid4().hex[:12]}"
    return run_gate(
        queue_id=qid,
        to_addresses=req.to_addresses,
        subject=req.subject,
        body=req.body,
        metadata=req.metadata or {},
    )


@router.get("/runs/{queue_id}")
async def runs_for_queue(queue_id: str):
    """Audit history for a queue row (append-only — every gate run preserved)."""
    runs = get_runs_for_queue(queue_id)
    return {"queue_id": queue_id, "count": len(runs), "runs": runs}


@router.get("/stats")
async def stats():
    """30-day aggregate by verdict for dashboards."""
    return get_aggregate_stats()
