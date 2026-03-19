"""
Ambient Context Store — Server-side persistence for ambient intelligence signals.
Stores context signals, synthesized insights, and delivery records to the
Murphy persistence directory (JSON files, same pattern as other persistence).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import json
import os
import time
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class AmbientContextStore:
    """Persists ambient context signals and insights to disk."""

    def __init__(self, persistence_dir: str = None):
        self.persistence_dir = persistence_dir or os.environ.get(
            "MURPHY_PERSISTENCE_DIR", ".murphy_persistence"
        )
        self.ambient_dir = os.path.join(self.persistence_dir, "ambient")
        os.makedirs(self.ambient_dir, exist_ok=True)
        self._signals_file = os.path.join(self.ambient_dir, "context_signals.json")
        self._insights_file = os.path.join(self.ambient_dir, "insights.json")
        self._deliveries_file = os.path.join(self.ambient_dir, "deliveries.json")
        self._settings_file = os.path.join(self.ambient_dir, "settings.json")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_json(self, path: str, default):
        """Read a JSON file, returning *default* on any error."""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return default

    def _write_json(self, path: str, data) -> None:
        """Atomically write *data* as JSON to *path*."""
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, default=str)
            os.replace(tmp, path)
        except OSError as exc:
            logger.warning("AmbientContextStore: could not write %s: %s", path, exc)

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def store_signals(self, signals: List[Dict]) -> int:
        """Append context signals. Returns total count after appending."""
        if not signals:
            return len(self._read_json(self._signals_file, []))
        ts = time.time()
        for sig in signals:
            sig.setdefault("stored_ts", ts)
        existing: List[Dict] = self._read_json(self._signals_file, [])
        existing.extend(signals)
        # Keep last 2000 signals to bound file size
        existing = existing[-2000:]
        self._write_json(self._signals_file, existing)
        logger.debug("AmbientContextStore: stored %d signals, total=%d", len(signals), len(existing))
        return len(existing)

    def get_recent_signals(self, limit: int = 100, since_ts: float = None) -> List[Dict]:
        """Get recent signals, optionally filtered by timestamp."""
        signals: List[Dict] = self._read_json(self._signals_file, [])
        if since_ts is not None:
            signals = [s for s in signals if s.get("stored_ts", 0) >= since_ts]
        return signals[-limit:]

    # ------------------------------------------------------------------
    # Insights
    # ------------------------------------------------------------------

    def store_insight(self, insight: Dict) -> None:
        """Store a synthesized insight."""
        insight.setdefault("stored_ts", time.time())
        existing: List[Dict] = self._read_json(self._insights_file, [])
        existing.append(insight)
        existing = existing[-500:]
        self._write_json(self._insights_file, existing)

    def get_insights(self, limit: int = 50) -> List[Dict]:
        """Get recent insights."""
        insights: List[Dict] = self._read_json(self._insights_file, [])
        return insights[-limit:]

    # ------------------------------------------------------------------
    # Deliveries
    # ------------------------------------------------------------------

    def store_delivery(self, delivery: Dict) -> None:
        """Record a delivery event."""
        delivery.setdefault("stored_ts", time.time())
        existing: List[Dict] = self._read_json(self._deliveries_file, [])
        existing.append(delivery)
        existing = existing[-500:]
        self._write_json(self._deliveries_file, existing)

    def get_deliveries(self, limit: int = 50) -> List[Dict]:
        """Get recent deliveries."""
        deliveries: List[Dict] = self._read_json(self._deliveries_file, [])
        return deliveries[-limit:]

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def get_settings(self) -> Dict:
        """Get ambient engine settings."""
        defaults: Dict = {
            "contextEnabled": True,
            "emailEnabled": True,
            "meetingLink": True,
            "frequency": "daily",
            "confidenceMin": 65,
            "shadowMode": False,
        }
        stored = self._read_json(self._settings_file, {})
        defaults.update(stored)
        return defaults

    def save_settings(self, settings: Dict) -> None:
        """Save ambient engine settings."""
        self._write_json(self._settings_file, settings)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict:
        """Return aggregate stats for the ambient engine.

        Returns a dict with:
          - signals_count
          - insights_count
          - deliveries_count
          - avg_confidence
          - last_activity_ts
        """
        signals: List[Dict] = self._read_json(self._signals_file, [])
        insights: List[Dict] = self._read_json(self._insights_file, [])
        deliveries: List[Dict] = self._read_json(self._deliveries_file, [])

        confidences = [s.get("confidence", 0) for s in signals if "confidence" in s]
        avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else 0.0

        all_ts = (
            [s.get("stored_ts", 0) for s in signals]
            + [i.get("stored_ts", 0) for i in insights]
            + [d.get("stored_ts", 0) for d in deliveries]
        )
        last_activity_ts = max(all_ts) if all_ts else None

        return {
            "signals_count": len(signals),
            "insights_count": len(insights),
            "deliveries_count": len(deliveries),
            "avg_confidence": avg_confidence,
            "last_activity_ts": last_activity_ts,
        }
import time
import threading
from collections import deque
from typing import Dict, List, Optional


class AmbientContextStore:
    def __init__(self, max_signals: int = 1000, ttl_seconds: int = 3600):
        self._signals = deque(maxlen=max_signals)
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def push(self, signals: List[Dict]) -> int:
        """Store signals, return count stored."""
        now = time.time()
        with self._lock:
            for sig in signals:
                sig['_stored_at'] = now
                self._signals.append(sig)
            self._evict()
        return len(signals)

    def get_recent(self, limit: int = 50, source: Optional[str] = None) -> List[Dict]:
        """Get most recent signals, optionally filtered by source."""
        with self._lock:
            self._evict()
            result = list(self._signals)
        if source:
            result = [s for s in result if s.get('source') == source]
        return result[-limit:]

    def get_stats(self) -> Dict:
        """Return store statistics."""
        with self._lock:
            oldest_age = 0
            if self._signals:
                stored_at = self._signals[0].get('_stored_at')
                if stored_at is not None:
                    oldest_age = time.time() - stored_at
            return {
                'total_signals': len(self._signals),
                'sources': list(set(s.get('source', 'unknown') for s in self._signals)),
                'oldest_signal_age_seconds': oldest_age,
            }

    def _evict(self):
        now = time.time()
        while self._signals and (now - self._signals[0].get('_stored_at', 0)) > self._ttl:
            self._signals.popleft()
