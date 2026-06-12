"""
turnover_criteria — Ship 31ao.LAUNCH B1

Universal turnover criteria for any spawned agent. Prevents:
  - infinite drill loops
  - cross-role ping-pong
  - retry-on-failure runaway
  - runaway cost or token consumption

USAGE:
    from src.turnover_criteria import TurnoverCriteria, TurnoverTracker

    criteria = TurnoverCriteria.for_role('pattern-analyst')
    tracker = TurnoverTracker(criteria, spawn_id='spawn_xxx')

    while not tracker.should_stop():
        result = do_one_iteration()
        tracker.record_iteration(
            tokens_used=result.tokens,
            cost_usd=result.cost,
            converged=result.converged,
        )
        if tracker.converged_this_iteration:
            break

    reason = tracker.stop_reason  # 'max_iter' | 'max_time' | 'max_cost' |
                                   # 'max_tokens' | 'converged' | 'diverged'
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("murphy.turnover")

# Ledger DB — persisted so the Immunology dept can mine it later
LEDGER_DB = "/var/lib/murphy-production/turnover_ledger.db"


def _init_ledger() -> None:
    Path(LEDGER_DB).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(LEDGER_DB, timeout=2.0)
    c.execute("""
      CREATE TABLE IF NOT EXISTS turnover_events (
        event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        ts              TEXT NOT NULL,
        spawn_id        TEXT NOT NULL,
        position        TEXT NOT NULL,
        stop_reason     TEXT NOT NULL,
        iterations_used INTEGER NOT NULL,
        wall_time_sec   REAL NOT NULL,
        tokens_used     INTEGER NOT NULL,
        cost_usd        REAL NOT NULL,
        max_iterations  INTEGER NOT NULL,
        max_wall_time   INTEGER NOT NULL,
        max_tokens      INTEGER NOT NULL,
        max_cost_usd    REAL NOT NULL,
        notes           TEXT
      )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_tev_pos ON turnover_events(position)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tev_reason ON turnover_events(stop_reason)")
    c.commit()
    c.close()


@dataclass
class TurnoverCriteria:
    """Per-spawn turnover criteria — sane defaults, role-overridable."""
    position: str = "unknown"
    max_iterations: int = 5
    max_wall_time_sec: int = 300        # 5 min
    max_tokens: int = 50_000
    max_cost_usd: float = 0.50
    on_turnover: str = "return_partial"   # 'return_partial' | 'rollback' | 'escalate_hitl'

    # ── Per-role registry — extend as roles are added to the org ──
    _ROLE_DEFAULTS = {
        # Lieutenants — give them a longer leash for synthesis work
        "ceo":                  {"max_iterations": 8,  "max_wall_time_sec": 900, "max_tokens": 100_000, "max_cost_usd": 2.00},
        "cto":                  {"max_iterations": 8,  "max_wall_time_sec": 900, "max_tokens": 100_000, "max_cost_usd": 2.00},
        "cfo":                  {"max_iterations": 8,  "max_wall_time_sec": 900, "max_tokens": 100_000, "max_cost_usd": 2.00},
        "cso":                  {"max_iterations": 8,  "max_wall_time_sec": 900, "max_tokens": 100_000, "max_cost_usd": 2.00},
        "general-counsel":      {"max_iterations": 5,  "max_wall_time_sec": 600, "max_tokens": 80_000,  "max_cost_usd": 1.00},
        "ciso":                 {"max_iterations": 5,  "max_wall_time_sec": 600, "max_tokens": 80_000,  "max_cost_usd": 1.00},

        # Immunology department
        "chief-immunologist":   {"max_iterations": 3,  "max_wall_time_sec": 120, "max_tokens": 20_000,  "max_cost_usd": 0.25},
        "pattern-analyst":      {"max_iterations": 5,  "max_wall_time_sec": 300, "max_tokens": 50_000,  "max_cost_usd": 0.50},
        "outcome-observer":     {"max_iterations": 2,  "max_wall_time_sec": 60,  "max_tokens": 10_000,  "max_cost_usd": 0.10},
        "antibody-curator":     {"max_iterations": 3,  "max_wall_time_sec": 180, "max_tokens": 30_000,  "max_cost_usd": 0.30},
        "potentiator-curator":  {"max_iterations": 3,  "max_wall_time_sec": 180, "max_tokens": 30_000,  "max_cost_usd": 0.30},

        # Sales / outreach work — must stay tight, real $ at stake
        "creator-liaison":      {"max_iterations": 3,  "max_wall_time_sec": 180, "max_tokens": 30_000,  "max_cost_usd": 0.30},
        "community-outreach":   {"max_iterations": 3,  "max_wall_time_sec": 180, "max_tokens": 30_000,  "max_cost_usd": 0.30},
        "demo-coordinator":     {"max_iterations": 3,  "max_wall_time_sec": 180, "max_tokens": 30_000,  "max_cost_usd": 0.30},

        # R&D — longer leash for actual experimentation
        "director-of-rnd":      {"max_iterations": 10, "max_wall_time_sec": 1200,"max_tokens": 150_000, "max_cost_usd": 3.00},
        "model-research-lead":  {"max_iterations": 8,  "max_wall_time_sec": 1200,"max_tokens": 150_000, "max_cost_usd": 3.00},
        "osmosis-specialist":   {"max_iterations": 10, "max_wall_time_sec": 1500,"max_tokens": 200_000, "max_cost_usd": 4.00},
        "research-scientist":   {"max_iterations": 10, "max_wall_time_sec": 900, "max_tokens": 100_000, "max_cost_usd": 2.00},
        "benchmark-engineer":   {"max_iterations": 5,  "max_wall_time_sec": 600, "max_tokens": 50_000,  "max_cost_usd": 0.75},
        "qa-engineer":          {"max_iterations": 8,  "max_wall_time_sec": 600, "max_tokens": 60_000,  "max_cost_usd": 1.00},

        # Stranger responder — kept tight; per-reply cost matters
        "stranger_responder":   {"max_iterations": 3,  "max_wall_time_sec": 90,  "max_tokens": 15_000,  "max_cost_usd": 0.15},
    }

    @classmethod
    def for_role(cls, position: str, **overrides) -> "TurnoverCriteria":
        defaults = cls._ROLE_DEFAULTS.get(position.lower(), {})
        return cls(position=position, **{**defaults, **overrides})


@dataclass
class TurnoverTracker:
    """Live counter — bounds an agent's runtime."""
    criteria: TurnoverCriteria
    spawn_id: str
    started_at: float = field(default_factory=time.monotonic)
    iterations_used: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0
    converged_this_iteration: bool = False
    stop_reason: Optional[str] = None
    notes: str = ""

    def should_stop(self) -> bool:
        # Check each criterion; first hit wins
        if self.iterations_used >= self.criteria.max_iterations:
            self.stop_reason = "max_iterations"
            return True
        if (time.monotonic() - self.started_at) >= self.criteria.max_wall_time_sec:
            self.stop_reason = "max_wall_time"
            return True
        if self.tokens_used >= self.criteria.max_tokens:
            self.stop_reason = "max_tokens"
            return True
        if self.cost_usd >= self.criteria.max_cost_usd:
            self.stop_reason = "max_cost"
            return True
        if self.converged_this_iteration:
            self.stop_reason = "converged"
            return True
        return False

    def record_iteration(
        self,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        converged: bool = False,
    ) -> None:
        self.iterations_used += 1
        self.tokens_used += tokens_used
        self.cost_usd += cost_usd
        self.converged_this_iteration = bool(converged)

    def write_ledger(self) -> None:
        """Persist the turnover event for Immunology Dept review."""
        try:
            _init_ledger()
            c = sqlite3.connect(LEDGER_DB, timeout=2.0)
            c.execute(
                """INSERT INTO turnover_events
                   (ts, spawn_id, position, stop_reason, iterations_used,
                    wall_time_sec, tokens_used, cost_usd,
                    max_iterations, max_wall_time, max_tokens, max_cost_usd, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    self.spawn_id,
                    self.criteria.position,
                    self.stop_reason or "unknown",
                    self.iterations_used,
                    round(time.monotonic() - self.started_at, 3),
                    self.tokens_used,
                    round(self.cost_usd, 4),
                    self.criteria.max_iterations,
                    self.criteria.max_wall_time_sec,
                    self.criteria.max_tokens,
                    self.criteria.max_cost_usd,
                    self.notes,
                ),
            )
            c.commit()
            c.close()
        except Exception as e:
            logger.warning("turnover ledger write failed: %s", e)


# Initialize ledger at import time
_init_ledger()
