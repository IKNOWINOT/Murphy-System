#!/usr/bin/env python3
"""
Ship 31ch — team_synthesis Fit Detector

Per b2b_positioning_2026_06_15 rule:
  Murphy spots tier_2_team accounts whose usage pattern shows they
  need advanced synthesis and would benefit from a quiet upgrade to
  team_synthesis (the unadvertised escalation SKU between Team $399
  and Business $799). Default proposed range $499–$599/mo.

  Murphy auto-detects. Surfaces fit candidates in the daily digest
  (Ship 31cg). Founder approves per row before any offer goes out.
  NEVER offers directly to customers.

Adjacent module. Kernel untouched. Posture-gated (only runs when
posture != OFF). Snapshot before any DB write. Idempotent on tenant_id
+ measurement_window (re-runs don't double-file).
"""
from __future__ import annotations
import sqlite3, json, sys, logging, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, "/opt/Murphy-System")

PROPOSAL_DB = "/var/lib/murphy-production/team_synthesis_fit.db"
TENANTS_DB  = "/var/lib/murphy-production/tenants.db"
INBOUND_DB  = "/var/lib/murphy-production/inbound_replies.db"
THREAD_DB   = "/var/lib/murphy-production/thread_situation.db"

logging.basicConfig(level=logging.INFO, format="  %(message)s")
log = logging.getLogger("team_synthesis_fit")
NOW = datetime.now(timezone.utc)


# ─── schema ───

def _init():
    c = sqlite3.connect(PROPOSAL_DB, timeout=10.0)
    c.execute("""CREATE TABLE IF NOT EXISTS fit_proposals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        tenant_name TEXT,
        detected_at TEXT NOT NULL,
        measurement_window_days INTEGER,
        fit_score REAL,
        signals_json TEXT,
        proposed_price_floor INTEGER DEFAULT 499,
        proposed_price_ceiling INTEGER DEFAULT 599,
        status TEXT DEFAULT 'pending_founder',  -- pending_founder | approved | rejected | offered | accepted | declined
        founder_decision_at TEXT,
        founder_decision_by TEXT,
        founder_decision_note TEXT,
        UNIQUE(tenant_id, measurement_window_days)
    )""")
    c.commit(); c.close()


# ─── tier reader (canonical, via platform_engine) ───

def get_tenant_tier(tenant_id: str) -> str:
    """Returns 'tier_2_team' | 'tier_1_solo' | ... | 'unknown'."""
    try:
        from src.platform_engine import get_subscription_status
        st = get_subscription_status(tenant_id)
        return st.get("tier", "unknown")
    except Exception:
        return "unknown"


# ─── signal scoring ───

WINDOW_DAYS = 30

def _count_summarize_intents(tenant_id: str) -> int:
    """How many summarize-style requests in the measurement window?"""
    try:
        c = sqlite3.connect(f"file:{INBOUND_DB}?mode=ro", uri=True, timeout=8)
        n = c.execute(
            "SELECT COUNT(*) FROM inbound_replies "
            "WHERE tenant_id=? AND received_at > datetime('now', ?) "
            "AND (LOWER(subject) LIKE '%summarize%' "
            "  OR LOWER(subject) LIKE '%summary%' "
            "  OR LOWER(body_preview) LIKE '%summarize%' "
            "  OR LOWER(body_preview) LIKE '%what did we say%' "
            "  OR LOWER(body_preview) LIKE '%recap%' "
            "  OR intent_class IN ('summarize','recall','synthesize'))",
            (tenant_id, f"-{WINDOW_DAYS} days")
        ).fetchone()[0]
        c.close()
        return n
    except Exception:
        return 0


def _count_threads(tenant_id: str) -> int:
    """Total active threads — proxy for volume."""
    try:
        c = sqlite3.connect(f"file:{INBOUND_DB}?mode=ro", uri=True, timeout=8)
        n = c.execute(
            "SELECT COUNT(DISTINCT from_addr) FROM inbound_replies "
            "WHERE tenant_id=? AND received_at > datetime('now', ?)",
            (tenant_id, f"-{WINDOW_DAYS} days")
        ).fetchone()[0]
        c.close()
        return n
    except Exception:
        return 0


def _count_cross_domain_threads(tenant_id: str) -> int:
    """Distinct domains in the tenant's inbox — proxy for breadth."""
    try:
        c = sqlite3.connect(f"file:{INBOUND_DB}?mode=ro", uri=True, timeout=8)
        n = c.execute(
            "SELECT COUNT(DISTINCT from_domain) FROM inbound_replies "
            "WHERE tenant_id=? AND received_at > datetime('now', ?) "
            "AND from_domain IS NOT NULL",
            (tenant_id, f"-{WINDOW_DAYS} days")
        ).fetchone()[0]
        c.close()
        return n
    except Exception:
        return 0


def _count_unique_verticals(tenant_id: str) -> int:
    """Distinct conversation verticals — proxy for synthesis need."""
    try:
        # join inbound_replies → thread_situation by from_addr
        c = sqlite3.connect(f"file:{INBOUND_DB}?mode=ro", uri=True, timeout=8)
        addrs = c.execute(
            "SELECT DISTINCT from_addr FROM inbound_replies "
            "WHERE tenant_id=? AND received_at > datetime('now', ?)",
            (tenant_id, f"-{WINDOW_DAYS} days")
        ).fetchall()
        c.close()
        if not addrs: return 0
        t = sqlite3.connect(f"file:{THREAD_DB}?mode=ro", uri=True, timeout=8)
        placeholders = ",".join(["?"]*len(addrs))
        verts = t.execute(
            f"SELECT DISTINCT vertical FROM thread_situation "
            f"WHERE from_addr IN ({placeholders}) AND vertical IS NOT NULL",
            tuple(a[0] for a in addrs)
        ).fetchall()
        t.close()
        return len(verts)
    except Exception:
        return 0


def score_tenant(tenant_id: str) -> dict:
    """Compute fit score 0.0–1.0 for team_synthesis."""
    signals = {
        "summarize_requests": _count_summarize_intents(tenant_id),
        "thread_count":       _count_threads(tenant_id),
        "cross_domain_count": _count_cross_domain_threads(tenant_id),
        "unique_verticals":   _count_unique_verticals(tenant_id),
    }

    # Scoring (each signal contributes 0–0.3, capped):
    #   summarize: 5+ in 30d = strong
    #   threads: 50+ = active
    #   cross_domain: 20+ = breadth
    #   verticals: 3+ = needs synthesis
    score = 0.0
    if signals["summarize_requests"] >= 5: score += 0.30
    elif signals["summarize_requests"] >= 2: score += 0.15
    if signals["thread_count"] >= 50: score += 0.25
    elif signals["thread_count"] >= 20: score += 0.10
    if signals["cross_domain_count"] >= 20: score += 0.25
    elif signals["cross_domain_count"] >= 10: score += 0.10
    if signals["unique_verticals"] >= 3: score += 0.20
    elif signals["unique_verticals"] >= 2: score += 0.10

    return {"signals": signals, "fit_score": round(min(score, 1.0), 3)}


# ─── proposal filing ───

def file_proposal(tenant_id: str, tenant_name: str, scoring: dict) -> int | None:
    """File a fit proposal if score >= 0.5 and not already filed for this window."""
    if scoring["fit_score"] < 0.5: return None
    _init()
    c = sqlite3.connect(PROPOSAL_DB, timeout=10.0)
    try:
        # idempotent: skip if same tenant + same window already pending/approved
        existing = c.execute(
            "SELECT id, status FROM fit_proposals "
            "WHERE tenant_id=? AND measurement_window_days=? "
            "AND status IN ('pending_founder','approved','offered','accepted') "
            "ORDER BY id DESC LIMIT 1",
            (tenant_id, WINDOW_DAYS)
        ).fetchone()
        if existing:
            log.info(f"  ─ skip {tenant_id[:14]} — already filed (id={existing[0]} status={existing[1]})")
            return None
        cur = c.execute(
            """INSERT INTO fit_proposals
               (tenant_id, tenant_name, detected_at, measurement_window_days,
                fit_score, signals_json, proposed_price_floor, proposed_price_ceiling, status)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (tenant_id, tenant_name, NOW.isoformat(), WINDOW_DAYS,
             scoring["fit_score"], json.dumps(scoring["signals"]),
             499, 599, "pending_founder")
        )
        c.commit()
        return cur.lastrowid
    finally:
        c.close()


# ─── posture gate ───

def _posture() -> str:
    try:
        from src.autonomy_policy_31cb import get_posture
        return get_posture()
    except Exception:
        return "OFF"


# ─── main cycle ───

def run_cycle() -> dict:
    posture = _posture()
    log.info(f"team_synthesis fit-detector cycle @ {NOW.isoformat()}, posture={posture}")
    if posture == "OFF":
        log.info("  posture=OFF — skipping (founder controls the switch)")
        return {"ok": True, "skipped": True, "reason": "posture_off"}

    _init()

    # Enumerate active tenants
    try:
        c = sqlite3.connect(f"file:{TENANTS_DB}?mode=ro", uri=True, timeout=8)
        tenants = c.execute(
            "SELECT tenant_id, name FROM tenants WHERE state='active'"
        ).fetchall()
        c.close()
    except Exception as e:
        log.warning(f"  tenants read failed: {e}")
        return {"ok": False, "error": str(e)}

    log.info(f"  examining {len(tenants)} active tenants")
    examined, candidates, filed = 0, 0, 0
    for tenant_id, name in tenants:
        if not tenant_id: continue
        examined += 1
        tier = get_tenant_tier(tenant_id)
        if tier != "tier_2_team":
            continue
        scoring = score_tenant(tenant_id)
        if scoring["fit_score"] < 0.5:
            continue
        candidates += 1
        pid = file_proposal(tenant_id, name or tenant_id, scoring)
        if pid:
            filed += 1
            log.info(f"  ✅ filed #{pid} for {name or tenant_id} "
                     f"(score={scoring['fit_score']:.2f})")

    summary = {"ok": True, "examined": examined, "candidates": candidates, "filed": filed,
               "posture": posture, "ts": NOW.isoformat()}
    print(json.dumps(summary, indent=2))
    return summary


# ─── pending proposals reader (for digest) ───

def get_pending_proposals(limit: int = 10) -> list[dict]:
    _init()
    c = sqlite3.connect(PROPOSAL_DB, timeout=10.0)
    try:
        rows = c.execute(
            "SELECT id, tenant_id, tenant_name, detected_at, fit_score, "
            "signals_json, proposed_price_floor, proposed_price_ceiling "
            "FROM fit_proposals WHERE status='pending_founder' "
            "ORDER BY fit_score DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{
            "id": r[0], "tenant_id": r[1], "tenant_name": r[2],
            "detected_at": r[3], "fit_score": r[4],
            "signals": json.loads(r[5] or "{}"),
            "price_floor": r[6], "price_ceiling": r[7]
        } for r in rows]
    finally:
        c.close()


if __name__ == "__main__":
    run_cycle()
