"""
Telemetry & Learning REST API

Provides endpoints for:
- Telemetry ingestion (write)
- Telemetry query (read-only)
- Insights and recommendations
- Gate evolution proposals
- Shadow mode control
- Authorization interface
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .ingestion import TelemetryBus, TelemetryIngester
from .learning import HardeningPolicyEngine
from .models import (
    ControlTelemetry,
    GateEvolutionArtifact,
    HumanTelemetry,
    InsightArtifact,
    MarketTelemetry,
    OperationalTelemetry,
    SafetyTelemetry,
    TelemetryArtifact,
    TelemetryDomain,
)
from .shadow_mode import (
    AuthorizationInterface,
    OperationMode,
    SafetyEnforcer,
    ShadowModeController,
)

logger = logging.getLogger(__name__)


# Pydantic models for API
class TelemetrySubmission(BaseModel):
    """Telemetry submission."""
    domain: str
    source_id: str
    data: Dict[str, Any]
    provenance: Optional[Dict[str, Any]] = None


class AuthorizationRequest(BaseModel):
    """Authorization request."""
    evolution_id: str
    authorized_by: str
    notes: Optional[str] = None


class RejectionRequest(BaseModel):
    """Rejection request."""
    evolution_id: str
    rejected_by: str
    reason: str


class RollbackRequest(BaseModel):
    """Rollback request."""
    evolution_id: str
    rolled_back_by: str
    reason: str


class ModeChangeRequest(BaseModel):
    """Mode change request."""
    mode: str
    enforcement_percentage: Optional[float] = None


# Initialize components
telemetry_bus = TelemetryBus(max_buffer_size=10000)
telemetry_ingester = TelemetryIngester(telemetry_bus)
hardening_engine = HardeningPolicyEngine()
shadow_controller = ShadowModeController(mode=OperationMode.SHADOW)
authorization_interface = AuthorizationInterface()
safety_enforcer = SafetyEnforcer()


# Create FastAPI app
app = FastAPI(
    title="Telemetry & Learning API",
    description="Enterprise telemetry collection with conservative learning loops",
    version="1.0.0",
)

# Apply security hardening (SEC-001, SEC-002, SEC-004)
from fastapi_security import configure_secure_fastapi

configure_secure_fastapi(app, service_name="telemetry-learning")


# Health endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "telemetry_bus": "operational",
            "telemetry_ingester": "operational",
            "hardening_engine": "operational",
            "shadow_controller": "operational",
            "authorization_interface": "operational",
            "safety_enforcer": "operational",
        },
        "mode": shadow_controller.mode.value,
    }


# Telemetry endpoints
@app.post("/telemetry/submit")
async def submit_telemetry(submission: TelemetrySubmission):
    """Submit telemetry event to the bus"""
    try:
        domain = TelemetryDomain(submission.domain)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain: {submission.domain}",
        )

    success = telemetry_bus.publish(
        domain=domain,
        source_id=submission.source_id,
        data=submission.data,
        provenance=submission.provenance,
    )

    if not success:
        raise HTTPException(
            status_code=409,
            detail="Event deduplicated or buffer full",
        )

    return {
        "status": "accepted",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/telemetry/ingest")
async def ingest_telemetry(batch_size: int = 100):
    """Ingest telemetry from bus to artifact store"""
    ingested = telemetry_ingester.ingest_batch(batch_size)

    return {
        "ingested": ingested,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/telemetry/query")
async def query_telemetry(
    domain: Optional[str] = None,
    source_id: Optional[str] = None,
    since_hours: Optional[int] = None,
    limit: int = Query(default=100, le=1000),
):
    """Query telemetry artifacts (read-only)"""
    domain_enum = None
    if domain:
        try:
            domain_enum = TelemetryDomain(domain)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid domain: {domain}",
            )

    since = None
    if since_hours:
        since = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    artifacts = telemetry_ingester.get_artifacts(
        domain=domain_enum,
        source_id=source_id,
        since=since,
        limit=limit,
    )

    return {
        "count": len(artifacts),
        "artifacts": [a.to_dict() for a in artifacts],
    }


@app.get("/telemetry/stats")
async def get_telemetry_stats():
    """Get telemetry statistics"""
    return telemetry_ingester.get_stats()


# Learning endpoints
@app.post("/learning/analyze")
async def analyze_telemetry(
    since_hours: int = Query(default=24, le=168),  # Max 1 week
):
    """Run learning loops on recent telemetry"""
    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    # Get recent telemetry
    artifacts = telemetry_ingester.get_artifacts(since=since, limit=10000)

    if not artifacts:
        return {
            "gate_proposals": [],
            "insights": [],
            "message": "No telemetry available for analysis",
        }

    # Run learning loops
    gate_proposals, insights = hardening_engine.analyze_all(artifacts)

    # Log in shadow mode
    for proposal in gate_proposals:
        should_enforce = shadow_controller.should_enforce(proposal.evolution_id)
        shadow_controller.log_proposal(proposal, enforced=should_enforce)

        # Submit for authorization if not in shadow mode
        if shadow_controller.mode != OperationMode.SHADOW:
            authorization_interface.submit_proposal(proposal)

    for insight in insights:
        shadow_controller.log_insight(insight)

    return {
        "gate_proposals": [p.to_dict() for p in gate_proposals],
        "insights": [i.to_dict() for i in insights],
        "mode": shadow_controller.mode.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Insights endpoints
@app.get("/insights")
async def get_insights(
    since_hours: Optional[int] = None,
    limit: int = Query(default=100, le=1000),
):
    """Get insights and recommendations"""
    since = None
    if since_hours:
        since = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    log = shadow_controller.get_shadow_log(since=since, limit=limit)

    # Filter for insights only
    insights = [
        entry for entry in log
        if "insight_id" in entry
    ]

    return {
        "count": len(insights),
        "insights": insights,
    }


# Gate evolution endpoints
@app.get("/gate-evolution/proposals")
async def get_gate_proposals(
    since_hours: Optional[int] = None,
    limit: int = Query(default=100, le=1000),
):
    """Get gate evolution proposals"""
    since = None
    if since_hours:
        since = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    log = shadow_controller.get_shadow_log(since=since, limit=limit)

    # Filter for proposals only
    proposals = [
        entry for entry in log
        if "evolution_id" in entry
    ]

    return {
        "count": len(proposals),
        "proposals": proposals,
    }


@app.get("/gate-evolution/pending")
async def get_pending_proposals():
    """Get pending authorization proposals"""
    proposals = authorization_interface.get_pending_proposals()

    return {
        "count": len(proposals),
        "proposals": [p.to_dict() for p in proposals],
    }


@app.post("/gate-evolution/authorize")
async def authorize_proposal(request: AuthorizationRequest):
    """Authorize a gate evolution proposal"""
    success = authorization_interface.authorize_proposal(
        evolution_id=request.evolution_id,
        authorized_by=request.authorized_by,
        notes=request.notes,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Proposal {request.evolution_id} not found",
        )

    return {
        "status": "authorized",
        "evolution_id": request.evolution_id,
        "authorized_by": request.authorized_by,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/gate-evolution/reject")
async def reject_proposal(request: RejectionRequest):
    """Reject a gate evolution proposal"""
    success = authorization_interface.reject_proposal(
        evolution_id=request.evolution_id,
        rejected_by=request.rejected_by,
        reason=request.reason,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Proposal {request.evolution_id} not found",
        )

    return {
        "status": "rejected",
        "evolution_id": request.evolution_id,
        "rejected_by": request.rejected_by,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/gate-evolution/rollback")
async def rollback_evolution(request: RollbackRequest):
    """Rollback a gate evolution"""
    rollback_state = authorization_interface.rollback_evolution(
        evolution_id=request.evolution_id,
        rolled_back_by=request.rolled_back_by,
        reason=request.reason,
    )

    if not rollback_state:
        raise HTTPException(
            status_code=404,
            detail=f"Evolution {request.evolution_id} not found or not authorized",
        )

    return {
        "status": "rolled_back",
        "rollback_state": rollback_state,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/gate-evolution/log")
async def get_authorization_log(
    since_hours: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
):
    """Get authorization log"""
    since = None
    if since_hours:
        since = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    from .shadow_mode import AuthorizationStatus
    status_enum = None
    if status:
        try:
            status_enum = AuthorizationStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}",
            )

    log = authorization_interface.get_authorization_log(
        since=since,
        status=status_enum,
        limit=limit,
    )

    return {
        "count": len(log),
        "log": log,
    }


@app.get("/gate-evolution/rollbacks")
async def get_rollback_history(
    since_hours: Optional[int] = None,
    limit: int = Query(default=100, le=1000),
):
    """Get rollback history"""
    since = None
    if since_hours:
        since = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    history = authorization_interface.get_rollback_history(
        since=since,
        limit=limit,
    )

    return {
        "count": len(history),
        "history": history,
    }


# Shadow mode endpoints
@app.get("/shadow-mode/status")
async def get_shadow_mode_status():
    """Get shadow mode status"""
    return {
        "mode": shadow_controller.mode.value,
        "enforcement_percentage": shadow_controller.enforcement_percentage,
        "stats": shadow_controller.get_stats(),
    }


@app.post("/shadow-mode/set-mode")
async def set_shadow_mode(request: ModeChangeRequest):
    """Change shadow mode"""
    try:
        mode = OperationMode(request.mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {request.mode}",
        )

    shadow_controller.set_mode(mode)

    if request.enforcement_percentage is not None:
        shadow_controller.set_enforcement_percentage(request.enforcement_percentage)

    return {
        "status": "updated",
        "mode": shadow_controller.mode.value,
        "enforcement_percentage": shadow_controller.enforcement_percentage,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/shadow-mode/log")
async def get_shadow_log(
    since_hours: Optional[int] = None,
    limit: int = Query(default=100, le=1000),
):
    """Get shadow mode log"""
    since = None
    if since_hours:
        since = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    log = shadow_controller.get_shadow_log(since=since, limit=limit)

    return {
        "count": len(log),
        "log": log,
    }


# Safety endpoints
@app.get("/safety/violations")
async def get_safety_violations(
    since_hours: Optional[int] = None,
):
    """Get safety violations"""
    since = None
    if since_hours:
        since = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    violations = safety_enforcer.get_violations(since=since)

    return {
        "count": len(violations),
        "violations": violations,
    }


@app.get("/safety/blocked-actions")
async def get_blocked_actions(
    since_hours: Optional[int] = None,
):
    """Get blocked execution actions"""
    since = None
    if since_hours:
        since = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    blocked = safety_enforcer.get_blocked_actions(since=since)

    return {
        "count": len(blocked),
        "blocked_actions": blocked,
    }


# Statistics endpoint
@app.get("/stats")
async def get_all_stats():
    """Get comprehensive statistics"""
    return {
        "telemetry": telemetry_ingester.get_stats(),
        "shadow_mode": shadow_controller.get_stats(),
        "authorization": authorization_interface.get_stats(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8062)
