"""
PCR-054m — Corpus Feedback Loop (event-sourced weights)

Founder's reframe (locked 2026-06-09):
  "Their employees train the system. The language and generation
   follows."

This module CLOSES the learning loop. PCR-054k captures what
practitioners SAY. PCR-054l uses that voice at draft time. But until
this patch, the system has no way to know WHICH voice actually leads
to good outcomes. A practitioner whose attestations always get FLAGGED
in post-fact verification is sending noisy signal — we shouldn't weigh
them the same as a practitioner whose attestations always VERIFY.

ARCHITECTURE — Murphy-approved C/Y/R/γ (chat-v2 consult 2026-06-09)
==================================================================
C) HYBRID granularity: per-engagement OUTCOME weight + per-entry
   INTENT modifier. A verified engagement reinforces attestation-
   intent entries strongly and clarifying-question entries weakly.

Y) RANK strategy: weights affect ORDER BY in voice queries, not
   filtering. Low-weight entries still appear, just later. Hard
   filtering is dangerous early — could exclude a practitioner
   before they have enough history to evaluate fairly.

R) STANDALONE TIMER: 'murphy-corpus-feedback.timer' (queued separately,
   pattern follows PCR-054i / engagement-inbound). Decoupled from
   state machine. Backfillable.

γ) EVENT-SOURCED schema: practitioner_corpus_feedback_events table.
   weight = SUM(weight_delta) per entry_id. Every weight change has
   a row explaining where it came from. Maximum auditability.

WEIGHT MODEL (C — hybrid granularity)
=====================================
For each entry harvested from engagement E, when E resolves to
terminal state T:

  outcome_delta(T) =
    VERIFIED -> +1.0
    FLAGGED  -> -0.8
    DECLINED_OR_EDITS_ASKED (terminal) -> -0.4

  intent_modifier(I) =
    attestation        -> 1.0   (strongest signal — this IS the work)
    revision_request   -> 0.5   (medium — practitioner improving)
    clarifying_question-> 0.3   (weak — early-stage signal)
    other              -> 0.2

  weight_delta = outcome_delta(T) * intent_modifier(I)

Examples:
  Jane sends an attestation, engagement VERIFIES: delta = +1.0 * 1.0 = +1.0
  Jane sends an attestation, engagement FLAGS:    delta = -0.8 * 1.0 = -0.8
  Jane asks a clarifying-q, engagement VERIFIES:  delta = +1.0 * 0.3 = +0.3
  Jane sends a revision,    engagement FLAGS:     delta = -0.8 * 0.5 = -0.4

DEFAULT WEIGHT
==============
Entries with no feedback events have effective weight = 1.0
(the conventional default). This matches the pre-054m world where
every entry was implicitly equal.

PRIVACY
=======
The feedback events table stores entry_id which is already scoped
to (practitioner_id, tenant_id) via the corpus. No tenant-crossing
queries; tenant isolation inherits from 054k.

REVERSIBILITY
=============
- New table only. No mutations to practitioner_corpus_entries.
- voice queries get optional include_weights param. Omitted =
  unchanged behavior. Set to True = ORDER BY weight DESC instead
  of received_at DESC.
- Disable the timer: rolls back instantly. Existing weights remain
  but stop updating. Future drafts use whatever the last weights
  were until backfill clears them.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.engagement_folder import DEFAULT_DB_PATH as ENGAGEMENT_DB_PATH
from src.engagement_folder import FolderState

LOG = logging.getLogger("murphy.corpus_feedback")


# ─────────────────────────────────────────────────────────────────────
# Weight model (C — hybrid)
# ─────────────────────────────────────────────────────────────────────

# Outcome deltas by terminal folder state
OUTCOME_DELTAS: Dict[str, float] = {
    "verified":                +1.0,
    "flagged":                 -0.8,
    "declined_or_edits_asked": -0.4,
}

# Intent modifiers (scales the outcome delta)
INTENT_MODIFIERS: Dict[str, float] = {
    "attestation":         1.0,
    "revision_request":    0.5,
    "clarifying_question": 0.3,
    "decline":             0.4,
    "other":               0.2,
}

DEFAULT_INTENT_MODIFIER = 0.2  # unknown intents


# ─────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS practitioner_corpus_feedback_events (
    event_id              TEXT PRIMARY KEY,
    entry_id              TEXT NOT NULL,
    source_engagement_id  TEXT NOT NULL,
    outcome_state         TEXT NOT NULL,
    intent                TEXT NOT NULL,
    weight_delta          REAL NOT NULL,
    reason                TEXT NOT NULL,
    created_at            REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_feedback_entry
    ON practitioner_corpus_feedback_events (entry_id);

CREATE INDEX IF NOT EXISTS idx_feedback_engagement
    ON practitioner_corpus_feedback_events (source_engagement_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_unique
    ON practitioner_corpus_feedback_events (entry_id, source_engagement_id, outcome_state);
"""


def init_feedback_db(db_path: str = ENGAGEMENT_DB_PATH) -> None:
    """Idempotent — safe on every startup or before any operation."""
    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────


@dataclass
class FeedbackEvent:
    event_id:              str
    entry_id:              str
    source_engagement_id:  str
    outcome_state:         str
    intent:                str
    weight_delta:          float
    reason:                str
    created_at:            float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "event_id":             self.event_id,
            "entry_id":             self.entry_id,
            "source_engagement_id": self.source_engagement_id,
            "outcome_state":        self.outcome_state,
            "intent":               self.intent,
            "weight_delta":         self.weight_delta,
            "reason":               self.reason,
            "created_at":           self.created_at,
        }


# ─────────────────────────────────────────────────────────────────────
# Core: compute_weight_delta (pure function — Murphy's C strategy)
# ─────────────────────────────────────────────────────────────────────


def compute_weight_delta(outcome_state: str, intent: str) -> float:
    """Per-engagement outcome * per-entry intent modifier.

    Pure function — no I/O, fully testable, deterministic.
    Unknown outcome -> 0.0 (no signal).
    Unknown intent  -> DEFAULT_INTENT_MODIFIER.
    """
    outcome_delta = OUTCOME_DELTAS.get(outcome_state, 0.0)
    intent_mod = INTENT_MODIFIERS.get(intent, DEFAULT_INTENT_MODIFIER)
    return outcome_delta * intent_mod


# ─────────────────────────────────────────────────────────────────────
# Record feedback for a single engagement
# ─────────────────────────────────────────────────────────────────────


def record_engagement_feedback(
    engagement_id: str,
    outcome_state: str,
    *,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> Dict[str, Any]:
    """Read all corpus entries from an engagement and record feedback events.

    Idempotent — re-running with same (entry_id, engagement_id, outcome)
    triggers the UNIQUE index and SQLite rejects the insert. So a timer
    that processes the same engagement twice doesn't double-count weight.

    Returns a summary dict.
    """
    init_feedback_db(db_path)

    # Validate outcome is a recognized terminal state
    if outcome_state not in OUTCOME_DELTAS:
        return {
            "ok":            False,
            "engagement_id": engagement_id,
            "reason":        f"outcome {outcome_state!r} not in OUTCOME_DELTAS",
            "events":        0,
        }

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        # Pull every corpus entry harvested from this engagement
        rows = con.execute(
            "SELECT entry_id, intent FROM practitioner_corpus_entries "
            "WHERE source_engagement_id = ?",
            (engagement_id,),
        ).fetchall()

        events_recorded = 0
        events_skipped = 0
        now = time.time()

        for row in rows:
            entry_id = row["entry_id"]
            intent = row["intent"]
            delta = compute_weight_delta(outcome_state, intent)
            event_id = f"fb_{entry_id[:12]}_{outcome_state[:4]}_{int(now*1000)%1000000:06d}"
            reason = f"engagement {engagement_id} resolved to {outcome_state}; intent={intent}"

            try:
                con.execute(
                    "INSERT INTO practitioner_corpus_feedback_events "
                    "(event_id, entry_id, source_engagement_id, outcome_state, "
                    " intent, weight_delta, reason, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (event_id, entry_id, engagement_id, outcome_state,
                     intent, delta, reason, now),
                )
                events_recorded += 1
            except sqlite3.IntegrityError:
                # UNIQUE violation — already recorded
                events_skipped += 1

        con.commit()
    finally:
        con.close()

    LOG.info(
        "PCR-054m feedback recorded engagement=%s outcome=%s "
        "events=%d skipped=%d",
        engagement_id, outcome_state, events_recorded, events_skipped,
    )
    return {
        "ok":             True,
        "engagement_id":  engagement_id,
        "outcome_state":  outcome_state,
        "events":         events_recorded,
        "skipped":        events_skipped,
    }


# ─────────────────────────────────────────────────────────────────────
# Get effective weight for an entry (SUM of all deltas + default 1.0)
# ─────────────────────────────────────────────────────────────────────


def get_entry_weight(
    entry_id: str,
    *,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> float:
    """SUM all weight_delta for this entry + 1.0 default.

    Cheap read — indexed on entry_id.
    """
    init_feedback_db(db_path)
    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            "SELECT COALESCE(SUM(weight_delta), 0.0) FROM "
            "practitioner_corpus_feedback_events WHERE entry_id = ?",
            (entry_id,),
        ).fetchone()
    finally:
        con.close()
    return 1.0 + (row[0] if row else 0.0)


def get_entry_weights_bulk(
    entry_ids: List[str],
    *,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> Dict[str, float]:
    """Bulk version: returns {entry_id: weight} for all requested ids.

    Defaults missing ids to 1.0.
    """
    if not entry_ids:
        return {}
    init_feedback_db(db_path)
    con = sqlite3.connect(db_path)
    try:
        placeholders = ",".join("?" * len(entry_ids))
        rows = con.execute(
            f"SELECT entry_id, SUM(weight_delta) FROM "
            f"practitioner_corpus_feedback_events "
            f"WHERE entry_id IN ({placeholders}) GROUP BY entry_id",
            entry_ids,
        ).fetchall()
    finally:
        con.close()
    deltas = {r[0]: (r[1] or 0.0) for r in rows}
    return {eid: 1.0 + deltas.get(eid, 0.0) for eid in entry_ids}


# ─────────────────────────────────────────────────────────────────────
# Batch processor — the R timer's main entry point
# ─────────────────────────────────────────────────────────────────────


def process_resolved_engagements(
    *,
    limit: int = 100,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> Dict[str, Any]:
    """Scan finalized/verified/flagged folders, record feedback events.

    Idempotent — the UNIQUE(entry_id, source_engagement_id, outcome_state)
    index prevents double-counting.

    Designed to be called from a heartbeat or systemd timer.
    """
    init_feedback_db(db_path)

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        # Pull engagements in terminal-or-near-terminal states
        rows = con.execute(
            "SELECT engagement_id, state FROM engagement_folders "
            "WHERE state IN ('verified', 'flagged', 'declined_or_edits_asked') "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    except sqlite3.OperationalError:
        # engagement_folders table doesn't exist in this DB
        rows = []
    finally:
        con.close()

    results = []
    for row in rows:
        result = record_engagement_feedback(
            row["engagement_id"], row["state"], db_path=db_path,
        )
        results.append(result)

    total_recorded = sum(r.get("events", 0) for r in results)
    total_skipped = sum(r.get("skipped", 0) for r in results)
    return {
        "ok":             True,
        "engagements":    len(results),
        "events_recorded": total_recorded,
        "events_skipped":  total_skipped,
        "results":        results,
    }


# ─────────────────────────────────────────────────────────────────────
# Audit query — explain a weight
# ─────────────────────────────────────────────────────────────────────


def explain_entry_weight(
    entry_id: str,
    *,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> Dict[str, Any]:
    """Why does this entry have its current weight? Return the event log."""
    init_feedback_db(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT * FROM practitioner_corpus_feedback_events "
            "WHERE entry_id = ? ORDER BY created_at ASC",
            (entry_id,),
        ).fetchall()
    finally:
        con.close()
    events = [dict(r) for r in rows]
    total_delta = sum(e["weight_delta"] for e in events)
    return {
        "entry_id":     entry_id,
        "weight":       1.0 + total_delta,
        "default":      1.0,
        "total_delta":  total_delta,
        "event_count":  len(events),
        "events":       events,
    }
