"""
ForgeRouter — PATCH-133
API endpoints for the ForgeEngine: create/invoke/edit/list functions,
modules, internal APIs, and external API wrappers on the fly.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
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

def _run_forge_create(job_id: str, description: str, item_type: str,
                      name, tenant: str, service, extra_context) -> None:
    """Background worker — runs forge.create() and stores result in job store."""
    from src.forge_engine import _job_set
    try:
        _job_set(job_id, "running")
        forge = _get_forge()
        result = forge.create(
            description=description,
            item_type=item_type,
            name=name,
            tenant_id=tenant,
            service=service,
            extra_context=extra_context,
        )
        if "error" in result:
            _job_set(job_id, "failed", error=str(result.get("error", result)))
        else:
            _job_set(job_id, "done", result=result)
    except Exception as exc:
        from src.forge_engine import _job_set as _js
        _js(job_id, "failed", error=str(exc))


@router.post("/create")
async def forge_create(req: ForgeCreateRequest, request: Request,
                       background_tasks: BackgroundTasks):
    """
    PATCH-139: Async forge create — returns job_id immediately.
    LLM codegen runs in background; poll GET /api/forge/job/{job_id} for result.

    Examples:
      {"description": "calculate compound interest given principal, rate, years", "item_type": "function"}
      {"description": "Stripe billing wrapper", "item_type": "external_api", "service": "stripe"}
      {"description": "CRUD endpoints for a simple task list", "item_type": "internal_api"}
    """
    tenant  = _tenant(request)
    job_id  = str(uuid.uuid4())

    # Kick off background task — returns instantly
    background_tasks.add_task(
        _run_forge_create,
        job_id, req.description, req.item_type,
        req.name, tenant, req.service, req.extra_context,
    )

    return {
        "success":     True,
        "job_id":      job_id,
        "status":      "queued",
        "poll_url":    f"/api/forge/job/{job_id}",
        "message":     "Forge job queued. Poll poll_url for result (usually ready in 5-30s).",
    }


@router.get("/job/{job_id}")
async def forge_job_status(job_id: str, request: Request):
    """
    PATCH-139: Poll the status of a background forge/create job.
    Returns status: queued | running | done | failed
    When done, includes forge_item with full details.
    """
    from src.forge_engine import get_job
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    resp = {"job_id": job_id, "status": job["status"]}
    if job["status"] == "done":
        resp["forge_item"] = job["result"]
    elif job["status"] == "failed":
        resp["error"] = job["error"]
    return resp


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


# ── Runtime API Dispatcher ─────────────────────────────────────────────────────
# Since FastAPI can't add routes after startup, we use a wildcard dispatcher
# that routes /api/user/{tenant}/{name}/{path} to the appropriate forge module.

@router.api_route(
    "/dispatch/{forge_name}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def forge_dispatch(forge_name: str, path: str, request: Request):
    """
    Runtime dispatcher for forged internal APIs.
    Forwards /api/forge/dispatch/{name}/{path} → the forged router.

    The client calls:  /api/forge/dispatch/kv_store/set
    Which routes to the kv_store module's /set endpoint.
    """
    tenant = _tenant(request)
    forge  = _get_forge()
    item   = forge._get_by_name(forge_name, tenant)

    if not item or item["item_type"] != "internal_api":
        raise HTTPException(
            status_code=404,
            detail=f"No internal_api forge item named '{forge_name}' for tenant '{tenant}'",
        )

    # Hot-load the module
    import importlib.util, sys, re as _re
    file_path = item["file_path"]
    mod_key   = f"forge_dispatch.{tenant}.{forge_name}"
    try:
        spec   = importlib.util.spec_from_file_location(mod_key, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_key] = module
        spec.loader.exec_module(module)
        inner_router = getattr(module, "router", None)
        if inner_router is None:
            raise HTTPException(status_code=500, detail="Forge module has no 'router'")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Module load error: {e}")

    # Find the matching route in the inner router
    method = request.method
    target_path = "/" + path.lstrip("/")

    from fastapi.routing import APIRoute
    from starlette.routing import Match
    from starlette.datastructures import URL

    matched_route = None
    matched_params: dict = {}
    for route in inner_router.routes:
        if not isinstance(route, APIRoute):
            continue
        # Build a mock scope to test match
        scope = {
            "type": "http",
            "method": method,
            "path": target_path,
            "query_string": request.url.query.encode(),
            "headers": [],
        }
        match, child_scope = route.matches(scope)
        if match == Match.FULL:
            matched_route = route
            matched_params = child_scope.get("path_params", {})
            break

    if matched_route is None:
        available = [
            f"{list(r.methods)[0] if r.methods else '?'} {r.path}"
            for r in inner_router.routes
            if isinstance(r, APIRoute)
        ]
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"No route '{method} {target_path}' in forge module '{forge_name}'",
                "available": available,
            },
        )

    # Execute the matched endpoint
    try:
        # Inject path params into request scope
        request._state.__dict__.update(matched_params)
        # Build kwargs for the handler
        import inspect as _inspect
        sig    = _inspect.signature(matched_route.endpoint)
        kwargs: dict = {}

        # Pass path params
        for k, v in matched_params.items():
            if k in sig.parameters:
                kwargs[k] = v

        # Pass query params
        query_params = dict(request.query_params)
        for k, v in query_params.items():
            if k in sig.parameters:
                kwargs[k] = v

        # Pass body
        if method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.json()
            except Exception:
                body = {}
            for pname, param in sig.parameters.items():
                if pname == "request" or pname in kwargs:
                    continue
                ann = param.annotation
                # dict annotation → pass body dict directly
                if ann is dict or ann == _inspect.Parameter.empty and pname == "data":
                    kwargs[pname] = body
                # Pydantic model → instantiate
                elif hasattr(ann, "model_fields"):
                    try:
                        kwargs[pname] = ann(**body)
                    except Exception:
                        kwargs[pname] = ann.model_validate(body)
                # plain param present in body → pass value
                elif pname in body:
                    kwargs[pname] = body[pname]

        # Pass request if handler wants it
        if "request" in sig.parameters:
            kwargs["request"] = request

        result = await matched_route.endpoint(**kwargs) \
                 if _inspect.iscoroutinefunction(matched_route.endpoint) \
                 else matched_route.endpoint(**kwargs)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Handler error: {e}")
