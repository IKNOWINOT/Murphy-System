"""
PAGE WIRING PROBE — created 2026-06-04
=====================================================
Walks every HTML page Murphy serves, extracts each /api/* endpoint
the page references, and probes whether the endpoint actually
responds. Catches the "shipped HTML without backend" pattern.

Result codes:
  ✅ WIRED     — 200, 3xx, 401, 403, 405 (endpoint exists)
  ❌ BROKEN    — 404 (endpoint doesn't exist)
  ⚠ ERROR     — 5xx (endpoint exists but crashing)
  ⏱ UNREACHED — 000 (timeout / connection refused)

Usage:
  from page_wiring_probe import run_probe
  report = run_probe()  # returns dict
"""
from __future__ import annotations
import json, os, re, time, glob, urllib.request, urllib.error
from typing import Dict, List
from datetime import datetime, timezone

ROOT          = "/opt/Murphy-System"
STATIC_DIR    = f"{ROOT}/static"
REPORT_PATH   = "/var/lib/murphy-production/page_wiring_report.json"
LOCAL_BASE    = "http://127.0.0.1:8000"
PROBE_TIMEOUT = 4
CACHE_TTL_SEC = 300

# Pages outside static/ that the monolith serves via FileResponse
TOP_LEVEL_PAGES = [
    "tenant_control.html", "tenant_home.html", "tenant_assistant_template.html",
    "founder.html", "pricing.html",
]

API_REGEX = re.compile(r"""['"](/api/[A-Za-z0-9_/\{\}\.\-]+)['"]""")

# Classify pages by audience so we can flag tenant breakage more loudly
def _classify(path: str) -> str:
    p = path.lower()
    if "tenant" in p:                                       return "tenant"
    if "customer" in p or "checkout" in p or "pricing" in p: return "customer"
    if "founder" in p or "control" in p or "patcher" in p:  return "founder"
    if "hitl" in p or "murphy-os" in p:                     return "operator"
    return "other"

def _collect_pages() -> List[str]:
    pages = sorted(glob.glob(f"{STATIC_DIR}/*.html"))
    for name in TOP_LEVEL_PAGES:
        full = os.path.join(ROOT, name)
        if os.path.exists(full):
            pages.append(full)
    return pages

def _extract_endpoints(html_path: str) -> List[str]:
    try:
        with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
            body = f.read()
    except Exception:
        return []
    return sorted(set(API_REGEX.findall(body)))

def _normalize_for_probe(ep: str) -> str:
    """Replace {path_params} with safe defaults so we can probe."""
    return re.sub(r"\{[^}]+\}", "_probe_", ep).rstrip("/")

def _probe(endpoint: str) -> Dict:
    url = LOCAL_BASE + _normalize_for_probe(endpoint)
    req = urllib.request.Request(url, headers={"User-Agent": "MurphyPageWiringProbe/1.0"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception:
        code = 0
    elapsed_ms = int((time.time() - t0) * 1000)
    if code == 0:
        verdict = "UNREACHED"
    elif code == 404:
        verdict = "BROKEN"
    elif 500 <= code < 600:
        verdict = "ERROR"
    else:
        verdict = "WIRED"
    return {"endpoint": endpoint, "probe_url": url, "code": code,
            "verdict": verdict, "ms": elapsed_ms}

def run_probe(force: bool = False) -> Dict:
    # Pre-flight: is the monolith even up? If not, do not pretend GREEN.
    try:
        with urllib.request.urlopen(LOCAL_BASE + "/api/health", timeout=3) as r:
            monolith_up = (200 <= r.status < 500)
    except Exception:
        monolith_up = False
    if not monolith_up:
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "ok": False,
            "monolith_up": False,
            "reason": "monolith_not_responding_on_localhost_8000",
            "shape_pillar": {"name": "B.PAGE_WIRING", "green": False,
                             "reason": "monolith down — cannot probe"},
        }
    # Respect cache unless force=True
    if not force and os.path.exists(REPORT_PATH):
        try:
            with open(REPORT_PATH) as f:
                cached = json.load(f)
            age = time.time() - cached.get("ts_epoch", 0)
            if age < CACHE_TTL_SEC:
                cached["from_cache"] = True
                return cached
        except Exception:
            pass

    pages = _collect_pages()
    results = []
    endpoint_cache: Dict[str, Dict] = {}

    for page in pages:
        eps = _extract_endpoints(page)
        page_rec = {
            "page":        os.path.relpath(page, ROOT),
            "audience":    _classify(page),
            "n_endpoints": len(eps),
            "endpoints":   [],
            "wired":       0,
            "broken":      0,
            "error":       0,
            "unreached":   0,
        }
        for ep in eps:
            if ep not in endpoint_cache:
                endpoint_cache[ep] = _probe(ep)
            probe = endpoint_cache[ep]
            page_rec["endpoints"].append(probe)
            v = probe["verdict"]
            if   v == "WIRED":     page_rec["wired"] += 1
            elif v == "BROKEN":    page_rec["broken"] += 1
            elif v == "ERROR":     page_rec["error"] += 1
            else:                  page_rec["unreached"] += 1
        page_rec["status"] = (
            "GREEN" if page_rec["broken"] == 0 and page_rec["error"] == 0
            else "RED"
        )
        results.append(page_rec)

    # Aggregate
    by_audience: Dict[str, Dict] = {}
    for r in results:
        a = r["audience"]
        b = by_audience.setdefault(a, {"pages": 0, "green": 0, "red": 0, "broken_endpoints": 0})
        b["pages"]  += 1
        b["green"]  += 1 if r["status"] == "GREEN" else 0
        b["red"]    += 1 if r["status"] == "RED"   else 0
        b["broken_endpoints"] += r["broken"]

    total_broken = sum(r["broken"] for r in results)
    total_error  = sum(r["error"]  for r in results)
    total_pages_red = sum(1 for r in results if r["status"] == "RED")

    # SHAPE_VERIFIER pillar evaluation
    tenant_red    = by_audience.get("tenant",   {}).get("red", 0)
    customer_red  = by_audience.get("customer", {}).get("red", 0)
    pillar_green = (tenant_red == 0 and customer_red == 0)

    out = {
        "ts":               datetime.now(timezone.utc).isoformat(),
        "ts_epoch":         time.time(),
        "ok":               True,
        "from_cache":       False,
        "pages_total":      len(results),
        "pages_red":        total_pages_red,
        "broken_endpoints": total_broken,
        "error_endpoints":  total_error,
        "by_audience":      by_audience,
        "results":          results,
        "shape_pillar": {
            "name":  "B.PAGE_WIRING",
            "green": pillar_green,
            "reason": ("all customer + tenant pages have working endpoints"
                       if pillar_green
                       else f"tenant_red={tenant_red} customer_red={customer_red}"),
        },
    }
    try:
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w") as f:
            json.dump(out, f, indent=2)
    except Exception as e:
        out["save_error"] = str(e)
    return out

if __name__ == "__main__":
    import sys
    report = run_probe(force=True)
    print(json.dumps({
        "pages_total":      report["pages_total"],
        "pages_red":        report["pages_red"],
        "broken_endpoints": report["broken_endpoints"],
        "by_audience":      report["by_audience"],
        "pillar":           report["shape_pillar"],
    }, indent=2))
    sys.exit(0 if report["shape_pillar"]["green"] else 2)
