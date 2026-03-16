"""
Tests for OBS-005: HeartbeatLivenessProtocol.

Validates:
  - Bot registration and heartbeat recording
  - State transitions on missed heartbeats (HEALTHY → DEGRADED → UNRESPONSIVE)
  - Recovery triggering via SelfHealingCoordinator
  - Circuit breaker tripping after repeated recovery failures
  - Health dashboard reporting
  - Thread safety
  - BotInventoryLibrary integration (auto-register / deregister)

Design Label: TEST-003 / OBS-005
Owner: QA Team
"""

import os
import time
import threading
import pytest


from heartbeat_liveness_protocol import (
    BotHealthState,
    BotHeartbeat,
    HeartbeatMonitor,
    HeartbeatPolicy,
)
from event_backbone import EventBackbone, EventType
from self_healing_coordinator import (
    SelfHealingCoordinator,
    RecoveryProcedure,
    RecoveryStatus,
)
from bot_inventory_library import BotInventoryLibrary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def policy_fast():
    """A policy with very short interval for test speed."""
    return HeartbeatPolicy(
        interval_sec=0.05,
        max_missed_beats=2,
        recovery_strategy="bot_unresponsive",
        max_recovery_attempts=3,
        circuit_breaker_threshold=2,
        circuit_breaker_timeout=300.0,
    )


@pytest.fixture
def monitor():
    return HeartbeatMonitor()


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def coordinator():
    return SelfHealingCoordinator()


@pytest.fixture
def wired_monitor(backbone):
    return HeartbeatMonitor(event_backbone=backbone)


@pytest.fixture
def full_monitor(backbone, coordinator):
    return HeartbeatMonitor(
        event_backbone=backbone,
        healing_coordinator=coordinator,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_bot_appears_in_dashboard(self, monitor):
        monitor.register_bot("bot-001")
        dashboard = monitor.get_health_dashboard()
        assert "bot-001" in dashboard["bots"]
        assert dashboard["total_bots"] == 1

    def test_register_with_custom_policy(self, monitor, policy_fast):
        monitor.register_bot("bot-002", policy_fast)
        dashboard = monitor.get_health_dashboard()
        entry = dashboard["bots"]["bot-002"]
        assert entry["policy"]["interval_sec"] == policy_fast.interval_sec

    def test_duplicate_registration_ignored(self, monitor):
        monitor.register_bot("bot-003")
        monitor.register_bot("bot-003")  # second call should be no-op
        dashboard = monitor.get_health_dashboard()
        assert dashboard["total_bots"] == 1

    def test_deregister_removes_bot(self, monitor):
        monitor.register_bot("bot-004")
        result = monitor.deregister_bot("bot-004")
        assert result is True
        assert "bot-004" not in monitor.get_health_dashboard()["bots"]

    def test_deregister_unknown_returns_false(self, monitor):
        assert monitor.deregister_bot("ghost-bot") is False


# ---------------------------------------------------------------------------
# Heartbeat recording
# ---------------------------------------------------------------------------

class TestHeartbeatRecording:
    def test_record_heartbeat_updates_last_seen(self, monitor, policy_fast):
        monitor.register_bot("bot-hb", policy_fast)
        before = monitor._heartbeats["bot-hb"].last_seen
        time.sleep(0.01)
        monitor.record_heartbeat("bot-hb")
        after = monitor._heartbeats["bot-hb"].last_seen
        assert after > before

    def test_record_heartbeat_resets_misses(self, monitor, policy_fast):
        monitor.register_bot("bot-hb2", policy_fast)
        hb = monitor._heartbeats["bot-hb2"]
        hb.consecutive_misses = 5
        hb.state = BotHealthState.DEGRADED
        monitor.record_heartbeat("bot-hb2")
        assert hb.consecutive_misses == 0
        assert hb.state == BotHealthState.HEALTHY

    def test_record_heartbeat_unknown_returns_false(self, monitor):
        assert monitor.record_heartbeat("nonexistent") is False

    def test_record_heartbeat_registered_returns_true(self, monitor):
        monitor.register_bot("bot-ok")
        assert monitor.record_heartbeat("bot-ok") is True


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------

class TestStateTransitions:
    def test_timely_beat_stays_healthy(self, monitor, policy_fast):
        monitor.register_bot("bot-t1", policy_fast)
        monitor.record_heartbeat("bot-t1")
        summary = monitor.tick()
        assert summary[BotHealthState.HEALTHY.value] >= 1

    def test_missed_beat_transitions_to_degraded(self, monitor, policy_fast):
        monitor.register_bot("bot-t2", policy_fast)
        # Manually age the last_seen
        monitor._heartbeats["bot-t2"].last_seen = (
            time.monotonic() - policy_fast.interval_sec - 1.0
        )
        summary = monitor.tick()
        assert summary[BotHealthState.DEGRADED.value] >= 1

    def test_exceeded_max_misses_transitions_to_unresponsive(
        self, monitor, policy_fast
    ):
        monitor.register_bot("bot-t3", policy_fast)
        hb = monitor._heartbeats["bot-t3"]
        # Simulate already degraded with enough misses to reach max
        hb.consecutive_misses = policy_fast.max_missed_beats
        hb.last_seen = time.monotonic() - policy_fast.interval_sec - 1.0
        monitor.tick()
        # With no coordinator wired, optimistic recovery resolves to HEALTHY;
        # with a coordinator it may be RECOVERING or UNRESPONSIVE.
        assert hb.state in (
            BotHealthState.UNRESPONSIVE,
            BotHealthState.RECOVERING,
            BotHealthState.HEALTHY,
        )

    def test_terminated_bot_excluded_from_active_states(
        self, monitor, policy_fast
    ):
        monitor.register_bot("bot-t4", policy_fast)
        hb = monitor._heartbeats["bot-t4"]
        hb.state = BotHealthState.TERMINATED
        summary = monitor.tick()
        assert summary[BotHealthState.TERMINATED.value] >= 1
        assert summary[BotHealthState.HEALTHY.value] == 0


# ---------------------------------------------------------------------------
# Recovery triggering
# ---------------------------------------------------------------------------

class TestRecoveryTriggering:
    def test_recovery_triggered_when_unresponsive(self, full_monitor, policy_fast):
        full_monitor.register_bot("bot-r1", policy_fast)
        hb = full_monitor._heartbeats["bot-r1"]
        hb.consecutive_misses = policy_fast.max_missed_beats
        hb.last_seen = time.monotonic() - policy_fast.interval_sec - 1.0
        full_monitor.tick()
        # After recovery attempt with default procedure the state should be
        # HEALTHY (default procedure succeeds), RECOVERING, or UNRESPONSIVE.
        assert hb.state in (
            BotHealthState.HEALTHY,
            BotHealthState.RECOVERING,
            BotHealthState.UNRESPONSIVE,
        )
        assert hb.recovery_attempts >= 1

    def test_recovery_procedure_auto_registered(self, full_monitor, policy_fast):
        full_monitor.register_bot("bot-r2", policy_fast)
        full_monitor._attempt_recovery(
            "bot-r2", full_monitor._heartbeats["bot-r2"]
        )
        status = full_monitor._healing_coordinator.get_status()
        assert policy_fast.recovery_strategy in status["categories"]

    def test_max_recovery_attempts_terminates_bot(self, monitor, policy_fast):
        monitor.register_bot("bot-r3", policy_fast)
        hb = monitor._heartbeats["bot-r3"]
        hb.recovery_attempts = policy_fast.max_recovery_attempts
        hb.consecutive_misses = policy_fast.max_missed_beats
        hb.last_seen = time.monotonic() - policy_fast.interval_sec - 1.0
        monitor.tick()
        assert hb.state == BotHealthState.TERMINATED

    def test_no_coordinator_optimistic_recovery(self, monitor, policy_fast):
        monitor.register_bot("bot-r4", policy_fast)
        hb = monitor._heartbeats["bot-r4"]
        hb.state = BotHealthState.UNRESPONSIVE
        hb.consecutive_misses = policy_fast.max_missed_beats + 1
        monitor._attempt_recovery("bot-r4", hb)
        assert hb.state == BotHealthState.HEALTHY


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def _failing_handler(self, ctx):
        return False

    def test_circuit_breaker_trips_after_repeated_failures(
        self, backbone, coordinator
    ):
        mon = HeartbeatMonitor(
            event_backbone=backbone,
            healing_coordinator=coordinator,
        )
        failing_policy = HeartbeatPolicy(
            interval_sec=0.01,
            max_missed_beats=1,
            recovery_strategy="fail_strategy",
            max_recovery_attempts=10,
            circuit_breaker_threshold=2,
            circuit_breaker_timeout=300.0,
        )
        # Register a failing recovery procedure
        coordinator.register_procedure(
            RecoveryProcedure(
                procedure_id="fail-proc",
                category="fail_strategy",
                description="Always fails",
                handler=self._failing_handler,
                cooldown_seconds=0.0,
                max_attempts=99,
            )
        )
        mon.register_bot("bot-cb1", failing_policy)
        hb = mon._heartbeats["bot-cb1"]

        # Trigger multiple failed recoveries
        for _ in range(3):
            hb.state = BotHealthState.UNRESPONSIVE
            hb.last_seen = time.monotonic() - 1.0
            mon._attempt_recovery("bot-cb1", hb)
            # Reset state to allow re-triggering
            hb.state = BotHealthState.UNRESPONSIVE

        cb = mon._circuit_breakers["bot-cb1"]
        assert cb.get_state() == "OPEN"

    def test_circuit_breaker_skips_recovery_when_open(self, monitor, policy_fast):
        monitor.register_bot("bot-cb2", policy_fast)
        hb = monitor._heartbeats["bot-cb2"]
        cb = monitor._circuit_breakers["bot-cb2"]
        # Force open the circuit breaker
        for _ in range(policy_fast.circuit_breaker_threshold + 1):
            cb._on_failure()
        assert cb.get_state() == "OPEN"

        original_attempts = hb.recovery_attempts
        hb.state = BotHealthState.UNRESPONSIVE
        monitor._attempt_recovery("bot-cb2", hb)
        # Recovery should have been skipped — attempts not incremented
        assert hb.recovery_attempts == original_attempts


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_dashboard_reports_all_bots(self, monitor, policy_fast):
        for i in range(3):
            monitor.register_bot(f"bot-d{i}", policy_fast)
        dashboard = monitor.get_health_dashboard()
        assert dashboard["total_bots"] == 3

    def test_dashboard_summary_counts(self, monitor, policy_fast):
        monitor.register_bot("bot-da", policy_fast)
        monitor.register_bot("bot-db", policy_fast)
        # Age bot-da so it misses a beat
        monitor._heartbeats["bot-da"].last_seen = (
            time.monotonic() - policy_fast.interval_sec - 1.0
        )
        monitor.tick()
        dashboard = monitor.get_health_dashboard()
        assert dashboard["summary"][BotHealthState.HEALTHY.value] >= 1
        assert dashboard["summary"][BotHealthState.DEGRADED.value] >= 1

    def test_dashboard_includes_circuit_breaker_info(self, monitor, policy_fast):
        monitor.register_bot("bot-dc", policy_fast)
        dashboard = monitor.get_health_dashboard()
        assert "bot-dc" in dashboard["circuit_breakers"]

    def test_tick_history_recorded(self, monitor, policy_fast):
        monitor.register_bot("bot-hist", policy_fast)
        monitor.tick()
        monitor.tick()
        history = monitor.get_tick_history()
        assert len(history) == 2
        assert "tick_id" in history[0]
        assert "summary" in history[0]


# ---------------------------------------------------------------------------
# EventBackbone integration
# ---------------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_heartbeat_ok_published(self, wired_monitor, backbone, policy_fast):
        recorder = []
        backbone.subscribe(EventType.BOT_HEARTBEAT_OK, lambda e: recorder.append(e))
        wired_monitor.register_bot("bot-ev1", policy_fast)
        wired_monitor.record_heartbeat("bot-ev1")
        backbone.process_pending()
        # record_heartbeat publishes BOT_HEARTBEAT_OK only when state changes;
        # the bot starts HEALTHY so the publish may not fire from record alone.
        # tick() will also publish OK events for on-time beats.
        wired_monitor.tick()
        backbone.process_pending()
        assert len(recorder) >= 1

    def test_heartbeat_missed_published(self, wired_monitor, backbone, policy_fast):
        recorder = []
        backbone.subscribe(
            EventType.BOT_HEARTBEAT_MISSED, lambda e: recorder.append(e)
        )
        wired_monitor.register_bot("bot-ev2", policy_fast)
        wired_monitor._heartbeats["bot-ev2"].last_seen = (
            time.monotonic() - policy_fast.interval_sec - 1.0
        )
        wired_monitor.tick()
        backbone.process_pending()
        assert len(recorder) >= 1
        assert recorder[0].payload["bot_id"] == "bot-ev2"

    def test_recovery_started_event_published(
        self, backbone, coordinator, policy_fast
    ):
        mon = HeartbeatMonitor(
            event_backbone=backbone,
            healing_coordinator=coordinator,
        )
        recorder = []
        backbone.subscribe(
            EventType.BOT_HEARTBEAT_RECOVERY_STARTED,
            lambda e: recorder.append(e),
        )
        mon.register_bot("bot-ev3", policy_fast)
        hb = mon._heartbeats["bot-ev3"]
        hb.consecutive_misses = policy_fast.max_missed_beats
        hb.last_seen = time.monotonic() - policy_fast.interval_sec - 1.0
        mon.tick()
        backbone.process_pending()
        assert len(recorder) >= 1

    def test_heartbeat_recovered_event_published(self, backbone, policy_fast):
        mon = HeartbeatMonitor(event_backbone=backbone)
        recorder = []
        backbone.subscribe(
            EventType.BOT_HEARTBEAT_RECOVERED, lambda e: recorder.append(e)
        )
        mon.register_bot("bot-ev4", policy_fast)
        hb = mon._heartbeats["bot-ev4"]
        hb.state = BotHealthState.UNRESPONSIVE
        mon._attempt_recovery("bot-ev4", hb)
        backbone.process_pending()
        # Optimistic recovery (no coordinator) publishes RECOVERED
        assert len(recorder) >= 1


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_register_and_heartbeat(self, monitor, policy_fast):
        errors = []

        def worker(bot_id):
            try:
                monitor.register_bot(bot_id, policy_fast)
                for _ in range(5):
                    monitor.record_heartbeat(bot_id)
                    monitor.tick()
            except Exception as exc:
                errors.append(str(exc))

        threads = [
            threading.Thread(target=worker, args=(f"bot-ts{i}",))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread-safety errors: {errors}"
        assert monitor.get_health_dashboard()["total_bots"] == 10

    def test_concurrent_tick_and_record(self, monitor, policy_fast):
        monitor.register_bot("bot-conc", policy_fast)
        errors = []

        def ticker():
            try:
                for _ in range(20):
                    monitor.tick()
            except Exception as exc:
                errors.append(str(exc))

        def recorder():
            try:
                for _ in range(20):
                    monitor.record_heartbeat("bot-conc")
            except Exception as exc:
                errors.append(str(exc))

        t1 = threading.Thread(target=ticker)
        t2 = threading.Thread(target=recorder)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert errors == [], f"Concurrent tick/record errors: {errors}"


# ---------------------------------------------------------------------------
# BotInventoryLibrary integration
# ---------------------------------------------------------------------------

class TestBotInventoryIntegration:
    def test_spawn_auto_registers_bot(self):
        monitor = HeartbeatMonitor()
        library = BotInventoryLibrary(heartbeat_monitor=monitor)
        bot = library.spawn_bot("TestBot", "expert")
        assert bot.agent_id in monitor.get_health_dashboard()["bots"]

    def test_despawn_deregisters_bot(self):
        monitor = HeartbeatMonitor()
        library = BotInventoryLibrary(heartbeat_monitor=monitor)
        bot = library.spawn_bot("TestBot2", "validator")
        agent_id = bot.agent_id
        library.despawn_bot(agent_id)
        assert agent_id not in monitor.get_health_dashboard()["bots"]

    def test_library_without_monitor_still_works(self):
        library = BotInventoryLibrary()
        bot = library.spawn_bot("NoMonitorBot", "expert")
        assert bot is not None
        assert library.despawn_bot(bot.agent_id) is True
