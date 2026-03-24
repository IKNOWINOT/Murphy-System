"""
System Update Recommendation Engine API — FastAPI router.

Design Label: ARCH-020-API
Owner: Backend Team / Platform Engineering
Dependencies:
  - SystemUpdateRecommendationEngine (ARCH-020)
  - FastAPI

Exposes:
  GET  /api/system-updates/status
  GET  /api/system-updates/recommendations
  GET  /api/system-updates/recommendations/{rec_id}
  PUT  /api/system-updates/recommendations/{rec_id}/status
  POST /api/system-updates/maintenance/scan
  GET  /api/system-updates/maintenance/recommendations
  POST /api/system-updates/sdk/scan
  GET  /api/system-updates/sdk/recommendations
  POST /api/system-updates/auto-update/scan
  GET  /api/system-updates/auto-update/recommendations
  POST /api/system-updates/bug-responses/ingest
  GET  /api/system-updates/bug-responses/recommendations
  POST /api/system-updates/operations/analyze
  GET  /api/system-updates/operations/recommendations
  POST /api/system-updates/full-scan

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, HTTPException, Query
    from pydantic import BaseModel
    _FASTAPI_AVAILABLE = True
except Exception:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment,misc]
    HTTPException = None  # type: ignore[assignment,misc]
    BaseModel = object  # type: ignore[assignment,misc]
    Query = None  # type: ignore[assignment]
    _FASTAPI_AVAILABLE = False

try:
    from system_update_recommendation_engine import (
        BugReportInput,
        SystemUpdateRecommendationEngine,
        CATEGORY_MAINTENANCE,
        CATEGORY_SDK_UPDATE,
        CATEGORY_AUTO_UPDATE,
        CATEGORY_BUG_RESPONSE,
        CATEGORY_OPERATIONS,
        STATUS_PENDING,
        STATUS_APPROVED,
        STATUS_DISMISSED,
    )
    _ENGINE_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    SystemUpdateRecommendationEngine = None  # type: ignore[assignment,misc]
    BugReportInput = None  # type: ignore[assignment,misc]
    CATEGORY_MAINTENANCE = "maintenance"  # type: ignore[assignment]
    CATEGORY_SDK_UPDATE = "sdk_update"  # type: ignore[assignment]
    CATEGORY_AUTO_UPDATE = "auto_update"  # type: ignore[assignment]
    CATEGORY_BUG_RESPONSE = "bug_response"  # type: ignore[assignment]
    CATEGORY_OPERATIONS = "operations"  # type: ignore[assignment]
    STATUS_PENDING = "pending"  # type: ignore[assignment]
    STATUS_APPROVED = "approved"  # type: ignore[assignment]
    STATUS_DISMISSED = "dismissed"  # type: ignore[assignment]
    _ENGINE_AVAILABLE = False
    logger.debug("SystemUpdateRecommendationEngine unavailable: %s", exc)

# ---------------------------------------------------------------------------
# Shared engine instance (lazily initialised)
# ---------------------------------------------------------------------------

_engine_instance: Optional[Any] = None


def _get_engine() -> Any:
    """Return the shared engine instance, initialising it on first call."""
    global _engine_instance
    if _engine_instance is None:
        if not _ENGINE_AVAILABLE or SystemUpdateRecommendationEngine is None:
            raise RuntimeError("SystemUpdateRecommendationEngine is not available.")
        _engine_instance = SystemUpdateRecommendationEngine()
    return _engine_instance


def set_engine(engine: Any) -> None:
    """Override the shared engine instance (useful for testing)."""
    global _engine_instance
    _engine_instance = engine


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_VALID_STATUSES = {STATUS_PENDING, STATUS_APPROVED, STATUS_DISMISSED, "executed"}
_VALID_CATEGORIES = {
    CATEGORY_MAINTENANCE,
    CATEGORY_SDK_UPDATE,
    CATEGORY_AUTO_UPDATE,
    CATEGORY_BUG_RESPONSE,
    CATEGORY_OPERATIONS,
}
_VALID_PRIORITIES = {"critical", "high", "medium", "low", "informational"}


def _run_subsystem_scan(engine: Any, subsystem_attr: str) -> List[Dict[str, Any]]:
    """Run a single subsystem's generate_recommendations() and store results.

    Args:
        engine: The SystemUpdateRecommendationEngine instance.
        subsystem_attr: Attribute name of the subsystem on the engine.

    Returns:
        List of new recommendation dicts produced by the subsystem.
    """
    subsystem = getattr(engine, subsystem_attr)
    recs = subsystem.generate_recommendations()
    with engine._lock:
        for rec in recs:
            engine._recommendations[rec.recommendation_id] = rec
    engine._persist_recommendations()
    return [r.to_dict() for r in recs]


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:

    class RecommendationStatusUpdate(BaseModel):  # type: ignore[valid-type]
        action: str  # "approve" | "dismiss"
        reason: Optional[str] = ""
        approved_by: Optional[str] = "founder"

    class BugReportIngestRequest(BaseModel):  # type: ignore[valid-type]
        report_id: Optional[str] = None
        title: str
        description: str
        component: str = "unknown"
        severity: str = "medium"
        stack_trace: str = ""
        reporter: str = "system"
        metadata: Dict[str, Any] = {}

    class RecommendationOut(BaseModel):  # type: ignore[valid-type]
        recommendation_id: str
        category: str
        priority: str
        title: str
        description: str
        affected_subsystems: List[str]
        proposed_actions: List[Dict[str, Any]]
        confidence_score: float
        requires_human_approval: bool
        status: str
        created_at: str
        updated_at: Optional[str]
        metadata: Dict[str, Any]

else:  # pragma: no cover
    class RecommendationStatusUpdate:  # type: ignore[no-redef]
        pass

    class BugReportIngestRequest:  # type: ignore[no-redef]
        pass

    class RecommendationOut:  # type: ignore[no-redef]
        pass


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    router = APIRouter(
        prefix="/api/system-updates",
        tags=["system-updates"],
    )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @router.get("/status")
    def get_status() -> Dict[str, Any]:
        """Return current engine status and summary."""
        engine = _get_engine()
        return engine.get_status()

    # ------------------------------------------------------------------
    # Recommendations — generic CRUD
    # ------------------------------------------------------------------

    @router.get("/recommendations", response_model=List[RecommendationOut])
    def list_recommendations(
        category: Optional[str] = Query(default=None),
        priority: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
    ) -> List[Dict[str, Any]]:
        """List all recommendations, filterable by category, priority, and status."""
        engine = _get_engine()

        if category is not None and category not in _VALID_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category '{category}'. Valid: {sorted(_VALID_CATEGORIES)}",
            )
        if priority is not None and priority not in _VALID_PRIORITIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid priority '{priority}'. Valid: {sorted(_VALID_PRIORITIES)}",
            )
        if status is not None and status not in _VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid: {sorted(_VALID_STATUSES)}",
            )

        recs = engine.get_recommendations(
            category=category,
            priority=priority,
            status=status,
        )
        return [r.to_dict() for r in recs]

    @router.get("/recommendations/{rec_id}", response_model=RecommendationOut)
    def get_recommendation(rec_id: str) -> Dict[str, Any]:
        """Get a specific recommendation by ID."""
        engine = _get_engine()
        rec = engine.get_recommendation(rec_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"Recommendation '{rec_id}' not found.")
        return rec.to_dict()

    @router.put("/recommendations/{rec_id}/status")
    def update_recommendation_status(
        rec_id: str,
        body: RecommendationStatusUpdate,
    ) -> Dict[str, Any]:
        """Approve or dismiss a recommendation.

        Body:
            action: "approve" or "dismiss"
            reason: optional dismissal reason
            approved_by: identifier of the approver (default: "founder")
        """
        engine = _get_engine()
        action = body.action.lower() if body.action else ""

        if action == "approve":
            approved_by = body.approved_by or "founder"
            success = engine.approve_recommendation(rec_id, approved_by=approved_by)
            if not success:
                rec = engine.get_recommendation(rec_id)
                if rec is None:
                    raise HTTPException(status_code=404, detail=f"Recommendation '{rec_id}' not found.")
                raise HTTPException(
                    status_code=422,
                    detail=f"Recommendation '{rec_id}' cannot be approved (current status: {rec.status}).",
                )
        elif action == "dismiss":
            reason = body.reason or ""
            success = engine.dismiss_recommendation(rec_id, reason=reason)
            if not success:
                rec = engine.get_recommendation(rec_id)
                if rec is None:
                    raise HTTPException(status_code=404, detail=f"Recommendation '{rec_id}' not found.")
                raise HTTPException(
                    status_code=422,
                    detail=f"Recommendation '{rec_id}' cannot be dismissed (current status: {rec.status}).",
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action '{body.action}'. Valid: approve, dismiss",
            )

        rec = engine.get_recommendation(rec_id)
        return rec.to_dict() if rec else {"recommendation_id": rec_id, "status": action + "d"}

    # ------------------------------------------------------------------
    # Maintenance domain
    # ------------------------------------------------------------------

    @router.post("/maintenance/scan")
    def maintenance_scan() -> Dict[str, Any]:
        """Trigger a maintenance integration scan."""
        engine = _get_engine()
        new_recs = _run_subsystem_scan(engine, "maintenance_advisor")
        return {
            "status": "ok",
            "domain": "maintenance",
            "new_recommendations": len(new_recs),
            "recommendations": new_recs,
        }

    @router.get("/maintenance/recommendations", response_model=List[RecommendationOut])
    def get_maintenance_recommendations(
        priority: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
    ) -> List[Dict[str, Any]]:
        """Get maintenance-specific recommendations."""
        engine = _get_engine()
        if priority is not None and priority not in _VALID_PRIORITIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid priority '{priority}'. Valid: {sorted(_VALID_PRIORITIES)}",
            )
        if status is not None and status not in _VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid: {sorted(_VALID_STATUSES)}",
            )
        recs = engine.get_recommendations(
            category=CATEGORY_MAINTENANCE,
            priority=priority,
            status=status,
        )
        return [r.to_dict() for r in recs]

    # ------------------------------------------------------------------
    # SDK update domain
    # ------------------------------------------------------------------

    @router.post("/sdk/scan")
    def sdk_scan() -> Dict[str, Any]:
        """Trigger an SDK/dependency update scan."""
        engine = _get_engine()
        new_recs = _run_subsystem_scan(engine, "sdk_tracker")
        return {
            "status": "ok",
            "domain": "sdk_update",
            "new_recommendations": len(new_recs),
            "recommendations": new_recs,
        }

    @router.get("/sdk/recommendations", response_model=List[RecommendationOut])
    def get_sdk_recommendations(
        priority: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
    ) -> List[Dict[str, Any]]:
        """Get SDK update recommendations."""
        engine = _get_engine()
        if priority is not None and priority not in _VALID_PRIORITIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid priority '{priority}'. Valid: {sorted(_VALID_PRIORITIES)}",
            )
        if status is not None and status not in _VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid: {sorted(_VALID_STATUSES)}",
            )
        recs = engine.get_recommendations(
            category=CATEGORY_SDK_UPDATE,
            priority=priority,
            status=status,
        )
        return [r.to_dict() for r in recs]

    # ------------------------------------------------------------------
    # Auto-update domain
    # ------------------------------------------------------------------

    @router.post("/auto-update/scan")
    def auto_update_scan() -> Dict[str, Any]:
        """Trigger an auto-update assessment."""
        engine = _get_engine()
        new_recs = _run_subsystem_scan(engine, "auto_update_orchestrator")
        return {
            "status": "ok",
            "domain": "auto_update",
            "new_recommendations": len(new_recs),
            "recommendations": new_recs,
        }

    @router.get("/auto-update/recommendations", response_model=List[RecommendationOut])
    def get_auto_update_recommendations(
        priority: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
    ) -> List[Dict[str, Any]]:
        """Get auto-update recommendations."""
        engine = _get_engine()
        if priority is not None and priority not in _VALID_PRIORITIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid priority '{priority}'. Valid: {sorted(_VALID_PRIORITIES)}",
            )
        if status is not None and status not in _VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid: {sorted(_VALID_STATUSES)}",
            )
        recs = engine.get_recommendations(
            category=CATEGORY_AUTO_UPDATE,
            priority=priority,
            status=status,
        )
        return [r.to_dict() for r in recs]

    # ------------------------------------------------------------------
    # Bug responses domain
    # ------------------------------------------------------------------

    @router.post("/bug-responses/ingest")
    def ingest_bug_report(body: BugReportIngestRequest) -> Dict[str, Any]:
        """Ingest a bug report for automated triage and auto-response generation."""
        engine = _get_engine()
        if BugReportInput is None:
            raise HTTPException(status_code=503, detail="BugReportInput not available.")

        import uuid as _uuid
        report_id = body.report_id or str(_uuid.uuid4())

        report = BugReportInput(
            report_id=report_id,
            title=body.title,
            description=body.description,
            component=body.component,
            severity=body.severity,
            stack_trace=body.stack_trace,
            reporter=body.reporter,
            metadata=body.metadata,
        )

        try:
            response = engine.ingest_bug_report(report)
        except Exception as exc:
            logger.error("Bug report ingestion failed: %s", exc)
            raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")

        return response

    @router.get("/bug-responses/recommendations", response_model=List[RecommendationOut])
    def get_bug_response_recommendations(
        priority: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
    ) -> List[Dict[str, Any]]:
        """Get bug report auto-response recommendations."""
        engine = _get_engine()
        if priority is not None and priority not in _VALID_PRIORITIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid priority '{priority}'. Valid: {sorted(_VALID_PRIORITIES)}",
            )
        if status is not None and status not in _VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid: {sorted(_VALID_STATUSES)}",
            )
        recs = engine.get_recommendations(
            category=CATEGORY_BUG_RESPONSE,
            priority=priority,
            status=status,
        )
        return [r.to_dict() for r in recs]

    # ------------------------------------------------------------------
    # Operations analysis domain
    # ------------------------------------------------------------------

    @router.post("/operations/analyze")
    def operations_analyze() -> Dict[str, Any]:
        """Trigger a system operations analysis."""
        engine = _get_engine()
        new_recs = _run_subsystem_scan(engine, "operations_analyzer")
        health = engine.operations_analyzer.compute_health_score()
        return {
            "status": "ok",
            "domain": "operations",
            "health": health,
            "new_recommendations": len(new_recs),
            "recommendations": new_recs,
        }

    @router.get("/operations/recommendations", response_model=List[RecommendationOut])
    def get_operations_recommendations(
        priority: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
    ) -> List[Dict[str, Any]]:
        """Get system operations recommendations."""
        engine = _get_engine()
        if priority is not None and priority not in _VALID_PRIORITIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid priority '{priority}'. Valid: {sorted(_VALID_PRIORITIES)}",
            )
        if status is not None and status not in _VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid: {sorted(_VALID_STATUSES)}",
            )
        recs = engine.get_recommendations(
            category=CATEGORY_OPERATIONS,
            priority=priority,
            status=status,
        )
        return [r.to_dict() for r in recs]

    # ------------------------------------------------------------------
    # Full scan
    # ------------------------------------------------------------------

    @router.post("/full-scan")
    def full_scan() -> Dict[str, Any]:
        """Trigger a full scan across all 5 recommendation domains."""
        engine = _get_engine()
        new_recs = engine.refresh_all()
        status_summary = engine.get_status()
        return {
            "status": "ok",
            "domains_scanned": [
                "maintenance",
                "sdk_update",
                "auto_update",
                "bug_response",
                "operations",
            ],
            "new_recommendations": len(new_recs),
            "engine_status": status_summary,
        }

else:  # pragma: no cover
    router = None  # type: ignore[assignment]
    logger.warning("FastAPI not available — system_update_api routes not registered.")
