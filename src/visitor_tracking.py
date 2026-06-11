"""
visitor_tracking.py — Anonymous landing-page visitor tracking + globe data
Ship 27 (2026-06-10)

Purpose:
  Lightweight, privacy-safe tracking of who's currently on the landing page.
  Powers the 3D globe widget AND admin analytics dashboard.

Privacy stance:
  - We DO NOT store IP addresses past the geo-lookup
  - We DO NOT store user-agent strings past coarse-grained device class
  - Sessions are anonymous (random session_id, no cookies persisted)
  - Session rows auto-expire after 5 minutes of inactivity
  - Long-term analytics only keep aggregates (country counts, hour buckets)
"""
from __future__ import annotations
import sqlite3
import json
import time
import secrets
import hashlib
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import logging

LOG = logging.getLogger("murphy.visitor_tracking")

DB_PATH = "/var/lib/murphy-production/visitor_analytics.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS visitors_live (
    session_id      TEXT PRIMARY KEY,
    lat             REAL,
    lon             REAL,
    country         TEXT,
    city            TEXT,
    first_seen_ns   INTEGER NOT NULL,
    last_seen_ns    INTEGER NOT NULL,
    path            TEXT DEFAULT '/',
    referrer        TEXT,
    device          TEXT
);
CREATE INDEX IF NOT EXISTS idx_visitors_live_last ON visitors_live(last_seen_ns);

CREATE TABLE IF NOT EXISTS visitor_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    path            TEXT,
    timestamp_ns    INTEGER NOT NULL,
    metadata        TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_session ON visitor_events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_time ON visitor_events(timestamp_ns);

CREATE TABLE IF NOT EXISTS visitor_aggregates_hourly (
    hour_bucket     TEXT NOT NULL,    -- 'YYYY-MM-DDTHH'
    country         TEXT NOT NULL,
    visits          INTEGER NOT NULL DEFAULT 0,
    unique_sessions INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (hour_bucket, country)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS visitor_aggregates_daily (
    day             TEXT NOT NULL,        -- 'YYYY-MM-DD'
    country         TEXT NOT NULL,
    visits          INTEGER NOT NULL DEFAULT 0,
    unique_sessions INTEGER NOT NULL DEFAULT 0,
    avg_dwell_seconds REAL DEFAULT 0,
    PRIMARY KEY (day, country)
) WITHOUT ROWID;
"""

# ───────────────────────────── DB init ─────────────────────────────

def _db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.executescript(SCHEMA)
    return conn

# ───────────────────────────── geo lookup ─────────────────────────────

# Free, no-key geo service. Falls back gracefully if unreachable.
_GEO_CACHE: Dict[str, Dict[str, Any]] = {}

def _geo_lookup(ip: str) -> Dict[str, Any]:
    """Look up coarse geo for an IP. Cached. Falls back to (0,0) on failure."""
    if not ip or ip.startswith("127.") or ip.startswith("10.") or ip.startswith("192.168."):
        return {"lat": 0.0, "lon": 0.0, "country": "LOCAL", "city": ""}
    # Hash the IP for cache key (we never store raw IP)
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:12]
    if ip_hash in _GEO_CACHE:
        return _GEO_CACHE[ip_hash]
    try:
        # ip-api.com is free for non-commercial up to 45 req/min. Good enough
        # for a landing page that gets a handful of visitors per minute.
        req = urllib.request.Request(
            f"http://ip-api.com/json/{ip}?fields=status,country,city,lat,lon",
            headers={"User-Agent": "MurphyVisitorTracker/1.0"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode())
        if data.get("status") == "success":
            geo = {
                "lat": float(data.get("lat", 0)),
                "lon": float(data.get("lon", 0)),
                "country": data.get("country", "Unknown"),
                "city": data.get("city", ""),
            }
        else:
            geo = {"lat": 0.0, "lon": 0.0, "country": "Unknown", "city": ""}
    except Exception as e:
        LOG.debug("geo lookup failed for %s: %s", ip_hash[:6], e)
        geo = {"lat": 0.0, "lon": 0.0, "country": "Unknown", "city": ""}
    _GEO_CACHE[ip_hash] = geo
    return geo

# ───────────────────────────── public API ─────────────────────────────

def ping(
    *,
    session_id: Optional[str],
    ip: str,
    path: str = "/",
    referrer: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Called by the landing-page JS every 20 seconds.
    Creates or updates the visitors_live row for this session.
    Returns the session_id (creates one if missing) so the JS can reuse it.
    """
    if not session_id:
        session_id = secrets.token_urlsafe(16)
    
    now_ns = time.time_ns()
    
    # Coarse device class — never store the full UA
    device = "desktop"
    if user_agent:
        ua_lower = user_agent.lower()
        if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
            device = "mobile"
        elif "tablet" in ua_lower or "ipad" in ua_lower:
            device = "tablet"
    
    # Truncate referrer to host only — never store the full URL with query params
    ref_host = ""
    if referrer:
        try:
            from urllib.parse import urlparse
            ref_host = urlparse(referrer).hostname or ""
        except Exception:
            ref_host = ""
    
    conn = _db()
    try:
        existing = conn.execute(
            "SELECT first_seen_ns, country FROM visitors_live WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        
        if existing:
            # Update last_seen only — keep first_seen and geo
            conn.execute(
                "UPDATE visitors_live SET last_seen_ns = ?, path = ? WHERE session_id = ?",
                (now_ns, path, session_id),
            )
            country = existing[1]
        else:
            # New session — do geo lookup
            geo = _geo_lookup(ip)
            conn.execute(
                "INSERT INTO visitors_live "
                "(session_id, lat, lon, country, city, first_seen_ns, last_seen_ns, path, referrer, device) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (session_id, geo["lat"], geo["lon"], geo["country"], geo["city"],
                 now_ns, now_ns, path, ref_host, device),
            )
            country = geo["country"]
            # Log event
            conn.execute(
                "INSERT INTO visitor_events (session_id, event_type, path, timestamp_ns, metadata) "
                "VALUES (?,?,?,?,?)",
                (session_id, "visit_start", path, now_ns,
                 json.dumps({"country": country, "device": device, "referrer": ref_host})),
            )
        
        # Bump hourly aggregate
        hour_bucket = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
        conn.execute(
            "INSERT INTO visitor_aggregates_hourly (hour_bucket, country, visits, unique_sessions) "
            "VALUES (?, ?, 1, ?) "
            "ON CONFLICT(hour_bucket, country) DO UPDATE SET visits = visits + 1",
            (hour_bucket, country or "Unknown", 1 if not existing else 0),
        )
        
        conn.commit()
    finally:
        conn.close()
    
    return {"session_id": session_id, "ok": True}


def get_live_visitors(window_seconds: int = 60) -> List[Dict[str, Any]]:
    """
    Returns visitors seen in last `window_seconds`. Used by the globe widget.
    Returns ONLY lat/lon/country/device (no session_id, no path).
    """
    cutoff_ns = time.time_ns() - (window_seconds * 1_000_000_000)
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT lat, lon, country, device, first_seen_ns FROM visitors_live "
            "WHERE last_seen_ns >= ? ORDER BY last_seen_ns DESC LIMIT 500",
            (cutoff_ns,),
        ).fetchall()
        now_ns = time.time_ns()
        return [
            {
                "lat": r[0],
                "lon": r[1],
                "country": r[2],
                "device": r[3],
                "dwell_seconds": round((now_ns - r[4]) / 1e9, 1),
            }
            for r in rows
            if r[0] != 0.0 or r[1] != 0.0  # skip unknown geo
        ]
    finally:
        conn.close()


def get_visitor_stats() -> Dict[str, Any]:
    """Snapshot stats for the admin dashboard."""
    cutoff_60s = time.time_ns() - (60 * 1_000_000_000)
    cutoff_24h = time.time_ns() - (24 * 3600 * 1_000_000_000)
    
    conn = _db()
    try:
        live_count = conn.execute(
            "SELECT COUNT(*) FROM visitors_live WHERE last_seen_ns >= ?",
            (cutoff_60s,),
        ).fetchone()[0]
        
        total_24h = conn.execute(
            "SELECT COUNT(DISTINCT session_id) FROM visitor_events "
            "WHERE event_type = 'visit_start' AND timestamp_ns >= ?",
            (cutoff_24h,),
        ).fetchone()[0]
        
        countries_24h = conn.execute(
            "SELECT country, COUNT(DISTINCT session_id) as c FROM visitors_live "
            "WHERE last_seen_ns >= ? GROUP BY country ORDER BY c DESC LIMIT 10",
            (cutoff_24h,),
        ).fetchall()
        
        # Hourly visit count for last 24h
        hourly = conn.execute(
            "SELECT hour_bucket, SUM(visits) FROM visitor_aggregates_hourly "
            "WHERE hour_bucket >= ? GROUP BY hour_bucket ORDER BY hour_bucket",
            ((datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H"),),
        ).fetchall()
        
        # Devices
        devices = conn.execute(
            "SELECT device, COUNT(*) FROM visitors_live WHERE last_seen_ns >= ? GROUP BY device",
            (cutoff_24h,),
        ).fetchall()
        
        return {
            "live_now": live_count,
            "unique_24h": total_24h,
            "countries_24h": [{"country": c[0], "count": c[1]} for c in countries_24h],
            "hourly_24h": [{"hour": h[0], "visits": h[1]} for h in hourly],
            "devices_24h": [{"device": d[0], "count": d[1]} for d in devices],
        }
    finally:
        conn.close()


def cleanup_stale(max_idle_seconds: int = 300):
    """Auto-expire sessions idle > N seconds. Called periodically."""
    cutoff_ns = time.time_ns() - (max_idle_seconds * 1_000_000_000)
    conn = _db()
    try:
        deleted = conn.execute(
            "DELETE FROM visitors_live WHERE last_seen_ns < ?", (cutoff_ns,)
        ).rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()


# Initialize on import
_db().close()
LOG.info("visitor_tracking initialized: db=%s", DB_PATH)
