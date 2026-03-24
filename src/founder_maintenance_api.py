"""
Founder Maintenance API — FastAPI routes for the Founder Maintenance
Recommendation Engine.

Design Label: FOUNDER-001 — Founder Maintenance API
Owner: Backend Team
Dependencies:
  - FounderMaintenanceRecommendationEngine
  - FastAPI

Exposes:
  GET  /api/founder/maintenance/recommendations
  GET  /api/founder/maintenance/recommendations/{id}
  POST /api/founder/maintenance/recommendations/{id}/approve
  POST /api/founder/maintenance/recommendations/{id}/reject
  POST /api/founder/maintenance/recommendations/{id}/apply
  GET  /api/founder/maintenance/summary
  GET  /api/founder/maintenance/subsystems
  POST /api/founder/maintenance/scan

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
    from founder_maintenance_recommendation_engine import (
        FounderMaintenanceRecommendationEngine,
        RecommendationCategory,
        RecommendationPriority,
        RecommendationStatus,
    )
    _ENGINE_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    FounderMaintenanceRecommendationEngine = None  # type: ignore[assignment,misc]
    RecommendationCategory = None  # type: ignore[assignment]
    RecommendationPriority = None  # type: ignore[assignment]
    RecommendationStatus = None  # type: ignore[assignment]
    _ENGINE_AVAILABLE = False
    logger.debug("FounderMaintenanceRecommendationEngine unavailable: %s", exc)

# ---------------------------------------------------------------------------
# Shared engine instance (lazily initialised)
# ---------------------------------------------------------------------------

_engine_instance: Optional[Any] = None


def _get_engine() -> Any:
    """Return the shared engine instance, initialising it on first call."""
    global _engine_instance
    if _engine_instance is None:
        if not _ENGINE_AVAILABLE or FounderMaintenanceRecommendationEngine is None:
            raise RuntimeError("FounderMaintenanceRecommendationEngine is not available.")
        _engine_instance = FounderMaintenanceRecommendationEngine()
    return _engine_instance


def set_engine(engine: Any) -> None:
    """Override the shared engine instance (useful for testing)."""
    global _engine_instance
    _engine_instance = engine


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:

    class RejectRequest(BaseModel):  # type: ignore[valid-type]
        reason: Optional[str] = ""

    class RecommendationOut(BaseModel):  # type: ignore[valid-type]
        id: str
        subsystem: str
        category: str
        priority: str
        title: str
        description: str
        suggested_action: str
        auto_applicable: bool
        status: str
        created_at: str
        expires_at: Optional[str]
        score: float
        metadata: Dict[str, Any]

    class SubsystemOut(BaseModel):  # type: ignore[valid-type]
        name: str
        description: str
        criticality: int
        registration_id: str
        last_health_status: Optional[Dict[str, Any]]
        last_polled_at: Optional[str]

else:  # pragma: no cover
    class RejectRequest:  # type: ignore[no-redef]
        pass

    class RecommendationOut:  # type: ignore[no-redef]
        pass

    class SubsystemOut:  # type: ignore[no-redef]
        pass


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    router = APIRouter(
        prefix="/api/founder/maintenance",
        tags=["founder-maintenance"],
    )

    @router.get("/recommendations", response_model=List[RecommendationOut])
    def list_recommendations(
        subsystem: Optional[str] = Query(default=None),
        category: Optional[str] = Query(default=None),
        priority: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
    ) -> List[Dict[str, Any]]:
        """List maintenance recommendations with optional filters."""
        engine = _get_engine()

        cat = None
        if category is not None:
            try:
                cat = RecommendationCategory(category.upper())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category '{category}'. Valid: {[c.value for c in RecommendationCategory]}",
                )

        pri = None
        if priority is not None:
            try:
                pri = RecommendationPriority(priority.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid priority '{priority}'. Valid: {[p.value for p in RecommendationPriority]}",
                )

        sta = None
        if status is not None:
            try:
                sta = RecommendationStatus(status.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status '{status}'. Valid: {[s.value for s in RecommendationStatus]}",
                )

        recs = engine.list_recommendations(
            subsystem=subsystem,
            category=cat,
            priority=pri,
            status=sta,
        )
        return [r.to_dict() for r in recs]

    @router.get("/recommendations/{recommendation_id}", response_model=RecommendationOut)
    def get_recommendation(recommendation_id: str) -> Dict[str, Any]:
        """Get a single recommendation by ID."""
        engine = _get_engine()
        rec = engine.get_recommendation(recommendation_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found.")
        return rec.to_dict()

    @router.post("/recommendations/{recommendation_id}/approve", response_model=RecommendationOut)
    def approve_recommendation(recommendation_id: str) -> Dict[str, Any]:
        """Approve a pending recommendation."""
        engine = _get_engine()
        try:
            rec = engine.approve(recommendation_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found.")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return rec.to_dict()

    @router.post("/recommendations/{recommendation_id}/reject", response_model=RecommendationOut)
    def reject_recommendation(
        recommendation_id: str,
        body: RejectRequest = None,  # type: ignore[assignment]
    ) -> Dict[str, Any]:
        """Reject a pending or approved recommendation."""
        engine = _get_engine()
        reason = (body.reason or "") if body else ""
        try:
            rec = engine.reject(recommendation_id, reason=reason)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found.")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return rec.to_dict()

    @router.post("/recommendations/{recommendation_id}/apply", response_model=RecommendationOut)
    def apply_recommendation(recommendation_id: str) -> Dict[str, Any]:
        """Apply an approved (or auto-applicable) recommendation."""
        engine = _get_engine()
        try:
            rec = engine.apply(recommendation_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found.")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return rec.to_dict()

    @router.get("/summary")
    def get_summary() -> Dict[str, Any]:
        """Return a dashboard summary for the founder."""
        engine = _get_engine()
        return engine.get_summary()

    @router.get("/subsystems", response_model=List[SubsystemOut])
    def list_subsystems() -> List[Dict[str, Any]]:
        """List all registered subsystems and their health status."""
        engine = _get_engine()
        return engine.list_subsystems()

    @router.post("/scan")
    def trigger_scan() -> Dict[str, Any]:
        """Trigger an immediate scan of all registered subsystems."""
        engine = _get_engine()
        return engine.scan_all()

else:  # pragma: no cover
    router = None  # type: ignore[assignment]
    logger.warning("FastAPI not available — founder_maintenance_api routes not registered.")
