"""
Engineering Toolbox adapter (revised: direct fetch + topic map).

Approach:
  - Search engines (DDG/Google) actively block scrapers
  - engineeringtoolbox.com has predictable URL patterns
  - We maintain a curated topic_map of canonical pages
  - search() returns matches from the topic_map (fast, no network)
  - fetch() pulls full content with 30-day cache
  - Map grows as Murphy encounters new questions (write-back)

Policy:
  - Browser-like UA (their site needs it; no robots.txt published)
  - 30-day cache for full content
  - Every use produces a citation string
  - Snippet-only in replies; we link the full page for verification
"""
from __future__ import annotations
import hashlib
import re
import sqlite3
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

CACHE_DB = "/var/lib/murphy-production/engineering_toolbox_cache.db"
TTL_SECONDS = 30 * 24 * 3600
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; Murphy-Reference/1.0; "
    "+https://murphy.systems)"
)

# Curated map of high-signal engineering topics → canonical URLs.
# Each entry is keywords list → URL + short description.
# Grows over time as Murphy sees new questions.
TOPIC_MAP: List[Dict] = [
    {"keywords": ["darcy", "weisbach", "pressure drop", "pressure loss",
                  "head loss", "friction"],
     "url": "https://www.engineeringtoolbox.com/darcy-weisbach-equation-d_646.html",
     "title": "Darcy-Weisbach Equation: Flow Resistance & Pressure Loss",
     "topic": "fluid_flow"},
    {"keywords": ["bernoulli", "fluid energy", "kinetic head"],
     "url": "https://www.engineeringtoolbox.com/bernouilli-equation-d_183.html",
     "title": "Bernoulli Equation",
     "topic": "fluid_flow"},
    {"keywords": ["reynolds", "laminar", "turbulent"],
     "url": "https://www.engineeringtoolbox.com/reynolds-number-d_237.html",
     "title": "Reynolds Number",
     "topic": "fluid_flow"},
    {"keywords": ["pipe sizing", "pipe diameter", "flow velocity"],
     "url": "https://www.engineeringtoolbox.com/pipe-sizing-d_43.html",
     "title": "Pipe Sizing",
     "topic": "fluid_flow"},
    {"keywords": ["hvac", "duct sizing", "air flow", "cfm"],
     "url": "https://www.engineeringtoolbox.com/duct-friction-pressure-loss-d_444.html",
     "title": "Duct Friction & Pressure Loss",
     "topic": "hvac"},
    {"keywords": ["air change", "ach", "ventilation rate"],
     "url": "https://www.engineeringtoolbox.com/air-change-rate-room-d_867.html",
     "title": "Air Change Rate",
     "topic": "hvac"},
    {"keywords": ["heat transfer", "thermal conductivity"],
     "url": "https://www.engineeringtoolbox.com/conductive-heat-transfer-d_428.html",
     "title": "Conductive Heat Transfer",
     "topic": "heat_transfer"},
    {"keywords": ["convection", "heat transfer coefficient"],
     "url": "https://www.engineeringtoolbox.com/convective-heat-transfer-d_430.html",
     "title": "Convective Heat Transfer",
     "topic": "heat_transfer"},
    {"keywords": ["radiation", "stefan boltzmann", "emissivity"],
     "url": "https://www.engineeringtoolbox.com/radiation-heat-transfer-d_431.html",
     "title": "Radiation Heat Transfer",
     "topic": "heat_transfer"},
    {"keywords": ["voltage drop", "conductor sizing", "wire size"],
     "url": "https://www.engineeringtoolbox.com/voltage-drop-d_1944.html",
     "title": "Voltage Drop",
     "topic": "electrical"},
    {"keywords": ["ohm", "ohm's law", "resistance"],
     "url": "https://www.engineeringtoolbox.com/ohms-law-d_1820.html",
     "title": "Ohm's Law",
     "topic": "electrical"},
    {"keywords": ["pump", "pump head", "affinity laws"],
     "url": "https://www.engineeringtoolbox.com/pump-affinity-laws-d_408.html",
     "title": "Pump Affinity Laws",
     "topic": "pumps"},
    {"keywords": ["beam", "deflection", "bending"],
     "url": "https://www.engineeringtoolbox.com/beam-stress-deflection-d_1312.html",
     "title": "Beam Stress & Deflection",
     "topic": "structural"},
    {"keywords": ["bus duct", "busway", "ampacity"],
     "url": "https://www.engineeringtoolbox.com/conductor-sizing-d_1438.html",
     "title": "Conductor Sizing",
     "topic": "electrical"},
    {"keywords": ["fan", "fan laws"],
     "url": "https://www.engineeringtoolbox.com/fan-affinity-laws-d_196.html",
     "title": "Fan Affinity Laws",
     "topic": "fans"},
    {"keywords": ["combustion", "fuel energy", "calorific"],
     "url": "https://www.engineeringtoolbox.com/fuels-higher-calorific-values-d_169.html",
     "title": "Fuels & Calorific Values",
     "topic": "combustion"},
    {"keywords": ["steel", "yield strength", "tensile"],
     "url": "https://www.engineeringtoolbox.com/young-modulus-d_417.html",
     "title": "Young's Modulus & Tensile Strength",
     "topic": "materials"},
]


def _conn():
    Path(CACHE_DB).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(CACHE_DB, timeout=2.0)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def _ensure_schema():
    c = _conn()
    try:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS eng_toolbox_cache (
            url_hash    TEXT PRIMARY KEY,
            url         TEXT NOT NULL,
            title       TEXT,
            body_text   TEXT,
            fetched_at  REAL NOT NULL,
            status      INTEGER,
            byte_count  INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_eng_fetched
            ON eng_toolbox_cache(fetched_at DESC);

        CREATE TABLE IF NOT EXISTS eng_toolbox_query_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            query       TEXT NOT NULL,
            matched_url TEXT,
            ts          REAL NOT NULL
        );
        """)
        c.commit()
    finally:
        c.close()


def _hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:32]


class EngineeringToolboxAdapter:
    name = "engineering_toolbox"
    domain = "engineeringtoolbox.com"

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """Match query against the curated topic map.

        Returns refs ranked by keyword overlap. The map grows over time
        as Murphy encounters new questions (call add_topic() to extend).
        """
        _ensure_schema()
        q = (query or "").lower()
        scored: List[tuple] = []
        for entry in TOPIC_MAP:
            score = sum(1 for kw in entry["keywords"] if kw in q)
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: -x[0])
        refs: List[Dict] = []
        for _, entry in scored[:limit]:
            refs.append({
                "title": entry["title"],
                "url": entry["url"],
                "snippet": f"Topic: {entry['topic']}",
                "corpus_name": self.name,
                "retrieved_ts": time.time(),
            })
        # Log the query for future map expansion
        try:
            c = _conn()
            try:
                c.execute(
                    "INSERT INTO eng_toolbox_query_log (query, matched_url, ts) VALUES (?,?,?)",
                    (q[:200], refs[0]["url"] if refs else None, time.time()),
                )
                c.commit()
            finally:
                c.close()
        except Exception:
            pass
        return refs

    def fetch(self, url: str) -> Optional[Dict]:
        """Fetch a page, cache with 30-day TTL. Returns doc dict or None."""
        _ensure_schema()
        h = _hash(url)
        c = _conn()
        try:
            row = c.execute(
                "SELECT url, title, body_text, fetched_at "
                "FROM eng_toolbox_cache WHERE url_hash=?", (h,)
            ).fetchone()
            if row and (time.time() - row[3]) < TTL_SECONDS:
                return {"title": row[1], "url": row[0],
                        "body_text": row[2], "retrieved_ts": row[3]}
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
            title = title_m.group(1).strip() if title_m else url
            text = re.sub(r"<script[^>]*>.*?</script>", " ", html,
                          flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", " ", text,
                          flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            text = text[:8000]
            c.execute(
                """INSERT OR REPLACE INTO eng_toolbox_cache
                   (url_hash, url, title, body_text, fetched_at, status, byte_count)
                   VALUES (?,?,?,?,?,?,?)""",
                (h, url, title, text, time.time(), 200, len(text)),
            )
            c.commit()
            return {"title": title, "url": url,
                    "body_text": text, "retrieved_ts": time.time()}
        except Exception:
            return None
        finally:
            c.close()

    def cite(self, ref: Dict) -> str:
        title = ref.get("title", "Engineering Toolbox")
        url = ref.get("url", "https://www.engineeringtoolbox.com/")
        return f"Source: {title} — {url}"

    def add_topic(self, keywords: List[str], url: str,
                  title: str, topic: str = "general"):
        """Extend the curated topic map at runtime."""
        TOPIC_MAP.append({
            "keywords": [k.lower() for k in keywords],
            "url": url, "title": title, "topic": topic,
        })

    def get_stats(self) -> Dict:
        _ensure_schema()
        c = _conn()
        try:
            n = c.execute("SELECT COUNT(*) FROM eng_toolbox_cache").fetchone()[0]
            bytes_ = c.execute(
                "SELECT COALESCE(SUM(byte_count),0) FROM eng_toolbox_cache"
            ).fetchone()[0]
            queries = c.execute(
                "SELECT COUNT(*) FROM eng_toolbox_query_log"
            ).fetchone()[0]
            unmatched = c.execute(
                "SELECT COUNT(*) FROM eng_toolbox_query_log WHERE matched_url IS NULL"
            ).fetchone()[0]
            return {"name": self.name, "domain": self.domain,
                    "topic_map_size": len(TOPIC_MAP),
                    "cached_pages": n, "cached_bytes": bytes_,
                    "total_queries": queries,
                    "unmatched_queries": unmatched}
        finally:
            c.close()
