"""
Strategy Templates — Murphy System Paper Trading Engine

Exports all strategy classes and the Signal / BaseStrategy types.
"""

from strategy_templates.base_strategy import (
    BaseStrategy,
    MarketBar,
    Signal,
    SignalAction,
)
from strategy_templates.momentum import MomentumStrategy
from strategy_templates.mean_reversion import MeanReversionStrategy
from strategy_templates.breakout import BreakoutStrategy
from strategy_templates.scalping import ScalpingStrategy
from strategy_templates.dca import DCAStrategy
from strategy_templates.grid import GridStrategy
from strategy_templates.trajectory import TrajectoryStrategy
from strategy_templates.sentiment import SentimentStrategy
from strategy_templates.arbitrage import ArbitrageStrategy

__all__ = [
    "BaseStrategy",
    "MarketBar",
    "Signal",
    "SignalAction",
    "MomentumStrategy",
    "MeanReversionStrategy",
    "BreakoutStrategy",
    "ScalpingStrategy",
    "DCAStrategy",
    "GridStrategy",
    "TrajectoryStrategy",
    "SentimentStrategy",
    "ArbitrageStrategy",
]

STRATEGY_REGISTRY: dict = {
    "momentum":      MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout":      BreakoutStrategy,
    "scalping":      ScalpingStrategy,
    "dca":           DCAStrategy,
    "grid":          GridStrategy,
    "trajectory":    TrajectoryStrategy,
    "sentiment":     SentimentStrategy,
    "arbitrage":     ArbitrageStrategy,
}
