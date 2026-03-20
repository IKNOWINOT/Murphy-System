"""
Paper Trading API Routes — Murphy System

Provides FastAPI endpoints for:
  - Starting / stopping paper trading sessions
  - Querying positions, trades, performance, and strategy signals
  - Running backtests

All endpoints are for PAPER/SIMULATED trading only.
No real money is ever moved.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, HTTPException, Request
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False
    logger.warning("FastAPI not available — paper trading routes disabled")

try:
    from paper_trading_engine import PaperTradingEngine, DEFAULT_CAPITAL
    _ENGINE_AVAILABLE = True
except ImportError as _e:
    _ENGINE_AVAILABLE = False
    logger.warning("PaperTradingEngine not available: %s", _e)

try:
    from cost_calibrator import CostCalibrator
    _COST_CAL_AVAILABLE = True
except ImportError:
    _COST_CAL_AVAILABLE = False

try:
    from error_calibrator import ErrorCalibrator
    _ERR_CAL_AVAILABLE = True
except ImportError:
    _ERR_CAL_AVAILABLE = False

try:
    from strategy_templates import STRATEGY_REGISTRY, Signal, SignalAction
    from strategy_templates.base_strategy import MarketBar
    _STRATEGIES_AVAILABLE = True
except ImportError:
    _STRATEGIES_AVAILABLE = False

try:
    from backtester import Backtester, load_dicts, load_yfinance
    _BACKTESTER_AVAILABLE = True
except ImportError:
    _BACKTESTER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Singleton engine instances (module-level, shared across requests)
# ---------------------------------------------------------------------------

_engine:        Optional[Any] = None
_cost_cal:      Optional[Any] = None
_error_cal:     Optional[Any] = None
_session_active: bool          = False
_session_start:  float         = 0.0
_session_config: Dict[str, Any] = {}


def _get_engine() -> Any:
    global _engine, _cost_cal, _error_cal
    if _engine is None and _ENGINE_AVAILABLE:
        capital = _session_config.get("initial_capital", DEFAULT_CAPITAL)
        _engine    = PaperTradingEngine(initial_capital=capital)
        _cost_cal  = CostCalibrator()  if _COST_CAL_AVAILABLE  else None
        _error_cal = ErrorCalibrator() if _ERR_CAL_AVAILABLE    else None
    return _engine


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    class StartRequest(BaseModel):
        strategies:      List[str] = Field(default_factory=list, description="Strategy names to activate")
        initial_capital: float     = Field(default=DEFAULT_CAPITAL, description="Starting capital in USD")
        symbols:         List[str] = Field(default_factory=list, description="Symbols to trade")

    class StopRequest(BaseModel):
        liquidate: bool = Field(default=False, description="Close all open positions before stopping")

    class TradeRequest(BaseModel):
        symbol:      str
        side:        str   = "buy"     # "buy" | "sell"
        quantity:    float = 0.0
        price:       float = 0.0
        strategy:    str   = "manual"
        confidence:  float = 0.5
        stop_loss:   Optional[float] = None
        take_profit: Optional[float] = None

    class BacktestRequest(BaseModel):
        strategy:        str
        symbol:          str
        timeframe:       str   = "1d"
        period:          str   = "6mo"   # yfinance period
        initial_capital: float = Field(default=DEFAULT_CAPITAL)
        ohlcv_data:      Optional[List[Dict[str, Any]]] = None  # pre-loaded data


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_paper_trading_router() -> Any:
    """Create and return the FastAPI router for paper trading endpoints."""
    if not _FASTAPI_AVAILABLE:
        raise RuntimeError("FastAPI is required for paper trading routes")

    router = APIRouter(prefix="/api/trading", tags=["paper-trading"])

    # ── POST /api/trading/paper/start ─────────────────────────────────
    @router.post("/paper/start")
    async def start_paper_trading(req: StartRequest) -> JSONResponse:
        """Start a paper trading session with the selected strategies."""
        global _engine, _session_active, _session_start, _session_config
        _session_config = {
            "initial_capital": req.initial_capital,
            "strategies":      req.strategies,
            "symbols":         req.symbols,
        }
        _engine = None          # reset so _get_engine() re-creates with new capital
        engine  = _get_engine()
        _session_active = True
        _session_start  = time.time()
        logger.info("Paper trading session started: capital=%.2f strategies=%s",
                    req.initial_capital, req.strategies)
        return JSONResponse({
            "status":    "started",
            "session_start": _session_start,
            "initial_capital": req.initial_capital,
            "strategies": req.strategies,
            "symbols":    req.symbols,
        })

    # ── POST /api/trading/paper/stop ──────────────────────────────────
    @router.post("/paper/stop")
    async def stop_paper_trading(req: StopRequest) -> JSONResponse:
        """Stop the active paper trading session."""
        global _session_active
        engine = _get_engine()
        liquidated = []
        if req.liquidate and engine:
            for pos in list(engine._positions.values()):  # noqa: SLF001
                result = engine.close_position(
                    pos.symbol, pos.current_price or pos.avg_entry,
                    exit_reason="session_stop",
                )
                liquidated.append(result)
        _session_active = False
        perf = engine.get_performance() if engine else {}
        logger.info("Paper trading session stopped")
        return JSONResponse({
            "status":       "stopped",
            "performance":  perf,
            "liquidated":   liquidated,
        })

    # ── GET /api/trading/paper/status ─────────────────────────────────
    @router.get("/paper/status")
    async def get_status() -> JSONResponse:
        """Return current paper trading session state."""
        engine = _get_engine()
        return JSONResponse({
            "active":         _session_active,
            "session_start":  _session_start,
            "session_config": _session_config,
            "available":      _ENGINE_AVAILABLE,
            "portfolio":      engine.get_portfolio() if engine else {},
            "strategies_available": list(STRATEGY_REGISTRY.keys()) if _STRATEGIES_AVAILABLE else [],
        })

    # ── GET /api/trading/paper/positions ──────────────────────────────
    @router.get("/paper/positions")
    async def get_positions() -> JSONResponse:
        """Return all currently open paper positions."""
        engine = _get_engine()
        if not engine:
            return JSONResponse({"positions": [], "error": "engine_not_initialised"})
        return JSONResponse({
            "positions": engine.get_positions(),
            "portfolio":  engine.get_portfolio(),
        })

    # ── GET /api/trading/paper/trades ─────────────────────────────────
    @router.get("/paper/trades")
    async def get_trades(limit: int = 200, strategy: Optional[str] = None) -> JSONResponse:
        """Return the paper trade journal."""
        engine = _get_engine()
        if not engine:
            return JSONResponse({"trades": []})
        return JSONResponse({
            "trades": engine.get_trades(limit=limit, strategy=strategy),
            "count":  len(engine.get_trades(limit=10_000)),
        })

    # ── GET /api/trading/paper/performance ────────────────────────────
    @router.get("/paper/performance")
    async def get_performance() -> JSONResponse:
        """Return full performance metrics."""
        engine = _get_engine()
        if not engine:
            return JSONResponse({"error": "engine_not_initialised"})
        return JSONResponse({
            "overall":    engine.get_performance(),
            "by_strategy": engine.get_strategy_performance(),
            "equity_curve": engine.get_equity_curve()[-100:],   # last 100 points
            "cost_calibration": _cost_cal.get_summary() if _cost_cal else {},
            "error_calibration": _error_cal.get_summary() if _error_cal else {},
        })

    # ── GET /api/trading/paper/strategies ─────────────────────────────
    @router.get("/paper/strategies")
    async def list_strategies() -> JSONResponse:
        """List all available strategy templates."""
        if not _STRATEGIES_AVAILABLE:
            return JSONResponse({"strategies": [], "error": "strategy_templates_not_available"})
        strategies = []
        for name, cls in STRATEGY_REGISTRY.items():
            instance = cls(strategy_id=name)
            strategies.append({
                "name":    name,
                "class":   cls.__name__,
                "params":  instance.get_params(),
                "description": cls.__doc__.strip().split("\n")[0] if cls.__doc__ else "",
            })
        return JSONResponse({"strategies": strategies, "count": len(strategies)})

    # ── POST /api/trading/paper/trade ─────────────────────────────────
    @router.post("/paper/trade")
    async def manual_trade(req: TradeRequest) -> JSONResponse:
        """Execute a manual paper trade."""
        engine = _get_engine()
        if not engine:
            raise HTTPException(status_code=503, detail="Paper trading engine not initialised")
        if req.side == "buy":
            result = engine.open_position(
                symbol=req.symbol, quantity=req.quantity, price=req.price,
                strategy=req.strategy, confidence=req.confidence,
                stop_loss=req.stop_loss, take_profit=req.take_profit,
            )
        elif req.side == "sell":
            result = engine.close_position(
                symbol=req.symbol, price=req.price, quantity=req.quantity,
                strategy=req.strategy,
            )
        else:
            raise HTTPException(status_code=400, detail="side must be 'buy' or 'sell'")
        return JSONResponse(result)

    # ── POST /api/trading/backtest ─────────────────────────────────────
    @router.post("/backtest")
    async def run_backtest(req: BacktestRequest) -> JSONResponse:
        """Run a strategy backtest against historical data."""
        if not _BACKTESTER_AVAILABLE:
            raise HTTPException(status_code=503, detail="Backtester not available")
        if not _STRATEGIES_AVAILABLE:
            raise HTTPException(status_code=503, detail="Strategy templates not available")

        if req.strategy not in STRATEGY_REGISTRY:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown strategy '{req.strategy}'. Available: {list(STRATEGY_REGISTRY.keys())}",
            )

        strategy_cls = STRATEGY_REGISTRY[req.strategy]
        strategy     = strategy_cls(strategy_id=req.strategy)

        # Load data
        if req.ohlcv_data:
            ohlcv = load_dicts(req.ohlcv_data)
        else:
            ohlcv = load_yfinance(req.symbol, period=req.period, interval=req.timeframe)

        if not ohlcv:
            raise HTTPException(status_code=400, detail="No OHLCV data available for backtest")

        backtester = Backtester(initial_capital=req.initial_capital)
        result     = backtester.run(strategy, ohlcv, req.symbol, req.timeframe)
        return JSONResponse(result.to_dict())

    # ── GET /api/trading/calibration/costs ────────────────────────────
    @router.get("/calibration/costs")
    async def get_cost_calibration() -> JSONResponse:
        """Return the cost calibrator summary and recent history."""
        if not _cost_cal:
            return JSONResponse({"error": "cost_calibrator_not_available"})
        return JSONResponse({
            "summary":  _cost_cal.get_summary(),
            "history":  _cost_cal.get_history(limit=50),
            "alerts":   _cost_cal.get_alerts(limit=20),
        })

    # ── GET /api/trading/calibration/errors ───────────────────────────
    @router.get("/calibration/errors")
    async def get_error_calibration() -> JSONResponse:
        """Return the error calibrator profiles for all strategies."""
        if not _error_cal:
            return JSONResponse({"error": "error_calibrator_not_available"})
        return JSONResponse({
            "summary":  _error_cal.get_summary(),
            "profiles": _error_cal.get_all_profiles(),
            "alerts":   _error_cal.get_alerts(limit=20),
        })

    return router
