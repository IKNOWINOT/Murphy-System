"""
Ship 31bm.API_PATCHER — slowly audit ingested APIs.

Murphy-approved spec (2026-06-13):
  - 12-minute cadence (5/hour, ~120/day)
  - 1 API per run (gentle on external endpoints + LLM)
  - Retry transient failures (up to 3 attempts over 3 days)
  - Score = HTTP reachability + auth fit + Murphy compatibility
  - Outcomes:
      * status='active'        → R424 picks it up
      * status='incompatible'  → out of scope or broken
      * status='retry'         → transient; try again later
      * status='blocked'       → affiliate, paid-only, or unsafe

Schema additions (idempotent):
  attempts            INTEGER  — number of probe attempts
  last_attempt_at     TEXT
  fit_score           REAL     — 0-1; higher = better fit
  fit_notes           TEXT
"""
import json
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple

DB = "/var/lib/murphy-production/api_registry.db"
PATCH_LOG_DB = "/var/lib/murphy-production/api_patch_log.db"

MAX_ATTEMPTS = 3
RETRY_BACKOFF_HOURS = 24

# Hostnames Murphy ALREADY uses (no value to re-add)
ALREADY_INTEGRATED = {
    "api.openai.com", "api.together.xyz", "api.anthropic.com",
    "api.coingecko.com", "api.nowpayments.io", "api.stripe.com",
    "api.twilio.com", "api.github.com",
}

# Vendor blocklist: pay-per-run or affiliate-dependent
BLOCKED_HOSTS = {"apify.com", "rapidapi.com"}


def _init_schema():
    conn = sqlite3.connect(DB, timeout=15.0)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(api_registry)").fetchall()]
    if "attempts" not in cols:
        conn.execute("ALTER TABLE api_registry ADD COLUMN attempts INTEGER DEFAULT 0")
    if "last_attempt_at" not in cols:
        conn.execute("ALTER TABLE api_registry ADD COLUMN last_attempt_at TEXT")
    if "fit_score" not in cols:
        conn.execute("ALTER TABLE api_registry ADD COLUMN fit_score REAL")
    if "fit_notes" not in cols:
        conn.execute("ALTER TABLE api_registry ADD COLUMN fit_notes TEXT")
    conn.commit()
    conn.close()

    log = sqlite3.connect(PATCH_LOG_DB, timeout=15.0)
    log.execute("""CREATE TABLE IF NOT EXISTS patch_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        api_id TEXT,
        from_status TEXT,
        to_status TEXT,
        http_code INTEGER,
        elapsed_ms INTEGER,
        fit_score REAL,
        reason TEXT)""")
    log.commit()
    log.close()


def _log(api_id, from_s, to_s, http_code, elapsed_ms, score, reason):
    try:
        with sqlite3.connect(PATCH_LOG_DB, timeout=10.0) as c:
            c.execute("INSERT INTO patch_log (ts,api_id,from_status,to_status,http_code,elapsed_ms,fit_score,reason) VALUES (?,?,?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), api_id, from_s, to_s, http_code, elapsed_ms, score, reason[:300]))
    except Exception:
        pass


def _pick_next() -> Optional[Dict]:
    """Pick the highest-tier pending API that's due for probing."""
    backoff_cutoff = (datetime.now(timezone.utc) - timedelta(hours=RETRY_BACKOFF_HOURS)).isoformat()
    conn = sqlite3.connect(DB, timeout=15.0)
    conn.row_factory = sqlite3.Row
    row = conn.execute("""
        SELECT * FROM api_registry
        WHERE status IN ('pending', 'retry')
          AND (attempts IS NULL OR attempts < ?)
          AND (last_attempt_at IS NULL OR last_attempt_at < ?)
        ORDER BY tier ASC, registered_at ASC
        LIMIT 1
    """, (MAX_ATTEMPTS, backoff_cutoff)).fetchone()
    conn.close()
    return dict(row) if row else None


def _probe(url: str, timeout: int = 12) -> Tuple[int, int, str]:
    """HTTP HEAD/GET probe. Returns (http_code, elapsed_ms, error_detail)."""
    import time
    start = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Murphy/31bm-patcher"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed_ms = int((time.time() - start) * 1000)
            return resp.getcode(), elapsed_ms, ""
    except urllib.error.HTTPError as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return e.code, elapsed_ms, str(e)
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return 0, elapsed_ms, str(e)[:100]


def _classify(api: Dict, http_code: int, elapsed_ms: int, err: str) -> Tuple[str, float, str]:
    """Decide new status + fit score + reason.

    Returns (new_status, fit_score, reason).
    """
    url = (api.get("test_url") or "").lower()
    host = url.split("//")[-1].split("/")[0]
    auth = api.get("auth_type") or ""
    attempts = (api.get("attempts") or 0) + 1

    # Block known affiliate / pay-per-run vendors
    for blocked in BLOCKED_HOSTS:
        if blocked in host:
            return ("blocked", 0.0,
                    f"vendor_blocked: {blocked} requires pay-per-run + affiliate code")

    # Already integrated
    for known in ALREADY_INTEGRATED:
        if known in host:
            return ("blocked", 0.0, f"already_integrated: {known}")

    # Reachability score
    if http_code in (200, 201, 204):
        score = 1.0
        new_status = "active"
        reason = f"http_{http_code}_in_{elapsed_ms}ms"
    elif http_code in (401, 403):
        # Needs auth — promising but can't auto-verify
        score = 0.7
        new_status = "needs_auth"
        reason = f"http_{http_code}_auth_required ({auth})"
    elif http_code in (404, 410):
        score = 0.0
        new_status = "incompatible"
        reason = f"http_{http_code}_not_found"
    elif http_code in (500, 502, 503, 504):
        # Transient — retry
        if attempts >= MAX_ATTEMPTS:
            score = 0.0
            new_status = "incompatible"
            reason = f"http_{http_code}_after_{attempts}_attempts"
        else:
            score = 0.3
            new_status = "retry"
            reason = f"http_{http_code}_transient_attempt_{attempts}"
    elif http_code == 0:
        # Network error
        if attempts >= MAX_ATTEMPTS:
            score = 0.0
            new_status = "incompatible"
            reason = f"network_failed_after_{attempts}: {err}"
        else:
            score = 0.2
            new_status = "retry"
            reason = f"network_attempt_{attempts}: {err}"
    else:
        score = 0.5
        new_status = "needs_review"
        reason = f"http_{http_code}_unusual"

    return new_status, score, reason


def patch_one() -> Dict:
    """Run one patch cycle: probe + classify + update."""
    _init_schema()
    api = _pick_next()
    if not api:
        return {"ok": True, "action": "queue_empty",
                "msg": "No pending APIs due for probing"}

    test_url = api.get("test_url") or api.get("base_url") or ""
    if not test_url:
        # No probable URL
        conn = sqlite3.connect(DB, timeout=15.0)
        conn.execute("UPDATE api_registry SET status='incompatible', attempts=attempts+1, last_attempt_at=?, fit_score=0, fit_notes='no_url' WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), api["id"]))
        conn.commit(); conn.close()
        _log(api["id"], api["status"], "incompatible", 0, 0, 0.0, "no_url")
        return {"ok": True, "action": "marked_incompatible_no_url",
                "api_id": api["id"], "api_name": api["name"]}

    http_code, elapsed_ms, err = _probe(test_url)
    new_status, fit_score, reason = _classify(api, http_code, elapsed_ms, err)

    # Ship 31bn — wrap successful URLs with Murphy tracking so future
    # outbound link embeds carry our ref code, not third-party affiliate codes
    tracked_url_31bn = ""
    if new_status in ("active", "needs_auth"):
        try:
            from src.revenue_ledger_31bn import rewrite_link
            rw = rewrite_link(test_url, recipient="system", tenant_id="murphy_platform",
                              context=f"api_registry/{api['id']}")
            if rw.get("ok"):
                tracked_url_31bn = rw["tracked_url"]
        except Exception:
            pass

    # Update
    conn = sqlite3.connect(DB, timeout=15.0)
    conn.execute("""UPDATE api_registry SET
        status=?, attempts=COALESCE(attempts,0)+1, last_attempt_at=?,
        test_result=?, fit_score=?, fit_notes=?, last_tested=?
        WHERE id=?""", (
        new_status, datetime.now(timezone.utc).isoformat(),
        f"http={http_code} elapsed={elapsed_ms}ms",
        fit_score, reason, datetime.now(timezone.utc).isoformat(),
        api["id"]
    ))
    conn.commit(); conn.close()

    _log(api["id"], api["status"], new_status, http_code, elapsed_ms, fit_score, reason)

    return {
        "ok":            True,
        "action":        "probed",
        "api_id":        api["id"],
        "api_name":      api["name"][:60],
        "test_url":      test_url[:100],
        "http_code":     http_code,
        "elapsed_ms":    elapsed_ms,
        "from_status":   api["status"],
        "to_status":     new_status,
        "fit_score":     fit_score,
        "reason":        reason,
    }


def stats() -> Dict:
    """Reporting for /api/health/api_patcher."""
    conn = sqlite3.connect(DB, timeout=15.0)
    counts = dict(conn.execute("SELECT status, COUNT(*) FROM api_registry GROUP BY status").fetchall())
    total = sum(counts.values())
    by_cat_active = dict(conn.execute("""
        SELECT json_extract(tags, '$[0]') AS cat, COUNT(*)
        FROM api_registry WHERE status='active'
        GROUP BY cat ORDER BY 2 DESC LIMIT 10
    """).fetchall())
    conn.close()

    log_total = 0
    try:
        with sqlite3.connect(PATCH_LOG_DB, timeout=10.0) as c:
            log_total = c.execute("SELECT COUNT(*) FROM patch_log WHERE ts > datetime('now','-7 days')").fetchone()[0]
    except Exception:
        pass

    pct_processed = round(100 * (total - counts.get("pending", 0) - counts.get("retry", 0)) / max(1, total), 1)
    return {
        "total_apis":        total,
        "by_status":         counts,
        "pct_processed":     pct_processed,
        "active_by_category": by_cat_active,
        "patches_7d":        log_total,
        "cadence":           "every 12 minutes (5/hour)",
        "max_attempts":      MAX_ATTEMPTS,
    }


if __name__ == "__main__":
    import sys
    if "--stats" in sys.argv:
        print(json.dumps(stats(), indent=2))
    else:
        result = patch_one()
        print(json.dumps(result, indent=2))
