"""
Module Instance API Endpoints for Murphy System

FastAPI endpoints for the Module Instance Manager providing:
- Spawn/despawn module instances
- Query instance status and capabilities
- Viability checking endpoints
- Audit trail access for configuration backward logic
- Resource monitoring

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/module-instances", tags=["Module Instances"])

# Will be injected at startup
_instance_manager = None


def get_manager():
    """Get the ModuleInstanceManager instance."""
    global _instance_manager
    if _instance_manager is None:
        from .module_instance_manager import get_instance_manager
        _instance_manager = get_instance_manager()
    return _instance_manager


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

class SpawnRequest(BaseModel):
    """Request to spawn a new module instance."""
    module_type: str = Field(..., description="Type of module to spawn")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Instance configuration")
    parent_instance_id: Optional[str] = Field(default=None, description="Parent instance ID for hierarchy")
    actor: str = Field(default="api", description="Who initiated the spawn")
    correlation_id: Optional[str] = Field(default=None, description="Correlation ID for linking operations")


class SpawnResponse(BaseModel):
    """Response from spawn request."""
    decision: str = Field(..., description="Spawn decision (approved/denied_*)")
    instance_id: Optional[str] = Field(default=None, description="Instance ID if spawned")
    correlation_id: str = Field(..., description="Correlation ID for this operation")
    reason: Optional[str] = Field(default=None, description="Reason if denied")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DespawnRequest(BaseModel):
    """Request to despawn a module instance."""
    reason: str = Field(default="manual", description="Reason for despawning")
    actor: str = Field(default="api", description="Who initiated the despawn")
    force: bool = Field(default=False, description="Force despawn even if busy")


class InstanceResponse(BaseModel):
    """Response with instance details."""
    instance_id: str
    module_type: str
    state: str
    spawned_at: str
    capabilities: List[str]
    config: Dict[str, Any]
    execution_count: int
    error_count: int
    last_activity: Optional[str]
    parent_instance_id: Optional[str]
    spawn_depth: int
    actor: str
    correlation_id: Optional[str]


class ViabilityRequest(BaseModel):
    """Request to check viability."""
    module_type: str = Field(..., description="Module type to check")
    request: Dict[str, Any] = Field(default_factory=dict, description="Request context")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


class ViabilityResponse(BaseModel):
    """Response from viability check."""
    module_type: str
    viable: bool
    result: str
    reason: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FindViableRequest(BaseModel):
    """Request to find viable instances."""
    request: Dict[str, Any] = Field(default_factory=dict, description="Request to match")
    required_capabilities: Optional[List[str]] = Field(default=None, description="Required capabilities")
    module_type: Optional[str] = Field(default=None, description="Filter by module type")


class AuditQueryParams(BaseModel):
    """Parameters for querying audit trail."""
    instance_id: Optional[str] = None
    module_type: Optional[str] = None
    action: Optional[str] = None
    actor: Optional[str] = None
    correlation_id: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)


class RegisterModuleTypeRequest(BaseModel):
    """Request to register a new module type."""
    module_type: str = Field(..., description="Unique module type identifier")
    capabilities: Optional[List[str]] = Field(default=None, description="Capability list")
    dependencies: Optional[List[str]] = Field(default=None, description="Required dependencies")
    max_instances: Optional[int] = Field(default=10, description="Max concurrent instances")


class ResourceTypeRequest(BaseModel):
    """Resource profile for a module type."""
    cpu_cores: float = Field(default=1.0, ge=0.1, le=64.0)
    memory_mb: int = Field(default=512, ge=64, le=65536)
    max_concurrent: int = Field(default=1, ge=1)
    timeout_seconds: int = Field(default=300, ge=10, le=86400)
    priority: int = Field(default=5, ge=1, le=10)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/spawn", response_model=SpawnResponse)
async def spawn_instance(request: SpawnRequest):
    """
    Spawn a new module instance.
    
    The spawn will be subject to:
    - Viability checking
    - Resource availability
    - Spawn depth limits
    - Circuit breaker status
    """
    manager = get_manager()
    
    from .module_instance_manager import SpawnDecision
    
    decision, instance_id, correlation_id = manager.spawn_module(
        module_type=request.module_type,
        config=request.config,
        parent_instance_id=request.parent_instance_id,
        actor=request.actor,
        correlation_id=request.correlation_id,
    )
    
    return SpawnResponse(
        decision=decision.value,
        instance_id=instance_id,
        correlation_id=correlation_id,
        reason=None if decision == SpawnDecision.APPROVED else instance_id,
    )


@router.post("/{instance_id}/despawn", response_model=Dict[str, Any])
async def despawn_instance(instance_id: str, request: DespawnRequest):
    """
    Despawn a module instance.
    
    Use force=True to despawn busy instances or instances with children.
    """
    manager = get_manager()
    
    success = manager.despawn_module(
        instance_id=instance_id,
        reason=request.reason,
        actor=request.actor,
        force=request.force,
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to despawn instance {instance_id}"
        )
    
    return {
        "success": True,
        "instance_id": instance_id,
        "message": f"Instance {instance_id} despawned",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/", response_model=Dict[str, Any])
async def list_instances(
    module_type: Optional[str] = Query(None, description="Filter by module type"),
    state: Optional[str] = Query(None, description="Filter by state"),
    capability: Optional[str] = Query(None, description="Filter by capability"),
):
    """List all instances with optional filtering."""
    manager = get_manager()
    
    if module_type:
        instances = manager.get_instances_by_type(module_type)
    elif capability:
        instances = manager.get_instances_by_capability(capability)
    else:
        instances = manager.get_active_instances()
    
    if state:
        from .module_instance_manager import InstanceState
        try:
            state_enum = InstanceState(state)
            instances = [i for i in instances if i.state == state_enum]
        except ValueError:
            pass  # Invalid state filter, ignore
    
    return {
        "total": len(instances),
        "instances": [inst.to_dict() for inst in instances],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/{instance_id}", response_model=InstanceResponse)
async def get_instance(instance_id: str):
    """Get details of a specific instance."""
    manager = get_manager()
    
    instance = manager.get_instance(instance_id)
    if instance is None:
        raise HTTPException(
            status_code=404,
            detail=f"Instance {instance_id} not found"
        )
    
    return InstanceResponse(
        instance_id=instance.instance_id,
        module_type=instance.module_type,
        state=instance.state.value,
        spawned_at=instance.spawned_at.isoformat(),
        capabilities=instance.capabilities,
        config=instance.config,
        execution_count=instance.execution_count,
        error_count=instance.error_count,
        last_activity=instance.last_activity.isoformat() if instance.last_activity else None,
        parent_instance_id=instance.parent_instance_id,
        spawn_depth=instance.spawn_depth,
        actor=instance.actor,
        correlation_id=instance.correlation_id,
    )


@router.post("/viability/check", response_model=ViabilityResponse)
async def check_viability(request: ViabilityRequest):
    """
    Check if a module type is viable for a request.
    
    This implements the "murphy cursor actions" style viability checking.
    """
    manager = get_manager()
    
    result, reason = manager._viability_checker.check_viability(
        module_type=request.module_type,
        request=request.request,
        context=request.context,
    )
    
    return ViabilityResponse(
        module_type=request.module_type,
        viable=(result.value == "viable"),
        result=result.value,
        reason=reason,
    )


@router.post("/find-viable", response_model=Dict[str, Any])
async def find_viable_instances(request: FindViableRequest):
    """
    Find all viable instances for a given request.
    
    Returns instances sorted by execution count and error count.
    """
    manager = get_manager()
    
    instances = manager.find_viable_instances(
        request=request.request,
        required_capabilities=request.required_capabilities,
        module_type=request.module_type,
    )
    
    return {
        "total": len(instances),
        "instances": [
            {
                "instance_id": inst.instance_id,
                "module_type": inst.module_type,
                "state": inst.state.value,
                "capabilities": inst.capabilities,
                "execution_count": inst.execution_count,
                "error_count": inst.error_count,
            }
            for inst in instances
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Audit Trail Endpoints
# ---------------------------------------------------------------------------

@router.get("/audit/trail", response_model=Dict[str, Any])
async def get_audit_trail(
    instance_id: Optional[str] = Query(None),
    module_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
    correlation_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Get audit trail entries for configuration backward logic.
    
    This enables tracing back from a current state to understand:
    - Who spawned/despawned instances
    - What configuration was used
    - What the parent-child relationships are
    """
    manager = get_manager()
    
    entries = manager.get_audit_trail(
        instance_id=instance_id,
        module_type=module_type,
        action=action,
        actor=actor,
        correlation_id=correlation_id,
        limit=limit,
    )
    
    return {
        "total": len(entries),
        "entries": [entry.to_dict() for entry in entries],
        "query": {
            "instance_id": instance_id,
            "module_type": module_type,
            "action": action,
            "actor": actor,
            "correlation_id": correlation_id,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/{instance_id}/config-history", response_model=Dict[str, Any])
async def get_config_history(instance_id: str):
    """
    Get full configuration backward logic for an instance.
    
    Returns the complete history including:
    - Configuration snapshot
    - Parent chain
    - Full audit trail
    """
    manager = get_manager()
    
    history = manager.get_configuration_history(instance_id)
    
    if "error" in history:
        raise HTTPException(
            status_code=404,
            detail=history["error"]
        )
    
    return history


@router.get("/audit/export", response_model=Dict[str, Any])
async def export_audit_report():
    """Export a complete audit report for compliance."""
    manager = get_manager()
    return manager.export_audit_report()


# ---------------------------------------------------------------------------
# Resource and Status Endpoints
# ---------------------------------------------------------------------------

@router.get("/status/manager", response_model=Dict[str, Any])
async def get_manager_status():
    """Get current status of the ModuleInstanceManager."""
    manager = get_manager()
    return manager.get_status()


@router.get("/status/resources", response_model=Dict[str, Any])
async def get_resources():
    """Get current resource availability."""
    manager = get_manager()
    return manager.get_available_resources()


# ---------------------------------------------------------------------------
# Module Type Registration Endpoints
# ---------------------------------------------------------------------------

@router.post("/types/register", response_model=Dict[str, Any])
async def register_module_type(request: RegisterModuleTypeRequest):
    """Register a new module type that can be spawned."""
    manager = get_manager()
    
    from .module_instance_manager import ResourceProfile
    
    resource_profile = ResourceProfile(
        cpu_cores=1.0,
        memory_mb=512,
        max_concurrent=request.max_instances,
    )
    
    success = manager.register_module_type(
        module_type=request.module_type,
        capabilities=request.capabilities,
        dependencies=request.dependencies,
        resource_profile=resource_profile,
    )
    
    return {
        "success": success,
        "module_type": request.module_type,
        "message": f"Module type {request.module_type} registered",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/types/{module_type}", response_model=Dict[str, Any])
async def unregister_module_type(module_type: str):
    """Unregister a module type."""
    manager = get_manager()
    
    success = manager.unregister_module_type(module_type)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Module type {module_type} not found"
        )
    
    return {
        "success": True,
        "module_type": module_type,
        "message": f"Module type {module_type} unregistered",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/types/{module_type}/blacklist", response_model=Dict[str, Any])
async def blacklist_module_type(module_type: str, reason: str = Query("")):
    """Blacklist a module type from spawning."""
    manager = get_manager()
    manager.blacklist_module_type(module_type, reason)
    
    return {
        "success": True,
        "module_type": module_type,
        "message": f"Module type {module_type} blacklisted",
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/types/{module_type}/blacklist", response_model=Dict[str, Any])
async def unblacklist_module_type(module_type: str):
    """Remove a module type from the blacklist."""
    manager = get_manager()
    manager.unblacklist_module_type(module_type)
    
    return {
        "success": True,
        "module_type": module_type,
        "message": f"Module type {module_type} removed from blacklist",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/types", response_model=Dict[str, Any])
async def list_module_types():
    """List all registered module types."""
    manager = get_manager()
    status = manager.get_status()
    
    return {
        "registered_types": status["registered_types"],
        "blacklisted_types": status["blacklisted_types"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Bulk Operations
# ---------------------------------------------------------------------------

@router.post("/bulk/despawn", response_model=Dict[str, Any])
async def bulk_despawn(
    module_type: Optional[str] = Query(None),
    reason: str = Query("bulk_despawn"),
    force: bool = Query(False),
):
    """Despawn multiple instances at once."""
    manager = get_manager()
    
    count = manager.despawn_all(
        module_type=module_type,
        reason=reason,
        actor="api_bulk",
        force=force,
    )
    
    return {
        "success": True,
        "despawned_count": count,
        "module_type": module_type or "all",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Integration Function
# ---------------------------------------------------------------------------

def register_module_instance_routes(app):
    """
    Register module instance routes with a FastAPI app.
    
    Usage:
        from src.module_instance_api import register_module_instance_routes
        register_module_instance_routes(app)
    """
    app.include_router(router)
    logger.info("Module instance API routes registered")