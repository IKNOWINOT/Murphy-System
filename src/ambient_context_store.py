"""
Ambient Context Store — Server-side signal persistence
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post | License: BSL 1.1

In-memory store for ambient context signals. Signals are evicted after TTL
or when the store exceeds max size. This is NOT a database — it's a fast
cache for the ambient engine's context pipeline.
"""
import time
import threading
from collections import deque
from typing import Dict, List, Optional


class AmbientContextStore:
    def __init__(self, max_signals: int = 1000, ttl_seconds: int = 3600):
        self._signals = deque(maxlen=max_signals)
        self._insights = deque(maxlen=500)
        self._deliveries = deque(maxlen=200)
        self._settings = {"enabled": True, "delivery_channel": "im", "min_confidence": 0.6}
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

    def store_signals(self, signals: List[Dict]) -> int:
        """Alias for push() — store signals and return count."""
        return self.push(signals)

    def store_insight(self, insight: dict) -> dict:
        """Store an insight in bounded deque."""
        now = time.time()
        insight['_stored_at'] = now
        with self._lock:
            self._insights.append(insight)
        return insight

    def store_delivery(self, delivery: dict) -> dict:
        """Store a delivery record in bounded deque."""
        with self._lock:
            self._deliveries.append(delivery)
        return delivery

    def get_settings(self) -> dict:
        """Return current ambient settings."""
        with self._lock:
            return self._settings.copy()

    def save_settings(self, settings: dict) -> dict:
        """Merge new settings into current settings."""
        with self._lock:
            self._settings.update(settings)
            return self._settings.copy()

    def get_insights(self, limit: int = 20) -> List[dict]:
        """Return last N insights."""
        with self._lock:
            result = list(self._insights)
        return result[-limit:]

    def get_deliveries(self, limit: int = 20) -> List[dict]:
        """Return last N deliveries."""
        with self._lock:
            result = list(self._deliveries)
        return result[-limit:]
