"""PCR-070 Stage 1 — HTTP surface for the perspective distiller.

Routes:
  GET  /api/perspective/list                     — current perspectives
  GET  /api/perspective/{role_id}/{jurisdiction} — current doc for (role, jur)
  POST /api/perspective/distill                  — trigger fresh distillation
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pcr070_perspective_distiller import (
    list_current,
    get_current,
    distill_and_persist,
    ensure_schema,
)

router = APIRouter(prefix="/api/perspective", tags=["perspective"])


@router.get("/list")
async def list_perspectives():
    ensure_schema()
    rows = list_current()
    return {
        "count": len(rows),
        "perspectives": rows,
    }


@router.get("/{role_id}/{jurisdiction}")
async def get_perspective(role_id: str, jurisdiction: str, tenant_id: Optional[str] = None):
    ensure_schema()
    doc = get_current(role_id, jurisdiction, tenant_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"No current perspective for {role_id}/{jurisdiction}")
    return doc


@router.post("/distill")
async def trigger_distill(
    role_id: str = Query(...),
    jurisdiction: str = Query(...),
    tenant_id: Optional[str] = Query(None),
):
    vid, p = distill_and_persist(role_id, jurisdiction, tenant_id)
    return {
        "version_id": vid,
        "perspective": p,
    }
