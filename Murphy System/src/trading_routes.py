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
        sweeper = _get_sweeper()
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
                portfolio_value = body.portfolio_value,
                open_positions  = body.open_positions,
                pending_orders  = body.pending_orders,
            )
        else:
            record = sweeper.run_sweep(
                portfolio_value = body.portfolio_value,
                open_positions  = body.open_positions,
                pending_orders  = body.pending_orders,
            )
        return {"success": True, "record": record.to_dict()}

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
