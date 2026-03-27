"""
Founder Update API — FastAPI routes for the Founder Update Orchestrator.

Design Label: ARCH-007 — Founder Update API
Owner: Backend Team
Dependencies:
  - FounderUpdateOrchestrator (ARCH-007)
  - FastAPI

Exposes:
  GET  /api/founder/report
  GET  /api/founder/recommendations
  POST /api/founder/recommendations/{id}/accept
  POST /api/founder/recommendations/{id}/reject
  POST /api/founder/recommendations/{id}/defer
  GET  /api/founder/health
  GET  /api/founder/history

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
    from founder_update_orchestrator import (
        FounderUpdateOrchestrator,
        RecommendationType,
    )
    _ORCHESTRATOR_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    FounderUpdateOrchestrator = None  # type: ignore[assignment,misc]
    RecommendationType = None  # type: ignore[assignment]
    _ORCHESTRATOR_AVAILABLE = False
    logger.debug("FounderUpdateOrchestrator unavailable: %s", exc)

# ---------------------------------------------------------------------------
# Shared orchestrator instance (lazily initialised)
# ---------------------------------------------------------------------------

_orchestrator_instance: Optional[Any] = None


def _get_orchestrator() -> Any:
    """Return the shared orchestrator instance, initialising it on first call."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        if not _ORCHESTRATOR_AVAILABLE or FounderUpdateOrchestrator is None:
            raise RuntimeError("FounderUpdateOrchestrator is not available.")
        _orchestrator_instance = FounderUpdateOrchestrator()
    return _orchestrator_instance


def set_orchestrator(orchestrator: Any) -> None:
    """Override the shared orchestrator instance (useful for testing)."""
    global _orchestrator_instance
    _orchestrator_instance = orchestrator


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:

    class RejectRequest(BaseModel):  # type: ignore[valid-type]
        reason: Optional[str] = ""

    class DeferRequest(BaseModel):  # type: ignore[valid-type]
        until: str  # ISO 8601 datetime string

    class RecommendationOut(BaseModel):  # type: ignore[valid-type]
        recommendation_id: str
        recommendation_type: str
        subsystem_source: str
        title: str
        description: str
        priority: str
        confidence: float
        suggested_actions: List[str]
        metadata: Dict[str, Any]
        status: str
        created_at: str
        expires_at: Optional[str]

    class SubsystemReportOut(BaseModel):  # type: ignore[valid-type]
        subsystem_name: str
        status: str
        last_check: str
        metrics: Dict[str, Any]
        recommendations: List[RecommendationOut]

    class FounderReportOut(BaseModel):  # type: ignore[valid-type]
        report_id: str
        generated_at: str
        overall_health_score: float
        subsystem_reports: List[SubsystemReportOut]
        all_recommendations: List[RecommendationOut]
        summary: Dict[str, Any]

    class HealthOut(BaseModel):  # type: ignore[valid-type]
        overall_health_score: float
        subsystem_count: int
        subsystems: List[Dict[str, Any]]

else:  # pragma: no cover
    class RejectRequest:  # type: ignore[no-redef]
        pass

    class DeferRequest:  # type: ignore[no-redef]
        pass

    class RecommendationOut:  # type: ignore[no-redef]
        pass

    class SubsystemReportOut:  # type: ignore[no-redef]
        pass

    class FounderReportOut:  # type: ignore[no-redef]
        pass

    class HealthOut:  # type: ignore[no-redef]
        pass


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    router = APIRouter(
        prefix="/api/founder",
        tags=["founder-updates"],
    )

    @router.get("/report", response_model=FounderReportOut)
    def get_full_report() -> Dict[str, Any]:
        """Generate and return a full founder update report from all subsystems."""
        orchestrator = _get_orchestrator()
        report = orchestrator.generate_full_report()
        return report.to_dict()

    @router.get("/recommendations", response_model=List[RecommendationOut])
    def list_recommendations(
        subsystem: Optional[str] = Query(default=None, description="Filter by subsystem source"),
        priority: Optional[str] = Query(default=None, description="Filter by priority: critical, high, medium, low"),
        type: Optional[str] = Query(default=None, description="Filter by recommendation type"),
        status: Optional[str] = Query(default=None, description="Filter by status: pending, accepted, rejected, implemented, deferred"),
    ) -> List[Dict[str, Any]]:
        """Return filtered recommendations. Triggers a fresh report if none exist."""
        orchestrator = _get_orchestrator()

        rec_type = None
        if type is not None:
            try:
                rec_type = RecommendationType(type)
            except ValueError:
                valid = [t.value for t in RecommendationType]
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid recommendation type '{type}'. Valid values: {valid}",
                )

        if priority is not None and priority not in ("critical", "high", "medium", "low"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid priority '{priority}'. Valid values: critical, high, medium, low",
            )

        if status is not None and status not in ("pending", "accepted", "rejected", "implemented", "deferred"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid values: pending, accepted, rejected, implemented, deferred",
            )

        # Generate initial recommendations if none exist
        recs = orchestrator.get_recommendations(
            subsystem=subsystem,
            priority=priority,
            recommendation_type=rec_type,
            status=status,
        )
        if not recs:
            orchestrator.generate_full_report()
            recs = orchestrator.get_recommendations(
                subsystem=subsystem,
                priority=priority,
                recommendation_type=rec_type,
                status=status,
            )

        return [r.to_dict() for r in recs]

    @router.post("/recommendations/{recommendation_id}/accept", response_model=RecommendationOut)
    def accept_recommendation(recommendation_id: str) -> Dict[str, Any]:
        """Accept a pending recommendation."""
        orchestrator = _get_orchestrator()
        rec = orchestrator.get_recommendation(recommendation_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found.")

        success = orchestrator.accept_recommendation(recommendation_id)
        if not success:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot accept recommendation '{recommendation_id}' in status '{rec.status}'.",
            )

        rec = orchestrator.get_recommendation(recommendation_id)
        return rec.to_dict()  # type: ignore[union-attr]

    @router.post("/recommendations/{recommendation_id}/reject", response_model=RecommendationOut)
    def reject_recommendation(
        recommendation_id: str,
        body: RejectRequest = None,  # type: ignore[assignment]
    ) -> Dict[str, Any]:
        """Reject a pending or accepted recommendation."""
        orchestrator = _get_orchestrator()
        rec = orchestrator.get_recommendation(recommendation_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found.")

        reason = (body.reason or "") if body else ""
        success = orchestrator.reject_recommendation(recommendation_id, reason=reason)
        if not success:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot reject recommendation '{recommendation_id}' in status '{rec.status}'.",
            )

        rec = orchestrator.get_recommendation(recommendation_id)
        return rec.to_dict()  # type: ignore[union-attr]

    @router.post("/recommendations/{recommendation_id}/defer", response_model=RecommendationOut)
    def defer_recommendation(recommendation_id: str, body: DeferRequest) -> Dict[str, Any]:
        """Defer a pending recommendation until the given ISO datetime."""
        orchestrator = _get_orchestrator()
        rec = orchestrator.get_recommendation(recommendation_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found.")

        success = orchestrator.defer_recommendation(recommendation_id, until=body.until)
        if not success:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot defer recommendation '{recommendation_id}' in status '{rec.status}'.",
            )

        rec = orchestrator.get_recommendation(recommendation_id)
        return rec.to_dict()  # type: ignore[union-attr]

    @router.get("/health", response_model=HealthOut)
    def get_health() -> Dict[str, Any]:
        """Return overall system health score with per-subsystem breakdown."""
        orchestrator = _get_orchestrator()
        report = orchestrator.generate_full_report()
        subsystems = [
            {
                "subsystem_name": sr.subsystem_name,
                "status": sr.status,
                "last_check": sr.last_check,
                "metrics": sr.metrics,
            }
            for sr in report.subsystem_reports
        ]
        return {
            "overall_health_score": report.overall_health_score,
            "subsystem_count": len(subsystems),
            "subsystems": subsystems,
        }

    @router.get("/history")
    def get_history() -> List[Dict[str, Any]]:
        """Return historical reports (summary only, newest last)."""
        orchestrator = _get_orchestrator()
        reports = orchestrator.get_reports()
        return [
            {
                "report_id": r.report_id,
                "generated_at": r.generated_at,
                "overall_health_score": r.overall_health_score,
                "total_recommendations": r.summary.get("total_recommendations", 0),
                "summary": r.summary,
            }
            for r in reports
        ]

else:  # pragma: no cover
    router = None  # type: ignore[assignment]
    logger.warning("FastAPI not available — founder_update_api routes not registered.")
