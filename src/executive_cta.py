"""
executive_cta.py — Inference-driven CTA proposal layer

Founder directive (locked 2026-06-09):
  "CTA functions commissioned while it happens for user perspective
   through inference of success."

The system watches typed signals from agents, the boundary loop, and
the executive engine. When inference of success crosses a threshold,
a CTA proposal is emitted to the user's panel.

CTAs are PROPOSALS, not executions. The user clicks to commit. All
external-action commits still gate through HITL-v2 / vault / "Ask
Murphy Before All Choices" — CTAs are the surface, not a bypass.

Three categories:

  A) COMPLETION  — an agent successfully produced output
                   Trigger: agent_accomplishment_writer success=True
                   CTA:     "View output" / "Ship it" / "Send to customer"

  B) THRESHOLD   — a quality/score gate just passed
                   Trigger: BoundaryResultV3.satisfied=True,
                            apnea ∈ {SATISFIED, RAISE_CEILING}
                   CTA:     "Approve and exit" / "Raise ceiling — confirm?"

  C) STEERING    — executive engine emits objective-status change
                   Trigger: ObjectiveStatus transitions to AT_RISK or
                            BLOCKED; new GateStatus.OPEN
                   CTA:     "Approve gate" / "Reroute" / "Pause subsystem"

STORAGE:
  SQLite table executive_cta in murphy_audit.db (already live, 470 MB).
  Append-only with status column. Auto-expire after 30 min.

DEDUPE:
  Same (category, source_signal_hash) within 60s = single CTA, not three.
  Prevents agent-firing-5x-in-a-row spam.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("murphy.executive_cta")

AUDIT_DB_PATH = "/var/lib/murphy-production/murphy_audit.db"

# Auto-expire CTAs after this many seconds — keeps the panel fresh
DEFAULT_TTL_S = 1800   # 30 min

# Dedupe window — same (category, source_hash) collapses within this
DEDUPE_WINDOW_S = 60


class CtaCategory(str, Enum):
    COMPLETION = "completion"
    THRESHOLD  = "threshold"
    STEERING   = "steering"


class CtaStatus(str, Enum):
    PENDING   = "pending"
    COMMITTED = "committed"
    DISMISSED = "dismissed"
    EXPIRED   = "expired"


@dataclass
class CtaProposal:
    """A single CTA card the user sees on /os."""
    cta_id:           str
    category:         str          # CtaCategory value
    label:            str          # button label, e.g. "Ship it"
    description:      str          # one-line context, e.g. "Lead Engineer produced deliverable"
    action_uri:       str          # endpoint or app-relative URI to call on commit
    confidence:       float        # 0..1 — how sure the inference is
    source_signal:    Dict[str, Any] = field(default_factory=dict)
    source_hash:      str          = ""
    suggested_at_ns:  int          = 0
    expires_at_ns:    int          = 0
    status:           str          = CtaStatus.PENDING.value
    requires_hitl:    bool         = False   # outbound actions → True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─────────────────────────────────────────────────────────────
# Schema bootstrap (idempotent)
# ─────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS executive_cta (
    cta_id          TEXT PRIMARY KEY,
    category        TEXT NOT NULL,
    label           TEXT NOT NULL,
    description     TEXT NOT NULL,
    action_uri      TEXT NOT NULL,
    confidence      REAL NOT NULL,
    source_signal   TEXT NOT NULL,
    source_hash     TEXT NOT NULL,
    suggested_at_ns INTEGER NOT NULL,
    expires_at_ns   INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    requires_hitl   INTEGER NOT NULL DEFAULT 0,
    committed_at_ns INTEGER,
    committed_by    TEXT
);
CREATE INDEX IF NOT EXISTS idx_cta_status_suggested
    ON executive_cta(status, suggested_at_ns DESC);
CREATE INDEX IF NOT EXISTS idx_cta_dedupe
    ON executive_cta(category, source_hash, suggested_at_ns DESC);
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Idempotent — safe to call repeatedly."""
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
    except sqlite3.Error as e:
        LOG.warning("CTA schema bootstrap failed (non-fatal): %s", e)


def _get_conn() -> Optional[sqlite3.Connection]:
    """Return a connection or None. Fail-soft — CTA layer never blocks."""
    try:
        conn = sqlite3.connect(AUDIT_DB_PATH, timeout=3)
        _ensure_schema(conn)
        return conn
    except sqlite3.Error as e:
        LOG.warning("CTA db connect failed (non-fatal): %s", e)
        return None


# ─────────────────────────────────────────────────────────────
# Dedupe + hashing
# ─────────────────────────────────────────────────────────────

def _hash_signal(signal: Dict[str, Any]) -> str:
    """Stable hash for dedupe. Sorts keys so equivalent dicts hash same."""
    try:
        payload = json.dumps(signal, sort_keys=True, default=str)
    except Exception:
        payload = str(signal)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _is_duplicate(
    conn: sqlite3.Connection,
    category: str,
    source_hash: str,
    within_s: int = DEDUPE_WINDOW_S,
) -> bool:
    """Return True if a CTA with same (category, source_hash) was created within window."""
    try:
        threshold_ns = time.time_ns() - (within_s * 1_000_000_000)
        row = conn.execute(
            "SELECT cta_id FROM executive_cta "
            "WHERE category = ? AND source_hash = ? "
            "  AND suggested_at_ns >= ? AND status = 'pending' "
            "LIMIT 1",
            (category, source_hash, threshold_ns),
        ).fetchone()
        return row is not None
    except sqlite3.Error:
        return False


# ─────────────────────────────────────────────────────────────
# Category-A: completion CTAs (from agent_accomplishment_writer)
# ─────────────────────────────────────────────────────────────

def propose_completion_cta(
    *,
    role: str,
    domain: str,
    output_type: str,
    accomplishment_id: str,
    success: bool,
    quality_score: float = 0.8,
) -> Optional[CtaProposal]:
    """Called by agent_accomplishment_writer when an agent finishes work.

    Only proposes a CTA when success=True AND quality_score >= 0.7.
    Failures and low-quality outputs do not surface as CTAs (would
    spam the user with negative noise).
    """
    if not success or quality_score < 0.7:
        return None

    signal = {
        "role":              role,
        "domain":            domain,
        "output_type":       output_type,
        "accomplishment_id": accomplishment_id,
        "quality_score":     quality_score,
    }
    return _emit_cta(
        category=CtaCategory.COMPLETION.value,
        label=f"View {output_type}",
        description=f"{role} (in {domain}) produced {output_type}",
        action_uri=f"/os#accomplishment/{accomplishment_id}",
        confidence=quality_score,
        source_signal=signal,
        requires_hitl=False,
    )


# ─────────────────────────────────────────────────────────────
# Category-B: threshold CTAs (from BoundaryResultV3)
# ─────────────────────────────────────────────────────────────

def propose_threshold_cta(
    *,
    dispatch_id: str,
    apnea_recommendation: str,
    score: float,
    satisfied: bool,
    ceiling_level: int = 0,
) -> Optional[CtaProposal]:
    """Called by boundary loop after each detector pass."""
    if not satisfied:
        return None

    signal = {
        "dispatch_id":  dispatch_id,
        "apnea":        apnea_recommendation,
        "score":        score,
        "ceiling_level": ceiling_level,
    }

    if apnea_recommendation == "raise_goal_ceiling":
        label = "Raise ceiling — confirm?"
        description = (
            f"Goal hit early (score {score:.2f}). System proposes "
            f"raising ceiling to L{ceiling_level + 1}."
        )
        action_uri = f"/api/jobs/{dispatch_id}/raise_ceiling"
        requires_hitl = True
    elif apnea_recommendation == "satisfied":
        label = "Approve and exit"
        description = f"Boundary loop satisfied (score {score:.2f}). Approve final deliverable?"
        action_uri = f"/api/jobs/{dispatch_id}/approve"
        requires_hitl = True
    else:
        return None

    return _emit_cta(
        category=CtaCategory.THRESHOLD.value,
        label=label,
        description=description,
        action_uri=action_uri,
        confidence=score,
        source_signal=signal,
        requires_hitl=requires_hitl,
    )


# ─────────────────────────────────────────────────────────────
# Category-C: steering CTAs (from executive_planning_engine)
# ─────────────────────────────────────────────────────────────

def propose_steering_cta(
    *,
    objective_id: str,
    objective_name: str,
    old_status: str,
    new_status: str,
    gate_id: Optional[str] = None,
) -> Optional[CtaProposal]:
    """Called when executive engine flips an objective status."""
    interesting_transitions = {
        ("on_track", "at_risk"),
        ("on_track", "blocked"),
        ("active", "at_risk"),
        ("active", "blocked"),
        ("at_risk", "blocked"),
    }
    if (old_status, new_status) not in interesting_transitions:
        return None

    signal = {
        "objective_id":   objective_id,
        "old_status":     old_status,
        "new_status":     new_status,
        "gate_id":        gate_id,
    }

    label = "Review and steer"
    description = f"{objective_name} → {new_status}. Review and decide next step."
    action_uri = f"/os#objective/{objective_id}"

    return _emit_cta(
        category=CtaCategory.STEERING.value,
        label=label,
        description=description,
        action_uri=action_uri,
        confidence=0.9,   # status change is unambiguous signal
        source_signal=signal,
        requires_hitl=True,
    )


# ─────────────────────────────────────────────────────────────
# Core emit + read + commit
# ─────────────────────────────────────────────────────────────

def _emit_cta(
    *,
    category: str,
    label: str,
    description: str,
    action_uri: str,
    confidence: float,
    source_signal: Dict[str, Any],
    requires_hitl: bool = False,
    ttl_s: int = DEFAULT_TTL_S,
) -> Optional[CtaProposal]:
    """Internal: create a CTA, dedupe, persist. Returns the proposal or None."""
    conn = _get_conn()
    if conn is None:
        return None

    source_hash = _hash_signal(source_signal)
    if _is_duplicate(conn, category, source_hash):
        conn.close()
        LOG.debug("CTA deduped: category=%s hash=%s", category, source_hash)
        return None

    now_ns = time.time_ns()
    proposal = CtaProposal(
        cta_id=str(uuid.uuid4()),
        category=category,
        label=label,
        description=description,
        action_uri=action_uri,
        confidence=float(max(0.0, min(1.0, confidence))),
        source_signal=source_signal,
        source_hash=source_hash,
        suggested_at_ns=now_ns,
        expires_at_ns=now_ns + (ttl_s * 1_000_000_000),
        status=CtaStatus.PENDING.value,
        requires_hitl=requires_hitl,
    )

    try:
        conn.execute(
            "INSERT INTO executive_cta "
            "(cta_id, category, label, description, action_uri, confidence, "
            " source_signal, source_hash, suggested_at_ns, expires_at_ns, "
            " status, requires_hitl) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                proposal.cta_id, proposal.category, proposal.label,
                proposal.description, proposal.action_uri, proposal.confidence,
                json.dumps(proposal.source_signal), proposal.source_hash,
                proposal.suggested_at_ns, proposal.expires_at_ns,
                proposal.status, int(proposal.requires_hitl),
            ),
        )
        conn.commit()
    except sqlite3.Error as e:
        LOG.warning("CTA insert failed (non-fatal): %s", e)
        conn.close()
        return None

    conn.close()

    # Also pulse cadence so panel can know "new CTA" without polling
    try:
        from src.cadence_emit import emit_heartbeat
        emit_heartbeat(
            source=f"cta.{category}",
            success=True,
            metadata={"cta_id": proposal.cta_id, "label": label},
        )
    except Exception:
        pass

    return proposal


def list_pending(limit: int = 10) -> List[Dict[str, Any]]:
    """Return up to `limit` pending CTAs, newest first. Auto-expires stale rows."""
    conn = _get_conn()
    if conn is None:
        return []

    now_ns = time.time_ns()
    try:
        # Auto-expire
        conn.execute(
            "UPDATE executive_cta SET status = 'expired' "
            "WHERE status = 'pending' AND expires_at_ns < ?",
            (now_ns,),
        )
        conn.commit()

        rows = conn.execute(
            "SELECT cta_id, category, label, description, action_uri, "
            "       confidence, source_signal, suggested_at_ns, "
            "       expires_at_ns, status, requires_hitl "
            "FROM executive_cta "
            "WHERE status = 'pending' "
            "ORDER BY suggested_at_ns DESC "
            "LIMIT ?",
            (limit,),
        ).fetchall()
    except sqlite3.Error as e:
        LOG.warning("CTA list failed: %s", e)
        conn.close()
        return []

    conn.close()
    out = []
    for r in rows:
        try:
            signal = json.loads(r[6])
        except Exception:
            signal = {}
        out.append({
            "cta_id":          r[0],
            "category":        r[1],
            "label":           r[2],
            "description":     r[3],
            "action_uri":      r[4],
            "confidence":      r[5],
            "source_signal":   signal,
            "suggested_at_ns": r[7],
            "age_seconds":     (now_ns - r[7]) / 1e9,
            "expires_at_ns":   r[8],
            "status":          r[9],
            "requires_hitl":   bool(r[10]),
        })
    return out


def commit_cta(cta_id: str, committed_by: str = "user") -> Dict[str, Any]:
    """Mark a CTA as committed. Returns the row (or error dict)."""
    return _transition_cta(cta_id, CtaStatus.COMMITTED.value, committed_by)


def dismiss_cta(cta_id: str, dismissed_by: str = "user") -> Dict[str, Any]:
    """Mark a CTA as dismissed."""
    return _transition_cta(cta_id, CtaStatus.DISMISSED.value, dismissed_by)


def _transition_cta(cta_id: str, new_status: str, actor: str) -> Dict[str, Any]:
    conn = _get_conn()
    if conn is None:
        return {"error": "db_unavailable", "cta_id": cta_id}
    try:
        cur = conn.execute(
            "UPDATE executive_cta "
            "SET status = ?, committed_at_ns = ?, committed_by = ? "
            "WHERE cta_id = ? AND status = 'pending'",
            (new_status, time.time_ns(), actor, cta_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            conn.close()
            return {"error": "cta_not_pending", "cta_id": cta_id}
    except sqlite3.Error as e:
        conn.close()
        return {"error": "db_error", "detail": str(e), "cta_id": cta_id}

    conn.close()
    return {"ok": True, "cta_id": cta_id, "status": new_status, "actor": actor}
