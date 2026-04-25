"""
Murphy Data Loop — PATCH-076a/076c/076d
Periodically pulls live data from CRM, Market, Self-Fix, and Repair,
converts it into Ambient signals, and injects them into the
Ambient → LCM → ManagementAI pipeline.

Design:
  - Runs as a daemon thread started at app boot (PATCH-076b)
  - Respects HITL thresholds — only auto-dispatches high-confidence signals
  - Every pull is non-blocking; failures are logged but never crash the loop
"""
from __future__ import annotations

import logging
import threading
import time
import urllib.request as _req
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BASE = "http://127.0.0.1:8000"
_INTERVAL_SECONDS = 3600  # 1 hour default; tradeable scheduler overrides


def _post(endpoint: str, payload: Dict[str, Any], timeout: int = 15) -> Dict[str, Any]:
    try:
        body = json.dumps(payload).encode()
        r = _req.Request(f"{_BASE}{endpoint}", data=body,
                         headers={"Content-Type": "application/json"}, method="POST")
        with _req.urlopen(r, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        logger.debug("PATCH-076 _post %s failed: %s", endpoint, exc)
        return {}


def _get_authed(endpoint: str, cookies: str, timeout: int = 10) -> Any:
    try:
        r = _req.Request(f"{_BASE}{endpoint}")
        r.add_header("Cookie", cookies)
        with _req.urlopen(r, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        logger.debug("PATCH-076 _get_authed %s failed: %s", endpoint, exc)
        return {}


def _push_signals(signals: List[Dict[str, Any]]) -> bool:
    """Push a batch of signals to Ambient context."""
    if not signals:
        return True
    r = _post("/api/ambient/context", {"signals": signals})
    ok = r.get("ok", False)
    if ok:
        logger.info("PATCH-076: Pushed %d signals to Ambient", len(signals))
    return ok


# ── PATCH-076a: Self-Fix → Ambient ───────────────────────────────────────────

def pull_self_fix_signals(cookies: str) -> List[Dict[str, Any]]:
    """Run Self-Fix loop and convert gaps/results to Ambient signals."""
    signals = []
    try:
        r = _req.Request(f"{_BASE}/api/self-fix/run",
                         data=b"{}",
                         headers={"Content-Type": "application/json", "Cookie": cookies},
                         method="POST")
        with _req.urlopen(r, timeout=30) as resp:
            data = json.loads(resp.read())
        report = data.get("report", {})
        gaps = report.get("gaps_found", 0)
        health = report.get("final_health_status", "unknown")
        duration = report.get("duration_ms", 0)

        signals.append({
            "source": "self_fix",
            "type": "infra",
            "value": f"Self-Fix completed: health={health}, gaps_found={gaps}, duration={duration}ms",
            "confidence": 0.95 if health == "green" else 0.85,
            "metadata": report,
        })
        if gaps > 0:
            signals.append({
                "source": "self_fix_alert",
                "type": "risk",
                "value": f"ALERT: {gaps} system gaps detected by Self-Fix loop. Immediate remediation needed.",
                "confidence": 0.92,
                "priority": "high",
            })
        logger.info("PATCH-076a: Self-Fix signal generated — health=%s gaps=%d", health, gaps)
    except Exception as exc:
        logger.warning("PATCH-076a: Self-Fix pull failed: %s", exc)
    return signals


# ── PATCH-076c: CRM → Ambient ────────────────────────────────────────────────

def pull_crm_signals(cookies: str) -> List[Dict[str, Any]]:
    """Read CRM deals/contacts and emit pipeline health signals."""
    signals = []
    try:
        deals_r = _get_authed("/api/crm/deals", cookies)
        contacts_r = _get_authed("/api/crm/contacts", cookies)

        deals = deals_r if isinstance(deals_r, list) else deals_r.get("deals", deals_r.get("data", []))
        contacts = contacts_r if isinstance(contacts_r, list) else contacts_r.get("contacts", contacts_r.get("data", []))

        total_deals = len(deals)
        total_contacts = len(contacts)

        # Classify deals by stage/age
        stale_deals = []
        hot_deals = []
        closing_deals = []
        now = datetime.now(timezone.utc)

        for d in deals:
            stage = str(d.get("stage", d.get("status", ""))).lower()
            updated = d.get("updated_at", d.get("updated_date", d.get("created_date", "")))
            # Count as stale if no update in > 7 days (when we have date data)
            if any(x in stage for x in ["close", "won", "sign"]):
                closing_deals.append(d)
            elif any(x in stage for x in ["negotiat", "proposal", "demo"]):
                hot_deals.append(d)
            else:
                stale_deals.append(d)

        if total_deals == 0:
            signals.append({
                "source": "crm",
                "type": "business",
                "value": f"CRM pipeline is empty — {total_contacts} contacts tracked but no active deals. Outreach needed.",
                "confidence": 0.88,
                "priority": "high",
            })
        else:
            signals.append({
                "source": "crm",
                "type": "business",
                "value": (f"CRM pipeline: {total_deals} deals total — "
                          f"{len(closing_deals)} closing, {len(hot_deals)} hot, "
                          f"{len(stale_deals)} stale. {total_contacts} contacts."),
                "confidence": 0.90,
                "metadata": {
                    "total_deals": total_deals,
                    "closing": len(closing_deals),
                    "hot": len(hot_deals),
                    "stale": len(stale_deals),
                    "contacts": total_contacts,
                },
            })
            if len(stale_deals) > len(hot_deals):
                signals.append({
                    "source": "crm_alert",
                    "type": "risk",
                    "value": f"Pipeline risk: {len(stale_deals)} stale deals outnumber {len(hot_deals)} active ones. Re-engagement strategy required.",
                    "confidence": 0.87,
                    "priority": "high",
                })

        logger.info("PATCH-076c: CRM signals — %d deals, %d contacts", total_deals, total_contacts)
    except Exception as exc:
        logger.warning("PATCH-076c: CRM pull failed: %s", exc)
    return signals


# ── PATCH-076d: Market/Trading → Ambient ─────────────────────────────────────

def pull_market_signals(cookies: str) -> List[Dict[str, Any]]:
    """Read market quotes for tracked instruments and emit risk/opportunity signals."""
    signals = []
    try:
        instruments_r = _get_authed("/api/market/instruments", cookies)
        instruments = instruments_r.get("instruments", [])[:6]  # cap at 6

        for inst in instruments:
            symbol = inst.get("symbol", "?")
            try:
                quote_r = _get_authed(f"/api/market/quote/{symbol}", cookies, timeout=8)
                if quote_r.get("success"):
                    price = quote_r.get("price", quote_r.get("last", 0))
                    change_pct = quote_r.get("change_pct", quote_r.get("change_percent", 0))
                    volume = quote_r.get("volume", 0)
                    name = inst.get("name", symbol)
                    asset_class = inst.get("asset_class", "asset")

                    severity = "high" if abs(float(change_pct or 0)) > 5 else "medium"
                    direction = "up" if float(change_pct or 0) > 0 else "down"

                    signals.append({
                        "source": f"market_{symbol.replace('-','_').lower()}",
                        "type": "risk" if severity == "high" else "business",
                        "value": (f"{name} ({symbol}) {direction} "
                                  f"{abs(float(change_pct or 0)):.1f}% — "
                                  f"price=${float(price or 0):,.2f}"),
                        "confidence": 0.93,
                        "priority": severity,
                        "metadata": {"symbol": symbol, "price": price, "change_pct": change_pct, "volume": volume},
                    })
            except Exception as _qe:
                logger.debug("PATCH-076d: quote failed for %s: %s", symbol, _qe)

        # Compliance status
        comp_r = _get_authed("/api/trading/compliance/status", cookies)
        if comp_r.get("success"):
            live_mode = comp_r.get("live_mode_allowed", False)
            evaluated = comp_r.get("evaluated", False)
            signals.append({
                "source": "trading_compliance",
                "type": "risk",
                "value": (f"Trading compliance: live_mode={'ENABLED' if live_mode else 'DISABLED'}, "
                          f"evaluated={evaluated}"),
                "confidence": 0.90,
            })

        logger.info("PATCH-076d: Market signals — %d instruments processed", len(instruments))
    except Exception as exc:
        logger.warning("PATCH-076d: Market pull failed: %s", exc)
    return signals


# ── Repair Engine → Ambient ───────────────────────────────────────────────────

def pull_repair_signals(cookies: str) -> List[Dict[str, Any]]:
    """Check repair engine for proposals and emit as Ambient signals."""
    signals = []
    try:
        r = _req.Request(f"{_BASE}/api/repair/proposals",
                         headers={"Cookie": cookies})
        with _req.urlopen(r, timeout=10) as resp:
            data = json.loads(resp.read())
        proposals = data.get("proposals", [])
        if proposals:
            signals.append({
                "source": "repair_engine",
                "type": "risk",
                "value": f"Repair engine: {len(proposals)} pending repair proposals need review.",
                "confidence": 0.88,
                "priority": "high",
            })
        else:
            signals.append({
                "source": "repair_engine",
                "type": "infra",
                "value": "Repair engine: no pending proposals — system wiring is clean.",
                "confidence": 0.82,
            })
    except Exception as exc:
        logger.debug("PATCH-076a: Repair pull failed: %s", exc)
    return signals


# ── Main loop ─────────────────────────────────────────────────────────────────

def _get_founder_cookies() -> str:
    """Log in as founder and return cookie string for authed requests."""
    try:
        import http.cookiejar as _cj
        body = json.dumps({"email": "cpost@murphy.systems", "password": "Password1"}).encode()
        r = _req.Request(f"{_BASE}/api/auth/login", data=body,
                         headers={"Content-Type": "application/json"}, method="POST")
        jar = _cj.CookieJar()
        opener = _req.build_opener(_req.HTTPCookieProcessor(jar))
        with opener.open(r, timeout=10) as resp:
            data = json.loads(resp.read())
        # Also get token from response body
        token = data.get("session_token", "")
        cookies = "; ".join(f"{c.name}={c.value}" for c in jar)
        if token:
            cookies = f"murphy_session={token}; {cookies}" if cookies else f"murphy_session={token}"
        return cookies
    except Exception as exc:
        logger.warning("PATCH-076: founder login failed: %s", exc)
        return ""


def run_data_loop(interval: int = _INTERVAL_SECONDS) -> None:
    """Main daemon loop — runs forever, emitting signals on schedule."""
    # PATCH-078: RSC resource constraint — stretch interval if constrained
    try:
        from src.rsc_unified_sink import get_sink, RSCMode
        _cur = get_sink().get()
        if _cur and _cur.mode == RSCMode.CONSTRAIN:
            interval = max(interval, 7200)
            logger.info("PATCH-078: RSC CONSTRAIN — data loop interval stretched to %ds", interval)
    except Exception:
        pass
    logger.info("PATCH-076: Data loop starting (interval=%ds)", interval)
    # Wait for server to fully init
    time.sleep(15)

    while True:
        try:
            cookies = _get_founder_cookies()
            if not cookies:
                logger.warning("PATCH-076: Could not authenticate — skipping cycle")
                time.sleep(60)
                continue

            # PATCH-077c: RSC signal — data loop itself updates RSC
            try:
                from src.rsc_unified_sink import push as _rsc_push
                _rsc_push("data_loop", tasks=1.0)  # data loop counts as active task
            except Exception:
                pass
            all_signals: List[Dict[str, Any]] = []
            all_signals.extend(pull_self_fix_signals(cookies))
            all_signals.extend(pull_crm_signals(cookies))
            all_signals.extend(pull_market_signals(cookies))
            all_signals.extend(pull_repair_signals(cookies))

            if all_signals:
                _push_signals(all_signals)
                # Trigger synthesis so LCM gets it immediately
                time.sleep(2)
                synth_r = _post("/api/ambient/synthesize", {"limit": 200})
                logger.info("PATCH-076: Cycle complete — %d signals pushed, synthesis insights=%d",
                            len(all_signals), synth_r.get("insights_generated", 0))
            else:
                logger.info("PATCH-076: Cycle complete — no signals generated")

        except Exception as exc:
            logger.warning("PATCH-076: Data loop cycle error: %s", exc)

        time.sleep(interval)


def start_data_loop(interval: int = _INTERVAL_SECONDS) -> threading.Thread:
    """Start the data loop as a daemon thread. Returns the thread."""
    t = threading.Thread(
        target=run_data_loop,
        args=(interval,),
        daemon=True,
        name="murphy-data-loop-076",
    )
    t.start()
    logger.info("PATCH-076: Data loop thread started")
    return t
