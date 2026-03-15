#!/usr/bin/env python3
"""
PHASE 2: Exercise every documented API endpoint as a user would.

FILES TESTED:
  - src/runtime/app.py              → all route handlers
  - src/form_intake/handlers.py      → /api/forms/*
  - src/runtime/murphy_system_core.py → core business logic
"""

import json
import os
import sys
import datetime
import traceback

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EVIDENCE_DIR = os.path.join(SCRIPT_DIR, "04_api_core")
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


# ── API Endpoint Definitions ──────────────────────────────────

# GET endpoints — read-only, safe to call without payload
GET_ENDPOINTS = [
    # Core system
    ("/api/health", "core_health"),
    ("/api/status", "core_status"),
    ("/api/info", "core_info"),
    ("/api/config", "core_config"),
    # Agents
    ("/api/agents", "agents_list"),
    ("/api/agent-dashboard/agents", "agent_dashboard_list"),
    ("/api/agent-dashboard/snapshot", "agent_dashboard_snapshot"),
    # Documents
    ("/api/deliverables", "deliverables_list"),
    # Forms
    ("/api/corrections/patterns", "corrections_patterns"),
    ("/api/corrections/statistics", "corrections_statistics"),
    ("/api/corrections/training-data", "corrections_training_data"),
    # HITL
    ("/api/hitl/interventions/pending", "hitl_pending"),
    ("/api/hitl/statistics", "hitl_statistics"),
    # Integrations
    ("/api/integrations", "integrations_list"),
    ("/api/integrations/active", "integrations_active"),
    # LLM
    ("/api/llm/status", "llm_status"),
    # Librarian
    ("/api/librarian/status", "librarian_status"),
    ("/api/librarian/api-links", "librarian_api_links"),
    # Modules
    ("/api/modules", "modules_list"),
    # Onboarding
    ("/api/onboarding/wizard/questions", "onboarding_questions"),
    ("/api/onboarding/employees", "onboarding_employees"),
    ("/api/onboarding/status", "onboarding_status"),
    # Universal integrations
    ("/api/universal-integrations/services", "ui_services"),
    ("/api/universal-integrations/categories", "ui_categories"),
    ("/api/universal-integrations/stats", "ui_stats"),
    # Workflows
    ("/api/workflows", "workflows_list"),
    ("/api/tasks", "tasks_list"),
    # Workflow terminal
    ("/api/workflow-terminal/sessions", "terminal_sessions"),
    # Profiles
    ("/api/profiles", "profiles_list"),
    # Readiness
    ("/api/readiness", "readiness"),
    ("/api/test-mode/status", "test_mode_status"),
    ("/api/learning/status", "learning_status"),
    # Flows
    ("/api/flows/inbound", "flows_inbound"),
    ("/api/flows/processing", "flows_processing"),
    ("/api/flows/outbound", "flows_outbound"),
    ("/api/flows/state", "flows_state"),
    # MFM
    ("/api/mfm/status", "mfm_status"),
    ("/api/mfm/metrics", "mfm_metrics"),
    ("/api/mfm/versions", "mfm_versions"),
    # Costs
    ("/api/costs/summary", "costs_summary"),
    ("/api/costs/by-bot", "costs_by_bot"),
    ("/api/costs/by-department", "costs_by_department"),
    ("/api/costs/by-project", "costs_by_project"),
    # Credentials
    ("/api/credentials/metrics", "credentials_metrics"),
    ("/api/credentials/profiles", "credentials_profiles"),
    # Graph & IP
    ("/api/graph/health", "graph_health"),
    ("/api/ip/summary", "ip_summary"),
    ("/api/ip/assets", "ip_assets"),
    ("/api/ip/trade-secrets", "ip_trade_secrets"),
    # Org chart
    ("/api/orgchart/live", "orgchart_live"),
    # Orchestrator
    ("/api/orchestrator/flows", "orchestrator_flows"),
    ("/api/orchestrator/overview", "orchestrator_overview"),
    # Production & telemetry
    ("/api/production/queue", "production_queue"),
    ("/api/telemetry", "telemetry"),
    ("/api/ucp/health", "ucp_health"),
    # Images
    ("/api/images/styles", "images_styles"),
    ("/api/images/stats", "images_stats"),
    # UI links
    ("/api/ui/links", "ui_links"),
    # MFGC
    ("/api/mfgc/state", "mfgc_state"),
    ("/api/mfgc/config", "mfgc_config"),
    # Golden path
    ("/api/golden-path", "golden_path"),
    # Diagnostics
    ("/api/diagnostics/activation", "diagnostics_activation"),
    ("/api/diagnostics/activation/last", "diagnostics_activation_last"),
]

# POST endpoints — with minimal safe payloads
POST_ENDPOINTS = [
    ("/api/chat", {"message": "Hello Murphy"}, "chat_basic"),
    ("/api/execute", {"task": "test_echo", "input": "hello"}, "execute_echo"),
    ("/api/sessions/create", {}, "session_create"),
    ("/api/feedback", {"rating": 5, "comment": "telemetry test"}, "feedback"),
    ("/api/test-mode/toggle", {"enabled": True}, "test_mode_on"),
    (
        "/api/forms/validation",
        {"form_type": "task_execution", "data": {"task": "test"}},
        "form_validation",
    ),
    ("/api/librarian/ask", {"question": "What can Murphy do?"}, "librarian_ask"),
    ("/api/llm/test", {"prompt": "Say hello"}, "llm_test"),
    (
        "/api/mss/score",
        {"document": "Test document for scoring"},
        "mss_score",
    ),
    (
        "/api/graph/query",
        {"query": "list entities", "limit": 5},
        "graph_query",
    ),
]


def test_get_endpoints():
    """Exercise all GET endpoints and capture responses."""
    results = []
    for path, label in GET_ENDPOINTS:
        url = f"{BASE_URL}{path}"
        try:
            resp = requests.get(url, timeout=15)
            result = {
                "method": "GET",
                "endpoint": path,
                "label": label,
                "status_code": resp.status_code,
                "response_time_ms": resp.elapsed.total_seconds() * 1000,
                "passed": resp.status_code in (200, 201, 204),
            }
            try:
                result["body_preview"] = str(resp.json())[:200]
            except ValueError:
                result["body_preview"] = resp.text[:200]
            results.append(result)
            save_evidence(f"get_{label}.json", result)
            log_event(
                "phase2",
                f"get_{label}",
                "pass" if result["passed"] else "fail",
                f"HTTP {resp.status_code}",
            )
        except Exception as exc:
            result = {
                "method": "GET",
                "endpoint": path,
                "label": label,
                "error": str(exc),
                "passed": False,
            }
            results.append(result)
            save_evidence(f"get_{label}_error.json", result)
            log_event("phase2", f"get_{label}", "fail", str(exc))
    return results


def test_post_endpoints():
    """Exercise POST endpoints with minimal payloads."""
    results = []
    for path, payload, label in POST_ENDPOINTS:
        url = f"{BASE_URL}{path}"
        try:
            resp = requests.post(url, json=payload, timeout=15)
            result = {
                "method": "POST",
                "endpoint": path,
                "label": label,
                "payload": payload,
                "status_code": resp.status_code,
                "response_time_ms": resp.elapsed.total_seconds() * 1000,
                "passed": resp.status_code in (200, 201, 202, 204),
            }
            try:
                result["body_preview"] = str(resp.json())[:200]
            except ValueError:
                result["body_preview"] = resp.text[:200]
            results.append(result)
            save_evidence(f"post_{label}.json", result)
            log_event(
                "phase2",
                f"post_{label}",
                "pass" if result["passed"] else "fail",
                f"HTTP {resp.status_code}",
            )
        except Exception as exc:
            result = {
                "method": "POST",
                "endpoint": path,
                "label": label,
                "error": str(exc),
                "passed": False,
            }
            results.append(result)
            save_evidence(f"post_{label}_error.json", result)
            log_event("phase2", f"post_{label}", "fail", str(exc))
    return results


def run_phase2():
    """Execute all Phase 2 tests and return summary."""
    print("=" * 60)
    print(" PHASE 2: Core API Feature Sweep")
    print(f" {timestamp()}")
    print("=" * 60)
    print()

    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    # GET endpoints
    print(f"→ Testing {len(GET_ENDPOINTS)} GET endpoints...")
    get_results = test_get_endpoints()
    get_passed = sum(1 for r in get_results if r.get("passed"))
    print(f"  GET: {get_passed}/{len(get_results)} passed")
    print()

    # POST endpoints
    print(f"→ Testing {len(POST_ENDPOINTS)} POST endpoints...")
    post_results = test_post_endpoints()
    post_passed = sum(1 for r in post_results if r.get("passed"))
    print(f"  POST: {post_passed}/{len(post_results)} passed")
    print()

    # Summary
    total = len(get_results) + len(post_results)
    total_passed = get_passed + post_passed
    summary = {
        "phase": "phase2",
        "timestamp": timestamp(),
        "get_endpoints": {"passed": get_passed, "total": len(get_results)},
        "post_endpoints": {"passed": post_passed, "total": len(post_results)},
        "overall": {"passed": total_passed, "total": total},
    }
    save_evidence("phase2_summary.json", summary)

    # List failed endpoints
    failed = [r for r in get_results + post_results if not r.get("passed")]
    if failed:
        print(f"  ⚠ {len(failed)} endpoints failed:")
        for f_item in failed[:10]:
            status = f_item.get('status_code', f_item.get('error', 'unknown'))
            print(f"    - {f_item.get('method', '?')} {f_item.get('endpoint', '?')}: {status}")
        if len(failed) > 10:
            print(f"    ... and {len(failed) - 10} more")
    print()
    print("=" * 60)
    print(f" PHASE 2 COMPLETE: {total_passed}/{total} endpoints passed")
    print("=" * 60)

    return summary


if __name__ == "__main__":
    run_phase2()
