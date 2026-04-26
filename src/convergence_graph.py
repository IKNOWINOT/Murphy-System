"""
PATCH-096b — Convergence Graph
src/convergence_graph.py

MSS Resolution Level: RM4 (Architecture Design)

Naming Assumptions (MSS-resolved, not assumed):
  ConvergenceEvent  — one content item processed by the RCE at a point in time.
                      This is a graph node. It has a state vector.
  StateVector       — the 8-dimensional representation of a node:
                      [flourishing, contraction, closure, coherence_delta,
                       p_physical, p_psychological, p_financial, p_autonomy]
  TrajectorySegment — the directed edge between two consecutive nodes
                      in the same session. Carries the velocity vector.
  VelocityVector    — delta between two state vectors. Positive in a
                      dimension = moving toward optimal. Negative = drifting.
  OptimalZone       — the named region where flourishing > 0.6, closure < 0.3,
                      harm_aggregate < 0.2. Entering this zone triggers Sustain Mode.
  SustainMode       — active when session is in OptimalZone. Steering magnitude
                      drops to SUSTAIN_MAGNITUDE (0.05). Exits if trajectory drifts out.
  ContractManifold  — the named complement: the shape of the bad space.
                      Defined by the same bounds, inverted. Used to define
                      optimal calculus trajectory by knowing what to avoid.
  TrajectoryCalc    — the computation that determines: given current position
                      and velocity, what is the steering force needed to
                      enter (or stay in) the optimal zone?

Storage:
  SQLite at /opt/Murphy-System/data/convergence_graph.db
  Tables: convergence_events, convergence_edges, session_trajectories

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MSS-NAMED CONSTANTS — not magic numbers, named boundaries
# ---------------------------------------------------------------------------

# OptimalZone bounds (MSS RM4)
OPTIMAL_FLOURISHING_MIN   = 0.60   # flourishing_score must exceed this
OPTIMAL_CLOSURE_MAX       = 0.30   # closure_score must be below this
OPTIMAL_HARM_MAX          = 0.20   # harm_aggregate must be below this
OPTIMAL_COHERENCE_MIN     = 0.0    # coherence_delta must be non-negative

# SustainMode steering magnitude — minimal nudge to reinforce, not push
SUSTAIN_MAGNITUDE         = 0.05

# ContractManifold — the bad region (inverse of OptimalZone)
CONTRACT_CLOSURE_MIN      = 0.60   # closure this high = contraction manifold
CONTRACT_FLOURISHING_MAX  = 0.30   # flourishing this low = contraction manifold
CONTRACT_HARM_MIN         = 0.50   # harm this high = contraction manifold

# Trajectory velocity thresholds
VELOCITY_APPROACHING      = 0.10   # per-dimension delta indicating movement toward optimal
VELOCITY_DRIFTING         = -0.10  # per-dimension delta indicating movement away

# DB path
_DB_PATH = os.environ.get(
    "CONVERGENCE_GRAPH_DB",
    "/opt/Murphy-System/data/convergence_graph.db"
)

# ---------------------------------------------------------------------------
# STATE VECTOR — 8-dimensional
# ---------------------------------------------------------------------------

@dataclass
class StateVector:
    """
    8-dimensional state representation of a convergence event.
    MSS RM4 — fully named, no unnamed dimensions.

    Dimensions:
      D1: flourishing_score   — how much flourishing signal is present (0–1)
      D2: contraction_score   — how much contraction signal is present (0–1)
      D3: closure_score       — how closed the tribal loop is (0–1)
      D4: coherence_delta     — flourishing minus contraction (-1 to 1)
      D5: p_harm_physical     — probability of physical harm (0–1)
      D6: p_harm_psychological — probability of psychological harm (0–1)
      D7: p_harm_financial    — probability of financial harm (0–1)
      D8: p_harm_autonomy     — probability of autonomy harm (0–1)
    """
    d1_flourishing:       float
    d2_contraction:       float
    d3_closure:           float
    d4_coherence_delta:   float
    d5_p_harm_physical:   float
    d6_p_harm_psychological: float
    d7_p_harm_financial:  float
    d8_p_harm_autonomy:   float

    def as_list(self) -> List[float]:
        return [
            self.d1_flourishing, self.d2_contraction, self.d3_closure,
            self.d4_coherence_delta, self.d5_p_harm_physical,
            self.d6_p_harm_psychological, self.d7_p_harm_financial,
            self.d8_p_harm_autonomy,
        ]

    def in_optimal_zone(self) -> bool:
        """True when this state is inside the named OptimalZone."""
        return (
            self.d1_flourishing   >= OPTIMAL_FLOURISHING_MIN and
            self.d3_closure       <= OPTIMAL_CLOSURE_MAX and
            self.d4_coherence_delta >= OPTIMAL_COHERENCE_MIN and
            self._harm_aggregate() <= OPTIMAL_HARM_MAX
        )

    def in_contraction_manifold(self) -> bool:
        """True when this state is inside the ContractManifold — the bad space."""
        return (
            self.d3_closure       >= CONTRACT_CLOSURE_MIN or
            self.d1_flourishing   <= CONTRACT_FLOURISHING_MAX or
            self._harm_aggregate() >= CONTRACT_HARM_MIN
        )

    def _harm_aggregate(self) -> float:
        return (
            self.d5_p_harm_physical + self.d6_p_harm_psychological +
            self.d7_p_harm_financial + self.d8_p_harm_autonomy
        ) / 4.0

    def distance_to_optimal(self) -> float:
        """
        Euclidean distance from this state to the nearest OptimalZone boundary.
        Zero if already inside the OptimalZone.
        MSS name: OptimalZoneDistance.
        """
        if self.in_optimal_zone():
            return 0.0
        # Target: center of OptimalZone
        target = [
            OPTIMAL_FLOURISHING_MIN + 0.2,   # D1: aim for 0.8
            0.1,                              # D2: low contraction
            OPTIMAL_CLOSURE_MAX / 2,          # D3: low closure
            0.4,                              # D4: positive coherence
            0.05, 0.05, 0.05, 0.05,          # D5-D8: near-zero harm
        ]
        current = self.as_list()
        return round(math.sqrt(sum((c - t) ** 2 for c, t in zip(current, target))), 4)


# ---------------------------------------------------------------------------
# VELOCITY VECTOR — delta between two StateVectors
# ---------------------------------------------------------------------------

@dataclass
class VelocityVector:
    """
    Per-dimension delta between two consecutive state vectors.
    Positive = moving toward optimal on that dimension.
    Negative = drifting away.
    MSS RM4.
    """
    deltas: List[float]   # length 8, one per StateVector dimension
    magnitude: float      # Euclidean magnitude of the velocity
    approaching: bool     # net movement toward optimal zone
    dominant_dimension: int  # which dimension has the largest delta

    @classmethod
    def compute(cls, prev: StateVector, curr: StateVector) -> "VelocityVector":
        p, c = prev.as_list(), curr.as_list()
        # For D1 and D4, positive delta = good. For D2, D3, D5-D8, negative delta = good.
        beneficial_direction = [1, -1, -1, 1, -1, -1, -1, -1]
        deltas = [round(c[i] - p[i], 4) for i in range(8)]
        aligned = [deltas[i] * beneficial_direction[i] for i in range(8)]
        net = sum(aligned)
        magnitude = round(math.sqrt(sum(d ** 2 for d in deltas)), 4)
        dominant = max(range(8), key=lambda i: abs(deltas[i]))
        return cls(
            deltas=deltas,
            magnitude=magnitude,
            approaching=net > 0,
            dominant_dimension=dominant,
        )


# ---------------------------------------------------------------------------
# CONVERGENCE EVENT — a graph node
# ---------------------------------------------------------------------------

@dataclass
class ConvergenceEvent:
    """
    One content item processed by the RCE. This is a graph node.
    MSS RM4.

    Naming:
      event_id      — UUID for this specific content evaluation
      session_id    — groups events into a trajectory
      domain        — content domain (media, political, personal, etc.)
      tribal_pattern — which tribal pattern was detected
      state         — 8-dimensional StateVector at this moment
      action_type   — what the steerer did (none / surface / question / inject)
      shift_magnitude — how large the steering action was
      in_optimal_zone — was this node inside the OptimalZone?
      in_sustain_mode — was SustainMode active?
      timestamp     — UTC ISO8601
    """
    event_id:        str
    session_id:      str
    domain:          str
    tribal_pattern:  str
    state:           StateVector
    action_type:     str
    shift_magnitude: float
    in_optimal_zone: bool
    in_sustain_mode: bool
    timestamp:       str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    content_hash:    str = ""
    steer_reason:    str = ""


# ---------------------------------------------------------------------------
# TRAJECTORY SEGMENT — a graph edge
# ---------------------------------------------------------------------------

@dataclass
class TrajectorySegment:
    """
    Directed edge between two consecutive ConvergenceEvents in a session.
    Carries the VelocityVector.
    MSS RM4.
    """
    from_event_id: str
    to_event_id:   str
    session_id:    str
    velocity:      VelocityVector
    crossed_into_optimal: bool  # True if this edge crossed the OptimalZone boundary
    crossed_out_optimal:  bool  # True if this edge crossed out of OptimalZone


# ---------------------------------------------------------------------------
# TRAJECTORY CALCULATOR — the calculus
# ---------------------------------------------------------------------------

class TrajectoryCalculator:
    """
    Computes the steering force needed to move the current state toward
    the OptimalZone, taking velocity into account.

    MSS RM5 (Implementation).

    TrajectoryCalc:
      Given current StateVector S and VelocityVector V:
      1. If S is in OptimalZone → SustainMode, return SUSTAIN_MAGNITUDE.
      2. If S is in ContractManifold → high steering force.
      3. Otherwise → steering force = OptimalZoneDistance * (1 - approach_bonus).
         approach_bonus: if already approaching, reduce force (don't overcorrect).

    This is the calculus: the optimal trajectory is not maximum force toward
    the goal. It is the minimum force that sustains the approach without
    overshooting into a new contraction manifold on the other side.
    """

    def compute_steering_force(
        self,
        state: StateVector,
        velocity: Optional[VelocityVector] = None,
    ) -> Tuple[float, bool]:
        """
        Returns (steering_magnitude, sustain_mode).

        steering_magnitude: 0.0–1.0 how strongly to steer.
        sustain_mode: True when already in OptimalZone.
        """
        if state.in_optimal_zone():
            return SUSTAIN_MAGNITUDE, True

        distance = state.distance_to_optimal()

        # In ContractManifold — maximum meaningful steering
        if state.in_contraction_manifold():
            force = min(0.75, distance * 0.8)
            if velocity and velocity.approaching:
                # Already moving toward optimal — reduce force slightly
                force = max(SUSTAIN_MAGNITUDE, force * 0.7)
            return round(force, 3), False

        # In the middle space — proportional steering
        force = min(0.6, distance * 0.5)
        if velocity:
            if velocity.approaching:
                # Good trajectory — light touch
                force = max(SUSTAIN_MAGNITUDE, force * 0.6)
            else:
                # Drifting — increase force
                force = min(0.7, force * 1.3)

        return round(force, 3), False


# ---------------------------------------------------------------------------
# CONVERGENCE GRAPH — persistent storage + retrieval
# ---------------------------------------------------------------------------

class ConvergenceGraph:
    """
    Persistent directed graph of ConvergenceEvents.

    MSS RM4 — Architecture Design.

    Tables:
      convergence_events  — one row per ConvergenceEvent (graph node)
      convergence_edges   — one row per TrajectorySegment (graph edge)
      session_summaries   — one row per session: entry/exit optimal zone, sustain time

    Thread-safe. Append-only for events and edges.

    fn: convergence_graph.ConvergenceGraph.save_event()
    fn: convergence_graph.ConvergenceGraph.get_session_trajectory()
    fn: convergence_graph.ConvergenceGraph.get_session_state()
    """

    def __init__(self, db_path: str = _DB_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._calc = TrajectoryCalculator()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS convergence_events (
                    event_id        TEXT PRIMARY KEY,
                    session_id      TEXT NOT NULL,
                    domain          TEXT NOT NULL,
                    tribal_pattern  TEXT NOT NULL,
                    d1_flourishing  REAL NOT NULL,
                    d2_contraction  REAL NOT NULL,
                    d3_closure      REAL NOT NULL,
                    d4_coherence    REAL NOT NULL,
                    d5_p_physical   REAL NOT NULL,
                    d6_p_psycho     REAL NOT NULL,
                    d7_p_financial  REAL NOT NULL,
                    d8_p_autonomy   REAL NOT NULL,
                    action_type     TEXT NOT NULL,
                    shift_magnitude REAL NOT NULL,
                    in_optimal_zone INTEGER NOT NULL,
                    in_sustain_mode INTEGER NOT NULL,
                    content_hash    TEXT,
                    steer_reason    TEXT,
                    timestamp       TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_session
                    ON convergence_events(session_id, timestamp);

                CREATE TABLE IF NOT EXISTS convergence_edges (
                    edge_id              TEXT PRIMARY KEY,
                    from_event_id        TEXT NOT NULL,
                    to_event_id          TEXT NOT NULL,
                    session_id           TEXT NOT NULL,
                    velocity_magnitude   REAL NOT NULL,
                    approaching          INTEGER NOT NULL,
                    dominant_dimension   INTEGER NOT NULL,
                    crossed_into_optimal INTEGER NOT NULL,
                    crossed_out_optimal  INTEGER NOT NULL,
                    timestamp            TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS session_summaries (
                    session_id        TEXT PRIMARY KEY,
                    domain            TEXT NOT NULL,
                    event_count       INTEGER NOT NULL DEFAULT 0,
                    in_sustain_mode   INTEGER NOT NULL DEFAULT 0,
                    sustain_entry_ts  TEXT,
                    optimal_entries   INTEGER NOT NULL DEFAULT 0,
                    optimal_exits     INTEGER NOT NULL DEFAULT 0,
                    last_event_id     TEXT,
                    last_updated      TEXT NOT NULL
                );
            """)
        logger.info("ConvergenceGraph schema initialised at %s", self._db_path)

    def save_event(self, event: ConvergenceEvent) -> Optional[TrajectorySegment]:
        """
        Persist a ConvergenceEvent node.
        If a prior event exists in the same session, compute and save the
        TrajectorySegment edge between them.
        Returns the segment if one was created.

        fn: convergence_graph.ConvergenceGraph.save_event()
        """
        with self._lock:
            try:
                conn = self._conn()
                # Insert event node
                conn.execute("""
                    INSERT OR IGNORE INTO convergence_events VALUES (
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                """, (
                    event.event_id, event.session_id, event.domain,
                    event.tribal_pattern,
                    event.state.d1_flourishing, event.state.d2_contraction,
                    event.state.d3_closure, event.state.d4_coherence_delta,
                    event.state.d5_p_harm_physical, event.state.d6_p_harm_psychological,
                    event.state.d7_p_harm_financial, event.state.d8_p_harm_autonomy,
                    event.action_type, event.shift_magnitude,
                    int(event.in_optimal_zone), int(event.in_sustain_mode),
                    event.content_hash, event.steer_reason,
                    event.timestamp,
                ))

                # Get previous event in session
                prev_row = conn.execute("""
                    SELECT * FROM convergence_events
                    WHERE session_id = ? AND event_id != ?
                    ORDER BY timestamp DESC LIMIT 1
                """, (event.session_id, event.event_id)).fetchone()

                segment: Optional[TrajectorySegment] = None

                if prev_row:
                    prev_state = StateVector(
                        d1_flourishing=prev_row["d1_flourishing"],
                        d2_contraction=prev_row["d2_contraction"],
                        d3_closure=prev_row["d3_closure"],
                        d4_coherence_delta=prev_row["d4_coherence"],
                        d5_p_harm_physical=prev_row["d5_p_physical"],
                        d6_p_harm_psychological=prev_row["d6_p_psycho"],
                        d7_p_harm_financial=prev_row["d7_p_financial"],
                        d8_p_harm_autonomy=prev_row["d8_p_autonomy"],
                    )
                    velocity = VelocityVector.compute(prev_state, event.state)
                    prev_in_optimal = bool(prev_row["in_optimal_zone"])
                    curr_in_optimal = event.in_optimal_zone

                    segment = TrajectorySegment(
                        from_event_id=prev_row["event_id"],
                        to_event_id=event.event_id,
                        session_id=event.session_id,
                        velocity=velocity,
                        crossed_into_optimal=(not prev_in_optimal and curr_in_optimal),
                        crossed_out_optimal=(prev_in_optimal and not curr_in_optimal),
                    )

                    conn.execute("""
                        INSERT OR IGNORE INTO convergence_edges VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (
                        f"edge-{uuid.uuid4().hex[:8]}",
                        segment.from_event_id, segment.to_event_id,
                        segment.session_id,
                        velocity.magnitude, int(velocity.approaching),
                        velocity.dominant_dimension,
                        int(segment.crossed_into_optimal),
                        int(segment.crossed_out_optimal),
                        datetime.now(timezone.utc).isoformat(),
                    ))

                # Upsert session summary
                conn.execute("""
                    INSERT INTO session_summaries
                        (session_id, domain, event_count, in_sustain_mode,
                         sustain_entry_ts, optimal_entries, optimal_exits,
                         last_event_id, last_updated)
                    VALUES (?,?,1,?,?,?,?,?,?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        event_count = event_count + 1,
                        in_sustain_mode = excluded.in_sustain_mode,
                        sustain_entry_ts = CASE
                            WHEN excluded.in_sustain_mode=1 AND in_sustain_mode=0
                            THEN excluded.sustain_entry_ts ELSE sustain_entry_ts END,
                        optimal_entries = optimal_entries + excluded.optimal_entries,
                        optimal_exits   = optimal_exits + excluded.optimal_exits,
                        last_event_id   = excluded.last_event_id,
                        last_updated    = excluded.last_updated
                """, (
                    event.session_id, event.domain,
                    int(event.in_sustain_mode),
                    event.timestamp if event.in_sustain_mode else None,
                    1 if (segment and segment.crossed_into_optimal) else 0,
                    1 if (segment and segment.crossed_out_optimal) else 0,
                    event.event_id,
                    datetime.now(timezone.utc).isoformat(),
                ))
                conn.commit()
                conn.close()

                logger.debug(
                    "ConvergenceGraph: saved event %s session=%s optimal=%s sustain=%s",
                    event.event_id, event.session_id, event.in_optimal_zone, event.in_sustain_mode,
                )
                return segment

            except Exception as exc:
                logger.error("ConvergenceGraph.save_event failed: %s", exc)
                return None

    def get_session_trajectory(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Return ordered list of events for a session (the trajectory).
        fn: convergence_graph.ConvergenceGraph.get_session_trajectory()
        """
        with self._lock:
            try:
                conn = self._conn()
                rows = conn.execute("""
                    SELECT * FROM convergence_events
                    WHERE session_id = ?
                    ORDER BY timestamp ASC
                """, (session_id,)).fetchall()
                conn.close()
                return [dict(r) for r in rows]
            except Exception as exc:
                logger.error("get_session_trajectory failed: %s", exc)
                return []

    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Return the current session summary + last state vector.
        fn: convergence_graph.ConvergenceGraph.get_session_state()
        """
        with self._lock:
            try:
                conn = self._conn()
                summary = conn.execute(
                    "SELECT * FROM session_summaries WHERE session_id = ?",
                    (session_id,)
                ).fetchone()
                if not summary:
                    conn.close()
                    return None

                last_event = conn.execute(
                    "SELECT * FROM convergence_events WHERE event_id = ?",
                    (summary["last_event_id"],)
                ).fetchone()
                conn.close()

                result = dict(summary)
                if last_event:
                    sv = StateVector(
                        d1_flourishing=last_event["d1_flourishing"],
                        d2_contraction=last_event["d2_contraction"],
                        d3_closure=last_event["d3_closure"],
                        d4_coherence_delta=last_event["d4_coherence"],
                        d5_p_harm_physical=last_event["d5_p_physical"],
                        d6_p_harm_psychological=last_event["d6_p_psycho"],
                        d7_p_harm_financial=last_event["d7_p_financial"],
                        d8_p_harm_autonomy=last_event["d8_p_autonomy"],
                    )
                    result["current_state"] = sv.as_list()
                    result["in_optimal_zone"] = sv.in_optimal_zone()
                    result["in_contraction_manifold"] = sv.in_contraction_manifold()
                    result["distance_to_optimal"] = sv.distance_to_optimal()
                    _, sustain = self._calc.compute_steering_force(sv)
                    result["sustain_mode_active"] = sustain
                return result
            except Exception as exc:
                logger.error("get_session_state failed: %s", exc)
                return None

    def get_global_stats(self) -> Dict[str, Any]:
        """
        Global graph statistics across all sessions.
        fn: convergence_graph.ConvergenceGraph.get_global_stats()
        """
        with self._lock:
            try:
                conn = self._conn()
                total_events = conn.execute("SELECT COUNT(*) FROM convergence_events").fetchone()[0]
                total_sessions = conn.execute("SELECT COUNT(*) FROM session_summaries").fetchone()[0]
                in_optimal = conn.execute(
                    "SELECT COUNT(*) FROM convergence_events WHERE in_optimal_zone=1"
                ).fetchone()[0]
                in_sustain = conn.execute(
                    "SELECT COUNT(*) FROM session_summaries WHERE in_sustain_mode=1"
                ).fetchone()[0]
                patterns = conn.execute(
                    "SELECT tribal_pattern, COUNT(*) as cnt FROM convergence_events GROUP BY tribal_pattern ORDER BY cnt DESC"
                ).fetchall()
                conn.close()
                return {
                    "total_events":    total_events,
                    "total_sessions":  total_sessions,
                    "events_in_optimal_zone": in_optimal,
                    "sessions_in_sustain": in_sustain,
                    "optimal_zone_rate": round(in_optimal / max(total_events, 1), 3),
                    "pattern_distribution": {r["tribal_pattern"]: r["cnt"] for r in patterns},
                    "optimal_zone_bounds": {
                        "flourishing_min": OPTIMAL_FLOURISHING_MIN,
                        "closure_max":     OPTIMAL_CLOSURE_MAX,
                        "harm_max":        OPTIMAL_HARM_MAX,
                        "coherence_min":   OPTIMAL_COHERENCE_MIN,
                    },
                    "contraction_manifold_bounds": {
                        "closure_min":     CONTRACT_CLOSURE_MIN,
                        "flourishing_max": CONTRACT_FLOURISHING_MAX,
                        "harm_min":        CONTRACT_HARM_MIN,
                    },
                }
            except Exception as exc:
                logger.error("get_global_stats failed: %s", exc)
                return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

_graph: Optional[ConvergenceGraph] = None

def get_graph() -> ConvergenceGraph:
    global _graph
    if _graph is None:
        _graph = ConvergenceGraph()
    return _graph
