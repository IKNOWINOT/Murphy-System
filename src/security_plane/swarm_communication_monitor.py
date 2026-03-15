"""Communication loop detection for inter-bot messaging in swarms."""
# Copyright © 2020 Inoni Limited Liability Company

from __future__ import annotations

import logging
import threading
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class CommunicationAlert(str, Enum):
    """Types of communication anomalies detected in swarm messaging."""

    LOOP_DETECTED = "loop_detected"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    UNUSUAL_PATTERN = "unusual_pattern"
    CHANNEL_THROTTLED = "channel_throttled"


@dataclass
class SwarmMessage:
    """A single inter-bot message within a swarm session."""

    message_id: str
    swarm_id: str
    from_bot: str
    to_bot: str
    timestamp: datetime
    content_hash: str  # SHA-256 of content, not content itself


@dataclass
class CommunicationIncident:
    """A detected communication anomaly."""

    incident_id: str
    swarm_id: str
    alert_type: CommunicationAlert
    involved_bots: List[str]
    cycle_path: Optional[List[str]]
    message_count: int
    timestamp: datetime
    auto_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "swarm_id": self.swarm_id,
            "alert_type": self.alert_type.value,
            "involved_bots": self.involved_bots,
            "cycle_path": self.cycle_path,
            "message_count": self.message_count,
            "timestamp": self.timestamp.isoformat(),
            "auto_action": self.auto_action,
        }


class SwarmCommunicationMonitor:
    """Monitors inter-bot communication for loops and anomalies."""

    def __init__(
        self,
        max_messages_per_minute: int = 60,
        max_messages_per_channel: int = 30,
        loop_detection_window: int = 100,
        max_incidents: int = 5000,
    ) -> None:
        self._max_messages_per_minute = max_messages_per_minute
        self._max_messages_per_channel = max_messages_per_channel
        self._loop_detection_window = loop_detection_window
        self._max_incidents = max_incidents

        self._lock = threading.Lock()

        # swarm_id -> directed adjacency list (from_bot -> [to_bot, ...])
        self._graphs: Dict[str, Dict[str, Set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )
        # swarm_id -> recent messages (bounded deque)
        self._messages: Dict[str, deque[SwarmMessage]] = {}
        # (swarm_id, bot_id) -> list of timestamps for rate limiting
        self._bot_timestamps: Dict[Tuple[str, str], deque[datetime]] = defaultdict(
            lambda: deque(maxlen=200)
        )
        # (swarm_id, from_bot, to_bot) -> list of timestamps for channel rate
        self._channel_timestamps: Dict[
            Tuple[str, str, str], deque[datetime]
        ] = defaultdict(lambda: deque(maxlen=200))

        self._incidents: deque[CommunicationIncident] = deque(
            maxlen=self._max_incidents
        )
        self._total_messages = 0

        logger.info(
            "SwarmCommunicationMonitor initialised: bot_rate=%d/min, "
            "channel_rate=%d/min, window=%d",
            max_messages_per_minute,
            max_messages_per_channel,
            loop_detection_window,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_message(
        self, message: SwarmMessage
    ) -> Optional[CommunicationIncident]:
        """Record a message and check for anomalies. Returns incident if detected."""
        with self._lock:
            self._total_messages += 1
            sid = message.swarm_id

            # Store message in per-swarm window
            if sid not in self._messages:
                self._messages[sid] = deque(
                    maxlen=self._loop_detection_window
                )
            self._messages[sid].append(message)

            # Update directed graph
            self._graphs[sid][message.from_bot].add(message.to_bot)

            # Track timestamps
            now = message.timestamp
            self._bot_timestamps[(sid, message.from_bot)].append(now)
            self._channel_timestamps[
                (sid, message.from_bot, message.to_bot)
            ].append(now)

            # Run checks in priority order; return first incident found
            incident = self._check_rate_limit(message.from_bot, sid)
            if incident:
                return self._record_incident(incident)

            incident = self._check_channel_rate(
                message.from_bot, message.to_bot, sid
            )
            if incident:
                return self._record_incident(incident)

            incident = self._detect_cycles(sid)
            if incident:
                return self._record_incident(incident)

            incident = self._detect_unusual_patterns(sid)
            if incident:
                return self._record_incident(incident)

            return None

    def get_incidents(
        self,
        swarm_id: Optional[str] = None,
        alert_type: Optional[CommunicationAlert] = None,
        limit: int = 100,
    ) -> List[CommunicationIncident]:
        """Retrieve recorded incidents, optionally filtered."""
        with self._lock:
            results: List[CommunicationIncident] = []
            for inc in reversed(self._incidents):
                if swarm_id and inc.swarm_id != swarm_id:
                    continue
                if alert_type and inc.alert_type != alert_type:
                    continue
                results.append(inc)
                if len(results) >= limit:
                    break
            return results

    def get_message_graph(self, swarm_id: str) -> Dict[str, List[str]]:
        """Get the communication graph for a swarm."""
        with self._lock:
            graph = self._graphs.get(swarm_id, {})
            return {src: sorted(dsts) for src, dsts in graph.items()}

    def clear_swarm(self, swarm_id: str) -> None:
        """Clear all tracking data for a swarm."""
        with self._lock:
            self._graphs.pop(swarm_id, None)
            self._messages.pop(swarm_id, None)
            # Remove bot/channel timestamps for this swarm
            bot_keys = [
                k for k in self._bot_timestamps if k[0] == swarm_id
            ]
            for k in bot_keys:
                del self._bot_timestamps[k]
            chan_keys = [
                k for k in self._channel_timestamps if k[0] == swarm_id
            ]
            for k in chan_keys:
                del self._channel_timestamps[k]
            logger.info("Cleared tracking data for swarm %s", swarm_id)

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregate monitoring statistics."""
        with self._lock:
            return {
                "total_messages_recorded": self._total_messages,
                "active_swarms": len(self._messages),
                "total_incidents": len(self._incidents),
                "incidents_by_type": self._count_incidents_by_type(),
                "config": {
                    "max_messages_per_minute": self._max_messages_per_minute,
                    "max_messages_per_channel": self._max_messages_per_channel,
                    "loop_detection_window": self._loop_detection_window,
                    "max_incidents": self._max_incidents,
                },
            }

    # ------------------------------------------------------------------
    # Internal helpers (caller must hold self._lock)
    # ------------------------------------------------------------------

    def _record_incident(
        self, incident: CommunicationIncident
    ) -> CommunicationIncident:
        capped_append(self._incidents, incident)
        logger.warning(
            "Communication incident %s in swarm %s: %s — action=%s",
            incident.incident_id,
            incident.swarm_id,
            incident.alert_type.value,
            incident.auto_action,
        )
        return incident

    def _check_rate_limit(
        self, bot_id: str, swarm_id: str
    ) -> Optional[CommunicationIncident]:
        """Check if a bot exceeds its message rate limit."""
        timestamps = self._bot_timestamps.get((swarm_id, bot_id))
        if not timestamps:
            return None
        now = timestamps[-1]
        cutoff = now.timestamp() - 60
        recent = [t for t in timestamps if t.timestamp() > cutoff]
        if len(recent) > self._max_messages_per_minute:
            return CommunicationIncident(
                incident_id=uuid.uuid4().hex,
                swarm_id=swarm_id,
                alert_type=CommunicationAlert.RATE_LIMIT_EXCEEDED,
                involved_bots=[bot_id],
                cycle_path=None,
                message_count=len(recent),
                timestamp=now,
                auto_action="throttled",
            )
        return None

    def _check_channel_rate(
        self, from_bot: str, to_bot: str, swarm_id: str
    ) -> Optional[CommunicationIncident]:
        """Check if a channel exceeds its rate limit."""
        timestamps = self._channel_timestamps.get(
            (swarm_id, from_bot, to_bot)
        )
        if not timestamps:
            return None
        now = timestamps[-1]
        cutoff = now.timestamp() - 60
        recent = [t for t in timestamps if t.timestamp() > cutoff]
        if len(recent) > self._max_messages_per_channel:
            return CommunicationIncident(
                incident_id=uuid.uuid4().hex,
                swarm_id=swarm_id,
                alert_type=CommunicationAlert.CHANNEL_THROTTLED,
                involved_bots=sorted({from_bot, to_bot}),
                cycle_path=None,
                message_count=len(recent),
                timestamp=now,
                auto_action="throttled",
            )
        return None

    def _detect_cycles(
        self, swarm_id: str
    ) -> Optional[CommunicationIncident]:
        """Detect circular communication patterns using DFS on directed graph."""
        graph = self._graphs.get(swarm_id)
        if not graph:
            return None

        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = defaultdict(int)
        parent: Dict[str, Optional[str]] = {}

        def _dfs(node: str) -> Optional[List[str]]:
            color[node] = GRAY
            for neighbour in graph.get(node, set()):
                if color[neighbour] == GRAY:
                    # Back edge found — reconstruct cycle via parent chain
                    cycle = [neighbour, node]
                    cur: Optional[str] = node
                    max_steps = len(color)
                    steps = 0
                    while cur is not None and cur != neighbour and steps < max_steps:
                        cur = parent.get(cur)
                        if cur is None or cur == neighbour:
                            break
                        cycle.append(cur)
                        steps += 1
                    cycle.reverse()
                    return cycle
                if color[neighbour] == WHITE:
                    parent[neighbour] = node
                    result = _dfs(neighbour)
                    if result is not None:
                        return result
            color[node] = BLACK
            return None

        all_nodes = set(graph.keys())
        for targets in graph.values():
            all_nodes.update(targets)

        for node in sorted(all_nodes):
            if color[node] == WHITE:
                parent[node] = None
                cycle = _dfs(node)
                if cycle is not None:
                    msgs = self._messages.get(swarm_id)
                    msg_count = len(msgs) if msgs else 0
                    return CommunicationIncident(
                        incident_id=uuid.uuid4().hex,
                        swarm_id=swarm_id,
                        alert_type=CommunicationAlert.LOOP_DETECTED,
                        involved_bots=sorted(set(cycle)),
                        cycle_path=cycle,
                        message_count=msg_count,
                        timestamp=datetime.now(timezone.utc),
                        auto_action="terminated",
                    )
        return None

    def _detect_unusual_patterns(
        self, swarm_id: str
    ) -> Optional[CommunicationIncident]:
        """Detect unusual communication patterns such as abnormally high
        frequency between two bots relative to the swarm average."""
        msgs = self._messages.get(swarm_id)
        if not msgs or len(msgs) < 10:
            return None

        channel_counts: Dict[Tuple[str, str], int] = defaultdict(int)
        for msg in msgs:
            channel_counts[(msg.from_bot, msg.to_bot)] += 1

        if not channel_counts:
            return None

        total = sum(channel_counts.values())
        avg = total / len(channel_counts)
        threshold = max(avg * 3, 10)

        for (src, dst), count in channel_counts.items():
            if count > threshold:
                return CommunicationIncident(
                    incident_id=uuid.uuid4().hex,
                    swarm_id=swarm_id,
                    alert_type=CommunicationAlert.UNUSUAL_PATTERN,
                    involved_bots=sorted({src, dst}),
                    cycle_path=None,
                    message_count=count,
                    timestamp=datetime.now(timezone.utc),
                    auto_action="warned",
                )
        return None

    def _count_incidents_by_type(self) -> Dict[str, int]:
        counts: Dict[str, int] = defaultdict(int)
        for inc in self._incidents:
            counts[inc.alert_type.value] += 1
        return dict(counts)
