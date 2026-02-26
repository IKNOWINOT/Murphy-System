"""Tests for the Compliance Monitoring Completeness module."""

import unittest
import time
import threading
from src.compliance_monitoring_completeness import (
    ContinuousComplianceMonitor,
    ComplianceDriftDetector,
    AutomatedRemediationEngine,
    ComplianceReportGenerator,
    RegulationChangeTracker,
    ComplianceCompletenessOrchestrator,
    ComplianceSensor,
    DriftBaseline,
    DriftSeverity,
    MonitorStatus,
    RemediationAction,
    RegulationImpact,
)


# -----------------------------------------------------------------------
# ContinuousComplianceMonitor
# -----------------------------------------------------------------------

class TestContinuousComplianceMonitor(unittest.TestCase):

    def setUp(self):
        self.monitor = ContinuousComplianceMonitor(check_interval=0.1)

    def test_default_sensors_registered(self):
        status = self.monitor.get_status()
        self.assertGreaterEqual(status["total_sensors"], 8)

    def test_register_sensor(self):
        sensor = ComplianceSensor(
            sensor_id="custom-1", framework="gdpr",
            control_id="C-01", description="Custom sensor"
        )
        sid = self.monitor.register_sensor(sensor)
        self.assertEqual(sid, "custom-1")
        info = self.monitor.get_sensor("custom-1")
        self.assertEqual(info["framework"], "gdpr")

    def test_unregister_sensor(self):
        result = self.monitor.unregister_sensor("gdpr-data-retention")
        self.assertEqual(result["status"], "removed")
        result2 = self.monitor.unregister_sensor("nonexistent")
        self.assertEqual(result2["status"], "not_found")

    def test_get_sensor_not_found(self):
        result = self.monitor.get_sensor("no-such-sensor")
        self.assertEqual(result["status"], "not_found")

    def test_run_sensor_check_default_pass(self):
        result = self.monitor.run_sensor_check("soc2-access-control")
        self.assertEqual(result["status"], "checked")
        self.assertTrue(result["compliant"])

    def test_run_sensor_check_not_found(self):
        result = self.monitor.run_sensor_check("nonexistent")
        self.assertEqual(result["status"], "error")

    def test_run_sensor_check_disabled(self):
        sensor = ComplianceSensor(
            sensor_id="disabled-1", framework="soc2",
            control_id="D-01", description="Disabled", enabled=False
        )
        self.monitor.register_sensor(sensor)
        result = self.monitor.run_sensor_check("disabled-1")
        self.assertEqual(result["status"], "skipped")

    def test_run_sensor_check_with_failing_fn(self):
        def fail_check(cfg):
            return {"compliant": False, "reason": "test failure"}

        sensor = ComplianceSensor(
            sensor_id="fail-1", framework="hipaa",
            control_id="F-01", description="Failing sensor",
            check_fn=fail_check
        )
        self.monitor.register_sensor(sensor)
        result = self.monitor.run_sensor_check("fail-1")
        self.assertFalse(result["compliant"])
        alerts = self.monitor.get_alerts()
        self.assertGreater(alerts["total_alerts"], 0)

    def test_run_sensor_check_with_exception(self):
        def error_check(cfg):
            raise RuntimeError("boom")

        sensor = ComplianceSensor(
            sensor_id="err-1", framework="pci_dss",
            control_id="E-01", description="Error sensor",
            check_fn=error_check
        )
        self.monitor.register_sensor(sensor)
        result = self.monitor.run_sensor_check("err-1")
        self.assertFalse(result["compliant"])

    def test_run_all_checks(self):
        result = self.monitor.run_all_checks()
        self.assertEqual(result["status"], "complete")
        self.assertGreaterEqual(result["total_checked"], 8)
        self.assertIn("compliance_rate", result)

    def test_get_alerts_with_filter(self):
        def fail(cfg):
            return {"compliant": False}

        sensor = ComplianceSensor(
            sensor_id="alert-filter-1", framework="gdpr",
            control_id="AF-01", description="Filter test", check_fn=fail
        )
        self.monitor.register_sensor(sensor)
        self.monitor.run_sensor_check("alert-filter-1")
        gdpr_alerts = self.monitor.get_alerts(framework="gdpr")
        self.assertGreater(gdpr_alerts["total_alerts"], 0)

    def test_clear_alerts(self):
        self.monitor.run_all_checks()
        result = self.monitor.clear_alerts()
        self.assertEqual(result["status"], "cleared")
        self.assertEqual(self.monitor.get_alerts()["total_alerts"], 0)

    def test_start_and_stop(self):
        start_result = self.monitor.start()
        self.assertEqual(start_result["status"], "started")
        self.assertEqual(self.monitor.get_status()["monitor_status"], "running")
        # Starting again should say already running
        self.assertEqual(self.monitor.start()["status"], "already_running")
        stop_result = self.monitor.stop()
        self.assertEqual(stop_result["status"], "stopped")
        # Stopping again should say not running
        self.assertEqual(self.monitor.stop()["status"], "not_running")

    def test_monitor_loop_runs_checks(self):
        self.monitor.start()
        time.sleep(0.3)
        self.monitor.stop()
        self.assertGreater(self.monitor.get_status()["check_count"], 0)


# -----------------------------------------------------------------------
# ComplianceDriftDetector
# -----------------------------------------------------------------------

class TestComplianceDriftDetector(unittest.TestCase):

    def setUp(self):
        self.detector = ComplianceDriftDetector()

    def test_create_baseline(self):
        result = self.detector.create_baseline(
            "gdpr", {"encryption_enabled": True, "retention_days": 90},
            baseline_id="b1"
        )
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["baseline_id"], "b1")

    def test_get_baseline(self):
        self.detector.create_baseline("soc2", {"audit_logging": True}, baseline_id="b2")
        result = self.detector.get_baseline("b2")
        self.assertEqual(result["framework"], "soc2")

    def test_get_baseline_not_found(self):
        result = self.detector.get_baseline("nope")
        self.assertEqual(result["status"], "not_found")

    def test_detect_drift_no_changes(self):
        snap = {"encryption_enabled": True, "retention": 90}
        self.detector.create_baseline("gdpr", snap, baseline_id="b3")
        result = self.detector.detect_drift("b3", snap)
        self.assertFalse(result["has_drift"])
        self.assertEqual(result["drifts_detected"], 0)

    def test_detect_drift_with_changes(self):
        self.detector.create_baseline(
            "hipaa", {"encryption_enabled": True, "phi_protected": True},
            baseline_id="b4"
        )
        current = {"encryption_enabled": False, "phi_protected": True}
        result = self.detector.detect_drift("b4", current)
        self.assertTrue(result["has_drift"])
        self.assertEqual(result["drifts_detected"], 1)
        self.assertEqual(result["drifts"][0]["severity"], "critical")

    def test_detect_drift_added_key(self):
        self.detector.create_baseline("soc2", {"a": 1}, baseline_id="b5")
        result = self.detector.detect_drift("b5", {"a": 1, "b": 2})
        self.assertTrue(result["has_drift"])
        self.assertEqual(result["drifts"][0]["drift_type"], "added")

    def test_detect_drift_removed_key(self):
        self.detector.create_baseline("soc2", {"a": 1, "b": 2}, baseline_id="b6")
        result = self.detector.detect_drift("b6", {"a": 1})
        self.assertTrue(result["has_drift"])
        self.assertEqual(result["drifts"][0]["drift_type"], "removed")

    def test_detect_drift_baseline_not_found(self):
        result = self.detector.detect_drift("nonexistent", {})
        self.assertEqual(result["status"], "error")

    def test_drift_history(self):
        self.detector.create_baseline("gdpr", {"x": 1}, baseline_id="bh")
        self.detector.detect_drift("bh", {"x": 2})
        history = self.detector.get_drift_history(baseline_id="bh")
        self.assertEqual(history["total_records"], 1)

    def test_compute_drift_score(self):
        self.detector.create_baseline("pci", {"a": 1, "b": 2, "c": 3}, baseline_id="bs")
        result = self.detector.compute_drift_score("bs", {"a": 1, "b": 2, "c": 3})
        self.assertEqual(result["drift_score"], 1.0)
        self.assertTrue(result["stable"])

    def test_compute_drift_score_with_drift(self):
        self.detector.create_baseline("pci", {"a": 1, "b": 2}, baseline_id="bs2")
        result = self.detector.compute_drift_score("bs2", {"a": 1, "b": 99})
        self.assertLess(result["drift_score"], 1.0)


# -----------------------------------------------------------------------
# AutomatedRemediationEngine
# -----------------------------------------------------------------------

class TestAutomatedRemediationEngine(unittest.TestCase):

    def setUp(self):
        self.engine = AutomatedRemediationEngine()

    def test_remediate_token_refresh(self):
        result = self.engine.remediate("token_refresh")
        self.assertTrue(result["success"])

    def test_remediate_enable_encryption(self):
        result = self.engine.remediate("enable_encryption")
        self.assertTrue(result["success"])

    def test_remediate_unknown_action(self):
        result = self.engine.remediate("unknown_action")
        self.assertEqual(result["status"], "error")

    def test_auto_remediate_violations(self):
        violations = [
            {"type": "expired_token", "resource": "api-key-1"},
            {"type": "missing_encryption", "resource": "storage-1"},
            {"type": "unknown_violation_type"},
        ]
        result = self.engine.auto_remediate_violations(violations)
        self.assertEqual(result["total_violations"], 3)
        self.assertEqual(result["remediated"], 2)

    def test_register_custom_handler(self):
        self.engine.register_handler("custom_action", lambda ctx: {"success": True})
        result = self.engine.remediate("custom_action")
        self.assertTrue(result["success"])

    def test_remediation_log(self):
        self.engine.remediate("token_refresh")
        self.engine.remediate("enable_encryption")
        log = self.engine.get_remediation_log()
        self.assertEqual(log["total_entries"], 2)

    def test_remediation_log_filter(self):
        self.engine.remediate("token_refresh")
        self.engine.remediate("enable_encryption")
        log = self.engine.get_remediation_log(action_filter="token_refresh")
        self.assertEqual(log["total_entries"], 1)

    def test_status(self):
        self.engine.remediate("rotate_credentials")
        status = self.engine.get_status()
        self.assertEqual(status["total_remediations"], 1)
        self.assertEqual(status["successful"], 1)
        self.assertIn("token_refresh", status["registered_handlers"])

    def test_handler_exception(self):
        def bad_handler(ctx):
            raise ValueError("handler error")
        self.engine.register_handler("bad", bad_handler)
        result = self.engine.remediate("bad")
        self.assertFalse(result["success"])


# -----------------------------------------------------------------------
# ComplianceReportGenerator
# -----------------------------------------------------------------------

class TestComplianceReportGenerator(unittest.TestCase):

    def setUp(self):
        self.reporter = ComplianceReportGenerator()

    def test_record_evidence(self):
        result = self.reporter.record_evidence(
            "gdpr", "GDPR-DR-01", "log", {"message": "Retention check passed"}
        )
        self.assertIn("evidence_id", result)

    def test_get_evidence_filtered(self):
        self.reporter.record_evidence("gdpr", "C-01", "log", {})
        self.reporter.record_evidence("soc2", "C-02", "scan", {})
        result = self.reporter.get_evidence(framework="gdpr")
        self.assertEqual(result["total_evidence"], 1)

    def test_compute_effectiveness_all_pass(self):
        controls = [{"compliant": True}, {"compliant": True}]
        result = self.reporter.compute_control_effectiveness(controls)
        self.assertEqual(result["score"], 1.0)
        self.assertEqual(result["rating"], "excellent")

    def test_compute_effectiveness_empty(self):
        result = self.reporter.compute_control_effectiveness([])
        self.assertEqual(result["score"], 0.0)

    def test_generate_report(self):
        controls = [
            {"control_id": "C-01", "compliant": True, "severity": "medium"},
            {"control_id": "C-02", "compliant": False, "severity": "critical"},
        ]
        report = self.reporter.generate_report("Q1 GDPR", "gdpr", controls)
        self.assertIn("report_id", report)
        self.assertEqual(report["framework"], "gdpr")
        self.assertFalse(report["summary"]["audit_ready"])

    def test_generate_report_audit_ready(self):
        controls = [{"control_id": f"C-{i}", "compliant": True, "severity": "low"}
                     for i in range(20)]
        report = self.reporter.generate_report("Audit", "soc2", controls)
        self.assertTrue(report["summary"]["audit_ready"])

    def test_get_report(self):
        controls = [{"control_id": "C-01", "compliant": True}]
        report = self.reporter.generate_report("Test", "hipaa", controls)
        fetched = self.reporter.get_report(report["report_id"])
        self.assertEqual(fetched["report_name"], "Test")

    def test_get_report_not_found(self):
        result = self.reporter.get_report("nonexistent")
        self.assertEqual(result["status"], "not_found")

    def test_list_reports(self):
        controls = [{"control_id": "C-01", "compliant": True}]
        self.reporter.generate_report("R1", "gdpr", controls)
        self.reporter.generate_report("R2", "soc2", controls)
        result = self.reporter.list_reports()
        self.assertEqual(result["total_reports"], 2)

    def test_list_reports_filtered(self):
        controls = [{"control_id": "C-01", "compliant": True}]
        self.reporter.generate_report("R1", "gdpr", controls)
        self.reporter.generate_report("R2", "soc2", controls)
        result = self.reporter.list_reports(framework="gdpr")
        self.assertEqual(result["total_reports"], 1)

    def test_status(self):
        self.reporter.record_evidence("gdpr", "C-01", "log", {})
        status = self.reporter.get_status()
        self.assertEqual(status["total_evidence"], 1)


# -----------------------------------------------------------------------
# RegulationChangeTracker
# -----------------------------------------------------------------------

class TestRegulationChangeTracker(unittest.TestCase):

    def setUp(self):
        self.tracker = RegulationChangeTracker()

    def test_register_update(self):
        result = self.tracker.register_update(
            "gdpr", "New consent requirements", "breaking",
            affected_controls=["GDPR-CN-01", "GDPR-CN-02"]
        )
        self.assertEqual(result["status"], "registered")
        self.assertEqual(result["impact"], "breaking")

    def test_register_update_invalid_impact(self):
        result = self.tracker.register_update("soc2", "Minor change", "unknown_impact")
        self.assertEqual(result["impact"], "informational")

    def test_get_update(self):
        reg = self.tracker.register_update("hipaa", "PHI rule change", "significant")
        fetched = self.tracker.get_update(reg["update_id"])
        self.assertEqual(fetched["regulation"], "hipaa")

    def test_get_update_not_found(self):
        result = self.tracker.get_update("nonexistent")
        self.assertEqual(result["status"], "not_found")

    def test_assess_impact(self):
        reg = self.tracker.register_update(
            "gdpr", "Update", "significant",
            affected_controls=["C-01", "C-02", "C-03"]
        )
        result = self.tracker.assess_impact(
            reg["update_id"], current_controls=["C-01", "C-02"]
        )
        self.assertEqual(len(result["controls_in_scope"]), 2)
        self.assertEqual(len(result["controls_not_covered"]), 1)
        self.assertTrue(result["action_required"])

    def test_assess_impact_not_found(self):
        result = self.tracker.assess_impact("nope", [])
        self.assertEqual(result["status"], "error")

    def test_list_updates(self):
        self.tracker.register_update("gdpr", "U1", "minor")
        self.tracker.register_update("soc2", "U2", "minor")
        result = self.tracker.list_updates()
        self.assertEqual(result["total_updates"], 2)

    def test_list_updates_filtered(self):
        self.tracker.register_update("gdpr", "U1", "minor")
        self.tracker.register_update("soc2", "U2", "minor")
        result = self.tracker.list_updates(regulation="gdpr")
        self.assertEqual(result["total_updates"], 1)

    def test_get_pending_updates(self):
        self.tracker.register_update("gdpr", "Pending", "minor")
        result = self.tracker.get_pending_updates()
        self.assertEqual(result["total_pending"], 1)

    def test_impact_history(self):
        reg = self.tracker.register_update(
            "gdpr", "Test", "minor", affected_controls=["C-01"]
        )
        self.tracker.assess_impact(reg["update_id"], ["C-01"])
        history = self.tracker.get_impact_history()
        self.assertEqual(history["total_assessments"], 1)

    def test_status(self):
        self.tracker.register_update("gdpr", "S", "minor")
        status = self.tracker.get_status()
        self.assertEqual(status["total_updates"], 1)
        self.assertEqual(status["pending"], 1)


# -----------------------------------------------------------------------
# ComplianceCompletenessOrchestrator
# -----------------------------------------------------------------------

class TestComplianceCompletenessOrchestrator(unittest.TestCase):

    def setUp(self):
        self.orch = ComplianceCompletenessOrchestrator(check_interval=0.1)

    def test_full_compliance_check(self):
        result = self.orch.full_compliance_check()
        self.assertEqual(result["status"], "complete")
        self.assertIn("monitor", result)

    def test_check_and_remediate(self):
        violations = [{"type": "expired_token"}]
        result = self.orch.check_and_remediate(violations=violations)
        self.assertIn("check", result)
        self.assertIsNotNone(result["remediation"])
        self.assertEqual(result["remediation"]["remediated"], 1)

    def test_check_and_remediate_no_violations(self):
        result = self.orch.check_and_remediate()
        self.assertIsNone(result["remediation"])

    def test_overall_status(self):
        result = self.orch.get_overall_status()
        self.assertIn("monitor", result)
        self.assertIn("remediation", result)
        self.assertIn("reporting", result)
        self.assertIn("regulation_tracker", result)

    def test_thread_safety(self):
        """Run concurrent operations to verify thread safety."""
        errors = []

        def worker():
            try:
                for _ in range(10):
                    self.orch.full_compliance_check()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
