"""
PATCH-089c — LLM Cost Ledger
ETH-COST-001

Taps llm_provider.LLMResponse to accumulate per-call token usage and
estimated cost into SQLite. Provides a REST API for querying spend.

DB: /var/lib/murphy-production/llm_cost_ledger.db
Schema: calls(id, ts, model, provider, prompt_tokens, completion_tokens,
              total_tokens, cost_usd, latency_ms, caller, success)
        daily_summary(date, total_calls, total_tokens, total_cost_usd)
"""
from __future__ import annotations
import logging, sqlite3, threading, time, pathlib, functools
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional
from fastapi import APIRouter

logger = logging.getLogger(__name__)

_DB_PATH = pathlib.Path("/var/lib/murphy-production/llm_cost_ledger.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ts               TEXT NOT NULL,
    model            TEXT,
    provider         TEXT,
    prompt_tokens    INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens     INTEGER DEFAULT 0,
    cost_usd         REAL DEFAULT 0.0,
    latency_ms       REAL DEFAULT 0.0,
    caller           TEXT,
    success          INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS daily_summary (
    date             TEXT PRIMARY KEY,
    total_calls      INTEGER DEFAULT 0,
    total_tokens     INTEGER DEFAULT 0,
    total_cost_usd   REAL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_calls_ts ON calls(ts);
CREATE INDEX IF NOT EXISTS idx_calls_model ON calls(model);
"""

# Cost per 1k tokens (input/output averaged) by model
_MODEL_COSTS: Dict[str, float] = {
    "llama-3.3-70b":   0.00088,
    "llama-3.1-8b":    0.00018,
    "qwen2.5-7b":      0.00018,
    "llama-3.1-70b":   0.00088,
    "llama-3.1-405b":  0.00500,
    "default":         0.00100,
}


class LLMCostLedger:
    """Thread-safe SQLite-backed LLM cost accumulator."""

    def __init__(self, db_path: pathlib.Path = _DB_PATH):
        self._db = db_path
        self._lock = threading.Lock()
        self._init_db()
        logger.info("PATCH-089c: LLM cost ledger initialised at %s", db_path)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db), timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        self._db.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._conn() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def record(self, *, model: str, provider: str, prompt_tokens: int,
               completion_tokens: int, latency_ms: float = 0.0,
               caller: str = "unknown", success: bool = True,
               tenant_id: str = "platform", job_id: str = None):
        """Record one LLM call.

        PATCH-409 (2026-06-08): every call is tagged with tenant_id + job_id
        for per-job cost attribution. See
        .agents/rules/vault_and_accounting_canon.md Part 4.
          - tenant_id="platform" → Murphy's own work (sales, watchdog, etc.)
          - tenant_id="<tenant>" → work performed FOR that tenant
          - job_id="JOB-..."     → optional job code; rolls up on tenant invoice
        """
        total = prompt_tokens + completion_tokens
        cost_key = next((k for k in _MODEL_COSTS if k in model.lower()), "default")
        cost_usd = (total / 1000.0) * _MODEL_COSTS[cost_key]
        ts = datetime.now(timezone.utc).isoformat()
        today = date.today().isoformat()
        try:
            with self._lock, self._conn() as conn:
                conn.execute(
                    "INSERT INTO calls (ts, model, provider, prompt_tokens, completion_tokens, "
                    "total_tokens, cost_usd, latency_ms, caller, success, tenant_id, job_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ts, model, provider, prompt_tokens, completion_tokens,
                     total, cost_usd, latency_ms, caller, int(success),
                     tenant_id, job_id)
                )
                conn.execute("""
                    INSERT INTO daily_summary (date, total_calls, total_tokens, total_cost_usd)
                    VALUES (?, 1, ?, ?)
                    ON CONFLICT(date) DO UPDATE SET
                        total_calls     = total_calls + 1,
                        total_tokens    = total_tokens + excluded.total_tokens,
                        total_cost_usd  = total_cost_usd + excluded.total_cost_usd
                """, (today, total, cost_usd))
                conn.commit()
        except Exception as e:
            logger.warning("PATCH-089c: ledger write failed: %s", e)

    def today_summary(self) -> Dict:
        today = date.today().isoformat()
        try:
            with self._lock, self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM daily_summary WHERE date=?", (today,)
                ).fetchone()
                total_ever = conn.execute("SELECT SUM(cost_usd) FROM calls").fetchone()[0] or 0.0
                call_count = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            return {
                "today": dict(row) if row else {"date": today, "total_calls": 0, "total_tokens": 0, "total_cost_usd": 0.0},
                "all_time": {"total_calls": call_count, "total_cost_usd": round(total_ever, 6)},
            }
        except Exception as e:
            return {"error": str(e)}

    def recent_calls(self, n: int = 50) -> List[Dict]:
        try:
            with self._lock, self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM calls ORDER BY id DESC LIMIT ?", (n,)
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            return [{"error": str(e)}]

    def model_breakdown(self) -> List[Dict]:
        try:
            with self._lock, self._conn() as conn:
                rows = conn.execute("""
                    SELECT model, provider,
                           COUNT(*) as calls,
                           SUM(total_tokens) as tokens,
                           SUM(cost_usd) as cost_usd,
                           AVG(latency_ms) as avg_latency_ms
                    FROM calls GROUP BY model, provider ORDER BY cost_usd DESC
                """).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            return [{"error": str(e)}]

    def daily_history(self, days: int = 30) -> List[Dict]:
        try:
            with self._lock, self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM daily_summary ORDER BY date DESC LIMIT ?", (days,)
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            return [{"error": str(e)}]


def patch_llm_provider(ledger: LLMCostLedger):
    """R405 (2026-06-01): Hook LLMCostLedger into the TWO real funnels —
    _complete_with_fallback (sync) and _acomplete_with_fallback (async).
    Both complete() and complete_messages() flow through _complete_with_fallback,
    so hooking that one method captures EVERY sync LLM call. Same for async.

    Previous implementation only hooked complete_messages() and missed:
      - all calls from .complete(prompt, ...) (~70% of usage)
      - all async calls from .acomplete*()
    R405 fixes this — captures 100% of LLM calls."""
    try:
        import src.llm_provider as lp
        import asyncio as _asyncio
        provider = lp.get_llm()

        # ── Sync funnel: _complete_with_fallback ──
        _orig_sync = provider._complete_with_fallback

        @functools.wraps(_orig_sync)
        def _patched_sync(*args, **kwargs):
            t0 = time.monotonic()
            try:
                result = _orig_sync(*args, **kwargs)
                latency = (time.monotonic() - t0) * 1000
                _record_safely(ledger, result, latency, "sync")
                return result
            except Exception:
                latency = (time.monotonic() - t0) * 1000
                _record_failure(ledger, latency, "sync")
                raise

        provider._complete_with_fallback = _patched_sync

        # ── Async funnel: _acomplete_with_fallback ──
        _orig_async = provider._acomplete_with_fallback

        @functools.wraps(_orig_async)
        async def _patched_async(*args, **kwargs):
            t0 = time.monotonic()
            try:
                result = await _orig_async(*args, **kwargs)
                latency = (time.monotonic() - t0) * 1000
                _record_safely(ledger, result, latency, "async")
                return result
            except Exception:
                latency = (time.monotonic() - t0) * 1000
                _record_failure(ledger, latency, "async")
                raise

        provider._acomplete_with_fallback = _patched_async

        logger.info("R405: LLMCostLedger hooked into sync + async funnels")
    except Exception as e:
        logger.warning("R405: could not patch llm_provider: %s", e)


def _record_safely(ledger: "LLMCostLedger", result: Any, latency_ms: float, mode: str):
    """Best-effort cost capture; never raises into caller's path."""
    try:
        ledger.record(
            model=str(getattr(result, "model", "unknown")),
            provider=str(getattr(result, "provider", "unknown")),
            prompt_tokens=int(getattr(result, "tokens_prompt", 0) or 0),
            completion_tokens=int(getattr(result, "tokens_completion", 0) or 0),
            latency_ms=latency_ms,
            caller=f"llm_provider_{mode}",
            success=bool(getattr(result, "success", True)),
        )
    except Exception as _e:
        logger.debug("R405: record error (%s): %s", mode, _e)


def _record_failure(ledger: "LLMCostLedger", latency_ms: float, mode: str):
    """Record a failure call so we still see latency on errors."""
    try:
        ledger.record(
            model="unknown", provider="unknown",
            prompt_tokens=0, completion_tokens=0,
            latency_ms=latency_ms,
            caller=f"llm_provider_{mode}_failed",
            success=False,
        )
    except Exception:
        pass


# ── REST API ─────────────────────────────────────────────────────────────
cost_router = APIRouter(prefix="/api/llm-cost", tags=["llm-cost"])
_ledger_ref: Optional[LLMCostLedger] = None

def _get_ledger() -> LLMCostLedger:
    global _ledger_ref
    if _ledger_ref is None:
        _ledger_ref = LLMCostLedger()
    return _ledger_ref


@cost_router.get("/summary")
async def cost_summary():
    return _get_ledger().today_summary()

@cost_router.get("/models")
async def cost_by_model():
    return {"breakdown": _get_ledger().model_breakdown()}

@cost_router.get("/history")
async def cost_history(days: int = 30):
    return {"history": _get_ledger().daily_history(days)}

@cost_router.get("/calls")
async def recent_calls(n: int = 50):
    return {"calls": _get_ledger().recent_calls(n)}
