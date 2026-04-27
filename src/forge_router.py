"""
ForgeRouter — PATCH-133
API endpoints for the ForgeEngine: create/invoke/edit/list functions,
modules, internal APIs, and external API wrappers on the fly.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("forge_router")
router = APIRouter(prefix="/api/forge", tags=["forge"])


# ── Pydantic models ────────────────────────────────────────────────────────────

class ForgeCreateRequest(BaseModel):
    description: str = Field(..., min_length=5, max_length=5000)
    item_type:   str = Field("function",
                              description="function | module | internal_api | external_api")
    name:        Optional[str] = Field(None, max_length=64)
    service:     Optional[str] = Field(None, max_length=64,
                                       description="External service name (for external_api only)")
    extra_context: Optional[str] = Field(None, max_length=2000)


class ForgeInvokeRequest(BaseModel):
    name: str = Field(..., max_length=64)
    args: Dict[str, Any] = Field(default_factory=dict)


class ForgeEditRequest(BaseModel):
    name:             str = Field(..., max_length=64)
    edit_description: str = Field(..., min_length=5, max_length=2000)


# ── Helper ─────────────────────────────────────────────────────────────────────

def _tenant(request: Request) -> str:
    """Extract tenant_id from auth state (set by OIDCAuthMiddleware)."""
    return getattr(request.state, "actor_tenant", None) or "default"


def _get_forge():
    from src.forge_engine import get_forge
    return get_forge()


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/create")
async def forge_create(req: ForgeCreateRequest, request: Request):
    """
    Create a function, module, internal API, or external API wrapper from NL.

    Examples:
      {"description": "calculate compound interest given principal, rate, years", "item_type": "function"}
      {"description": "Stripe billing wrapper: create customer, create subscription, get invoice", "item_type": "external_api", "service": "stripe"}
      {"description": "CRUD endpoints for a simple task list", "item_type": "internal_api"}
    """
    tenant = _tenant(request)
    forge = _get_forge()

    result = forge.create(
        description=req.description,
        item_type=req.item_type,
        name=req.name,
        tenant_id=tenant,
        service=req.service,
        extra_context=req.extra_context,
    )

    if "error" in result:
        status_code = 422 if result.get("status") == "blocked" else 500
        raise HTTPException(status_code=status_code, detail=result)

    return {"success": True, "forge_item": result}


@router.post("/invoke")
async def forge_invoke(req: ForgeInvokeRequest, request: Request):
    """
    Invoke a forged function or module method.

    For functions:   {"name": "fn_compound_interest", "args": {"principal": 1000, "rate": 0.05, "years": 10}}
    For modules:     {"name": "mod_task_manager", "args": {"method": "create_task", "title": "Buy milk"}}
    For external:    {"name": "ext_stripe_billing", "args": {"method": "health_check"}}
    For internal_api: returns the mounted route URL instead of invoking
    """
    tenant = _tenant(request)
    result = _get_forge().invoke(req.name, req.args.copy(), tenant_id=tenant)
    if "error" in result and result.get("status") == "invocation_error":
        raise HTTPException(status_code=500, detail=result)
    return result


@router.post("/edit")
async def forge_edit(req: ForgeEditRequest, request: Request):
    """Surgically edit an existing forge item via NL."""
    tenant = _tenant(request)
    result = _get_forge().edit(req.name, req.edit_description, tenant_id=tenant)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result)
    return {"success": True, **result}


@router.get("/list")
async def forge_list(request: Request, item_type: Optional[str] = None):
    """List all active forged items for the current tenant."""
    tenant = _tenant(request)
    items = _get_forge().list_items(tenant_id=tenant, item_type=item_type)
    return {"items": items, "count": len(items), "tenant_id": tenant}


@router.get("/item/{item_id}")
async def forge_get_item(item_id: str, request: Request):
    """Get full details (including source code) of a forge item."""
    tenant = _tenant(request)
    item = _get_forge().get_item(item_id, tenant_id=tenant)
    if not item:
        raise HTTPException(status_code=404, detail=f"Forge item {item_id!r} not found")
    return item


@router.delete("/item/{item_id}")
async def forge_delete_item(item_id: str, request: Request):
    """Soft-delete a forge item."""
    tenant = _tenant(request)
    return _get_forge().delete_item(item_id, tenant_id=tenant)


@router.get("/status")
async def forge_status(request: Request):
    """ForgeEngine health check — returns supported item types and item count."""
    tenant = _tenant(request)
    items = _get_forge().list_items(tenant_id=tenant)
    by_type: Dict[str, int] = {}
    for it in items:
        by_type[it["item_type"]] = by_type.get(it["item_type"], 0) + 1
    return {
        "status": "online",
        "engine": "ForgeEngine",
        "patch": "PATCH-133",
        "tenant_id": tenant,
        "supported_types": ["function", "module", "internal_api", "external_api"],
        "active_items": len(items),
        "by_type": by_type,
    }
