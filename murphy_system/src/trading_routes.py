# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Trading Routes — Murphy System

FastAPI route surface for the full trading automation stack (PR 4/4).

Endpoints
---------
Orchestrator:
  POST /api/trading/start          — Start the orchestrator
  POST /api/trading/stop           — Stop the orchestrator
  GET  /api/trading/status         — Full system status
  GET  /api/trading/mode           — Current mode (paper/live)
  POST /api/trading/mode           — Switch mode

Portfolio:
  GET  /api/trading/portfolio      — Full portfolio state
  GET  /api/trading/portfolio/history — Portfolio value history

Positions:
  GET  /api/trading/positions      — All open positions
  GET  /api/trading/positions/{id} — Single position

Trades:
  GET  /api/trading/trades         — Trade history
  GET  /api/trading/trades/today   — Today's trades

Profit sweep:
  GET  /api/trading/sweep/status   — Next sweep info
  GET  /api/trading/sweep/history  — Sweep history (last 30 records)
  POST /api/trading/sweep/trigger  — Manually trigger sweep (dry-run default)
  GET  /api/trading/sweep/atom-balance — ATOM staking info

Emergency:
  GET  /api/trading/emergency/status  — Emergency stop system status
  POST /api/trading/emergency/trigger — Trigger emergency stop

Risk:
  GET  /api/trading/risk/assessment   — Current risk assessment

Graduation:
  GET  /api/trading/graduation/status — Paper-trading graduation status

Dashboard:
  GET  /ui/trading                 — Serve the trading dashboard HTML
  GET  /ui/trading-dashboard       — Alias

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ModeSwitchRequest(BaseModel):
    mode: str   # "paper" | "live"


class SweepTriggerRequest(BaseModel):
    dry_run:          bool  = True
    portfolio_value:  Optional[float] = None
    open_positions:   float = 0.0
    pending_orders:   float = 0.0


# ---------------------------------------------------------------------------
# Singletons — resolved lazily so the file is importable without heavy deps
# ---------------------------------------------------------------------------

_orchestrator:  Optional[Any] = None
_sweeper:       Optional[Any] = None


def _get_orchestrator() -> Any:
    global _orchestrator
    if _orchestrator is None:
        from trading_orchestrator import TradingOrchestrator
        _orchestrator = TradingOrchestrator()
    return _orchestrator


def _get_sweeper() -> Any:
    global _sweeper
    if _sweeper is None:
        from profit_sweep import ProfitSweep
        _sweeper = ProfitSweep()
    return _sweeper


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_trading_router() -> APIRouter:
    """Return the FastAPI router for all /api/trading/* and /ui/trading routes."""
    router = APIRouter(tags=["Trading Automation"])

    # ── Orchestrator ────────────────────────────────────────────────────

    @router.post("/api/trading/start")
    async def start_orchestrator() -> Dict[str, Any]:
        """Start the trading orchestrator."""
        try:
            orch = _get_orchestrator()
            orch.start()
            return {"success": True, "status": orch.get_status()}
        except Exception as exc:
            logger.error("Failed to start orchestrator: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/api/trading/stop")
    async def stop_orchestrator() -> Dict[str, Any]:
        """Stop the trading orchestrator gracefully."""
        try:
            orch = _get_orchestrator()
            orch.stop()
            return {"success": True, "state": "stopped"}
        except Exception as exc:
            logger.error("Failed to stop orchestrator: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/api/trading/status")
    async def get_trading_status() -> Dict[str, Any]:
        """Return full system status."""
        try:
            orch   = _get_orchestrator()
            status = orch.get_status()
            # Enrich with live engine gate info if available
            live = getattr(orch, "_live_engine", None)
            if live is not None:
                gates = live.check_gates()
                status["live_gates"] = gates.to_dict()
            return status
        except Exception as exc:
            logger.error("Status error: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/api/trading/mode")
    async def get_trading_mode() -> Dict[str, str]:
        """Return current trading mode."""
        orch = _get_orchestrator()
        return {"mode": orch._mode.value}  # type: ignore[union-attr]

    @router.post("/api/trading/mode")
    async def set_trading_mode(body: ModeSwitchRequest) -> Dict[str, Any]:
        """Switch trading mode (paper / live).  Live requires 5-gate pass."""
        from trading_orchestrator import TradingMode
        try:
            new_mode = TradingMode(body.mode.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid mode '{body.mode}'. Use 'paper' or 'live'.")
        orch   = _get_orchestrator()
        result = orch.switch_mode(new_mode)
        if not result.get("success"):
            raise HTTPException(status_code=403, detail=result.get("reason", "Mode switch failed"))
        return result

    # ── Portfolio ───────────────────────────────────────────────────────

    @router.get("/api/trading/portfolio")
    async def get_portfolio() -> Dict[str, Any]:
        """Return full portfolio state including starting_capital from the sweeper."""
        orch     = _get_orchestrator()
        sweeper  = _get_sweeper()
        portfolio = orch.get_portfolio()
        portfolio["starting_capital"] = sweeper._starting_capital
        return portfolio

    @router.get("/api/trading/portfolio/history")
    async def get_portfolio_history() -> Dict[str, Any]:
        """Return portfolio value history."""
        orch = _get_orchestrator()
        return {"history": orch.get_portfolio_history()}

    # ── Positions ───────────────────────────────────────────────────────

    @router.get("/api/trading/positions")
    async def get_positions() -> Dict[str, Any]:
        """Return all open positions."""
        orch = _get_orchestrator()
        live = getattr(orch, "_live_engine", None)
        if live is not None:
            return {"positions": live.get_positions()}
        return {"positions": []}

    @router.get("/api/trading/positions/{position_id}")
    async def get_position(position_id: str) -> Dict[str, Any]:
        """Return detail for a single position."""
        orch = _get_orchestrator()
        live = getattr(orch, "_live_engine", None)
        if live is not None:
            for pos in live.get_positions():
                if pos.get("position_id") == position_id:
                    return pos
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found")

    # ── Trades ──────────────────────────────────────────────────────────

    @router.get("/api/trading/trades")
    async def get_trades(
        limit: int = Query(default=100, ge=1, le=1000)
    ) -> Dict[str, Any]:
        """Return trade history."""
        orch = _get_orchestrator()
        return {"trades": orch.get_trade_history(limit=limit)}

    @router.get("/api/trading/trades/today")
    async def get_todays_trades() -> Dict[str, Any]:
        """Return today's trades."""
        orch = _get_orchestrator()
        return {"trades": orch.get_todays_trades()}

    # ── Profit Sweep ────────────────────────────────────────────────────

    @router.get("/api/trading/sweep/status")
    async def get_sweep_status() -> Dict[str, Any]:
        """Return next sweep schedule and stats."""
        sweeper = _get_sweeper()
        return {
            "next_sweep": sweeper.get_next_sweep_info(),
            "stats":      sweeper.get_stats(),
        }

    @router.get("/api/trading/sweep/history")
    async def get_sweep_history(
        limit: int = Query(default=30, ge=1, le=200)
    ) -> Dict[str, Any]:
        """Return sweep history."""
        sweeper = _get_sweeper()
        return {"history": sweeper.get_history(limit=limit)}

    @router.post("/api/trading/sweep/trigger")
    async def trigger_sweep(body: SweepTriggerRequest) -> Dict[str, Any]:
        """Manually trigger a profit sweep (dry-run by default)."""
        try:
            sweeper = _get_sweeper()
        except Exception as _exc:
            return {"success": False, "error": str(_exc), "record": None}
        # Default portfolio_value to 0.0 when not provided (no Coinbase connector)
        portfolio_val = body.portfolio_value if body.portfolio_value is not None else 0.0
        try:
            if body.dry_run:
                # For dry-run: create a temporary sweeper with enabled=False so
                # we never mutate shared state (avoids race conditions).
                from profit_sweep import ProfitSweep
                dry_sweeper = ProfitSweep(
                    coinbase_connector = getattr(sweeper, "_coinbase", None),
                    starting_capital   = sweeper._starting_capital,
                    enabled            = False,
                    min_sweep_amount   = sweeper._min_sweep,
                    cash_reserve_pct   = sweeper._cash_reserve,
                    sweep_asset        = sweeper._sweep_asset,
                )
                record = dry_sweeper.run_sweep(
                    portfolio_value = portfolio_val,
                    open_positions  = body.open_positions,
                    pending_orders  = body.pending_orders,
                )
            else:
                record = sweeper.run_sweep(
                    portfolio_value = portfolio_val,
                    open_positions  = body.open_positions,
                    pending_orders  = body.pending_orders,
                )
            return {"success": True, "record": record.to_dict()}
        except Exception as _sweep_exc:
            return {"success": False, "error": str(_sweep_exc), "record": None}

    @router.get("/api/trading/sweep/atom-balance")
    async def get_atom_balance() -> Dict[str, Any]:
        """Return ATOM staking info."""
        sweeper = _get_sweeper()
        stats   = sweeper.get_stats()
        return {
            "atom_staked":      stats["current_atom_staked"],
            "atom_accumulated": stats["total_atom_accumulated"],
            "staking_apy":      stats["atom_staking_apy"],
            "total_usd_swept":  stats["total_usd_swept"],
        }

    # ── Emergency Stop ──────────────────────────────────────────────────

    @router.get("/api/trading/emergency/status")
    async def get_emergency_status() -> Dict[str, Any]:
        """Return the state of the emergency stop controller."""
        orch = _get_orchestrator()
        try:
            from trading_compliance_engine import get_compliance_engine
            ce = get_compliance_engine()
            return {
                "emergency_stop_active": getattr(ce, "emergency_stop_active", False),
                "stop_reason":           getattr(ce, "emergency_stop_reason", None),
                "trading_allowed":       getattr(orch, "live_trading_enabled", False),
            }
        except Exception as exc:  # pragma: no cover
            logger.warning("emergency status unavailable: %s", exc)
            return {
                "emergency_stop_active": False,
                "stop_reason":           None,
                "trading_allowed":       getattr(orch, "live_trading_enabled", False),
            }

    @router.post("/api/trading/emergency/trigger")
    async def trigger_emergency_stop() -> Dict[str, Any]:
        """Trigger an emergency stop of all live trading."""
        orch = _get_orchestrator()
        try:
            from trading_compliance_engine import get_compliance_engine
            ce = get_compliance_engine()
            if hasattr(ce, "trigger_emergency_stop"):
                ce.trigger_emergency_stop("manual-ui-trigger")
        except Exception as exc:  # pragma: no cover
            logger.warning("compliance engine unavailable: %s", exc)

        if hasattr(orch, "emergency_stop"):
            orch.emergency_stop()
        elif hasattr(orch, "stop"):
            orch.stop()

        logger.warning("Emergency stop triggered via API")
        return {"success": True, "message": "Emergency stop activated"}

    # ── Risk Assessment ─────────────────────────────────────────────────

    @router.get("/api/trading/risk/assessment")
    async def get_risk_assessment() -> Dict[str, Any]:
        """Return the current risk assessment from the compliance engine."""
        try:
            from trading_compliance_engine import get_compliance_engine
            ce = get_compliance_engine()
            if hasattr(ce, "get_risk_assessment"):
                return ce.get_risk_assessment()
            # Fallback: compose from available attributes
            return {
                "risk_level":          getattr(ce, "current_risk_level", "unknown"),
                "daily_loss":          getattr(ce, "daily_loss_usd", 0.0),
                "max_daily_loss":      getattr(ce, "max_daily_loss_usd", 0.0),
                "position_count":      getattr(ce, "open_position_count", 0),
                "circuit_breaker_open": getattr(ce, "circuit_breaker_open", False),
            }
        except Exception as exc:  # pragma: no cover
            logger.warning("risk assessment unavailable: %s", exc)
            return {"risk_level": "unavailable", "error": str(exc)}

    # ── Graduation Status ───────────────────────────────────────────────

    @router.get("/api/trading/graduation/status")
    async def get_graduation_status() -> Dict[str, Any]:
        """Return paper-trading graduation tracker summary."""
        try:
            from trading_compliance_engine import get_graduation_tracker
            gt = get_graduation_tracker()
            return {
                "days_tracked":         len(getattr(gt, "daily_records", [])),
                "meets_threshold":      gt.meets_graduation_threshold() if hasattr(gt, "meets_graduation_threshold") else False,
                "win_rate":             getattr(gt, "win_rate", None),
                "sharpe_ratio":         getattr(gt, "sharpe_ratio", None),
                "max_drawdown":         getattr(gt, "max_drawdown_pct", None),
                "graduated":            getattr(gt, "graduated", False),
            }
        except Exception as exc:  # pragma: no cover
            logger.warning("graduation status unavailable: %s", exc)
            return {"graduated": False, "error": str(exc)}

    # ── Dashboard HTML ──────────────────────────────────────────────────

    _project_root = Path(__file__).resolve().parent.parent

    def _dashboard_file() -> Path:
        for candidate in [
            _project_root / "trading_dashboard.html",
            _project_root / "templates" / "trading_dashboard.html",
        ]:
            if candidate.is_file():
                return candidate
        return _project_root / "trading_dashboard.html"

    @router.get("/ui/trading", include_in_schema=False)
    @router.get("/ui/trading-dashboard", include_in_schema=False)
    async def serve_trading_dashboard() -> FileResponse:
        """Serve the trading dashboard HTML page."""
        fp = _dashboard_file()
        if not fp.is_file():
            raise HTTPException(status_code=404, detail="Trading dashboard not found")
        return FileResponse(str(fp), media_type="text/html")

    return router
