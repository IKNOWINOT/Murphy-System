#!/usr/bin/env python3
"""
PHASE 6: The "Murphy Sells Itself" Demo

This script simulates a prospective customer's first experience.
Murphy must demonstrate every capability that would close a sale.

FILES TESTED:
  - src/runtime/app.py                → API entry points
  - src/runtime/murphy_system_core.py → Core business logic
  - src/confidence_engine/             → G/D/H + 5D uncertainty
  - src/execution_engine/              → Task execution pipeline
  - src/form_intake/handlers.py        → Form intake
  - src/learning_engine/               → Shadow agent training
  - src/delivery_adapters.py           → Doc/email/chat/voice
  - src/compliance_engine.py           → GDPR/SOC2/HIPAA/PCI
  - src/analytics_dashboard.py         → Metrics dashboard
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
EVIDENCE_DIR = os.path.join(SCRIPT_DIR, "21_sales_demo")
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


def safe_request(method, path, **kwargs):
    """Make an HTTP request, returning (result_dict, passed)."""
    url = f"{BASE_URL}{path}"
    kwargs.setdefault("timeout", 15)
    try:
        resp = getattr(requests, method)(url, **kwargs)
        result = {
            "method": method.upper(),
            "url": url,
            "status_code": resp.status_code,
            "response_time_ms": resp.elapsed.total_seconds() * 1000,
        }
        try:
            result["body"] = resp.json()
        except ValueError:
            result["body"] = resp.text[:500]
        result["passed"] = resp.status_code in (200, 201, 202, 204)
        return result, result["passed"]
    except Exception as exc:
        return {"method": method.upper(), "url": url, "error": str(exc), "passed": False}, False


# ── Demo Scenarios ────────────────────────────────────────────


def demo_1_first_impression():
    """Scenario 1: Customer hits the landing page and health check."""
    print("  📍 Demo 1: First Impression")
    results = []

    # Health check
    r, ok = safe_request("get", "/api/health")
    results.append({"step": "health_check", **r})
    log_event("phase6", "demo1_health", "pass" if ok else "fail", "")

    # System info
    r, ok = safe_request("get", "/api/info")
    results.append({"step": "system_info", **r})
    log_event("phase6", "demo1_info", "pass" if ok else "fail", "")

    # UI links
    r, ok = safe_request("get", "/api/ui/links")
    results.append({"step": "ui_links", **r})
    log_event("phase6", "demo1_ui_links", "pass" if ok else "fail", "")

    passed = sum(1 for x in results if x.get("passed"))
    save_evidence("demo1_first_impression.json", results)
    print(f"     Result: {passed}/{len(results)} passed")
    return results


def demo_2_chat_interaction():
    """Scenario 2: Customer asks Murphy a question via chat."""
    print("  📍 Demo 2: Chat Interaction")
    results = []

    # Ask Murphy a question
    r, ok = safe_request("post", "/api/chat", json={"message": "What can Murphy do for my business?"})
    results.append({"step": "chat_ask", **r})
    log_event("phase6", "demo2_chat", "pass" if ok else "fail", "")

    # Follow-up question
    r, ok = safe_request("post", "/api/chat", json={"message": "How does Murphy handle compliance?"})
    results.append({"step": "chat_compliance", **r})
    log_event("phase6", "demo2_compliance", "pass" if ok else "fail", "")

    passed = sum(1 for x in results if x.get("passed"))
    save_evidence("demo2_chat_interaction.json", results)
    print(f"     Result: {passed}/{len(results)} passed")
    return results


def demo_3_task_execution():
    """Scenario 3: Customer submits a task for execution."""
    print("  📍 Demo 3: Task Execution")
    results = []

    r, ok = safe_request("post", "/api/execute", json={
        "task": "generate_report",
        "input": "Q4 sales summary for ACME Corp",
    })
    results.append({"step": "execute_task", **r})
    log_event("phase6", "demo3_execute", "pass" if ok else "fail", "")

    passed = sum(1 for x in results if x.get("passed"))
    save_evidence("demo3_task_execution.json", results)
    print(f"     Result: {passed}/{len(results)} passed")
    return results


def demo_4_onboarding_flow():
    """Scenario 4: Customer starts the onboarding wizard."""
    print("  📍 Demo 4: Onboarding Flow")
    results = []

    # Get wizard questions
    r, ok = safe_request("get", "/api/onboarding/wizard/questions")
    results.append({"step": "wizard_questions", **r})
    log_event("phase6", "demo4_questions", "pass" if ok else "fail", "")

    # Answer first question
    r, ok = safe_request("post", "/api/onboarding/wizard/answer", json={
        "question_id": "industry",
        "answer": "Technology",
    })
    results.append({"step": "wizard_answer", **r})
    log_event("phase6", "demo4_answer", "pass" if ok else "fail", "")

    # Get onboarding status
    r, ok = safe_request("get", "/api/onboarding/status")
    results.append({"step": "onboarding_status", **r})
    log_event("phase6", "demo4_status", "pass" if ok else "fail", "")

    passed = sum(1 for x in results if x.get("passed"))
    save_evidence("demo4_onboarding_flow.json", results)
    print(f"     Result: {passed}/{len(results)} passed")
    return results


def demo_5_integration_showcase():
    """Scenario 5: Show available integrations."""
    print("  📍 Demo 5: Integration Showcase")
    results = []

    r, ok = safe_request("get", "/api/integrations")
    results.append({"step": "list_integrations", **r})
    log_event("phase6", "demo5_integrations", "pass" if ok else "fail", "")

    r, ok = safe_request("get", "/api/universal-integrations/services")
    results.append({"step": "universal_services", **r})
    log_event("phase6", "demo5_services", "pass" if ok else "fail", "")

    r, ok = safe_request("get", "/api/universal-integrations/categories")
    results.append({"step": "integration_categories", **r})
    log_event("phase6", "demo5_categories", "pass" if ok else "fail", "")

    passed = sum(1 for x in results if x.get("passed"))
    save_evidence("demo5_integration_showcase.json", results)
    print(f"     Result: {passed}/{len(results)} passed")
    return results


def demo_6_analytics_overview():
    """Scenario 6: Show analytics and cost management."""
    print("  📍 Demo 6: Analytics & Costs")
    results = []

    r, ok = safe_request("get", "/api/costs/summary")
    results.append({"step": "costs_summary", **r})
    log_event("phase6", "demo6_costs", "pass" if ok else "fail", "")

    r, ok = safe_request("get", "/api/orchestrator/overview")
    results.append({"step": "orchestrator_overview", **r})
    log_event("phase6", "demo6_orchestrator", "pass" if ok else "fail", "")

    r, ok = safe_request("get", "/api/telemetry")
    results.append({"step": "telemetry", **r})
    log_event("phase6", "demo6_telemetry", "pass" if ok else "fail", "")

    passed = sum(1 for x in results if x.get("passed"))
    save_evidence("demo6_analytics_overview.json", results)
    print(f"     Result: {passed}/{len(results)} passed")
    return results


def demo_7_security_compliance():
    """Scenario 7: Demonstrate security and compliance posture."""
    print("  📍 Demo 7: Security & Compliance")
    results = []

    r, ok = safe_request("get", "/api/readiness")
    results.append({"step": "readiness", **r})
    log_event("phase6", "demo7_readiness", "pass" if ok else "fail", "")

    r, ok = safe_request("get", "/api/graph/health")
    results.append({"step": "graph_health", **r})
    log_event("phase6", "demo7_graph_health", "pass" if ok else "fail", "")

    r, ok = safe_request("get", "/api/ucp/health")
    results.append({"step": "ucp_health", **r})
    log_event("phase6", "demo7_ucp_health", "pass" if ok else "fail", "")

    passed = sum(1 for x in results if x.get("passed"))
    save_evidence("demo7_security_compliance.json", results)
    print(f"     Result: {passed}/{len(results)} passed")
    return results


def run_phase6():
    """Execute all Phase 6 demo scenarios and return summary."""
    print("=" * 60)
    print(" PHASE 6: Sales Readiness Demo")
    print(f" {timestamp()}")
    print("=" * 60)
    print()

    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    demos = [
        ("First Impression", demo_1_first_impression),
        ("Chat Interaction", demo_2_chat_interaction),
        ("Task Execution", demo_3_task_execution),
        ("Onboarding Flow", demo_4_onboarding_flow),
        ("Integration Showcase", demo_5_integration_showcase),
        ("Analytics Overview", demo_6_analytics_overview),
        ("Security & Compliance", demo_7_security_compliance),
    ]

    all_results = []
    demo_summaries = []
    for name, func in demos:
        print(f"\n── Demo: {name} ──")
        results = func()
        all_results.extend(results)
        demo_passed = sum(1 for r in results if r.get("passed"))
        demo_summaries.append({
            "demo": name,
            "passed": demo_passed,
            "total": len(results),
        })
        print()

    total = len(all_results)
    total_passed = sum(1 for r in all_results if r.get("passed"))

    summary = {
        "phase": "phase6",
        "timestamp": timestamp(),
        "demos": demo_summaries,
        "overall": {"passed": total_passed, "total": total},
    }
    save_evidence("phase6_summary.json", summary)

    print("=" * 60)
    print(f" PHASE 6 COMPLETE: {total_passed}/{total} demo steps passed")
    for ds in demo_summaries:
        icon = "✓" if ds["passed"] == ds["total"] else "✗"
        print(f"  {icon} {ds['demo']}: {ds['passed']}/{ds['total']}")
    print("=" * 60)

    return summary


if __name__ == "__main__":
    run_phase6()
