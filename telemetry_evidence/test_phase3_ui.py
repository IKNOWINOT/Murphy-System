#!/usr/bin/env python3
"""
PHASE 3: Test all web interfaces by loading them and checking HTTP 200.

FILES TESTED:
  - Murphy System/murphy_landing_page.html         → Public front door
  - Murphy System/onboarding_wizard.html            → New user onboarding
  - Murphy System/murphy_ui_integrated.html         → Integrated UI
  - Murphy System/murphy_ui_integrated_terminal.html→ Integrated terminal
  - Murphy System/terminal_unified.html             → Unified terminal
  - Murphy System/terminal_enhanced.html            → Enhanced terminal
  - Murphy System/terminal_integrated.html          → Integrated terminal view
  - Murphy System/terminal_architect.html           → Architect terminal
  - Murphy System/terminal_costs.html               → Cost terminal
  - Murphy System/terminal_integrations.html        → Integrations terminal
  - Murphy System/terminal_orchestrator.html        → Orchestrator terminal
  - Murphy System/terminal_orgchart.html            → Org chart terminal
  - Murphy System/terminal_worker.html              → Worker terminal
  - Murphy System/workflow_canvas.html              → Workflow canvas
  - Murphy System/system_visualizer.html            → System visualizer
  - Murphy System/murphy-smoke-test.html            → Smoke test page
"""

import json
import os
import sys
import datetime

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EVIDENCE_DIR = os.path.join(SCRIPT_DIR, "17_ui_interfaces")
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


# ── UI Interface Definitions ──────────────────────────────────

# HTML files served as static content or via dedicated routes
UI_INTERFACES = [
    ("murphy_landing_page.html", "landing_page", "Public landing page"),
    ("onboarding_wizard.html", "onboarding_wizard", "Onboarding wizard"),
    ("murphy_ui_integrated.html", "ui_integrated", "Integrated UI"),
    ("murphy_ui_integrated_terminal.html", "ui_integrated_terminal", "Integrated terminal"),
    ("terminal_unified.html", "terminal_unified", "Unified terminal"),
    ("terminal_enhanced.html", "terminal_enhanced", "Enhanced terminal"),
    ("terminal_integrated.html", "terminal_integrated", "Integrated terminal view"),
    ("terminal_architect.html", "terminal_architect", "Architect terminal"),
    ("terminal_costs.html", "terminal_costs", "Cost management terminal"),
    ("terminal_integrations.html", "terminal_integrations", "Integrations terminal"),
    ("terminal_orchestrator.html", "terminal_orchestrator", "Orchestrator terminal"),
    ("terminal_orgchart.html", "terminal_orgchart", "Org chart terminal"),
    ("terminal_worker.html", "terminal_worker", "Worker terminal"),
    ("workflow_canvas.html", "workflow_canvas", "Workflow canvas"),
    ("system_visualizer.html", "system_visualizer", "System visualizer"),
    ("murphy-smoke-test.html", "smoke_test", "Smoke test page"),
]


def test_ui_file_exists():
    """Verify all UI HTML files exist on disk."""
    repo_root = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
    murphy_dir = os.path.join(repo_root, "Murphy System")
    results = []

    for filename, label, description in UI_INTERFACES:
        filepath = os.path.join(murphy_dir, filename)
        exists = os.path.isfile(filepath)
        size = os.path.getsize(filepath) if exists else 0
        result = {
            "file": filename,
            "label": label,
            "description": description,
            "exists": exists,
            "size_bytes": size,
            "passed": exists and size > 0,
        }
        results.append(result)

        # Check for design system and accessibility markers
        if exists:
            with open(filepath, "r", errors="replace") as f:
                content = f.read()
            result["has_design_system_css"] = "murphy-design-system.css" in content
            result["has_components_js"] = "murphy-components.js" in content
            result["has_skip_link"] = "skip" in content.lower()
            result["has_bsl_header"] = "BSL" in content or "license" in content.lower()

        save_evidence(f"file_{label}.json", result)
        status = "pass" if result["passed"] else "fail"
        log_event("phase3", f"file_{label}", status, f"exists={exists}, size={size}")

    return results


def test_ui_http_access():
    """Test HTTP access to UI files via the running server."""
    results = []

    for filename, label, description in UI_INTERFACES:
        # Try common serving paths
        paths_to_try = [
            f"/{filename}",
            f"/static/{filename}",
            f"/ui/{filename}",
        ]
        best_result = None

        for path in paths_to_try:
            url = f"{BASE_URL}{path}"
            try:
                resp = requests.get(url, timeout=10)
                result = {
                    "file": filename,
                    "label": label,
                    "url": url,
                    "status_code": resp.status_code,
                    "content_type": resp.headers.get("content-type", ""),
                    "response_time_ms": resp.elapsed.total_seconds() * 1000,
                    "content_length": len(resp.content),
                    "passed": resp.status_code == 200,
                }
                if result["passed"]:
                    best_result = result
                    break
                if best_result is None:
                    best_result = result
            except requests.exceptions.ConnectionError:
                if best_result is None:
                    best_result = {
                        "file": filename,
                        "label": label,
                        "url": url,
                        "error": "Connection refused",
                        "passed": False,
                    }
            except Exception as exc:
                if best_result is None:
                    best_result = {
                        "file": filename,
                        "label": label,
                        "url": url,
                        "error": str(exc),
                        "passed": False,
                    }

        results.append(best_result)
        save_evidence(f"http_{label}.json", best_result)
        status = "pass" if best_result.get("passed") else "fail"
        log_event(
            "phase3",
            f"http_{label}",
            status,
            f"HTTP {best_result.get('status_code', 'N/A')}",
        )

    return results


def test_static_assets():
    """Test that shared static assets are accessible."""
    assets = [
        ("/static/murphy-design-system.css", "design_system_css"),
        ("/static/murphy-components.js", "components_js"),
        ("/static/murphy-canvas.js", "canvas_js"),
        ("/static/murphy-icons.svg", "icons_svg"),
    ]
    results = []
    for path, label in assets:
        url = f"{BASE_URL}{path}"
        try:
            resp = requests.get(url, timeout=10)
            result = {
                "asset": path,
                "label": label,
                "status_code": resp.status_code,
                "content_type": resp.headers.get("content-type", ""),
                "size_bytes": len(resp.content),
                "passed": resp.status_code == 200,
            }
        except Exception as exc:
            result = {
                "asset": path,
                "label": label,
                "error": str(exc),
                "passed": False,
            }
        results.append(result)
        save_evidence(f"asset_{label}.json", result)
        log_event(
            "phase3",
            f"asset_{label}",
            "pass" if result.get("passed") else "fail",
            f"HTTP {result.get('status_code', 'N/A')}",
        )
    return results


def run_phase3():
    """Execute all Phase 3 tests and return summary."""
    print("=" * 60)
    print(" PHASE 3: UI Interface Testing")
    print(f" {timestamp()}")
    print("=" * 60)
    print()

    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    # Test 1: File existence
    print(f"→ Checking {len(UI_INTERFACES)} UI files on disk...")
    file_results = test_ui_file_exists()
    file_passed = sum(1 for r in file_results if r.get("passed"))
    print(f"  Files found: {file_passed}/{len(file_results)}")
    print()

    # Test 2: HTTP access
    print("→ Testing HTTP access to UI interfaces...")
    http_results = test_ui_http_access()
    http_passed = sum(1 for r in http_results if r.get("passed"))
    print(f"  HTTP accessible: {http_passed}/{len(http_results)}")
    print()

    # Test 3: Static assets
    print("→ Testing static asset access...")
    asset_results = test_static_assets()
    asset_passed = sum(1 for r in asset_results if r.get("passed"))
    print(f"  Assets accessible: {asset_passed}/{len(asset_results)}")
    print()

    summary = {
        "phase": "phase3",
        "timestamp": timestamp(),
        "file_checks": {"passed": file_passed, "total": len(file_results)},
        "http_access": {"passed": http_passed, "total": len(http_results)},
        "static_assets": {"passed": asset_passed, "total": len(asset_results)},
    }
    save_evidence("phase3_summary.json", summary)

    total = len(file_results) + len(http_results) + len(asset_results)
    total_passed = file_passed + http_passed + asset_passed
    print("=" * 60)
    print(f" PHASE 3 COMPLETE: {total_passed}/{total} checks passed")
    print("=" * 60)

    return summary


if __name__ == "__main__":
    run_phase3()
