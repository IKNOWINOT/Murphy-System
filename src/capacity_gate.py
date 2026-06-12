"""
capacity_gate — Ship 31ao.LAUNCH B3

Pre-spawn gate that reads current system capacity and decides
whether a proposed spawn can proceed.

USAGE:
    from src.capacity_gate import can_spawn, CapacityVerdict

    v = can_spawn(estimated_cost_usd=0.50, est_wall_time_sec=300)
    if not v.allow:
        log.warning("spawn refused: %s", v.reason)
        return  # defer or escalate
    do_the_work()

The gate is conservative by default — when in doubt, refuses.
That protects the bank account during launch.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


LEDGER_DB = "/var/lib/murphy-production/capacity_gate_ledger.db"

# Hard ceilings — if any of these are hit, spawn is refused regardless
HARD_LIMITS = {
    "cpu_pct_used":   85.0,      # if CPU > 85%, refuse
    "mem_pct_used":   88.0,      # if memory > 88%, refuse
    "load_1min":      8.0,       # 1-min load avg
    "disk_pct_used":  90.0,      # if disk > 90%, refuse
    "daily_spend_usd": 100.0,    # if today's spend > $100, refuse non-revenue work
}


def _init_ledger() -> None:
    Path(LEDGER_DB).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(LEDGER_DB, timeout=2.0)
    c.execute("""
      CREATE TABLE IF NOT EXISTS capacity_decisions (
        decision_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        ts              TEXT NOT NULL,
        allow           INTEGER NOT NULL,
        reason          TEXT NOT NULL,
        cpu_pct         REAL,
        mem_pct         REAL,
        load_1min       REAL,
        disk_pct        REAL,
        daily_spend_usd REAL,
        est_cost_usd    REAL,
        est_wall_sec    INTEGER,
        caller          TEXT
      )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_cap_allow ON capacity_decisions(allow)")
    c.commit()
    c.close()


@dataclass
class CapacityVerdict:
    allow: bool
    reason: str
    cpu_pct: float = 0.0
    mem_pct: float = 0.0
    load_1min: float = 0.0
    disk_pct: float = 0.0
    daily_spend_usd: float = 0.0


def _read_cpu_pct() -> float:
    """Quick CPU read from /proc/loadavg + nproc — light, no psutil dep."""
    try:
        with open("/proc/loadavg") as f:
            load1 = float(f.read().split()[0])
        nproc = os.cpu_count() or 1
        return min(100.0, 100.0 * load1 / nproc)
    except Exception:
        return 0.0


def _read_mem_pct() -> float:
    try:
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                k, v = line.split(":", 1)
                mem[k] = int(v.strip().split()[0])  # kB
        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", 0)
        if total <= 0:
            return 0.0
        return 100.0 * (total - avail) / total
    except Exception:
        return 0.0


def _read_load_1min() -> float:
    try:
        with open("/proc/loadavg") as f:
            return float(f.read().split()[0])
    except Exception:
        return 0.0


def _read_disk_pct(path: str = "/") -> float:
    try:
        s = os.statvfs(path)
        total = s.f_blocks * s.f_frsize
        avail = s.f_bavail * s.f_frsize
        if total <= 0:
            return 0.0
        return 100.0 * (total - avail) / total
    except Exception:
        return 0.0


def _read_daily_spend_usd() -> float:
    """Sum cost_usd from turnover_ledger over the last 24h."""
    db = "/var/lib/murphy-production/turnover_ledger.db"
    if not Path(db).exists():
        return 0.0
    try:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1.0)
        row = c.execute(
            "SELECT COALESCE(SUM(cost_usd), 0.0) FROM turnover_events "
            "WHERE ts > datetime('now','-1 day')"
        ).fetchone()
        c.close()
        return float(row[0] or 0.0)
    except Exception:
        return 0.0


def can_spawn(
    estimated_cost_usd: float = 0.50,
    est_wall_time_sec: int = 300,
    caller: str = "unknown",
) -> CapacityVerdict:
    """Decide whether a spawn can proceed. Records the decision to ledger."""
    cpu = _read_cpu_pct()
    mem = _read_mem_pct()
    load1 = _read_load_1min()
    disk = _read_disk_pct()
    spend = _read_daily_spend_usd()

    # Check each hard limit
    if cpu > HARD_LIMITS["cpu_pct_used"]:
        verdict = CapacityVerdict(False, f"cpu_pct={cpu:.1f} > {HARD_LIMITS['cpu_pct_used']}",
                                  cpu, mem, load1, disk, spend)
    elif mem > HARD_LIMITS["mem_pct_used"]:
        verdict = CapacityVerdict(False, f"mem_pct={mem:.1f} > {HARD_LIMITS['mem_pct_used']}",
                                  cpu, mem, load1, disk, spend)
    elif load1 > HARD_LIMITS["load_1min"]:
        verdict = CapacityVerdict(False, f"load_1min={load1:.2f} > {HARD_LIMITS['load_1min']}",
                                  cpu, mem, load1, disk, spend)
    elif disk > HARD_LIMITS["disk_pct_used"]:
        verdict = CapacityVerdict(False, f"disk_pct={disk:.1f} > {HARD_LIMITS['disk_pct_used']}",
                                  cpu, mem, load1, disk, spend)
    elif spend + estimated_cost_usd > HARD_LIMITS["daily_spend_usd"]:
        verdict = CapacityVerdict(False,
            f"daily_spend=${spend:.2f}+${estimated_cost_usd:.2f} > ${HARD_LIMITS['daily_spend_usd']}",
            cpu, mem, load1, disk, spend)
    else:
        verdict = CapacityVerdict(True, "all_limits_ok", cpu, mem, load1, disk, spend)

    # Write ledger
    try:
        _init_ledger()
        c = sqlite3.connect(LEDGER_DB, timeout=2.0)
        c.execute(
            """INSERT INTO capacity_decisions
               (ts, allow, reason, cpu_pct, mem_pct, load_1min, disk_pct,
                daily_spend_usd, est_cost_usd, est_wall_sec, caller)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (datetime.now(timezone.utc).isoformat(),
             1 if verdict.allow else 0,
             verdict.reason, cpu, mem, load1, disk, spend,
             estimated_cost_usd, est_wall_time_sec, caller),
        )
        c.commit()
        c.close()
    except Exception:
        pass  # ledger failure must NEVER block spawn decision

    return verdict


_init_ledger()
