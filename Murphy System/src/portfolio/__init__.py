"""
Portfolio – Project Portfolio Management
==========================================

Phase 4 of management systems feature parity for the Murphy System.

Provides project portfolio management including:

- **Gantt chart engine** with dependency-aware scheduling
- **Dependencies** – FS, SS, FF, SF types with lag and cycle detection
- **Critical path** calculation via forward/backward pass
- **Milestones** with target dates and status tracking
- **Baselines** – schedule snapshots for variance analysis
- **REST API** at ``/api/portfolio``

Quick start::

    from portfolio import GanttEngine, DependencyType

    engine = GanttEngine()
    engine.add_bar("i1", "Design", "2025-01-01", "2025-01-10", board_id="b1")
    engine.add_bar("i2", "Build",  "2025-01-11", "2025-01-25", board_id="b1")
    engine.deps.add_dependency("i1", "i2", DependencyType.FINISH_TO_START)
    result = engine.compute_critical_path("b1")
    gantt = engine.render_gantt("b1")

Copyright 2024 Inoni LLC – BSL-1.1
"""

__version__ = "0.1.0"
__codename__ = "Portfolio"

# -- Models -----------------------------------------------------------------
# -- Critical path ----------------------------------------------------------
from .critical_path import CriticalPathEngine

# -- Dependencies -----------------------------------------------------------
from .dependencies import DependencyManager

# -- Gantt engine -----------------------------------------------------------
from .gantt import GanttEngine
from .models import (
    Baseline,
    Dependency,
    DependencyType,
    GanttBar,
    Milestone,
    MilestoneStatus,
    PortfolioProject,
)

# -- API (optional – requires fastapi) -------------------------------------
try:
    from .api import create_portfolio_router
except Exception:  # pragma: no cover
    create_portfolio_router = None  # type: ignore[assignment]

__all__ = [
    # Models
    "Baseline",
    "Dependency",
    "DependencyType",
    "GanttBar",
    "Milestone",
    "MilestoneStatus",
    "PortfolioProject",
    # Dependencies
    "DependencyManager",
    # Critical path
    "CriticalPathEngine",
    # Gantt engine
    "GanttEngine",
    # API
    "create_portfolio_router",
]
