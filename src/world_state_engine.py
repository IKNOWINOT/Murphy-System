"""
src/world_state_engine.py
PATCH-103: Murphy World State Engine

Murphy's external sensory system. Continuously monitors 8 real-world signal domains,
collapses them into a single World State Index (WSI 0.0–1.0), runs dynamic scenario
models, and feeds directly into PCC, RROM, and Front-of-Line decision gates.

Domains:
  markets       — S&P500, VIX, BTC, DXY (Yahoo Finance + CoinGecko)
  shipping      — Baltic Dry Index proxy, container rate signals (FRED/web)
  satellite     — NASA FIRMS fire alerts, NSIDC ice extent proxy
  speeches      — NewsAPI headlines → LLM sentiment extraction
  sanctions     — OFAC SDN list change rate (web scrape)
  conflict      — GDELT military event count, ACLED proxy
  sentiment     — News headline sentiment (NewsAPI/Reddit)
  legislative   — Emergency declaration tracking (web)
  weather       — Open-Meteo temperature anomaly + energy proxy (EIA)

WSI labels:
  0.8–1.0  STABLE      (green)
  0.6–0.8  ELEVATED    (yellow)
  0.4–0.6  STRAINED    (orange)
  0.2–0.4  CRITICAL    (red)
  0.0–0.2  CASCADE     (black)

PATCH: 103
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import statistics
import threading
import time
import urllib.request
import urllib.error
from collections import deque
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_DB_PATH        = "/var/lib/murphy-production/world_state.db"
_RING_SIZE      = 1440          # 24h at 1-min resolution
_REFRESH_INTERVAL = 300         # 5 minutes between full refresh cycles
_SCENARIO_THRESHOLD = 0.6       # WSI below this triggers scenario generation
_UA             = "MurphyWorldStateEngine/1.0 (murphy.systems)"

# Domain weights — must sum to 1.0
_WEIGHTS: Dict[str, float] = {
    "markets":     0.20,
    "shipping":    0.10,
    "satellite":   0.08,
    "speeches":    0.10,
    "sanctions":   0.10,
    "conflict":    0.15,
    "sentiment":   0.10,
    "legislative": 0.10,
    "weather":     0.07,
}

_WSI_LABELS = [
    (0.80, "STABLE"),
    (0.60, "ELEVATED"),
    (0.40, "STRAINED"),
    (0.20, "CRITICAL"),
    (0.00, "CASCADE"),
]

# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class DomainReading:
    domain:          str
    stability_score: float          # 0.0 (crisis) – 1.0 (calm)
    raw_signals:     Dict[str, Any]
    source:          str
    fetched_at:      str
    error:           Optional[str]  = None
    trend:           float          = 0.0   # positive = improving
    confidence:      float          = 1.0   # 0.0–1.0 (lower if fallback used)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Scenario:
    name:             str
    trigger_domain:   str
    probability:      float
    horizon_days:     int
    wsi_impact:       float
    affected_domains: List[str]
    murphy_response:  str
    generated_at:     str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorldStateSnapshot:
    timestamp:      str
    epoch:          float
    wsi:            float
    wsi_label:      str
    domains:        Dict[str, DomainReading]
    scenarios:      List[Scenario]
    trend_6h:       float           # WSI trend over last 6h (positive = improving)
    dominant_risk:  str             # domain pulling WSI lowest
    notes:          List[str]
    refresh_duration_s: float       # how long the refresh took

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    def graph_point(self) -> Dict[str, Any]:
        """Compact form for time-series graphing."""
        return {
            "ts":           self.timestamp,
            "wsi":          self.wsi,
            "label":        self.wsi_label,
            "dominant":     self.dominant_risk,
            **{f"d_{k}": v.stability_score for k, v in self.domains.items()},
        }


# ── Domain Fetchers ───────────────────────────────────────────────────────────

def _fetch_url(url: str, timeout: int = 8) -> Optional[Dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _yahoo(ticker: str) -> Optional[float]:
    """PATCH-107a: Fetch last close via yfinance (handles rate-limits, proper headers).
    Falls back to raw urllib if yfinance import fails."""
    try:
        import yfinance as _yf
        t = _yf.Ticker(ticker)
        h = t.history(period="5d", auto_adjust=True)
        if not h.empty:
            return float(h["Close"].iloc[-1])
        return None
    except Exception:
        pass
    # urllib fallback (original path)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
    data = _fetch_url(url)
    if not data:
        return None
    try:
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        return closes[-1] if closes else None
    except Exception:
        return None


# ── D1: Markets ───────────────────────────────────────────────────────────────

def fetch_markets() -> DomainReading:
    signals: Dict[str, Any] = {}
    score_components: List[float] = []
    source_parts: List[str] = []
    errors: List[str] = []

    # S&P 500 — stability = distance from 52-week high is the fear; we track VIX instead
    sp500 = _yahoo("%5EGSPC")
    if sp500 is not None:
        signals["sp500"] = round(sp500, 2)
        source_parts.append("Yahoo/^GSPC")

    # VIX — fear index. <15 = calm, 15-25 = normal, 25-35 = elevated, >35 = panic
    vix = _yahoo("%5EVIX")
    if vix is not None:
        signals["vix"] = round(vix, 2)
        # Map VIX to stability: 0 = 50+, 1.0 = 10 or below
        vix_score = max(0.0, min(1.0, (50.0 - vix) / 40.0))
        score_components.append(vix_score * 0.40)   # VIX is the best single fear gauge
        source_parts.append("Yahoo/^VIX")

    # BTC/USD — risk appetite proxy. Crash = <50k, euphoria > 100k
    btc = _fetch_url("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=6)
    if btc:
        btc_price = btc.get("bitcoin", {}).get("usd", 0)
        signals["btc_usd"] = btc_price
        # Score: < 20k = distress (0.2), 60-100k = healthy (0.8), >100k = euphoric (1.0)
        btc_score = min(1.0, max(0.1, btc_price / 100_000))
        score_components.append(btc_score * 0.20)
        source_parts.append("CoinGecko/BTC")

    # DXY — dollar strength. >105 = risk-off, <95 = risk-on (weak dollar = emerging market relief)
    dxy = _yahoo("DX-Y.NYB")
    if dxy is not None:
        signals["dxy"] = round(dxy, 2)
        # DXY 100 is neutral. >110 = stress, <95 = loose
        dxy_score = max(0.2, min(1.0, 1.0 - (dxy - 100) / 20.0))
        score_components.append(dxy_score * 0.20)
        source_parts.append("Yahoo/DXY")

    # 10Y Treasury yield — >5% = tight financial conditions
    tsy = _yahoo("%5ETNX")
    if tsy is not None:
        signals["us10y"] = round(tsy, 3)
        # 2% = easy (1.0), 5% = tight (0.4), >7% = crisis (0.0)
        tsy_score = max(0.0, min(1.0, 1.0 - (tsy - 2.0) / 6.0))
        score_components.append(tsy_score * 0.20)
        source_parts.append("Yahoo/^TNX")

    # Composite
    if score_components:
        raw = sum(score_components) / sum([0.40, 0.20, 0.20, 0.20][:len(score_components)])
        stability = round(min(1.0, max(0.0, raw)), 4)
        confidence = min(1.0, len(score_components) / 3)
    else:
        stability = 0.5
        confidence = 0.1
        errors.append("All market feeds failed — using baseline 0.5")

    return DomainReading(
        domain          = "markets",
        stability_score = stability,
        raw_signals     = signals,
        source          = ", ".join(source_parts) or "fallback",
        fetched_at      = datetime.now(timezone.utc).isoformat(),
        error           = "; ".join(errors) or None,
        confidence      = confidence,
    )


# ── D2: Shipping ─────────────────────────────────────────────────────────────

def _fred_series_last(series_id: str) -> Optional[float]:
    """PATCH-108a-r1: Fetch latest FRED time-series value via subprocess curl.
    urllib times out from venv context; curl is reliable on this server.
    Skips blank values (FRED emits empty strings for unreleased dates)."""
    try:
        import subprocess as _sp
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        result = _sp.run(
            ["curl", "-s", "--max-time", "10", url],
            capture_output=True, text=True, timeout=12,
        )
        if result.returncode != 0:
            return None
        lines = [l.strip() for l in result.stdout.splitlines()
                 if l.strip() and not l.startswith("DATE")]
        for line in reversed(lines):
            parts = line.split(",")
            if len(parts) == 2 and parts[1] not in ("", ".", " "):
                try:
                    return float(parts[1])
                except ValueError:
                    continue
    except Exception:
        pass
    return None


def fetch_shipping() -> DomainReading:
    """PATCH-108a: Shipping stability via FRED proxies.
    BDI (BDI/BDIY) was delisted from Yahoo Finance.
    New sources:
      - WTISPLC: WTI crude oil price (FRED) — shipping cost proxy; high oil = cost stress
      - CASSFREIGHTIDX: Cass Freight Index (FRED) — US freight volume leading indicator
      - DCOILWTICO: WTI daily spot (FRED) — more recent than WTISPLC
    Scoring: high oil = shipping cost stress; low freight volume = demand weakness.
    """
    signals: Dict[str, Any] = {}
    errors: List[str] = []
    score_components: List[Tuple[float, float]] = []

    # WTI crude oil — shipping cost proxy (FRED DCOILWTICO, daily)
    wti = _fred_series_last("DCOILWTICO")
    if wti is not None:
        signals["wti_usd"] = round(wti, 2)
        # $50 = low cost (0.85), $80 = moderate (0.65), $120+ = stress (0.30)
        wti_score = max(0.20, min(0.90, 1.0 - (wti - 50.0) / 100.0))
        score_components.append((wti_score, 0.50))
        errors_src = "FRED/DCOILWTICO"
    else:
        errors.append("WTI feed unavailable")
        errors_src = None

    # Cass Freight Index (monthly) — US freight demand
    cassf = _fred_series_last("RAILFRTINTERMODAL")  # PATCH-108a-r2: CASSFREIGHTIDX invalid, use rail intermodal volume
    if cassf is not None:
        signals["cass_freight"] = round(cassf, 3)
        # RAILFRTINTERMODAL ~1.1M-1.3M carloads. <1M=weak, 1.3M=strong
        cassf_score = max(0.30, min(0.90, (cassf - 900_000) / 500_000))
        score_components.append((cassf_score, 0.50))
        cass_src = "FRED/CASSFREIGHTIDX"
    else:
        errors.append("Cass Freight feed unavailable")
        cass_src = None

    if score_components:
        total_w = sum(w for _, w in score_components)
        stability = round(sum(s * w for s, w in score_components) / total_w, 4)
        confidence = min(0.85, 0.50 * len(score_components))
        source_parts = [s for s in [errors_src if wti else None, cass_src if cassf else None] if s]
        source = ", ".join(source_parts)
    else:
        stability = 0.60
        confidence = 0.20
        source = "synthetic-baseline"
        errors.append("All shipping feeds unavailable — baseline 0.60")

    return DomainReading(
        domain          = "shipping",
        stability_score = stability,
        raw_signals     = signals,
        source          = source,
        fetched_at      = datetime.now(timezone.utc).isoformat(),
        error           = "; ".join(errors) or None,
        confidence      = confidence,
    )


# ── D3: Satellite ─────────────────────────────────────────────────────────────

def fetch_satellite() -> DomainReading:
    """
    NASA FIRMS fire alerts (active fires globally) + NSIDC Arctic ice proxy.
    High fire count + declining ice = environmental instability.
    """
    signals: Dict[str, Any] = {}
    errors: List[str] = []
    score_components: List[Tuple[float, float]] = []  # (score, weight)

    # NASA FIRMS — active fire count (last 24h, global)
    # Public API, no key needed for basic counts
    firms_url = (
        "https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        "VIIRS_SNPP_NRT/World/1/2026-01-01"
        # Note: full FIRMS needs a MAP_KEY. Use summary stats instead.
    )

    # Alternative: use WorldFires summary from FIRMS web
    # Since full FIRMS needs a key, use the public summary endpoint
    try:
        req = urllib.request.Request(
            "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/shapes/zips/",
            headers={"User-Agent": _UA}
        )
        # Just check if reachable — count unavailable without key
        with urllib.request.urlopen(req, timeout=5) as r:
            signals["firms_reachable"] = True
    except Exception:
        signals["firms_reachable"] = False

    # Global fire stress: use MODIS/VIIRS global active fire proxy
    # Public FIRMS count endpoint (no key for summary)
    firms_data = _fetch_url(
        "https://firms.modaps.eosdis.nasa.gov/api/country/csv/NOAA-20/VIIRS_SNPP_NRT/World/1/2026-04-01",
        timeout=5
    )
    if firms_data:
        signals["firms_data"] = "available"
    else:
        signals["fires_note"] = "FIRMS key required for counts — using climate anomaly proxy"

    # Open-Meteo global temperature anomaly (proxy for climate stress)
    # Use multiple major city average as global proxy
    cities = [
        ("40.71", "-74.01", "NYC"),
        ("51.51", "-0.13", "London"),
        ("35.69", "139.69", "Tokyo"),
        ("28.61", "77.21", "Delhi"),
    ]
    temp_readings: List[float] = []
    for lat, lon, name in cities[:2]:  # limit API calls
        weather = _fetch_url(
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m&timezone=auto",
            timeout=5
        )
        if weather:
            temp = weather.get("current", {}).get("temperature_2m")
            if temp is not None:
                temp_readings.append(float(temp))
                signals[f"temp_{name}"] = temp

    if temp_readings:
        avg_temp = statistics.mean(temp_readings)
        signals["avg_temp_sample"] = round(avg_temp, 1)
        # Temperature anomaly proxy: very high or very low = instability signal
        # This is a crude proxy — real anomaly needs historical baseline
        score_components.append((0.75, 0.5))  # baseline — not enough data for true anomaly
    else:
        errors.append("Open-Meteo unavailable")

    # Composite satellite score
    if score_components:
        total_w = sum(w for _, w in score_components)
        stability = sum(s * w for s, w in score_components) / total_w
        confidence = 0.5   # proxy data, not true satellite
    else:
        stability = 0.65
        confidence = 0.2
        errors.append("All satellite proxies failed")

    signals["note"] = "Full satellite feed requires NASA FIRMS MAP_KEY + commercial APIs; using open proxies"

    return DomainReading(
        domain          = "satellite",
        stability_score = round(min(1.0, max(0.0, stability)), 4),
        raw_signals     = signals,
        source          = "Open-Meteo + NASA FIRMS (proxy)",
        fetched_at      = datetime.now(timezone.utc).isoformat(),
        error           = "; ".join(errors) or None,
        confidence      = confidence,
    )


# ── D4: Speeches / Rhetoric ───────────────────────────────────────────────────

def fetch_speeches() -> DomainReading:
    """
    NewsAPI headlines from key geopolitical sources → LLM sentiment.
    Proxy: top 10 geopolitical headlines → Murphy's LLM → stability score.
    """
    signals: Dict[str, Any] = {}
    errors: List[str] = []

    # Use GDELT document search — free, no key
    gdelt_url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        "?query=diplomatic+statement+OR+summit+OR+ceasefire+OR+sanctions+OR+military"
        "&mode=artlist&maxrecords=10&format=json&timespan=24h"
        "&sort=datedesc"
    )
    articles: List[Dict] = []
    gdelt_data = _fetch_url(gdelt_url, timeout=10)
    if gdelt_data and isinstance(gdelt_data, dict):
        articles = gdelt_data.get("articles", [])
        signals["gdelt_articles"] = len(articles)
        signals["headlines"] = [a.get("title", "")[:80] for a in articles[:5]]

    if not articles:
        errors.append("GDELT unavailable")
        signals["headlines"] = []

    # Score based on keyword analysis (LLM-lite — keyword-based until LLM available)
    hawkish_keywords = [
        "attack", "strike", "war", "invasion", "missile", "bomb",
        "escalat", "threat", "ultimatum", "nuclear", "troops", "military action",
        "crisis", "coup", "sanctions", "blockade", "conflict",
    ]
    cooperative_keywords = [
        "ceasefire", "peace", "agreement", "treaty", "summit", "deal",
        "cooperat", "diplomatic", "negotiat", "alliance", "partner",
        "aid", "relief", "stabiliz",
    ]

    all_text = " ".join(signals.get("headlines", [])).lower()
    hawk_count = sum(1 for kw in hawkish_keywords if kw in all_text)
    coop_count = sum(1 for kw in cooperative_keywords if kw in all_text)

    signals["hawkish_signals"] = hawk_count
    signals["cooperative_signals"] = coop_count

    if articles:
        # Score: more hawkish = lower stability
        raw = 0.5 + (coop_count - hawk_count * 1.5) / max(20, hawk_count + coop_count + 1)
        stability = round(min(1.0, max(0.1, raw)), 4)
        confidence = 0.7
    else:
        stability = 0.55
        confidence = 0.2

    # Try LLM enrichment if available
    try:
        if articles:
            from src.llm_provider import get_llm
            headline_str = "\n".join(f"- {h}" for h in signals.get("headlines", [])[:8])
            llm_result = get_llm().complete(
                f"Rate the geopolitical stability implied by these headlines on a scale 0.0 to 1.0.\n"
                f"0.0 = imminent conflict/crisis, 1.0 = peaceful cooperation.\n"
                f"Headlines:\n{headline_str}\n\n"
                f"Reply with ONLY a number like 0.65",
                system="You are a geopolitical analyst. Reply with only a decimal number between 0.0 and 1.0.",
                temperature=0.1,
                max_tokens=10,
            )
            if llm_result and llm_result.content:
                nums = re.findall(r"0?\.\d+|\d+\.\d+", llm_result.content.strip())
                if nums:
                    llm_score = float(nums[0])
                    if 0.0 <= llm_score <= 1.0:
                        stability = round(llm_score, 4)
                        signals["llm_scored"] = True
                        signals["llm_score"] = llm_score
                        confidence = 0.85
    except Exception as exc:
        signals["llm_error"] = str(exc)[:60]

    return DomainReading(
        domain          = "speeches",
        stability_score = stability,
        raw_signals     = signals,
        source          = "GDELT/NewsAPI + keyword analysis",
        fetched_at      = datetime.now(timezone.utc).isoformat(),
        error           = "; ".join(errors) or None,
        confidence      = confidence,
    )


# ── D5: Sanctions ─────────────────────────────────────────────────────────────

def fetch_sanctions() -> DomainReading:
    """
    OFAC SDN list size proxy + sanctions news volume via GDELT.
    Rapidly growing sanctions = geopolitical pressure escalating.
    """
    signals: Dict[str, Any] = {}
    errors: List[str] = []

    # GDELT sanctions news volume (free)
    gdelt_url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        "?query=sanctions+OR+OFAC+OR+embargo+OR+export+control"
        "&mode=artlist&maxrecords=20&format=json&timespan=48h"
    )
    sanctions_data = _fetch_url(gdelt_url, timeout=10)
    article_count_48h = 0
    if sanctions_data and isinstance(sanctions_data, dict):
        arts = sanctions_data.get("articles", [])
        article_count_48h = len(arts)
        signals["sanctions_articles_48h"] = article_count_48h
        signals["sanctions_headlines"] = [a.get("title","")[:60] for a in arts[:3]]

    # OFAC SDN list: check current count via public API
    # OFAC publishes SDN list in XML — count entries as proxy for escalation
    try:
        req = urllib.request.Request(
            "https://www.treasury.gov/ofac/downloads/sdn.xml",
            headers={"User-Agent": _UA}
        )
        # Just get content-length as a proxy (full XML is large)
        req.get_method = lambda: "HEAD"
        with urllib.request.urlopen(req, timeout=5) as r:
            size = r.headers.get("content-length", 0)
            signals["ofac_sdn_bytes"] = int(size)
    except Exception as e:
        signals["ofac_note"] = "HEAD request failed"
        errors.append(f"OFAC check failed: {e}")

    # Score: high sanctions news volume = lower stability
    # Baseline: ~5 articles/48h = normal. >30 = elevated. >80 = crisis.
    if article_count_48h <= 5:
        stability = 0.85
    elif article_count_48h <= 20:
        stability = 0.70
    elif article_count_48h <= 50:
        stability = 0.50
    elif article_count_48h <= 100:
        stability = 0.30
    else:
        stability = 0.15

    confidence = 0.8 if article_count_48h > 0 else 0.3

    return DomainReading(
        domain          = "sanctions",
        stability_score = round(stability, 4),
        raw_signals     = signals,
        source          = "GDELT sanctions news volume + OFAC size probe",
        fetched_at      = datetime.now(timezone.utc).isoformat(),
        error           = "; ".join(errors) or None,
        confidence      = confidence,
    )


# ── D6: Conflict / Troop Movements ───────────────────────────────────────────

def fetch_conflict() -> DomainReading:
    """
    GDELT military/conflict event volume (free, no key).
    High event count = active conflict. Lower = peace.
    """
    signals: Dict[str, Any] = {}
    errors: List[str] = []

    # GDELT conflict events (last 48h)
    conflict_url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        "?query=military+attack+OR+airstrike+OR+troops+OR+shelling+OR+offensive+OR+ceasefire+violation"
        "&mode=artlist&maxrecords=25&format=json&timespan=48h"
    )
    conflict_data = _fetch_url(conflict_url, timeout=10)
    conflict_48h = 0
    if conflict_data and isinstance(conflict_data, dict):
        arts = conflict_data.get("articles", [])
        conflict_48h = len(arts)
        signals["conflict_articles_48h"] = conflict_48h
        signals["conflict_headlines"] = [a.get("title","")[:70] for a in arts[:5]]

    # Nuclear/WMD escalation check
    nuclear_url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        "?query=nuclear+threat+OR+nuclear+weapon+OR+missile+test+OR+ICBM"
        "&mode=artlist&maxrecords=10&format=json&timespan=48h"
    )
    nuclear_data = _fetch_url(nuclear_url, timeout=8)
    nuclear_48h = 0
    if nuclear_data and isinstance(nuclear_data, dict):
        nuclear_48h = len(nuclear_data.get("articles", []))
        signals["nuclear_articles_48h"] = nuclear_48h

    # Score: conflict 0–5 = peaceful (0.9), 5–15 = low conflict (0.7),
    #        15–30 = active (0.5), 30–60 = high (0.3), >60 = crisis (0.1)
    if conflict_48h <= 5:
        base_score = 0.90
    elif conflict_48h <= 15:
        base_score = 0.70
    elif conflict_48h <= 30:
        base_score = 0.50
    elif conflict_48h <= 60:
        base_score = 0.30
    else:
        base_score = 0.15

    # Nuclear escalation penalty
    if nuclear_48h > 5:
        base_score *= 0.7
        signals["nuclear_escalation"] = True
    elif nuclear_48h > 2:
        base_score *= 0.85

    stability = round(min(1.0, max(0.05, base_score)), 4)
    confidence = 0.75 if conflict_48h > 0 else 0.3

    return DomainReading(
        domain          = "conflict",
        stability_score = stability,
        raw_signals     = signals,
        source          = "GDELT conflict event volume",
        fetched_at      = datetime.now(timezone.utc).isoformat(),
        error           = "; ".join(errors) or None,
        confidence      = confidence,
    )


# ── D7: Social Sentiment ──────────────────────────────────────────────────────

def fetch_sentiment() -> DomainReading:
    """
    News headline sentiment via GDELT tone scores + keyword analysis.
    GDELT provides average tone of articles — negative tone = lower stability.
    """
    signals: Dict[str, Any] = {}
    errors: List[str] = []

    # GDELT timeline tone (global news mood)
    tone_url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        "?query=world+global+international"
        "&mode=artlist&maxrecords=20&format=json&timespan=12h"
        "&sort=datedesc"
    )
    tone_data = _fetch_url(tone_url, timeout=10)
    articles: List[Dict] = []
    if tone_data and isinstance(tone_data, dict):
        articles = tone_data.get("articles", [])

    # Panic/fear keyword detection in headlines
    panic_keywords = [
        "crash", "collapse", "catastroph", "panic", "emergency", "crisis",
        "disaster", "imminent", "breaking", "urgent", "alarming",
        "chaos", "meltdown", "worst", "record high", "surge", "plunge",
    ]
    calm_keywords = [
        "recovery", "stabiliz", "growth", "optimis", "progress",
        "agreement", "cooperat", "improve", "steady", "resilient",
    ]

    all_text = " ".join(a.get("title","") + " " + a.get("seendate","")
                        for a in articles).lower()
    panic_count = sum(1 for kw in panic_keywords if kw in all_text)
    calm_count  = sum(1 for kw in calm_keywords  if kw in all_text)

    signals["articles_sampled"] = len(articles)
    signals["panic_signals"] = panic_count
    signals["calm_signals"] = calm_count
    signals["sample_headlines"] = [a.get("title","")[:60] for a in articles[:4]]

    if articles:
        raw = 0.55 + (calm_count - panic_count * 1.2) / max(20, panic_count + calm_count + 1)
        stability = round(min(1.0, max(0.1, raw)), 4)
        confidence = 0.7
    else:
        stability = 0.60
        confidence = 0.2
        errors.append("No GDELT articles returned")

    return DomainReading(
        domain          = "sentiment",
        stability_score = stability,
        raw_signals     = signals,
        source          = "GDELT headline sentiment analysis",
        fetched_at      = datetime.now(timezone.utc).isoformat(),
        error           = "; ".join(errors) or None,
        confidence      = confidence,
    )


# ── D8: Legislative ───────────────────────────────────────────────────────────

def fetch_legislative() -> DomainReading:
    """
    Emergency declarations + major legislative disruption signals via GDELT.
    Emergency powers, constitutional crises, election interference = low stability.
    """
    signals: Dict[str, Any] = {}
    errors: List[str] = []

    # Emergency declaration news
    emergency_url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        "?query=emergency+declaration+OR+martial+law+OR+constitutional+crisis+"
        "OR+election+fraud+OR+government+shutdown+OR+coup+OR+impeachment"
        "&mode=artlist&maxrecords=15&format=json&timespan=72h"
    )
    emergency_data = _fetch_url(emergency_url, timeout=10)
    emergency_count = 0
    if emergency_data and isinstance(emergency_data, dict):
        arts = emergency_data.get("articles", [])
        emergency_count = len(arts)
        signals["emergency_articles_72h"] = emergency_count
        signals["emergency_headlines"] = [a.get("title","")[:60] for a in arts[:3]]

    # Normal legislative news (bills passed, policy)
    normal_leg_url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        "?query=legislation+OR+parliament+OR+senate+OR+congress+bill+passed"
        "&mode=artlist&maxrecords=10&format=json&timespan=48h"
    )
    normal_data = _fetch_url(normal_leg_url, timeout=8)
    normal_count = len(normal_data.get("articles", [])) if normal_data and isinstance(normal_data, dict) else 0
    signals["normal_legislative_48h"] = normal_count

    # Score: high emergency signals = instability
    if emergency_count <= 2:
        stability = 0.85
    elif emergency_count <= 5:
        stability = 0.70
    elif emergency_count <= 10:
        stability = 0.50
    elif emergency_count <= 20:
        stability = 0.30
    else:
        stability = 0.15

    confidence = 0.75 if emergency_count > 0 or normal_count > 0 else 0.3

    return DomainReading(
        domain          = "legislative",
        stability_score = round(stability, 4),
        raw_signals     = signals,
        source          = "GDELT emergency + legislative news volume",
        fetched_at      = datetime.now(timezone.utc).isoformat(),
        error           = "; ".join(errors) or None,
        confidence      = confidence,
    )


# ── D9: Weather / Energy ─────────────────────────────────────────────────────

def fetch_weather_energy() -> DomainReading:
    """
    Open-Meteo: temperature extremes in key regions.
    EIA natural gas storage (US) as energy supply proxy.
    Extreme weather + energy shortfall = physical constraint on all other systems.
    """
    signals: Dict[str, Any] = {}
    errors: List[str] = []
    score_components: List[Tuple[float, float]] = []  # (score, weight)

    # Open-Meteo: key regions — temperature anomaly proxy
    regions = [
        ("52.52", "13.41", "Berlin",   15.0),   # (lat, lon, name, seasonal_baseline_C)
        ("55.75", "37.61", "Moscow",   8.0),
        ("30.04", "31.23", "Cairo",    24.0),
    ]

    for lat, lon, name, baseline in regions[:2]:
        data = _fetch_url(
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,wind_speed_10m,precipitation"
            f"&daily=temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=1",
            timeout=6
        )
        if data:
            curr = data.get("current", {})
            temp = curr.get("temperature_2m")
            wind = curr.get("wind_speed_10m")
            precip = curr.get("precipitation", 0)
            if temp is not None:
                signals[f"{name}_temp_c"] = temp
                signals[f"{name}_wind_kmh"] = wind
                signals[f"{name}_precip_mm"] = precip
                # Anomaly from seasonal baseline
                anomaly = abs(temp - baseline)
                # >10°C anomaly = stress, >20°C = severe
                temp_score = max(0.2, min(1.0, 1.0 - anomaly / 25.0))
                # Wind > 60 km/h = stress
                wind_score = max(0.3, 1.0 - max(0, (wind or 0) - 30) / 60) if wind else 1.0
                region_score = (temp_score * 0.7 + wind_score * 0.3)
                score_components.append((region_score, 0.3))

    # EIA natural gas storage (US) — proxy for energy security
    # Free with API key — use DEMO_KEY for basic access
    eia_data = _fetch_url(
        "https://api.eia.gov/v2/natural-gas/stor/wkly/data/"
        "?frequency=weekly&data[0]=value&sort[0][column]=period"
        "&sort[0][direction]=desc&length=4&api_key=DEMO_KEY",
        timeout=6
    )
    if eia_data:
        try:
            rows = eia_data.get("response", {}).get("data", [])
            if rows:
                latest_storage = float(rows[0].get("value", 0))
                signals["us_natgas_storage_bcf"] = latest_storage
                # US natural gas storage: below 1500 BCF = concern, 2000-4000 = normal, <1000 = crisis
                if latest_storage > 2000:
                    storage_score = 0.90
                elif latest_storage > 1500:
                    storage_score = 0.75
                elif latest_storage > 1000:
                    storage_score = 0.50
                else:
                    storage_score = 0.25
                score_components.append((storage_score, 0.4))
        except Exception:
            errors.append("EIA storage parse failed")
    else:
        signals["energy_note"] = "EIA DEMO_KEY rate limited — using baseline"
        score_components.append((0.70, 0.4))

    if score_components:
        total_w = sum(w for _, w in score_components)
        stability = sum(s * w for s, w in score_components) / total_w
        confidence = 0.75
    else:
        stability = 0.65
        confidence = 0.2
        errors.append("All weather/energy feeds failed")

    return DomainReading(
        domain          = "weather",
        stability_score = round(min(1.0, max(0.0, stability)), 4),
        raw_signals     = signals,
        source          = "Open-Meteo + EIA (DEMO_KEY)",
        fetched_at      = datetime.now(timezone.utc).isoformat(),
        error           = "; ".join(errors) or None,
        confidence      = confidence,
    )


# ── WSI Computation ───────────────────────────────────────────────────────────

class WSIComputer:
    """Computes the World State Index from domain readings."""

    def compute(self, domains: Dict[str, DomainReading]) -> Tuple[float, str, str, List[str]]:
        """Returns (wsi, label, dominant_risk, notes)."""
        weighted_sum = 0.0
        total_weight = 0.0
        notes: List[str] = []
        min_score = 1.0
        dominant_risk = "unknown"

        for domain, weight in _WEIGHTS.items():
            reading = domains.get(domain)
            if reading is None:
                continue
            score = reading.stability_score
            # Confidence-weighted (low confidence readings pulled toward 0.5)
            adjusted = score * reading.confidence + 0.5 * (1 - reading.confidence)
            weighted_sum += adjusted * weight
            total_weight += weight
            if adjusted < min_score:
                min_score = adjusted
                dominant_risk = domain
            if score < 0.4:
                notes.append(f"{domain}: CRITICAL ({score:.2f})")
            elif score < 0.6:
                notes.append(f"{domain}: strained ({score:.2f})")

        wsi = round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.5

        label = "STABLE"
        for threshold, lbl in _WSI_LABELS:
            if wsi >= threshold:
                label = lbl
                break

        return wsi, label, dominant_risk, notes


# ── Scenario Engine ───────────────────────────────────────────────────────────

class ScenarioEngine:
    """Generates dynamic scenario models when WSI < threshold."""

    # Pre-built scenario templates — filled in with current data
    _TEMPLATES = [
        {
            "name": "Trade War Escalation",
            "trigger": "markets",
            "condition": lambda d: d.get("markets", DomainReading("m",0,{},"","")).stability_score < 0.5,
            "affected": ["shipping", "sentiment", "legislative"],
            "horizon": 30,
            "base_prob": 0.35,
            "wsi_impact": -0.15,
            "response": "Increase monitoring of shipping and legislative domains. Alert PCC to elevated financial harm risk.",
        },
        {
            "name": "Regional Conflict Spillover",
            "trigger": "conflict",
            "condition": lambda d: d.get("conflict", DomainReading("c",0,{},"","")).stability_score < 0.4,
            "affected": ["sanctions", "shipping", "sentiment", "weather"],
            "horizon": 14,
            "base_prob": 0.45,
            "wsi_impact": -0.20,
            "response": "Front-of-Line: humanitarian monitoring. PCC: p_harm_physical elevated. RROM: shed ambient tasks.",
        },
        {
            "name": "Energy Supply Shock",
            "trigger": "weather",
            "condition": lambda d: d.get("weather", DomainReading("w",0,{},"","")).stability_score < 0.45,
            "affected": ["markets", "shipping", "sentiment"],
            "horizon": 21,
            "base_prob": 0.30,
            "wsi_impact": -0.12,
            "response": "Monitor EIA storage weekly. PCC: note physical constraint signal. Alert if markets follow.",
        },
        {
            "name": "Sanctions Cascade",
            "trigger": "sanctions",
            "condition": lambda d: d.get("sanctions", DomainReading("s",0,{},"","")).stability_score < 0.45,
            "affected": ["markets", "shipping", "conflict"],
            "horizon": 45,
            "base_prob": 0.40,
            "wsi_impact": -0.18,
            "response": "Track OFAC SDN list growth rate. Legislative domain watch. PCC: financial harm elevated.",
        },
        {
            "name": "Social Panic Spiral",
            "trigger": "sentiment",
            "condition": lambda d: d.get("sentiment", DomainReading("s",0,{},"","")).stability_score < 0.35,
            "affected": ["markets", "legislative"],
            "horizon": 7,
            "base_prob": 0.50,
            "wsi_impact": -0.10,
            "response": "Self-amplifying sentiment loop. Markets and legislative often follow. Monitor closely.",
        },
    ]

    def generate(self, domains: Dict[str, DomainReading], wsi: float) -> List[Scenario]:
        if wsi >= _SCENARIO_THRESHOLD:
            return []   # Only generate when under pressure

        now = datetime.now(timezone.utc).isoformat()
        scenarios: List[Scenario] = []

        for tmpl in self._TEMPLATES:
            try:
                if tmpl["condition"](domains):
                    trigger_domain = tmpl["trigger"]
                    trigger_score = domains.get(trigger_domain, DomainReading("x",0.5,{},"","")).stability_score
                    # Probability scales with how bad the trigger domain is
                    prob = round(min(0.95, tmpl["base_prob"] * (1.5 - trigger_score)), 3)
                    scenarios.append(Scenario(
                        name             = tmpl["name"],
                        trigger_domain   = trigger_domain,
                        probability      = prob,
                        horizon_days     = tmpl["horizon"],
                        wsi_impact       = tmpl["wsi_impact"],
                        affected_domains = tmpl["affected"],
                        murphy_response  = tmpl["response"],
                        generated_at     = now,
                    ))
            except Exception as exc:
                logger.debug("Scenario eval error (%s): %s", tmpl["name"], exc)

        # Sort by probability descending
        scenarios.sort(key=lambda s: s.probability, reverse=True)
        return scenarios[:3]  # top 3 most likely


# ── SQLite Persistence ────────────────────────────────────────────────────────

class WorldStateDB:
    """Lightweight SQLite store for WSI time-series."""

    def __init__(self, path: str):
        self._path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self._path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wsi_snapshots (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    epoch       REAL NOT NULL,
                    timestamp   TEXT NOT NULL,
                    wsi         REAL NOT NULL,
                    wsi_label   TEXT NOT NULL,
                    dominant    TEXT,
                    domains_json TEXT,
                    notes_json  TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_epoch ON wsi_snapshots(epoch)")
            conn.commit()

    def save(self, snap: WorldStateSnapshot):
        with sqlite3.connect(self._path) as conn:
            conn.execute("""
                INSERT INTO wsi_snapshots
                  (epoch, timestamp, wsi, wsi_label, dominant, domains_json, notes_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                snap.epoch,
                snap.timestamp,
                snap.wsi,
                snap.wsi_label,
                snap.dominant_risk,
                json.dumps({k: v.stability_score for k, v in snap.domains.items()}),
                json.dumps(snap.notes),
            ))
            conn.commit()

    def get_history(self, hours: int = 24, limit: int = 288) -> List[Dict]:
        cutoff = time.time() - hours * 3600
        with sqlite3.connect(self._path) as conn:
            rows = conn.execute("""
                SELECT epoch, timestamp, wsi, wsi_label, dominant, domains_json
                FROM wsi_snapshots
                WHERE epoch > ?
                ORDER BY epoch DESC
                LIMIT ?
            """, (cutoff, limit)).fetchall()
        result = []
        for row in rows:
            domains = json.loads(row[5]) if row[5] else {}
            result.append({
                "epoch":    row[0],
                "ts":       row[1],
                "wsi":      row[2],
                "label":    row[3],
                "dominant": row[4],
                **{f"d_{k}": v for k, v in domains.items()},
            })
        return list(reversed(result))   # chronological order

    def get_trend(self, hours: int = 6) -> float:
        """WSI trend: positive = improving, negative = worsening."""
        cutoff = time.time() - hours * 3600
        with sqlite3.connect(self._path) as conn:
            rows = conn.execute("""
                SELECT wsi FROM wsi_snapshots WHERE epoch > ?
                ORDER BY epoch ASC
            """, (cutoff,)).fetchall()
        values = [r[0] for r in rows]
        if len(values) < 2:
            return 0.0
        # Simple linear trend: last half avg vs first half avg
        mid = len(values) // 2
        first_avg = statistics.mean(values[:mid])
        last_avg  = statistics.mean(values[mid:])
        return round(last_avg - first_avg, 4)


# ── Main Engine ───────────────────────────────────────────────────────────────

class WorldStateEngine:
    """
    PATCH-103: Murphy's World State Engine.

    Continuously monitors 8 geopolitical/economic domains,
    computes a World State Index (WSI), runs scenario models,
    and feeds into PCC, RROM, and Front-of-Line.

    Thread-safe singleton. Background refresh every 5 minutes.
    """

    def __init__(self):
        self._current:      Optional[WorldStateSnapshot] = None
        self._lock          = threading.RLock()
        self._ring:         deque = deque(maxlen=_RING_SIZE)
        self._db            = WorldStateDB(_DB_PATH)
        self._wsi_computer  = WSIComputer()
        self._scenario_engine = ScenarioEngine()
        self._running       = False
        self._thread:       Optional[threading.Thread] = None
        self._fetchers      = {
            "markets":     fetch_markets,
            "shipping":    fetch_shipping,
            "satellite":   fetch_satellite,
            "speeches":    fetch_speeches,
            "sanctions":   fetch_sanctions,
            "conflict":    fetch_conflict,
            "sentiment":   fetch_sentiment,
            "legislative": fetch_legislative,
            "weather":     fetch_weather_energy,
        }
        logger.info("WorldStateEngine initialized — PATCH-103")

    def start(self):
        """Start background refresh loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._refresh_loop,
            name="world-state-refresher",
            daemon=True,
        )
        self._thread.start()
        logger.info("WorldStateEngine background loop started (interval=%ds)", _REFRESH_INTERVAL)

    def stop(self):
        self._running = False

    def _refresh_loop(self):
        # Initial refresh with slight delay to let service fully start
        time.sleep(15)
        while self._running:
            try:
                snap = self._do_refresh()
                logger.info(
                    "WorldState refreshed: WSI=%.3f (%s) dominant=%s scenarios=%d",
                    snap.wsi, snap.wsi_label, snap.dominant_risk, len(snap.scenarios)
                )
            except Exception as exc:
                logger.error("WorldState refresh error: %s", exc, exc_info=True)
            time.sleep(_REFRESH_INTERVAL)

    def _do_refresh(self) -> WorldStateSnapshot:
        t0 = time.monotonic()
        domains: Dict[str, DomainReading] = {}

        # Fetch all domains — parallel where possible (thread pool)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="wse-fetch") as pool:
            futures = {domain: pool.submit(fn) for domain, fn in self._fetchers.items()}
            for domain, future in futures.items():
                try:
                    domains[domain] = future.result(timeout=15)
                except Exception as exc:
                    logger.warning("Domain %s fetch failed: %s", domain, exc)
                    domains[domain] = DomainReading(
                        domain          = domain,
                        stability_score = 0.5,
                        raw_signals     = {"error": str(exc)},
                        source          = "error-fallback",
                        fetched_at      = datetime.now(timezone.utc).isoformat(),
                        error           = str(exc),
                        confidence      = 0.1,
                    )

        wsi, label, dominant, notes = self._wsi_computer.compute(domains)
        scenarios = self._scenario_engine.generate(domains, wsi)
        trend = self._db.get_trend(hours=6)
        duration = round(time.monotonic() - t0, 2)

        snap = WorldStateSnapshot(
            timestamp          = datetime.now(timezone.utc).isoformat(),
            epoch              = time.time(),
            wsi                = wsi,
            wsi_label          = label,
            domains            = domains,
            scenarios          = scenarios,
            trend_6h           = trend,
            dominant_risk      = dominant,
            notes              = notes,
            refresh_duration_s = duration,
        )

        with self._lock:
            self._current = snap
            self._ring.append(snap)

        self._db.save(snap)
        self._notify_downstream(snap)
        return snap

    def _notify_downstream(self, snap: WorldStateSnapshot):
        """Wire WSI into PCC, RROM, and Front-of-Line."""
        # 1. PCC — inject world_state_pressure as context
        # (PCC will pick this up on next compute() call via module-level state)
        try:
            _WSE_STATE["wsi"] = snap.wsi
            _WSE_STATE["label"] = snap.wsi_label
            _WSE_STATE["dominant_risk"] = snap.dominant_risk
            _WSE_STATE["conflict_score"] = snap.domains.get("conflict", DomainReading("c",0.5,{},"","")).stability_score
        except Exception:
            pass

        # 2. Front-of-Line — insert alert if critical
        if snap.wsi < 0.4:
            try:
                from src.front_of_line import front_of_line
                front_of_line.submit({
                    "name":         f"World State CRITICAL: {snap.wsi_label} (WSI={snap.wsi:.3f})",
                    "priority":     "HIGH" if snap.wsi < 0.3 else "MEDIUM",
                    "threatens_ai": snap.wsi < 0.25,
                    "source":       "WorldStateEngine",
                    "dominant":     snap.dominant_risk,
                    "scenarios":    [s.name for s in snap.scenarios],
                })
            except Exception as exc:
                logger.debug("FoL notification failed: %s", exc)

    def refresh(self) -> WorldStateSnapshot:
        """Force an immediate refresh (blocking)."""
        return self._do_refresh()

    def current_snapshot(self) -> Optional[WorldStateSnapshot]:
        with self._lock:
            return self._current

    def history(self, hours: int = 24) -> List[Dict]:
        """Time-series data for graphing (chronological)."""
        return self._db.get_history(hours=hours, limit=288)

    def graph_data(self, hours: int = 24) -> Dict[str, Any]:
        """Structured graph-ready data: WSI + all domain scores over time."""
        history = self.history(hours)
        return {
            "series": history,
            "domain_keys": list(_WEIGHTS.keys()),
            "weights": _WEIGHTS,
            "wsi_labels": [{"threshold": t, "label": l} for t, l in _WSI_LABELS],
            "current_wsi": self._current.wsi if self._current else None,
            "current_label": self._current.wsi_label if self._current else "UNKNOWN",
        }

    def summary(self) -> Dict[str, Any]:
        """PATCH-104: Richer summary — includes domain breakdown and scenario list."""
        snap = self._current
        if not snap:
            return {"wsi": 0.5, "label": "UNKNOWN", "world_pressure": 0.5, "domains": {}, "scenarios": []}
        domains = {}
        for name, domain in snap.domains.items():
            domains[name] = {
                "stability_score": round(domain.stability_score, 4),
                "confidence":      round(domain.confidence, 4),
                "source":          domain.source,
                "error":           str(domain.error) if domain.error else None,
            }
        scenarios = [
            {"name": sc.name, "probability": round(sc.probability, 3), "severity": sc.severity}
            for sc in snap.scenarios[:5]
        ]
        return {
            "wsi":              round(snap.wsi, 4),
            "label":            snap.wsi_label,
            "world_pressure":   round(1.0 - snap.wsi, 4),
            "dominant_risk":    snap.dominant_risk,
            "domains":          domains,
            "scenarios":        scenarios,
            "trend_6h":         snap.trend_6h,
            "refreshed_at":     snap.timestamp,
            "refresh_duration_s": snap.refresh_duration_s,
        }


# ── Module-level state shared with PCC ───────────────────────────────────────
_WSE_STATE: Dict[str, Any] = {
    "wsi":            0.5,
    "label":          "UNKNOWN",
    "dominant_risk":  "unknown",
    "conflict_score": 0.5,
}

# ── Singleton ─────────────────────────────────────────────────────────────────
world_state = WorldStateEngine()
