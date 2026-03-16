# `src/portfolio` — Project Portfolio Management

Gantt charts, dependency management, critical-path calculation, and baseline snapshots for project portfolio oversight.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The portfolio package delivers project scheduling and portfolio management on top of Murphy boards. The `GanttEngine` tracks `GanttBar` items with start/end dates and links them through a `DependencyManager` that supports Finish-to-Start, Start-to-Start, Finish-to-Finish, and Start-to-Finish dependency types with optional lag. A forward/backward-pass `CriticalPathEngine` identifies the longest path and marks critical bars. `Baseline` snapshots capture schedule states at key moments for variance analysis. A FastAPI router at `/api/portfolio` exposes all operations.

## Key Components

| Module | Purpose |
|--------|---------|
| `gantt.py` | `GanttEngine` — Gantt bar CRUD, rendering, and scheduling |
| `dependencies.py` | `DependencyManager` — dependency CRUD with cycle detection |
| `critical_path.py` | `CriticalPathEngine` — forward/backward pass critical path calculation |
| `models.py` | `GanttBar`, `Dependency`, `DependencyType`, `Milestone`, `Baseline`, `PortfolioProject` |
| `api.py` | FastAPI router (`create_portfolio_router`) |

## Usage

```python
from portfolio import GanttEngine, DependencyType

engine = GanttEngine()
engine.add_bar("i1", "Design", "2025-01-01", "2025-01-10", board_id="b1")
engine.add_bar("i2", "Build", "2025-01-11", "2025-01-25", board_id="b1")
engine.deps.add_dependency("i1", "i2", DependencyType.FINISH_TO_START)
result = engine.compute_critical_path("b1")
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
