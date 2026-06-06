"""R382 tenant-scoped chat endpoint module.

Mounted by app.py via include_router. Provides:
  POST /api/tenant/{slug}/chat — tenant-scoped LLM chat with platform-access guard
  GET  /api/tenant/{slug}/assistant-status — health check for the tenant assistant
"""
import sys
sys.path.insert(0, "/usr/local/bin")

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import importlib.util

router = APIRouter(prefix="/api/tenant", tags=["tenant_assistant"])

# Load r382 router module
spec = importlib.util.spec_from_file_location("r382", "/usr/local/bin/r382_tenant_chat_router.py")
r382 = importlib.util.module_from_spec(spec); spec.loader.exec_module(r382)


class TenantChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    tenant_slug: Optional[str] = None  # client may pass; we use path param as source of truth


@router.post("/{slug}/chat")
async def tenant_chat(slug: str, req: TenantChatRequest):
    """Tenant-scoped chat endpoint. No founder key required — endpoint is
    public for tenant users but server-side validates tenant exists +
    blocks platform-access prompts."""
    result = r382.handle_tenant_chat(
        tenant_slug=slug,
        message=req.message,
        session_id=req.session_id,
        founder_key=None  # use internal fallback
    )
    return result


@router.get("/{slug}/assistant-status")
async def tenant_assistant_status(slug: str):
    """Health check + tenant context for the assistant page."""
    ctx, err = r382.get_tenant_context(slug)
    if err == "tenant_not_found":
        raise HTTPException(status_code=404, detail="tenant_not_found")
    if err:
        raise HTTPException(status_code=500, detail=err)
    return {"ok": True, "tenant": slug, "context": ctx}
