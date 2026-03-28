"""
Module Instance Manager — FastAPI REST endpoints.

Exposes lifecycle management for dynamically spawned module instances
as HTTP endpoints, including spawn/despawn, viability checks,
audit trail, configuration history, type registration, and bulk
operations.

Endpoints (all prefixed with ``/module-instances``):
    POST   /module-instances/spawn
    POST   /module-instances/{instance_id}/despawn
    GET    /module-instances/
    GET    /module-instances/{instance_id}
    POST   /module-instances/viability/check
    POST   /module-instances/find-viable
    GET    /module-instances/audit/trail
    GET    /module-instances/{instance_id}/config-history
    GET    /module-instances/status/manager
    GET    /module-instances/status/resources
    POST   /module-instances/types/register
    POST   /module-instances/types/{module_type}/blacklist
    POST   /module-instances/bulk/despawn

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.module_instance_manager import (
    InstanceState,
    ModuleInstanceManager,
    ResourceProfile,
    SpawnDecision,
    ViabilityResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager: ModuleInstanceManager = ModuleInstanceManager()


def get_module_instance_manager() -> ModuleInstanceManager:
    """Return the module-level ``ModuleInstanceManager`` singleton."""
    return _manager


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class SpawnRequest(BaseModel):
    """Payload for POST /module-instances/spawn."""

    module_type: str = Field(..., min_length=1, max_length=200)
    config: dict = Field(default_factory=dict)
    cpu_cores: float = Field(default=1.0, gt=0, le=16)
    memory_mb: int = Field(default=512, gt=0, le=8192)
    max_concurrent: int = Field(default=5, gt=0, le=100)
    timeout_seconds: int = Field(default=300, gt=0, le=3600)
    priority: int = Field(default=5, ge=1, le=10)
    capabilities: list = Field(default_factory=list)
    parent_instance_id: Optional[str] = Field(default=None)
    actor: str = Field(default="system", min_length=1, max_length=100)
    correlation_id: Optional[str] = Field(default=None)


class DespawnRequest(BaseModel):
    """Payload for POST /module-instances/{instance_id}/despawn."""

    actor: str = Field(default="system", min_length=1, max_length=100)
    correlation_id: Optional[str] = Field(default=None)


class ViabilityCheckRequest(BaseModel):
    """Payload for POST /module-instances/viability/check."""

    module_type: str = Field(..., min_length=1, max_length=200)
    cpu_cores: float = Field(default=1.0, gt=0, le=16)
    memory_mb: int = Field(default=512, gt=0, le=8192)
    parent_depth: int = Field(default=0, ge=0)


class FindViableRequest(BaseModel):
    """Payload for POST /module-instances/find-viable."""

    module_type: str = Field(..., min_length=1, max_length=200)
    required_capabilities: list = Field(default_factory=list)


class RegisterTypeRequest(BaseModel):
    """Payload for POST /module-instances/types/register."""

    module_type: str = Field(..., min_length=1, max_length=200)
    metadata: dict = Field(default_factory=dict)


class BlacklistRequest(BaseModel):
    """Payload for POST /module-instances/types/{module_type}/blacklist."""

    actor: str = Field(default="system", min_length=1, max_length=100)
    correlation_id: Optional[str] = Field(default=None)


class BulkDespawnRequest(BaseModel):
    """Payload for POST /module-instances/bulk/despawn."""

    instance_ids: list = Field(..., min_length=1)
    actor: str = Field(default="system", min_length=1, max_length=100)
    correlation_id: Optional[str] = Field(default=None)


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def register_module_instance_routes(app: FastAPI) -> None:
    """Attach all module-instance endpoints directly to *app*."""

    # ---------------------------------------------------------------
    # Static-path routes MUST be registered before parameterized
    # routes so that FastAPI does not match e.g. "bulk" or "audit"
    # as an {instance_id}.
    # ---------------------------------------------------------------

    # -- 1. Spawn --------------------------------------------------------

    @app.post("/module-instances/spawn")
    async def spawn_instance(req: SpawnRequest) -> JSONResponse:
        """Spawn a new module instance."""
        try:
            resource_profile = ResourceProfile(
                cpu_cores=req.cpu_cores,
                memory_mb=req.memory_mb,
                max_concurrent=req.max_concurrent,
                timeout_seconds=req.timeout_seconds,
                priority=req.priority,
            )
            decision, instance = _manager.spawn_instance(
                module_type=req.module_type,
                config=req.config,
                resource_profile=resource_profile,
                capabilities=req.capabilities,
                parent_instance_id=req.parent_instance_id,
                actor=req.actor,
                correlation_id=req.correlation_id,
            )
            payload: Dict[str, Any] = {
                "success": decision == SpawnDecision.APPROVED,
                "decision": decision.value,
            }
            if instance is not None:
                payload["instance"] = instance.to_dict()
            return JSONResponse(content=payload)
        except Exception:
            logger.exception("spawn_instance failed")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Internal server error"},
            )

    # -- 2. List instances -----------------------------------------------

    @app.get("/module-instances/")
    async def list_instances(
        module_type: Optional[str] = Query(
            default=None, description="Filter by module type"
        ),
        state: Optional[str] = Query(
            default=None, description="Filter by instance state"
        ),
    ) -> JSONResponse:
        """Return all instances with optional filtering."""
        try:
            state_enum: Optional[InstanceState] = None
            if state is not None:
                try:
                    state_enum = InstanceState(state)
                except ValueError:
                    valid = [s.value for s in InstanceState]
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid state '{state}'. Valid values: {valid}",
                    )

            instances = _manager.list_instances(
                module_type=module_type, state=state_enum
            )
            return JSONResponse(
                content={
                    "success": True,
                    "count": len(instances),
                    "instances": [i.to_dict() for i in instances],
                },
            )
        except HTTPException:
            raise
        except Exception:
            logger.exception("list_instances failed")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Internal server error"},
            )

    # -- 3. Viability check ----------------------------------------------

    @app.post("/module-instances/viability/check")
    async def viability_check(req: ViabilityCheckRequest) -> JSONResponse:
        """Pre-flight viability check before spawning."""
        try:
            resource_profile = ResourceProfile(
                cpu_cores=req.cpu_cores,
                memory_mb=req.memory_mb,
            )
            result = _manager.check_viability(
                module_type=req.module_type,
                resource_profile=resource_profile,
                parent_depth=req.parent_depth,
            )
            return JSONResponse(
                content={
                    "success": True,
                    "module_type": req.module_type,
                    "result": result.value,
                    "viable": result == ViabilityResult.VIABLE,
                },
            )
        except Exception:
            logger.exception("viability_check failed")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Internal server error"},
            )

    # -- 4. Find viable instances ----------------------------------------

    @app.post("/module-instances/find-viable")
    async def find_viable(req: FindViableRequest) -> JSONResponse:
        """Find active instances matching type and capabilities."""
        try:
            matches = _manager.find_viable_instances(
                module_type=req.module_type,
                required_capabilities=req.required_capabilities or None,
            )
            return JSONResponse(
                content={
                    "success": True,
                    "count": len(matches),
                    "instances": [m.to_dict() for m in matches],
                },
            )
        except Exception:
            logger.exception("find_viable failed")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Internal server error"},
            )

    # -- 5. Audit trail --------------------------------------------------

    @app.get("/module-instances/audit/trail")
    async def audit_trail(
        limit: int = Query(default=50, ge=1, le=1000, description="Max entries"),
        instance_id: Optional[str] = Query(
            default=None, description="Scope to a single instance"
        ),
    ) -> JSONResponse:
        """Return recent audit entries."""
        try:
            entries = _manager.get_audit_trail(
                limit=limit, instance_id=instance_id
            )
            return JSONResponse(
                content={
                    "success": True,
                    "count": len(entries),
                    "entries": [e.to_dict() for e in entries],
                },
            )
        except Exception:
            logger.exception("audit_trail failed")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Internal server error"},
            )

    # -- 6. Manager status -----------------------------------------------

    @app.get("/module-instances/status/manager")
    async def manager_status() -> JSONResponse:
        """Return manager status overview."""
        try:
            status = _manager.get_status()
            return JSONResponse(content={"success": True, **status})
        except Exception:
            logger.exception("manager_status failed")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Internal server error"},
            )

    # -- 7. Resource availability ----------------------------------------

    @app.get("/module-instances/status/resources")
    async def resource_availability() -> JSONResponse:
        """Return resource allocation summary."""
        try:
            resources = _manager.get_resource_availability()
            return JSONResponse(content={"success": True, **resources})
        except Exception:
            logger.exception("resource_availability failed")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Internal server error"},
            )

    # -- 8. Register module type -----------------------------------------

    @app.post("/module-instances/types/register")
    async def register_type(req: RegisterTypeRequest) -> JSONResponse:
        """Register a new module type."""
        try:
            created = _manager.register_module_type(
                module_type=req.module_type,
                metadata=req.metadata or None,
            )
            return JSONResponse(
                content={
                    "success": True,
                    "module_type": req.module_type,
                    "created": created,
                },
            )
        except Exception:
            logger.exception("register_type failed")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Internal server error"},
            )

    # -- 9. Blacklist module type ----------------------------------------

    @app.post("/module-instances/types/{module_type}/blacklist")
    async def blacklist_type(
        module_type: str,
        req: BlacklistRequest,
    ) -> JSONResponse:
        """Add a module type to the viability blacklist."""
        try:
            ok = _manager.blacklist_module_type(
                module_type=module_type,
                actor=req.actor,
                correlation_id=req.correlation_id,
            )
            return JSONResponse(
                content={
                    "success": ok,
                    "module_type": module_type,
                    "blacklisted": ok,
                },
            )
        except Exception:
            logger.exception("blacklist_type failed")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Internal server error"},
            )

    # -- 10. Bulk despawn ------------------------------------------------

    @app.post("/module-instances/bulk/despawn")
    async def bulk_despawn(req: BulkDespawnRequest) -> JSONResponse:
        """Despawn multiple instances in one call."""
        try:
            bulk_result = _manager.bulk_despawn(
                instance_ids=req.instance_ids,
                actor=req.actor,
                correlation_id=req.correlation_id,
            )
            return JSONResponse(
                content={"success": True, **bulk_result},
            )
        except Exception:
            logger.exception("bulk_despawn failed")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Internal server error"},
            )

    # ---------------------------------------------------------------
    # Parameterized routes (registered last to avoid shadowing the
    # static paths above).
    # ---------------------------------------------------------------

    # -- 11. Despawn -----------------------------------------------------

    @app.post("/module-instances/{instance_id}/despawn")
    async def despawn_instance(
        instance_id: str,
        req: DespawnRequest,
    ) -> JSONResponse:
        """Despawn an existing module instance."""
        try:
            existing = _manager.get_instance(instance_id)
            if existing is None:
                raise HTTPException(status_code=404, detail="Instance not found")

            ok = _manager.despawn_instance(
                instance_id=instance_id,
                actor=req.actor,
                correlation_id=req.correlation_id,
            )
            return JSONResponse(
                content={"success": ok, "instance_id": instance_id},
            )
        except HTTPException:
            raise
        except Exception:
            logger.exception("despawn_instance failed")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Internal server error"},
            )

    # -- 12. Config history ----------------------------------------------

    @app.get("/module-instances/{instance_id}/config-history")
    async def config_history(instance_id: str) -> JSONResponse:
        """Return configuration snapshot history for an instance."""
        try:
            instance = _manager.get_instance(instance_id)
            if instance is None:
                raise HTTPException(status_code=404, detail="Instance not found")
            snapshots = _manager.get_config_history(instance_id)
            return JSONResponse(
                content={
                    "success": True,
                    "instance_id": instance_id,
                    "count": len(snapshots),
                    "snapshots": [s.to_dict() for s in snapshots],
                },
            )
        except HTTPException:
            raise
        except Exception:
            logger.exception("config_history failed")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Internal server error"},
            )

    # -- 13. Get single instance -----------------------------------------

    @app.get("/module-instances/{instance_id}")
    async def get_instance(instance_id: str) -> JSONResponse:
        """Return details of a single instance."""
        try:
            instance = _manager.get_instance(instance_id)
            if instance is None:
                raise HTTPException(status_code=404, detail="Instance not found")
            return JSONResponse(
                content={"success": True, "instance": instance.to_dict()},
            )
        except HTTPException:
            raise
        except Exception:
            logger.exception("get_instance failed")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Internal server error"},
            )
