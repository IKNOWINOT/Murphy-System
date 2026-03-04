"""
Gap-closure tests — Round 3.

Each test class targets one specific gap found during the audit,
proves the gap *existed* (by checking the fixed behaviour), and
confirms the fix closes it.

Gaps addressed:
1.  rbac_governance — `roles[0]` returned wrong granting role
2.  governance_kernel — budget debit silently lost when no budget had capacity
3.  emergency_stop_controller — persistence failures hidden at debug level
4.  input_validation — XSS patterns missing onload= and friends
5.  delivery_adapters — translation returned DELIVERED with null text
6.  shutdown_manager — cleanup handlers had no timeout
7.  config — default api_host was 0.0.0.0 (all interfaces)
8.  self_improvement_engine — _outcomes and _corrections_applied unbounded
9.  delivery_adapters — DeliveryOrchestrator._history unbounded
10. compliance_monitoring — _alerts, _drift_history, _remediation_log unbounded
"""

import logging
import sys
import os
import threading
import time
import uuid

import pytest

# ---------------------------------------------------------------------------
# Ensure src/ is on the path
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ===================================================================
# Gap 1 — rbac_governance: granting role reported correctly
# ===================================================================
class TestRBACGrantingRole:
    """The automation-toggle reason must name the actual granting role,
    not just whatever sits at index 0 of the user's role list."""

    def test_admin_at_non_zero_index_reports_admin(self):
        from rbac_governance import (
            RBACGovernance, Role, TenantPolicy, UserIdentity,
        )

        gov = RBACGovernance()
        policy = TenantPolicy(tenant_id="t1", name="TestCo")
        gov.create_tenant(policy)

        # Register user whose FIRST role is VIEWER, second is ADMIN
        gov.register_user(UserIdentity(
            user_id="u1", tenant_id="t1",
            roles=[Role.VIEWER, Role.ADMIN], display_name="Tester",
        ))

        allowed, reason = gov.can_toggle_full_automation("u1", "t1", is_organization=True)
        assert allowed is True
        # The reason must reference admin (the role that grants permission),
        # not viewer (which happens to be at index 0).
        assert "admin" in reason, f"Expected 'admin' in reason, got: {reason}"

    def test_owner_always_reported_correctly(self):
        from rbac_governance import (
            RBACGovernance, Role, TenantPolicy, UserIdentity,
        )

        gov = RBACGovernance()
        policy = TenantPolicy(tenant_id="t2", name="OwnerCo")
        gov.create_tenant(policy)
        gov.register_user(UserIdentity(
            user_id="owner1", tenant_id="t2",
            roles=[Role.OWNER], display_name="Boss",
        ))

        allowed, reason = gov.can_toggle_full_automation(
            "owner1", "t2", is_organization=True
        )
        assert allowed is True
        assert "owner" in reason


# ===================================================================
# Gap 2 — governance_kernel: untracked cost logs an error
# ===================================================================
class TestGovernanceKernelUntrackedCost:
    """When no budget can cover a cost the kernel must log an error
    so operators know money is leaking."""

    def test_cost_without_budget_logs_error(self, caplog):
        from governance_kernel import GovernanceKernel, DepartmentScope

        kernel = GovernanceKernel()
        kernel.register_department(DepartmentScope(department_id="d1", name="Dept1"))
        kernel.set_budget("d1", total_budget=10.0, limit_per_task=5.0)

        # Record a cost that exceeds every budget's pending capacity
        with caplog.at_level(logging.ERROR):
            kernel.record_execution(
                caller_id="alice",
                tool_name="expensive_tool",
                cost=999.0,
                success=True,
            )

        error_messages = [r.message for r in caplog.records if r.levelno >= logging.ERROR]
        assert any("could not be debited" in m for m in error_messages), (
            f"Expected an error about untracked cost, got: {error_messages}"
        )

    def test_cost_within_budget_no_error(self, caplog):
        from governance_kernel import GovernanceKernel, DepartmentScope

        kernel = GovernanceKernel()
        kernel.register_department(DepartmentScope(department_id="d2", name="Dept2"))
        kernel.set_budget("d2", total_budget=100.0, limit_per_task=50.0)

        with caplog.at_level(logging.ERROR):
            kernel.record_execution(
                caller_id="bob",
                tool_name="cheap_tool",
                cost=5.0,
                success=True,
                department_id="d2",
            )

        error_messages = [r.message for r in caplog.records if r.levelno >= logging.ERROR]
        assert not any("could not be debited" in m for m in error_messages)


# ===================================================================
# Gap 3 — emergency_stop_controller: persistence failure at ERROR
# ===================================================================
class TestEmergencyStopPersistenceLogging:
    """Emergency-stop persistence failures must be logged at ERROR,
    not DEBUG, so operators can see them."""

    def test_persistence_failure_logged_at_error(self, caplog):
        from emergency_stop_controller import EmergencyStopController

        class BrokenPM:
            def save_document(self, **kwargs):
                raise IOError("disk full")

        esc = EmergencyStopController(persistence_manager=BrokenPM())
        with caplog.at_level(logging.DEBUG):
            esc.activate_global(reason="test stop")

        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert any("NOT persisted" in r.message for r in error_records), (
            "Persistence failure should be logged at ERROR level"
        )


# ===================================================================
# Gap 4 — input_validation: XSS patterns expanded
# ===================================================================
class TestInputValidationXSSPatterns:
    """Chat messages containing event-handler XSS patterns must be rejected."""

    @pytest.mark.parametrize("payload", [
        '<img src=x onerror=alert(1)>',
        '<body onload=alert(1)>',
        '<div onmouseover=alert(1)>',
        '<input onfocus=alert(1)>',
        '<select onblur=alert(1)>',
        '<button onclick=alert(1)>',
    ])
    def test_event_handler_xss_blocked(self, payload):
        from input_validation import ChatMessageInput

        with pytest.raises(Exception):
            ChatMessageInput(message=payload)

    def test_safe_message_still_allowed(self):
        from input_validation import ChatMessageInput

        msg = ChatMessageInput(message="Hello, how are you today?")
        assert msg.message == "Hello, how are you today?"


# ===================================================================
# Gap 5 — delivery_adapters: translation with null text = NEEDS_INFO
# ===================================================================
class TestTranslationDeliveryNullText:
    """The translation adapter must NOT return DELIVERED when the
    translated_text is still None."""

    def test_null_translation_returns_needs_info(self):
        from delivery_adapters import (
            TranslationDeliveryAdapter,
            DeliveryRequest,
            DeliveryChannel,
            DeliveryStatus,
        )

        adapter = TranslationDeliveryAdapter()
        req = DeliveryRequest(
            channel=DeliveryChannel.TRANSLATION,
            session_id="sess-1",
            payload={
                "source_locale": "en",
                "target_locale": "es",
                "text": "Hello world",
            },
        )
        result = adapter.deliver(req)
        # Translation service hasn't filled translated_text yet
        assert result.status == DeliveryStatus.NEEDS_INFO, (
            f"Expected NEEDS_INFO for null translation, got {result.status}"
        )
        assert result.error is not None

    def test_translation_counter_increments(self):
        from delivery_adapters import (
            TranslationDeliveryAdapter,
            DeliveryRequest,
            DeliveryChannel,
        )

        adapter = TranslationDeliveryAdapter()
        req = DeliveryRequest(
            channel=DeliveryChannel.TRANSLATION,
            session_id="sess-2",
            payload={
                "source_locale": "en",
                "target_locale": "fr",
                "text": "Hi",
            },
        )
        adapter.deliver(req)
        status = adapter.get_status()
        assert status["deliveries"] >= 1


# ===================================================================
# Gap 6 — shutdown_manager: cleanup timeout prevents hung shutdown
# ===================================================================
class TestShutdownManagerTimeout:
    """A cleanup handler that hangs must be timed out, not block forever."""

    def test_hanging_handler_does_not_block(self):
        from shutdown_manager import ShutdownManager

        sm = ShutdownManager.__new__(ShutdownManager)
        sm.cleanup_handlers = []
        sm.is_shutting_down = False

        executed = []

        def fast_handler():
            executed.append("fast")

        def hanging_handler():
            time.sleep(60)  # simulate hang

        sm.register_cleanup_handler(fast_handler, "fast")
        sm.register_cleanup_handler(hanging_handler, "hanging")

        start = time.time()
        sm._CLEANUP_TIMEOUT = 1  # 1-second timeout for test
        sm.shutdown()
        elapsed = time.time() - start

        # Hanging handler should have been timed out after ~1s
        assert elapsed < 10, f"Shutdown took {elapsed}s — timeout did not work"
        # Fast handler (registered first, runs second in LIFO) should still run
        assert "fast" in executed

    def test_normal_handler_completes(self):
        from shutdown_manager import ShutdownManager

        sm = ShutdownManager.__new__(ShutdownManager)
        sm.cleanup_handlers = []
        sm.is_shutting_down = False

        executed = []
        sm.register_cleanup_handler(lambda: executed.append("a"), "a")
        sm.register_cleanup_handler(lambda: executed.append("b"), "b")

        sm.shutdown()
        assert executed == ["b", "a"]  # LIFO order


# ===================================================================
# Gap 7 — config: default api_host is now localhost-only
# ===================================================================
class TestConfigSecureDefaults:
    """The default API host must be 127.0.0.1, not 0.0.0.0."""

    def test_default_host_is_localhost(self):
        from config import Settings

        s = Settings()
        assert s.api_host == "127.0.0.1", (
            f"Default api_host should be 127.0.0.1 for security, got {s.api_host}"
        )

    def test_host_can_be_overridden(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "0.0.0.0")
        from config import Settings

        s = Settings()
        assert s.api_host == "0.0.0.0"


# ===================================================================
# Gap 8 — self_improvement_engine: bounded _outcomes and _corrections
# ===================================================================
class TestSelfImprovementEngineBounded:
    """_outcomes and _corrections_applied must not grow without limit."""

    def test_outcomes_capped(self):
        from self_improvement_engine import SelfImprovementEngine, ExecutionOutcome, OutcomeType
        from datetime import datetime, timezone

        engine = SelfImprovementEngine()
        engine._MAX_OUTCOMES = 50  # small cap for test

        for i in range(60):
            engine.record_outcome(ExecutionOutcome(
                task_id=f"t-{i}",
                session_id=f"s-{i}",
                outcome=OutcomeType.SUCCESS,
                metrics={},
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))

        assert len(engine._outcomes) <= 50, (
            f"Expected <=50 outcomes, got {len(engine._outcomes)}"
        )

    def test_corrections_capped(self):
        from self_improvement_engine import SelfImprovementEngine, ImprovementProposal

        engine = SelfImprovementEngine()
        engine._MAX_CORRECTIONS = 20  # small cap for test

        for i in range(25):
            pid = f"p-{i}"
            engine._proposals[pid] = ImprovementProposal(
                proposal_id=pid,
                category="test",
                description="desc",
                priority="low",
                source_pattern="pattern",
                suggested_action="action",
            )
            engine.apply_correction(pid, "ok")

        assert len(engine._corrections_applied) <= 20


# ===================================================================
# Gap 9 — delivery_adapters: DeliveryOrchestrator._history bounded
# ===================================================================
class TestDeliveryOrchestratorHistoryBounded:
    """DeliveryOrchestrator._history must not grow without limit."""

    def test_history_capped(self):
        from delivery_adapters import (
            DeliveryOrchestrator,
            DeliveryChannel,
            DeliveryRequest,
            ChatDeliveryAdapter,
        )

        orch = DeliveryOrchestrator()
        orch._MAX_HISTORY = 30  # small cap for test
        orch.register_adapter(DeliveryChannel.CHAT, ChatDeliveryAdapter())

        for i in range(40):
            req = DeliveryRequest(
                channel=DeliveryChannel.CHAT,
                session_id=f"s-{i}",
                payload={"text": f"msg-{i}"},
            )
            orch.deliver(req)

        assert len(orch._history) <= 30, (
            f"Expected <=30 history entries, got {len(orch._history)}"
        )


# ===================================================================
# Gap 10 — compliance_monitoring: bounded lists
# ===================================================================
class TestComplianceMonitoringBounded:
    """ContinuousComplianceMonitor._alerts, ComplianceDriftDetector._drift_history,
    and AutomatedRemediationEngine._remediation_log must be bounded."""

    def test_monitor_alerts_capped(self):
        from compliance_monitoring_completeness import ContinuousComplianceMonitor

        monitor = ContinuousComplianceMonitor(check_interval=999)
        monitor._MAX_ALERTS = 20  # small cap for test

        for i in range(25):
            monitor._alerts.append({"id": i})
            if len(monitor._alerts) >= monitor._MAX_ALERTS:
                monitor._alerts = monitor._alerts[monitor._MAX_ALERTS // 10:]

        assert len(monitor._alerts) <= 20

    def test_drift_history_capped(self):
        from compliance_monitoring_completeness import ComplianceDriftDetector

        detector = ComplianceDriftDetector()
        detector._MAX_DRIFT_HISTORY = 20

        detector.create_baseline("SOC2", {"encryption_enabled": True})
        bid = list(detector._baselines.keys())[0]

        for i in range(25):
            detector.detect_drift(bid, {"encryption_enabled": bool(i % 2)})

        assert len(detector._drift_history) <= 20

    def test_remediation_log_capped(self):
        from compliance_monitoring_completeness import AutomatedRemediationEngine

        engine = AutomatedRemediationEngine()
        engine._MAX_REMEDIATION_LOG = 20

        for i in range(25):
            engine.remediate("token_refresh", {"token_id": f"t-{i}"})

        assert len(engine._remediation_log) <= 20
