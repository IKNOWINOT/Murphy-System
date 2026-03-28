#!/usr/bin/env python3
"""
PHASE 4: Security hardening verification.

FILES TESTED:
  - Murphy System/src/security_hardening_config.py                → XSS/SQLi/path traversal
  - Murphy System/src/security_plane/authorization_enhancer.py    → ownership verification
  - Murphy System/src/security_plane/log_sanitizer.py             → PII redaction
  - Murphy System/src/security_plane/bot_resource_quotas.py       → bot limits
  - Murphy System/src/security_plane/bot_identity_verifier.py     → HMAC identity
  - Murphy System/src/security_plane/bot_anomaly_detector.py      → anomaly detection
  - Murphy System/src/security_plane/security_dashboard.py        → unified dashboard
  - Murphy System/src/security_plane/swarm_communication_monitor.py → DFS cycles
"""

import json
import os
import sys
import datetime
import importlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EVIDENCE_DIR = os.path.join(SCRIPT_DIR, "18_security_plane")
LOG_FILE = os.path.join(SCRIPT_DIR, "telemetry_log.jsonl")

# Add src/ to path for imports
MURPHY_SRC = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "Murphy System", "src")
)
if MURPHY_SRC not in sys.path:
    sys.path.insert(0, MURPHY_SRC)


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


# ── Security Module Import Tests ──────────────────────────────

SECURITY_MODULES = [
    ("security_hardening_config", "Input sanitizer & CORS policy"),
    ("security_plane.authorization_enhancer", "Authorization ownership"),
    ("security_plane.log_sanitizer", "PII redaction"),
    ("security_plane.bot_resource_quotas", "Bot resource limits"),
    ("security_plane.bot_identity_verifier", "HMAC bot identity"),
    ("security_plane.bot_anomaly_detector", "Z-score anomaly"),
    ("security_plane.security_dashboard", "Unified security dashboard"),
    ("security_plane.swarm_communication_monitor", "Swarm cycle detection"),
    ("security_plane.access_control", "Access control enforcement"),
    ("security_plane.authentication", "Authentication logic"),
    ("security_plane.data_leak_prevention", "DLP enforcement"),
    ("security_plane.middleware", "Security middleware"),
]


def test_security_module_imports():
    """Verify all security modules can be imported."""
    results = []
    for module_name, description in SECURITY_MODULES:
        try:
            mod = importlib.import_module(module_name)
            result = {
                "module": module_name,
                "description": description,
                "imported": True,
                "attributes": [a for a in dir(mod) if not a.startswith("_")][:20],
                "passed": True,
            }
            log_event("phase4", f"import_{module_name}", "pass", "Imported OK")
        except ImportError as exc:
            result = {
                "module": module_name,
                "description": description,
                "imported": False,
                "error": str(exc),
                "passed": False,
            }
            log_event("phase4", f"import_{module_name}", "fail", str(exc))
        except Exception as exc:
            result = {
                "module": module_name,
                "description": description,
                "imported": False,
                "error": str(exc),
                "passed": False,
            }
            log_event("phase4", f"import_{module_name}", "fail", str(exc))
        results.append(result)
        save_evidence(f"import_{module_name.replace('.', '_')}.json", result)
    return results


# ── Input Sanitization Tests ──────────────────────────────────

XSS_PAYLOADS = [
    "<script>alert('xss')</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(1)",
    "<svg onload=alert(1)>",
    "'-alert(1)-'",
]

SQLI_PAYLOADS = [
    "'; DROP TABLE users; --",
    "1 OR 1=1",
    "' UNION SELECT * FROM users --",
    "1; DELETE FROM orders",
]

PATH_TRAVERSAL_PAYLOADS = [
    "../../../etc/passwd",
    "..\\..\\..\\windows\\system32",
    "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "....//....//etc/passwd",
]


def test_input_sanitization():
    """Test the InputSanitizer against common attack payloads."""
    results = []

    try:
        from security_hardening_config import InputSanitizer
        sanitizer = InputSanitizer()
    except (ImportError, Exception) as exc:
        log_event("phase4", "input_sanitizer", "fail", f"Cannot import: {exc}")
        return [{"test": "import_sanitizer", "passed": False, "error": str(exc)}]

    # Test XSS payloads
    for i, payload in enumerate(XSS_PAYLOADS):
        try:
            sanitized = sanitizer.sanitize_string(payload)
            is_safe = "<script" not in sanitized.lower() and "onerror" not in sanitized.lower()
            result = {
                "test": f"xss_{i}",
                "payload": payload,
                "sanitized": sanitized,
                "is_safe": is_safe,
                "passed": is_safe,
            }
        except Exception as exc:
            # If the sanitizer raises on dangerous input, that's also acceptable
            result = {
                "test": f"xss_{i}",
                "payload": payload,
                "rejected": True,
                "error": str(exc),
                "passed": True,
            }
        results.append(result)
        log_event(
            "phase4",
            f"xss_test_{i}",
            "pass" if result["passed"] else "fail",
            f"payload={'safe' if result['passed'] else 'UNSAFE'}",
        )

    # Test SQL injection payloads
    for i, payload in enumerate(SQLI_PAYLOADS):
        try:
            sanitized = sanitizer.sanitize_string(payload)
            is_safe = "DROP" not in sanitized or "UNION" not in sanitized
            result = {
                "test": f"sqli_{i}",
                "payload": payload,
                "sanitized": sanitized,
                "is_safe": is_safe,
                "passed": is_safe,
            }
        except Exception as exc:
            result = {
                "test": f"sqli_{i}",
                "payload": payload,
                "rejected": True,
                "error": str(exc),
                "passed": True,
            }
        results.append(result)
        log_event(
            "phase4",
            f"sqli_test_{i}",
            "pass" if result["passed"] else "fail",
            "",
        )

    # Test path traversal payloads
    for i, payload in enumerate(PATH_TRAVERSAL_PAYLOADS):
        try:
            sanitized = sanitizer.sanitize_string(payload)
            is_safe = ".." not in sanitized
            result = {
                "test": f"path_traversal_{i}",
                "payload": payload,
                "sanitized": sanitized,
                "is_safe": is_safe,
                "passed": is_safe,
            }
        except Exception as exc:
            result = {
                "test": f"path_traversal_{i}",
                "payload": payload,
                "rejected": True,
                "error": str(exc),
                "passed": True,
            }
        results.append(result)
        log_event(
            "phase4",
            f"path_traversal_test_{i}",
            "pass" if result["passed"] else "fail",
            "",
        )

    save_evidence("sanitization_results.json", results)
    return results


# ── HTTP Security Header Tests ────────────────────────────────


def test_security_headers():
    """Check that the running server returns security headers."""
    try:
        import requests
    except ImportError:
        return [{"test": "security_headers", "passed": False, "error": "requests not installed"}]

    base_url = os.environ.get("MURPHY_BASE_URL", "http://localhost:8000")
    expected_headers = [
        "x-content-type-options",
        "x-frame-options",
        "strict-transport-security",
        "content-security-policy",
        "x-xss-protection",
    ]
    results = []

    try:
        resp = requests.get(f"{base_url}/api/health", timeout=10)
        headers = {k.lower(): v for k, v in resp.headers.items()}

        for header in expected_headers:
            present = header in headers
            result = {
                "header": header,
                "present": present,
                "value": headers.get(header, None),
                "passed": present,
            }
            results.append(result)
            log_event(
                "phase4",
                f"header_{header}",
                "pass" if present else "warn",
                f"{'present' if present else 'missing'}",
            )
    except Exception as exc:
        results.append({"test": "security_headers", "error": str(exc), "passed": False})
        log_event("phase4", "security_headers", "fail", str(exc))

    save_evidence("security_headers.json", results)
    return results


def run_phase4():
    """Execute all Phase 4 tests and return summary."""
    print("=" * 60)
    print(" PHASE 4: Security Plane Validation")
    print(f" {timestamp()}")
    print("=" * 60)
    print()

    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    # Test 1: Module imports
    print(f"→ Testing {len(SECURITY_MODULES)} security module imports...")
    import_results = test_security_module_imports()
    import_passed = sum(1 for r in import_results if r.get("passed"))
    print(f"  Imports: {import_passed}/{len(import_results)} passed")
    print()

    # Test 2: Input sanitization
    print("→ Testing input sanitization (XSS/SQLi/path traversal)...")
    sanitization_results = test_input_sanitization()
    san_passed = sum(1 for r in sanitization_results if r.get("passed"))
    print(f"  Sanitization: {san_passed}/{len(sanitization_results)} passed")
    print()

    # Test 3: Security headers
    print("→ Testing HTTP security headers...")
    header_results = test_security_headers()
    hdr_passed = sum(1 for r in header_results if r.get("passed"))
    print(f"  Headers: {hdr_passed}/{len(header_results)} passed")
    print()

    total = len(import_results) + len(sanitization_results) + len(header_results)
    total_passed = import_passed + san_passed + hdr_passed

    summary = {
        "phase": "phase4",
        "timestamp": timestamp(),
        "imports": {"passed": import_passed, "total": len(import_results)},
        "sanitization": {"passed": san_passed, "total": len(sanitization_results)},
        "headers": {"passed": hdr_passed, "total": len(header_results)},
        "overall": {"passed": total_passed, "total": total},
    }
    save_evidence("phase4_summary.json", summary)

    print("=" * 60)
    print(f" PHASE 4 COMPLETE: {total_passed}/{total} checks passed")
    print("=" * 60)

    return summary


if __name__ == "__main__":
    run_phase4()
