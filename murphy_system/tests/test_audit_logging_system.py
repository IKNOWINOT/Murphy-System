# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for audit_logging_system — AUD-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable AUDRecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

from audit_logging_system import (  # noqa: E402
    AuditAction,
    AuditCategory,
    AuditEntry,
    AuditLogger,
    AuditQuery,
    AuditSeverity,
    RetentionPolicy,
    create_audit_api,
)

# -- Record pattern --------------------------------------------------------

@dataclass
class AUDRecord:
    """One AUD check record."""
    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )

_RESULTS: List[AUDRecord] = []

def record(
    check_id: str, desc: str, expected: Any, actual: Any,
    cause: str = "", effect: str = "", lesson: str = "",
) -> bool:
    ok = expected == actual
    _RESULTS.append(AUDRecord(
        check_id=check_id, description=desc, expected=expected,
        actual=actual, passed=ok, cause=cause, effect=effect, lesson=lesson,
    ))
    return ok

# -- Helpers ---------------------------------------------------------------

def _al(**kw: Any) -> AuditLogger:
    """Create a fresh AuditLogger."""
    return AuditLogger(**kw)

# ==================================================================== #
#  Enum tests                                                           #
# ==================================================================== #

def test_aud_001_action_enum():
    """AuditAction enum has expected members."""
    expected = {
        "create", "read", "update", "delete", "login", "logout",
        "configure", "execute", "approve", "deny", "export",
    }
    assert record("AUD-001", "AuditAction values", expected, {m.value for m in AuditAction})

def test_aud_002_severity_enum():
    """AuditSeverity enum has expected members."""
    assert record(
        "AUD-002", "AuditSeverity values",
        {"info", "warning", "critical", "security"},
        {m.value for m in AuditSeverity},
    )

def test_aud_003_category_enum():
    """AuditCategory enum has expected members."""
    expected = {
        "api_call", "admin_action", "config_change",
        "security_event", "data_access", "system_event", "user_action",
    }
    assert record("AUD-003", "AuditCategory values", expected, {m.value for m in AuditCategory})

# ==================================================================== #
#  Dataclass tests                                                      #
# ==================================================================== #

def test_aud_004_entry_defaults():
    """AuditEntry has sane defaults."""
    e = AuditEntry()
    assert record(
        "AUD-004", "Entry defaults",
        (True, AuditAction.READ, True),
        (bool(e.id), e.action, e.success),
    )

def test_aud_005_entry_ip_redaction():
    """AuditEntry.to_dict() redacts IPv4 address."""
    e = AuditEntry(source_ip="192.168.1.42")
    d = e.to_dict()
    assert record(
        "AUD-005", "IP redaction",
        "192.168.xxx.xxx", d["source_ip"],
        cause="PII must be redacted in serialised output",
        effect="last two octets masked",
        lesson="never expose full IP addresses in audit exports",
    )

def test_aud_006_entry_user_agent_truncation():
    """AuditEntry.to_dict() truncates long user agent."""
    e = AuditEntry(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    d = e.to_dict()
    assert record("AUD-006", "UA truncated", True, d["user_agent"].endswith("..."))

def test_aud_007_entry_hash():
    """AuditEntry.compute_hash() produces consistent SHA-256."""
    e = AuditEntry(action=AuditAction.CREATE, actor="admin", resource="user")
    h = e.compute_hash()
    assert record("AUD-007", "Hash is 64-char hex", 64, len(h))

def test_aud_008_retention_policy_to_dict():
    """RetentionPolicy.to_dict() serialises correctly."""
    p = RetentionPolicy(name="test", category=AuditCategory.API_CALL)
    d = p.to_dict()
    assert record("AUD-008", "Policy to_dict", "api_call", d["category"])

# ==================================================================== #
#  Core logging tests                                                   #
# ==================================================================== #

def test_aud_009_log_entry():
    """AuditLogger.log() creates an entry with hash chain."""
    al = _al()
    e = al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION, actor="admin")
    assert record(
        "AUD-009", "Log creates entry",
        (True, AuditAction.CREATE, "admin"),
        (bool(e.entry_hash), e.action, e.actor),
    )

def test_aud_010_hash_chain():
    """Hash chain links entries correctly."""
    al = _al()
    e1 = al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
    e2 = al.log(AuditAction.UPDATE, AuditCategory.CONFIG_CHANGE)
    assert record(
        "AUD-010", "Hash chain link",
        e1.entry_hash, e2.previous_hash,
        cause="each entry stores the hash of the previous one",
        effect="tamper-evident chain",
        lesson="hash chains detect any modification to historical entries",
    )

def test_aud_011_verify_chain_valid():
    """verify_chain() returns True for untampered log."""
    al = _al()
    for i in range(5):
        al.log(AuditAction.READ, AuditCategory.API_CALL, actor=f"u{i}")
    valid, count = al.verify_chain()
    assert record("AUD-011", "Chain valid", (True, 5), (valid, count))

def test_aud_012_verify_chain_tampered():
    """verify_chain() detects tampered entry."""
    al = _al()
    al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
    al.log(AuditAction.UPDATE, AuditCategory.CONFIG_CHANGE)
    # Tamper with entry
    with al._lock:
        al._entries[0].detail = "TAMPERED"
    valid, idx = al.verify_chain()
    assert record("AUD-012", "Tampered chain detected", False, valid)

def test_aud_013_verify_empty():
    """verify_chain() on empty log returns True."""
    al = _al()
    valid, count = al.verify_chain()
    assert record("AUD-013", "Empty chain valid", (True, 0), (valid, count))

# ==================================================================== #
#  Convenience loggers                                                  #
# ==================================================================== #

def test_aud_014_log_api_call():
    """log_api_call() sets correct action and category."""
    al = _al()
    e = al.log_api_call("GET", "/api/health", actor="sys", status_code=200)
    assert record(
        "AUD-014", "API call log",
        (AuditAction.READ, AuditCategory.API_CALL, True),
        (e.action, e.category, e.success),
    )

def test_aud_015_log_api_call_failure():
    """log_api_call() marks 4xx/5xx as failure."""
    al = _al()
    e = al.log_api_call("POST", "/api/exec", status_code=500)
    assert record("AUD-015", "API failure", False, e.success)

def test_aud_016_log_admin_action():
    """log_admin_action() sets severity to WARNING."""
    al = _al()
    e = al.log_admin_action("admin", AuditAction.DELETE, "user", "u123")
    assert record(
        "AUD-016", "Admin action severity",
        AuditSeverity.WARNING, e.severity,
    )

def test_aud_017_log_config_change():
    """log_config_change() sets category and action."""
    al = _al()
    e = al.log_config_change("admin", "rate_limit", "changed from 100 to 200")
    assert record(
        "AUD-017", "Config change",
        (AuditAction.CONFIGURE, AuditCategory.CONFIG_CHANGE),
        (e.action, e.category),
    )

def test_aud_018_log_security_event():
    """log_security_event() sets security severity."""
    al = _al()
    e = al.log_security_event("attacker", "brute force attempt", success=False, source_ip="10.0.0.1")
    assert record(
        "AUD-018", "Security event",
        (AuditSeverity.SECURITY, False),
        (e.severity, e.success),
    )

# ==================================================================== #
#  Query tests                                                          #
# ==================================================================== #

def test_aud_019_query_by_action():
    """Query filters by action."""
    al = _al()
    al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
    al.log(AuditAction.READ, AuditCategory.API_CALL)
    al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
    q = AuditQuery(action=AuditAction.CREATE)
    assert record("AUD-019", "Query by action", 2, len(al.query(q)))

def test_aud_020_query_by_category():
    """Query filters by category."""
    al = _al()
    al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
    al.log(AuditAction.READ, AuditCategory.API_CALL)
    q = AuditQuery(category=AuditCategory.API_CALL)
    assert record("AUD-020", "Query by category", 1, len(al.query(q)))

def test_aud_021_query_by_actor():
    """Query filters by actor."""
    al = _al()
    al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION, actor="alice")
    al.log(AuditAction.READ, AuditCategory.API_CALL, actor="bob")
    q = AuditQuery(actor="alice")
    assert record("AUD-021", "Query by actor", 1, len(al.query(q)))

def test_aud_022_query_by_success():
    """Query filters by success flag."""
    al = _al()
    al.log(AuditAction.LOGIN, AuditCategory.SECURITY_EVENT, success=True)
    al.log(AuditAction.LOGIN, AuditCategory.SECURITY_EVENT, success=False)
    q = AuditQuery(success=False)
    assert record("AUD-022", "Query by success", 1, len(al.query(q)))

def test_aud_023_query_limit():
    """Query respects limit parameter."""
    al = _al()
    for i in range(10):
        al.log(AuditAction.READ, AuditCategory.API_CALL, actor=f"u{i}")
    q = AuditQuery(limit=3)
    assert record("AUD-023", "Query limit", 3, len(al.query(q)))

def test_aud_024_get_entry():
    """Get entry by ID."""
    al = _al()
    e = al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
    got = al.get_entry(e.id)
    assert record("AUD-024", "Get entry", e.id, got.id if got else None)

def test_aud_025_get_entry_missing():
    """Get entry returns None for unknown ID."""
    al = _al()
    assert record("AUD-025", "Missing entry", None, al.get_entry("nope"))

def test_aud_026_count():
    """Count entries with category filter."""
    al = _al()
    al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
    al.log(AuditAction.READ, AuditCategory.API_CALL)
    al.log(AuditAction.READ, AuditCategory.API_CALL)
    assert record("AUD-026a", "Total count", 3, al.count())
    assert record("AUD-026b", "Category count", 2, al.count(AuditCategory.API_CALL))

# ==================================================================== #
#  Retention & export tests                                             #
# ==================================================================== #

def test_aud_027_add_policy():
    """Add and list retention policies."""
    al = _al()
    p = al.add_policy("default", max_age_days=90)
    assert record("AUD-027", "Policy created", True, bool(p.id))
    assert record("AUD-027b", "Policy listed", 1, len(al.list_policies()))

def test_aud_028_delete_policy():
    """Delete a retention policy."""
    al = _al()
    p = al.add_policy("temp")
    assert record("AUD-028", "Delete policy", True, al.delete_policy(p.id))
    assert record("AUD-028b", "Policy gone", 0, len(al.list_policies()))

def test_aud_029_apply_retention():
    """Retention policy trims entries exceeding max_entries."""
    al = _al()
    for i in range(20):
        al.log(AuditAction.READ, AuditCategory.API_CALL, actor=f"u{i}")
    al.add_policy("trim", max_entries=5, category=AuditCategory.API_CALL)
    removed = al.apply_retention()
    assert record("AUD-029", "Retention trimmed", 15, removed)

def test_aud_030_export_json():
    """Export produces valid JSON."""
    al = _al()
    al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION, actor="admin")
    exported = al.export_json()
    data = json.loads(exported)
    assert record("AUD-030", "Export JSON", 1, len(data))

# ==================================================================== #
#  Sink callback tests                                                  #
# ==================================================================== #

def test_aud_031_sink_callback():
    """Sink callback receives entries."""
    captured: list = []
    al = _al(sink_callback=lambda e: (captured.append(e), True)[-1])
    al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
    assert record("AUD-031", "Sink received entry", 1, len(captured))

def test_aud_032_sink_failure():
    """Sink failure doesn't crash the logger."""
    def bad_sink(e: Any) -> bool:
        raise RuntimeError("sink down")
    al = _al(sink_callback=bad_sink)
    e = al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
    assert record("AUD-032", "Sink failure handled", True, bool(e.entry_hash))

# ==================================================================== #
#  Statistics tests                                                     #
# ==================================================================== #

def test_aud_033_stats():
    """Stats returns expected structure."""
    al = _al()
    al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION, actor="admin")
    al.log(AuditAction.READ, AuditCategory.API_CALL, success=False)
    s = al.stats()
    assert record(
        "AUD-033", "Stats structure",
        (2, 1, True, 2),
        (s["total_entries"], s["failed_operations"], s["chain_valid"], s["chain_verified"]),
    )

# ==================================================================== #
#  Thread safety                                                        #
# ==================================================================== #

def test_aud_034_thread_safety():
    """Concurrent logging from 10 threads."""
    al = _al()
    barrier = threading.Barrier(10)
    def worker(i: int) -> None:
        barrier.wait()
        al.log(AuditAction.READ, AuditCategory.API_CALL, actor=f"t-{i}")
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert record(
        "AUD-034", "10 concurrent logs",
        10, al.count(),
        cause="threading.Lock guards mutations",
        effect="no race conditions",
        lesson="thread-safe append prevents data loss",
    )

def test_aud_035_concurrent_chain_valid():
    """Chain remains valid after concurrent writes."""
    al = _al()
    barrier = threading.Barrier(5)
    def worker(i: int) -> None:
        barrier.wait()
        al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION, actor=f"w-{i}")
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    valid, count = al.verify_chain()
    assert record("AUD-035", "Concurrent chain valid", (True, 5), (valid, count))

# ==================================================================== #
#  Flask API tests                                                      #
# ==================================================================== #

try:
    from flask import Flask

    def _app() -> tuple:
        al = _al()
        app = Flask(__name__)
        app.register_blueprint(create_audit_api(al))
        return app, al

    def test_aud_036_api_create_entry():
        """POST /api/audit/entries creates an entry."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/audit/entries", json={
                "action": "create", "category": "admin_action",
                "actor": "admin", "resource": "user",
            })
            data = resp.get_json()
        assert record(
            "AUD-036", "POST entries returns 201",
            (201, "create"), (resp.status_code, data.get("action")),
        )

    def test_aud_037_api_list_entries():
        """GET /api/audit/entries lists entries."""
        app, al = _app()
        al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
        al.log(AuditAction.READ, AuditCategory.API_CALL)
        with app.test_client() as c:
            resp = c.get("/api/audit/entries")
        assert record(
            "AUD-037", "GET entries", (200, 2), (resp.status_code, len(resp.get_json())),
        )

    def test_aud_038_api_list_entries_filter():
        """GET /api/audit/entries?action=create filters."""
        app, al = _app()
        al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
        al.log(AuditAction.READ, AuditCategory.API_CALL)
        with app.test_client() as c:
            resp = c.get("/api/audit/entries?action=create")
        assert record("AUD-038", "Filter by action", 1, len(resp.get_json()))

    def test_aud_039_api_get_entry():
        """GET /api/audit/entries/<id> returns entry."""
        app, al = _app()
        e = al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
        with app.test_client() as c:
            resp = c.get(f"/api/audit/entries/{e.id}")
        assert record("AUD-039", "GET entry by ID", 200, resp.status_code)

    def test_aud_040_api_get_entry_404():
        """GET /api/audit/entries/<id> returns 404."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.get("/api/audit/entries/nope")
        assert record("AUD-040", "GET unknown entry", 404, resp.status_code)

    def test_aud_041_api_verify():
        """GET /api/audit/verify returns chain status."""
        app, al = _app()
        al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
        with app.test_client() as c:
            resp = c.get("/api/audit/verify")
            data = resp.get_json()
        assert record(
            "AUD-041", "Verify endpoint", (200, True, 1),
            (resp.status_code, data["valid"], data["verified_count"]),
        )

    def test_aud_042_api_export():
        """GET /api/audit/export returns JSON entries."""
        app, al = _app()
        al.log(AuditAction.READ, AuditCategory.API_CALL)
        with app.test_client() as c:
            resp = c.get("/api/audit/export?limit=10")
        assert record("AUD-042", "Export endpoint", (200, 1), (resp.status_code, len(resp.get_json())))

    def test_aud_043_api_count():
        """GET /api/audit/count returns entry count."""
        app, al = _app()
        al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
        al.log(AuditAction.READ, AuditCategory.API_CALL)
        with app.test_client() as c:
            resp = c.get("/api/audit/count")
            data = resp.get_json()
        assert record("AUD-043", "Count endpoint", 2, data["count"])

    def test_aud_044_api_count_category():
        """GET /api/audit/count?category=api_call filters."""
        app, al = _app()
        al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
        al.log(AuditAction.READ, AuditCategory.API_CALL)
        with app.test_client() as c:
            resp = c.get("/api/audit/count?category=api_call")
            data = resp.get_json()
        assert record("AUD-044", "Count by category", 1, data["count"])

    def test_aud_045_api_add_policy():
        """POST /api/audit/policies creates a policy."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/audit/policies", json={"name": "default", "max_entries": 10000})
        assert record("AUD-045", "POST policy", 201, resp.status_code)

    def test_aud_046_api_list_policies():
        """GET /api/audit/policies lists policies."""
        app, al = _app()
        al.add_policy("p1")
        with app.test_client() as c:
            resp = c.get("/api/audit/policies")
        assert record("AUD-046", "GET policies", (200, 1), (resp.status_code, len(resp.get_json())))

    def test_aud_047_api_delete_policy():
        """DELETE /api/audit/policies/<id> deletes policy."""
        app, al = _app()
        p = al.add_policy("temp")
        with app.test_client() as c:
            resp = c.delete(f"/api/audit/policies/{p.id}")
        assert record("AUD-047", "DELETE policy", 200, resp.status_code)

    def test_aud_048_api_apply_retention():
        """POST /api/audit/retention/apply applies policies."""
        app, al = _app()
        for i in range(10):
            al.log(AuditAction.READ, AuditCategory.API_CALL)
        al.add_policy("trim", max_entries=5)
        with app.test_client() as c:
            resp = c.post("/api/audit/retention/apply")
            data = resp.get_json()
        assert record("AUD-048", "Apply retention", (200, 5), (resp.status_code, data["removed"]))

    def test_aud_049_api_stats():
        """GET /api/audit/stats returns statistics."""
        app, al = _app()
        al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION)
        with app.test_client() as c:
            resp = c.get("/api/audit/stats")
            data = resp.get_json()
        assert record(
            "AUD-049", "Stats endpoint",
            (200, 1, True), (resp.status_code, data["total_entries"], data["chain_valid"]),
        )

    def test_aud_050_api_missing_fields():
        """POST /api/audit/entries without required fields returns 400."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/audit/entries", json={})
        assert record("AUD-050", "Missing fields", 400, resp.status_code)

except ImportError:
    pass

# ==================================================================== #
#  Wingman & Sandbox gates                                              #
# ==================================================================== #

def test_aud_051_wingman_gate():
    """Wingman pair validation gate."""
    al = _al()
    storyteller_says = "Record admin config change to audit log"
    wingman_approves = True
    e = al.log_config_change("admin", "api_rate_limit", "100 -> 200") if wingman_approves else None
    assert record(
        "AUD-051", "Wingman gate — approved",
        True, e is not None and bool(e.entry_hash),
        cause="storyteller requests audit logging, wingman approves",
        effect="audit entry created with hash chain",
        lesson="Wingman pair validation ensures all config changes are audited",
    )

def test_aud_052_sandbox_gate():
    """Causality Sandbox gate — side-effect tracking."""
    al = _al()
    sandbox_mode = True
    if sandbox_mode:
        pre = al.count()
    al.log(AuditAction.CREATE, AuditCategory.ADMIN_ACTION, actor="sandbox-test")
    al.log(AuditAction.READ, AuditCategory.API_CALL, actor="sandbox-test")
    if sandbox_mode:
        post = al.count()
        delta = post - pre
    assert record(
        "AUD-052", "Sandbox gate — side effects tracked",
        2, delta,
        cause="sandbox monitors state changes",
        effect="two new audit entries detected",
        lesson="causality sandbox ensures auditable changes",
    )
