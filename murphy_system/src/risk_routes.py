# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Risk API Routes — Murphy System

FastAPI router exposing the full risk management, trajectory,
graduation, emergency stop, and audit-log surfaces.

Endpoints
---------
  GET  /api/trading/risk/assessment             — Current risk assessment
  GET  /api/trading/risk/trajectory/{product_id} — Trajectory analysis for asset
  GET  /api/trading/risk/costs                  — Hidden cost dashboard
  GET  /api/trading/graduation/status           — Graduation status + criteria
  POST /api/trading/graduation/confirm          — Confirm graduation (enable live)
  POST /api/trading/graduation/override         — Manual status override (admin)
  GET  /api/trading/emergency/status            — Emergency stop status
  POST /api/trading/emergency/trigger           — Manually trigger emergency stop
  POST /api/trading/emergency/reset             — Reset emergency stop (cooldown check)
  GET  /api/trading/audit/log                   — Query audit log
  GET  /api/trading/audit/summary               — Aggregate audit statistics
  GET  /api/trading/audit/export                — Export audit log as CSV

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException, Query
    from fastapi.responses import JSONResponse, Response
    from pydantic import BaseModel, Field
    _HAS_FASTAPI = True
except ImportError:  # pragma: no cover
    _HAS_FASTAPI = False
    APIRouter = None  # type: ignore[assignment,misc]

from dynamic_risk_manager import DynamicRiskManager
from emergency_stop import TradingEmergencyStop
from graduation_controller import GraduationController, GraduationStatus
from hidden_cost_tracker import HiddenCostTracker
from trajectory_engine import Candle, TrajectoryEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton service instances (lazy-initialized)
# ---------------------------------------------------------------------------

_risk_manager:   Optional[DynamicRiskManager]  = None
_traj_engine:    Optional[TrajectoryEngine]    = None
_cost_tracker:   Optional[HiddenCostTracker]   = None
_graduation:     Optional[GraduationController] = None
_emergency_stop: Optional[TradingEmergencyStop] = None


def _get_risk_manager() -> DynamicRiskManager:
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = DynamicRiskManager()
    return _risk_manager


def _get_trajectory_engine() -> TrajectoryEngine:
    global _traj_engine
    if _traj_engine is None:
        _traj_engine = TrajectoryEngine()
    return _traj_engine


def _get_cost_tracker() -> HiddenCostTracker:
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = HiddenCostTracker()
    return _cost_tracker


def _get_graduation() -> GraduationController:
    global _graduation
    if _graduation is None:
        _graduation = GraduationController()
    return _graduation


def _get_emergency_stop() -> TradingEmergencyStop:
    global _emergency_stop
    if _emergency_stop is None:
        _emergency_stop = TradingEmergencyStop()
    return _emergency_stop


def inject_services(
    risk_manager:   Optional[DynamicRiskManager]   = None,
    traj_engine:    Optional[TrajectoryEngine]     = None,
    cost_tracker:   Optional[HiddenCostTracker]    = None,
    graduation:     Optional[GraduationController] = None,
    emergency_stop: Optional[TradingEmergencyStop] = None,
) -> None:
    """Inject pre-built service instances (useful for testing and app startup)."""
    global _risk_manager, _traj_engine, _cost_tracker, _graduation, _emergency_stop
    if risk_manager:
        _risk_manager = risk_manager
    if traj_engine:
        _traj_engine = traj_engine
    if cost_tracker:
        _cost_tracker = cost_tracker
    if graduation:
        _graduation = graduation
    if emergency_stop:
        _emergency_stop = emergency_stop


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

if _HAS_FASTAPI:

    # ── Request / Response models ────────────────────────────────────────

    class RiskAssessmentRequest(BaseModel):
        prices:      List[float] = Field(..., min_length=5, description="Recent close prices (oldest first)")
        entry_price: float       = Field(..., gt=0)
        side:        str         = Field("buy", pattern="^(buy|sell)$")
        win_rate:    float       = Field(0.5, ge=0, le=1)
        avg_win:     float       = Field(1.0, gt=0)
        avg_loss:    float       = Field(1.0, gt=0)
        volumes:     Optional[List[float]] = None

    class TrajectoryRequest(BaseModel):
        candles: List[Dict[str, Any]] = Field(
            ..., description="OHLCV candles: [{open,high,low,close,volume}]"
        )

    class GraduationConfirmRequest(BaseModel):
        confirmed_by: str = Field("user", min_length=1)

    class GraduationOverrideRequest(BaseModel):
        status:      str = Field(..., description="Target status value")
        reason:      str = Field(..., min_length=3)
        override_by: str = Field("admin")

    class EmergencyTriggerRequest(BaseModel):
        reason: str = Field("Manual emergency stop", min_length=3)

    class EmergencyResetRequest(BaseModel):
        reset_by: str = Field("operator", min_length=1)

    # ── Router ──────────────────────────────────────────────────────────

    def create_risk_router(
        risk_manager:   Optional[DynamicRiskManager]   = None,
        traj_engine:    Optional[TrajectoryEngine]     = None,
        cost_tracker:   Optional[HiddenCostTracker]    = None,
        graduation:     Optional[GraduationController] = None,
        emergency_stop: Optional[TradingEmergencyStop] = None,
    ) -> "APIRouter":
        """
        Create and return the risk management APIRouter.

        Pass pre-built service instances to avoid relying on module-level
        singletons (useful during testing).
        """
        inject_services(risk_manager, traj_engine, cost_tracker, graduation, emergency_stop)
        router = APIRouter(prefix="/api/trading", tags=["Trading Risk"])

        # ── Risk assessment ──────────────────────────────────────────────

        @router.post("/risk/assessment", summary="Compute a risk assessment")
        async def post_risk_assessment(body: RiskAssessmentRequest) -> JSONResponse:
            mgr = _get_risk_manager()
            try:
                assessment = mgr.assess(
                    prices      = body.prices,
                    entry_price = body.entry_price,
                    side        = body.side,
                    win_rate    = body.win_rate,
                    avg_win     = body.avg_win,
                    avg_loss    = body.avg_loss,
                    volumes     = body.volumes,
                )
                return JSONResponse({"success": True, "assessment": assessment.to_dict()})
            except Exception as exc:
                logger.exception("risk/assessment error")
                raise HTTPException(status_code=500, detail=str(exc)) from exc

        @router.get("/risk/assessment", summary="Get current risk summary")
        async def get_risk_summary() -> JSONResponse:
            mgr = _get_risk_manager()
            return JSONResponse({"success": True, "summary": mgr.get_summary()})

        # ── Trajectory ──────────────────────────────────────────────────

        @router.post(
            "/risk/trajectory/{product_id}",
            summary="Trajectory analysis for an asset",
        )
        async def post_trajectory(
            product_id: str, body: TrajectoryRequest
        ) -> JSONResponse:
            engine = _get_trajectory_engine()
            try:
                raw = body.candles
                candles = [
                    Candle(
                        open   = float(c.get("open",   c.get("o", 0))),
                        high   = float(c.get("high",   c.get("h", 0))),
                        low    = float(c.get("low",    c.get("l", 0))),
                        close  = float(c.get("close",  c.get("c", 0))),
                        volume = float(c.get("volume", c.get("v", 0))),
                    )
                    for c in raw
                ]
                analysis = engine.analyze(product_id, candles)
                return JSONResponse({"success": True, "analysis": analysis.to_dict()})
            except Exception as exc:
                logger.exception("risk/trajectory error")
                raise HTTPException(status_code=500, detail=str(exc)) from exc

        @router.get(
            "/risk/trajectory/{product_id}",
            summary="Trailing stop state for an active position",
        )
        async def get_trailing_stop(product_id: str) -> JSONResponse:
            engine = _get_trajectory_engine()
            state = engine.get_trailing_stop(product_id)
            if state is None:
                raise HTTPException(status_code=404, detail=f"No active trailing stop for {product_id!r}.")
            return JSONResponse({"success": True, "trailing_stop": state})

        # ── Hidden costs ─────────────────────────────────────────────────

        @router.get("/risk/costs", summary="Hidden cost dashboard data")
        async def get_cost_dashboard() -> JSONResponse:
            tracker = _get_cost_tracker()
            return JSONResponse({"success": True, "costs": tracker.get_dashboard()})

        # ── Graduation ───────────────────────────────────────────────────

        @router.get("/graduation/status", summary="Graduation status and criteria")
        async def get_graduation_status() -> JSONResponse:
            grad = _get_graduation()
            return JSONResponse({"success": True, "graduation": grad.get_status()})

        @router.post("/graduation/confirm", summary="Confirm graduation to live trading")
        async def confirm_graduation(body: GraduationConfirmRequest) -> JSONResponse:
            grad = _get_graduation()
            ok, msg = grad.confirm_graduation(body.confirmed_by)
            if not ok:
                raise HTTPException(status_code=400, detail=msg)
            return JSONResponse({"success": True, "message": msg})

        @router.post("/graduation/override", summary="Manually override graduation status")
        async def override_graduation(body: GraduationOverrideRequest) -> JSONResponse:
            grad = _get_graduation()
            try:
                new_status = GraduationStatus(body.status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status {body.status!r}. Valid: {[s.value for s in GraduationStatus]}",
                )
            ok, msg = grad.override_status(new_status, body.reason, body.override_by)
            return JSONResponse({"success": ok, "message": msg})

        @router.get("/graduation/history", summary="Graduation event history")
        async def get_graduation_history() -> JSONResponse:
            grad = _get_graduation()
            return JSONResponse({"success": True, "history": grad.get_history()})

        # ── Emergency stop ───────────────────────────────────────────────

        @router.get("/emergency/status", summary="Emergency stop status")
        async def get_emergency_status() -> JSONResponse:
            es = _get_emergency_stop()
            return JSONResponse({"success": True, "emergency_stop": es.get_status()})

        @router.post("/emergency/trigger", summary="Manually trigger emergency stop")
        async def trigger_emergency(body: EmergencyTriggerRequest) -> JSONResponse:
            es = _get_emergency_stop()
            event = es.trigger_manual(body.reason)
            return JSONResponse({"success": True, "event": event.to_dict()})

        @router.post("/emergency/reset", summary="Reset emergency stop (cooldown required)")
        async def reset_emergency(body: EmergencyResetRequest) -> JSONResponse:
            es = _get_emergency_stop()
            ok, msg = es.reset(body.reset_by)
            if not ok:
                raise HTTPException(status_code=400, detail=msg)
            return JSONResponse({"success": True, "message": msg})

        # ── Audit log ────────────────────────────────────────────────────

        @router.get("/audit/log", summary="Query trading audit log")
        async def get_audit_log(
            strategy_id: Optional[str] = Query(None),
            pair:        Optional[str] = Query(None),
            outcome:     Optional[str] = Query(None),
            since:       Optional[str] = Query(None, description="ISO timestamp"),
            until:       Optional[str] = Query(None, description="ISO timestamp"),
            limit:       int           = Query(100, ge=1, le=1000),
        ) -> JSONResponse:
            from audit_logger import TradeOutcome, TradingAuditLogger
            logger_inst = _get_audit_logger()
            outcome_enum = None
            if outcome:
                try:
                    outcome_enum = TradeOutcome(outcome)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid outcome: {outcome!r}")
            entries = logger_inst.query(
                strategy_id=strategy_id,
                pair=pair,
                outcome=outcome_enum,
                since=since,
                until=until,
                limit=limit,
            )
            return JSONResponse({"success": True, "entries": entries, "count": len(entries)})

        @router.get("/audit/summary", summary="Audit log aggregate statistics")
        async def get_audit_summary() -> JSONResponse:
            logger_inst = _get_audit_logger()
            return JSONResponse({"success": True, "summary": logger_inst.get_summary()})

        @router.get("/audit/export", summary="Export audit log as CSV")
        async def export_audit_csv(
            strategy_id: Optional[str] = Query(None),
            since:       Optional[str] = Query(None),
        ) -> Response:
            logger_inst = _get_audit_logger()
            csv_data = logger_inst.export_csv(strategy_id=strategy_id, since=since)
            return Response(
                content=csv_data,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
            )

        return router


# ---------------------------------------------------------------------------
# Audit logger singleton (shared across the router)
# ---------------------------------------------------------------------------

_audit_logger_inst: Optional[Any] = None


def _get_audit_logger() -> Any:
    global _audit_logger_inst
    if _audit_logger_inst is None:
        from audit_logger import TradingAuditLogger
        _audit_logger_inst = TradingAuditLogger()
    return _audit_logger_inst


def inject_audit_logger(inst: Any) -> None:
    global _audit_logger_inst
    _audit_logger_inst = inst
