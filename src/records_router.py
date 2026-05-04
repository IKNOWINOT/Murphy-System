"""
records_router.py — PATCH-182
FastAPI router for Records Assembly Engine.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger("murphy.records_router")
router = APIRouter(prefix="/api/assembly", tags=["Assembly"])


class CreateRecordReq(BaseModel):
    record_type_id: str
    title: str
    fields: Dict[str, Any] = {}
    created_by: str = "system"
    project_id: Optional[str] = None
    block_id: Optional[str] = None
    milestone_id: Optional[str] = None
    detail_item_id: Optional[str] = None
    product_id: Optional[str] = None

class UpdateRecordReq(BaseModel):
    fields: Optional[Dict[str, Any]] = None
    title: Optional[str] = None
    status: Optional[str] = None
    approved_by: Optional[str] = None

class AmendRecordReq(BaseModel):
    fields: Dict[str, Any]
    amended_by: str
    reason: str = ""

class CreateProductReq(BaseModel):
    name: str
    description: str = ""
    project_id: Optional[str] = None
    block_id: Optional[str] = None
    milestone_id: Optional[str] = None
    created_by: str = "system"
    required_record_types: List[str] = []

class ShipProductReq(BaseModel):
    shipped_by: str


@router.get("/record-types")
async def list_record_types(lane: Optional[str] = None):
    from src.records_engine import get_record_types
    return {"record_types": get_record_types(lane)}

@router.get("/record-types/{type_id}")
async def get_record_type(type_id: str):
    from src.records_engine import get_record_type as _grt
    rt = _grt(type_id)
    if not rt: raise HTTPException(404, "Record type not found")
    return rt

@router.post("/records")
async def create_record(req: CreateRecordReq):
    from src.records_engine import create_record as _cr
    r = _cr(req.record_type_id, req.title, req.fields, req.created_by,
            req.project_id, req.block_id, req.milestone_id,
            req.detail_item_id, req.product_id)
    if "error" in r: raise HTTPException(400, r["error"])
    return r

@router.get("/records")
async def list_records(project_id: Optional[str]=None, lane: Optional[str]=None,
                       record_type_id: Optional[str]=None, status: Optional[str]=None,
                       product_id: Optional[str]=None, limit: int=100):
    from src.records_engine import list_records as _lr
    return {"records": _lr(project_id, lane, record_type_id, status, product_id, limit)}

@router.get("/records/{record_id}")
async def get_record(record_id: str):
    from src.records_engine import get_record as _gr
    r = _gr(record_id)
    if not r: raise HTTPException(404, "Record not found")
    return r

@router.patch("/records/{record_id}")
async def update_record(record_id: str, req: UpdateRecordReq):
    from src.records_engine import update_record as _ur
    return _ur(record_id, req.fields, req.title, req.status, req.approved_by)

@router.post("/records/{record_id}/amend")
async def amend_record(record_id: str, req: AmendRecordReq):
    from src.records_engine import amend_record as _ar
    r = _ar(record_id, req.fields, req.amended_by, req.reason)
    if "error" in r: raise HTTPException(400, r["error"])
    return r

@router.post("/records/{record_id}/approve")
async def approve_record(record_id: str, approved_by: str = "system"):
    from src.records_engine import update_record as _ur
    return _ur(record_id, status="approved", approved_by=approved_by)

@router.post("/products")
async def create_product(req: CreateProductReq):
    from src.records_engine import create_product as _cp
    return _cp(req.name, req.description, req.project_id, req.block_id,
               req.milestone_id, req.created_by, req.required_record_types)

@router.get("/products")
async def list_products(project_id: Optional[str]=None):
    from src.records_engine import list_products as _lp
    return {"products": _lp(project_id)}

@router.get("/products/{product_id}")
async def get_product(product_id: str):
    from src.records_engine import get_product as _gp
    p = _gp(product_id)
    if not p: raise HTTPException(404, "Product not found")
    return p

@router.post("/products/{product_id}/ship")
async def ship_product(product_id: str, req: ShipProductReq):
    from src.records_engine import ship_product as _sp
    r = _sp(product_id, req.shipped_by)
    if "error" in r: raise HTTPException(400, r["error"])
    return r

@router.get("/log")
async def assembly_log(product_id: Optional[str]=None, limit: int=100):
    from src.records_engine import get_assembly_log as _gal
    return {"log": _gal(product_id, limit)}

@router.get("/status")
async def assembly_status():
    from src.records_engine import get_status
    return get_status()
