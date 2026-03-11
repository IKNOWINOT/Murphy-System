#!/usr/bin/env python3
"""
PHASE 1: Health checks, telemetry baseline, system introspection.
Screenshot every response. Log to telemetry_log.jsonl.

FILES TESTED:
  - Murphy System/src/runtime/app.py         → /api/health, /api/status, /api/info
  - Murphy System/src/runtime/murphy_system_core.py → MurphySystem class
  - Murphy System/src/config.py               → Pydantic BaseSettings
"""

import json
import os
import sys
import datetime
import traceback

# Allow running standalone or via pytest
try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EVIDENCE_DIR = os.path.join(SCRIPT_DIR, "03_health")
LOG_FILE = os.path.join(SCRIPT_DIR, "telemetry_log.jsonl")
BASE_URL = os.environ.get("MURPHY_BASE_URL", "http://localhost:8000")


def timestamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def log_event(phase, step, status, detail=""):
    entry = {
        "ts": timestamp(),
        "phase": phase,
        "step": step,
        "status": status,
        "detail": detail,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def save_evidence(filename, content):
    filepath = os.path.join(EVIDENCE_DIR, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        if isinstance(content, (dict, list)):
            json.dump(content, f, indent=2, default=str)
        else:
            f.write(str(content))
    return filepath


# ── Health Endpoint Tests ─────────────────────────────────────

HEALTH_ENDPOINTS = [
    ("/api/health", "health_check"),
    ("/api/status", "system_status"),
    ("/api/info", "system_info"),
    ("/api/system/info", "system_info_alt"),
    ("/api/readiness", "readiness_probe"),
    ("/api/config", "config_endpoint"),
]


def test_health_endpoints():
    """Test all health-related endpoints and capture responses."""
    results = []
    for path, label in HEALTH_ENDPOINTS:
        url = f"{BASE_URL}{path}"
        try:
            resp = requests.get(url, timeout=10)
            result = {
                "endpoint": path,
                "label": label,
                "status_code": resp.status_code,
                "response_time_ms": resp.elapsed.total_seconds() * 1000,
                "body": resp.json() if resp.headers.get(
                    "content-type", ""
                ).startswith("application/json") else resp.text[:500],
            }
            passed = resp.status_code == 200
            result["passed"] = passed
            results.append(result)

            save_evidence(f"{label}_response.json", result)
            log_event(
                "phase1",
                f"health_{label}",
                "pass" if passed else "fail",
                f"HTTP {resp.status_code} in {result['response_time_ms']:.0f}ms",
            )
        except requests.exceptions.ConnectionError:
            result = {
                "endpoint": path,
                "label": label,
                "status_code": None,
                "error": "Connection refused — server not running?",
                "passed": False,
            }
            results.append(result)
            save_evidence(f"{label}_error.json", result)
            log_event("phase1", f"health_{label}", "fail", "Connection refused")
        except Exception as exc:
            result = {
                "endpoint": path,
                "label": label,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "passed": False,
            }
            results.append(result)
            save_evidence(f"{label}_error.json", result)
            log_event("phase1", f"health_{label}", "fail", str(exc))

    return results


# ── Telemetry Baseline ────────────────────────────────────────


def test_telemetry_baseline():
    """Capture telemetry and flow state as baseline."""
    telemetry_endpoints = [
        ("/api/telemetry", "telemetry_snapshot"),
        ("/api/flows/state", "flow_state"),
        ("/api/llm/status", "llm_status"),
        ("/api/learning/status", "learning_status"),
    ]
    results = []
    for path, label in telemetry_endpoints:
        url = f"{BASE_URL}{path}"
        try:
            resp = requests.get(url, timeout=10)
            result = {
                "endpoint": path,
                "label": label,
                "status_code": resp.status_code,
                "passed": resp.status_code == 200,
            }
            if resp.status_code == 200:
                try:
                    result["body"] = resp.json()
                except ValueError:
                    result["body"] = resp.text[:500]
            results.append(result)
            save_evidence(f"baseline_{label}.json", result)
            log_event(
                "phase1",
                f"baseline_{label}",
                "pass" if result["passed"] else "fail",
                f"HTTP {resp.status_code}",
            )
        except Exception as exc:
            result = {
                "endpoint": path,
                "label": label,
                "error": str(exc),
                "passed": False,
            }
            results.append(result)
            log_event("phase1", f"baseline_{label}", "fail", str(exc))

    return results


# ── Module Introspection ──────────────────────────────────────


def test_module_introspection():
    """Check system module listing and status."""
    url = f"{BASE_URL}/api/modules"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            save_evidence("modules_list.json", data)
            log_event(
                "phase1",
                "modules_list",
                "pass",
                f"{len(data) if isinstance(data, list) else 'N/A'} modules",
            )
            return {"passed": True, "module_count": len(data) if isinstance(data, list) else 0}
        else:
            log_event("phase1", "modules_list", "fail", f"HTTP {resp.status_code}")
            return {"passed": False, "status_code": resp.status_code}
    except Exception as exc:
        log_event("phase1", "modules_list", "fail", str(exc))
        return {"passed": False, "error": str(exc)}


# ── Main Runner ───────────────────────────────────────────────


def run_phase1():
    """Execute all Phase 1 tests and return summary."""
    print("=" * 60)
    print(" PHASE 1: Health & Telemetry Baseline")
    print(f" {timestamp()}")
    print("=" * 60)
    print()

    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    # Test 1: Health endpoints
    print("→ Testing health endpoints...")
    health_results = test_health_endpoints()
    passed = sum(1 for r in health_results if r.get("passed"))
    total = len(health_results)
    print(f"  Health endpoints: {passed}/{total} passed")
    print()

    # Test 2: Telemetry baseline
    print("→ Capturing telemetry baseline...")
    baseline_results = test_telemetry_baseline()
    b_passed = sum(1 for r in baseline_results if r.get("passed"))
    b_total = len(baseline_results)
    print(f"  Telemetry baseline: {b_passed}/{b_total} passed")
    print()

    # Test 3: Module introspection
    print("→ Checking module introspection...")
    module_result = test_module_introspection()
    print(f"  Module list: {'✓' if module_result.get('passed') else '✗'}")
    print()

    # Summary
    summary = {
        "phase": "phase1",
        "timestamp": timestamp(),
        "health": {"passed": passed, "total": total},
        "baseline": {"passed": b_passed, "total": b_total},
        "modules": module_result,
    }
    save_evidence("phase1_summary.json", summary)

    total_tests = total + b_total + 1
    total_passed = passed + b_passed + (1 if module_result.get("passed") else 0)
    print("=" * 60)
    print(f" PHASE 1 COMPLETE: {total_passed}/{total_tests} tests passed")
    print("=" * 60)

    return summary


if __name__ == "__main__":
    run_phase1()
