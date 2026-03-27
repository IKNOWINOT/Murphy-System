# `src/strategy_templates` — Trading Strategy Templates

Paper-trading strategy library — provides typed `BaseStrategy` implementations for Murphy's algorithmic trading simulation layer.

© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1

## Overview

The `strategy_templates` package contains a collection of battle-tested trading strategy implementations built on top of `BaseStrategy`. Each strategy receives `MarketBar` candles and emits `Signal` objects (`BUY`, `SELL`, `HOLD`) consumed by the paper-trading engine. All strategies are stateless between bar calls and safe for parallel execution across multiple instruments.

## Strategies

| Module | Class | Description |
|--------|-------|-------------|
| `momentum.py` | `MomentumStrategy` | Trend-following via EMA crossover |
| `mean_reversion.py` | `MeanReversionStrategy` | RSI-based mean-reversion entries |
| `breakout.py` | `BreakoutStrategy` | Donchian-channel breakout signals |
| `scalping.py` | `ScalpingStrategy` | High-frequency micro-move scalper |
| `dca.py` | `DCAStrategy` | Dollar-cost averaging accumulation |
| `grid.py` | `GridStrategy` | Grid trading between price bands |
| `trajectory.py` | `TrajectoryStrategy` | Predictive trajectory extrapolation |
| `sentiment.py` | `SentimentStrategy` | News/social sentiment signal injection |
| `arbitrage.py` | `ArbitrageStrategy` | Cross-exchange spread arbitrage |

## Public API

```python
from src.strategy_templates import (
    BaseStrategy, MarketBar, Signal, SignalAction,
    MomentumStrategy, MeanReversionStrategy, BreakoutStrategy,
    ScalpingStrategy, DCAStrategy, GridStrategy,
    TrajectoryStrategy, SentimentStrategy, ArbitrageStrategy,
)
```

## Related

- `src/trading_routes.py` — REST endpoints for live strategy execution
- `src/ml/` — ML-based signal generation that feeds strategies
