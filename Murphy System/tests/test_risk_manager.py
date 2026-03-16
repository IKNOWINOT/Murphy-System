"""
Tests for Risk Manager component

Tests:
- Risk assessment functionality
- Risk monitoring and alerts
- Mitigation planning
- Risk manager integration
"""

import unittest
from datetime import datetime
from src.autonomous_systems import (
    RiskManager,
    RiskAssessment,
    RiskMonitor,
    MitigationPlanner,
    RiskFactor,
    RiskSeverity,
    RiskCategory,
    RiskAlert,
    MitigationAction
)


class TestRiskAssessment(unittest.TestCase):
    """Test RiskAssessment functionality"""

    def setUp(self):
        self.assessment = RiskAssessment()

    def test_assess_risk_critical(self):
        """Test assessing a critical risk"""
        risk_factor = self.assessment.assess_risk(
            factor_id="risk_1",
            factor_name="Security Vulnerability",
            category=RiskCategory.SECURITY,
            description="Critical security vulnerability",
            probability=0.9,
            impact=0.9,
            affected_components=["auth", "database"]
        )

        self.assertEqual(risk_factor.factor_id, "risk_1")
        self.assertEqual(risk_factor.severity, RiskSeverity.CRITICAL)
        self.assertEqual(risk_factor.risk_score, 0.81)  # 0.9 * 0.9
        self.assertEqual(risk_factor.mitigation_status, "none")

    def test_assess_risk_high(self):
        """Test assessing a high risk"""
        risk_factor = self.assessment.assess_risk(
            factor_id="risk_2",
            factor_name="Performance Degradation",
            category=RiskCategory.PERFORMANCE,
            description="Performance degradation",
            probability=0.7,
            impact=0.9
        )

        self.assertEqual(risk_factor.severity, RiskSeverity.HIGH)
        self.assertEqual(risk_factor.risk_score, 0.63)  # 0.7 * 0.9 = 0.63 (>= 0.6)

    def test_assess_risk_medium(self):
        """Test assessing a medium risk"""
        risk_factor = self.assessment.assess_risk(
            factor_id="risk_3",
            factor_name="Reliability Issue",
            category=RiskCategory.RELIABILITY,
            description="Reliability issue",
            probability=0.6,
            impact=0.7
        )

        self.assertEqual(risk_factor.severity, RiskSeverity.MEDIUM)
        self.assertEqual(risk_factor.risk_score, 0.42)  # 0.6 * 0.7 = 0.42 (>= 0.4)

    def test_assess_risk_low(self):
        """Test assessing a low risk"""
        risk_factor = self.assessment.assess_risk(
            factor_id="risk_4",
            factor_name="Minor Issue",
            category=RiskCategory.OPERATIONAL,
            description="Minor operational issue",
            probability=0.3,
            impact=0.7
        )

        self.assertEqual(risk_factor.severity, RiskSeverity.LOW)
        self.assertEqual(risk_factor.risk_score, 0.21)  # 0.3 * 0.7 = 0.21 (>= 0.2)

    def test_update_risk_probability(self):
        """Test updating risk probability"""
        # Create initial risk
        self.assessment.assess_risk(
            factor_id="risk_1",
            factor_name="Test Risk",
            category=RiskCategory.SECURITY,
            description="Test",
            probability=0.5,
            impact=0.8
        )

        # Update probability
        updated = self.assessment.update_risk(
            factor_id="risk_1",
            probability=0.3
        )

        self.assertEqual(updated.probability, 0.3)
        self.assertEqual(updated.risk_score, 0.24)  # 0.3 * 0.8

    def test_update_risk_mitigation_status(self):
        """Test updating risk mitigation status"""
        # Create initial risk
        self.assessment.assess_risk(
            factor_id="risk_1",
            factor_name="Test Risk",
            category=RiskCategory.SECURITY,
            description="Test",
            probability=0.5,
            impact=0.8
        )

        # Update mitigation status
        updated = self.assessment.update_risk(
            factor_id="risk_1",
            mitigation_status="in_progress",
            mitigation_actions=["Implement patch", "Monitor system"]
        )

        self.assertEqual(updated.mitigation_status, "in_progress")
        self.assertEqual(len(updated.mitigation_actions), 2)

    def test_get_risk_factor(self):
        """Test retrieving a risk factor"""
        self.assessment.assess_risk(
            factor_id="risk_1",
            factor_name="Test Risk",
            category=RiskCategory.SECURITY,
            description="Test",
            probability=0.5,
            impact=0.8
        )

        risk_factor = self.assessment.get_risk_factor("risk_1")

        self.assertIsNotNone(risk_factor)
        self.assertEqual(risk_factor.factor_id, "risk_1")

    def test_get_risks_by_severity(self):
        """Test retrieving risks by severity"""
        # Create risks of different severities
        self.assessment.assess_risk(
            factor_id="risk_1",
            factor_name="Critical Risk",
            category=RiskCategory.SECURITY,
            description="Critical",
            probability=0.9,
            impact=0.9
        )

        self.assessment.assess_risk(
            factor_id="risk_2",
            factor_name="High Risk",
            category=RiskCategory.PERFORMANCE,
            description="High",
            probability=0.7,
            impact=0.9
        )

        self.assessment.assess_risk(
            factor_id="risk_3",
            factor_name="Medium Risk",
            category=RiskCategory.RELIABILITY,
            description="Medium",
            probability=0.6,
            impact=0.7
        )

        critical_risks = self.assessment.get_risks_by_severity(RiskSeverity.CRITICAL)
        high_risks = self.assessment.get_risks_by_severity(RiskSeverity.HIGH)

        self.assertEqual(len(critical_risks), 1)
        self.assertEqual(len(high_risks), 1)

    def test_get_high_priority_risks(self):
        """Test retrieving high priority risks"""
        # Create critical and high risks
        self.assessment.assess_risk(
            factor_id="risk_1",
            factor_name="Critical Risk",
            category=RiskCategory.SECURITY,
            description="Critical",
            probability=0.9,
            impact=0.9
        )

        self.assessment.assess_risk(
            factor_id="risk_2",
            factor_name="High Risk",
            category=RiskCategory.PERFORMANCE,
            description="High",
            probability=0.7,
            impact=0.9
        )

        self.assessment.assess_risk(
            factor_id="risk_3",
            factor_name="Low Risk",
            category=RiskCategory.OPERATIONAL,
            description="Low",
            probability=0.2,
            impact=0.3
        )

        high_priority = self.assessment.get_high_priority_risks()

        self.assertEqual(len(high_priority), 2)


class TestRiskMonitor(unittest.TestCase):
    """Test RiskMonitor functionality"""

    def setUp(self):
        self.assessment = RiskAssessment()
        self.monitor = RiskMonitor(self.assessment)

    def test_monitor_critical_risk(self):
        """Test monitoring critical risk generates alert"""
        # Assess critical risk
        self.assessment.assess_risk(
            factor_id="risk_1",
            factor_name="Critical Security Risk",
            category=RiskCategory.SECURITY,
            description="Critical",
            probability=0.9,
            impact=0.9
        )

        # Monitor risks
        alerts = self.monitor.monitor_risks()

        # Should generate alert for critical risk
        self.assertGreater(len(alerts), 0)
        self.assertEqual(alerts[0].severity, RiskSeverity.CRITICAL)

    def test_monitor_high_risk_no_mitigation(self):
        """Test monitoring high risk with no mitigation generates alert"""
        # Assess high risk
        self.assessment.assess_risk(
            factor_id="risk_1",
            factor_name="High Risk",
            category=RiskCategory.PERFORMANCE,
            description="High",
            probability=0.7,
            impact=0.9
        )

        # Monitor risks
        alerts = self.monitor.monitor_risks()

        # Should generate alert for high risk
        self.assertGreater(len(alerts), 0)

    def test_acknowledge_alert(self):
        """Test acknowledging an alert"""
        # Create risk
        self.assessment.assess_risk(
            factor_id="risk_1",
            factor_name="Critical Risk",
            category=RiskCategory.SECURITY,
            description="Critical",
            probability=0.9,
            impact=0.9
        )

        # Generate alerts
        alerts = self.monitor.monitor_risks()

        if alerts:
            # Acknowledge alert
            success = self.monitor.acknowledge_alert(alerts[0].alert_id, "admin")

            self.assertTrue(success)
            self.assertTrue(alerts[0].acknowledged)
            self.assertEqual(alerts[0].acknowledged_by, "admin")

    def test_resolve_alert(self):
        """Test resolving an alert"""
        # Create risk
        self.assessment.assess_risk(
            factor_id="risk_1",
            factor_name="Critical Risk",
            category=RiskCategory.SECURITY,
            description="Critical",
            probability=0.9,
            impact=0.9
        )

        # Generate alerts
        alerts = self.monitor.monitor_risks()

        if alerts:
            # Resolve alert
            success = self.monitor.resolve_alert(alerts[0].alert_id, "Risk mitigated")

            self.assertTrue(success)
            self.assertIsNotNone(alerts[0].resolved_at)

    def test_get_active_alerts(self):
        """Test getting active alerts"""
        # Create critical risk
        self.assessment.assess_risk(
            factor_id="risk_1",
            factor_name="Critical Risk",
            category=RiskCategory.SECURITY,
            description="Critical",
            probability=0.9,
            impact=0.9
        )

        # Generate alerts
        self.monitor.monitor_risks()

        # Get active alerts
        active = self.monitor.get_active_alerts()

        self.assertGreater(len(active), 0)


class TestMitigationPlanner(unittest.TestCase):
    """Test MitigationPlanner functionality"""

    def setUp(self):
        self.planner = MitigationPlanner()

    def test_create_mitigation_action(self):
        """Test creating a mitigation action"""
        action = self.planner.create_mitigation_action(
            risk_factor_id="risk_1",
            action_type="prevent",
            action_name="Implement Security Patch",
            description="Apply security patch to fix vulnerability",
            priority=1,
            estimated_cost=0.5,
            estimated_benefit=0.9
        )

        self.assertEqual(action.risk_factor_id, "risk_1")
        self.assertEqual(action.action_type, "prevent")
        self.assertEqual(action.status, "proposed")

    def test_get_actions_for_risk(self):
        """Test getting mitigation actions for a risk"""
        # Create multiple actions for same risk
        action1 = self.planner.create_mitigation_action(
            risk_factor_id="risk_1",
            action_type="prevent",
            action_name="Action 1",
            description="First action"
        )

        action2 = self.planner.create_mitigation_action(
            risk_factor_id="risk_1",
            action_type="reduce",
            action_name="Action 2",
            description="Second action"
        )

        # Get actions for risk
        actions = self.planner.get_actions_for_risk("risk_1")

        self.assertEqual(len(actions), 2)

    def test_approve_action(self):
        """Test approving a mitigation action"""
        action = self.planner.create_mitigation_action(
            risk_factor_id="risk_1",
            action_type="prevent",
            action_name="Test Action",
            description="Test"
        )

        # Approve action
        success = self.planner.approve_action(action.action_id)

        self.assertTrue(success)

        # Check status
        status = self.planner.get_action_status(action.action_id)
        self.assertEqual(status['status'], 'approved')

    def test_start_action(self):
        """Test starting a mitigation action"""
        action = self.planner.create_mitigation_action(
            risk_factor_id="risk_1",
            action_type="prevent",
            action_name="Test Action",
            description="Test"
        )

        # Start action
        success = self.planner.start_action(action.action_id, "developer_1")

        self.assertTrue(success)

        # Check status
        status = self.planner.get_action_status(action.action_id)
        self.assertEqual(status['status'], 'in_progress')
        self.assertEqual(status['assigned_to'], 'developer_1')

    def test_complete_action(self):
        """Test completing a mitigation action"""
        action = self.planner.create_mitigation_action(
            risk_factor_id="risk_1",
            action_type="prevent",
            action_name="Test Action",
            description="Test"
        )

        # Complete action
        success = self.planner.complete_action(action.action_id, 0.9)

        self.assertTrue(success)

        # Check status
        status = self.planner.get_action_status(action.action_id)
        self.assertEqual(status['status'], 'completed')
        self.assertEqual(status['effectiveness'], 0.9)


class TestRiskManager(unittest.TestCase):
    """Test RiskManager functionality"""

    def setUp(self):
        self.manager = RiskManager(enable_risk_management=True)

    def test_assess_risk(self):
        """Test assessing a risk through manager"""
        risk_factor = self.manager.assess_risk(
            factor_id="risk_1",
            factor_name="Security Risk",
            category=RiskCategory.SECURITY,
            description="Security vulnerability",
            probability=0.9,
            impact=0.9
        )

        self.assertIsNotNone(risk_factor)
        self.assertEqual(risk_factor.severity, RiskSeverity.CRITICAL)

    def test_get_risk_summary(self):
        """Test getting risk summary"""
        # Create multiple risks
        self.manager.assess_risk(
            factor_id="risk_1",
            factor_name="Critical Risk",
            category=RiskCategory.SECURITY,
            description="Critical",
            probability=0.9,
            impact=0.9
        )

        self.manager.assess_risk(
            factor_id="risk_2",
            factor_name="High Risk",
            category=RiskCategory.PERFORMANCE,
            description="High",
            probability=0.7,
            impact=0.8
        )

        summary = self.manager.get_risk_summary()

        self.assertEqual(summary['total_risks'], 2)
        self.assertIn('average_risk_score', summary)
        self.assertIn('by_severity', summary)
        self.assertIn('by_category', summary)

    def test_get_risk_matrix(self):
        """Test getting risk matrix"""
        # Create risks
        self.manager.assess_risk(
            factor_id="risk_1",
            factor_name="Critical Risk",
            category=RiskCategory.SECURITY,
            description="Critical",
            probability=0.8,
            impact=0.9
        )

        self.manager.assess_risk(
            factor_id="risk_2",
            factor_name="Low Risk",
            category=RiskCategory.OPERATIONAL,
            description="Low",
            probability=0.2,
            impact=0.3
        )

        matrix = self.manager.get_risk_matrix()

        self.assertIn('critical', matrix)
        self.assertIn('high', matrix)
        self.assertIn('medium', matrix)
        self.assertIn('low', matrix)
        self.assertEqual(matrix['critical'], 1)  # One critical risk
        self.assertEqual(matrix['low'], 1)  # One low risk

    def test_create_mitigation_action(self):
        """Test creating mitigation action through manager"""
        # First create a risk
        self.manager.assess_risk(
            factor_id="risk_1",
            factor_name="Security Risk",
            category=RiskCategory.SECURITY,
            description="Security",
            probability=0.8,
            impact=0.9
        )

        # Create mitigation action
        action = self.manager.create_mitigation_action(
            risk_factor_id="risk_1",
            action_type="prevent",
            action_name="Apply Patch",
            description="Apply security patch"
        )

        self.assertIsNotNone(action)
        self.assertEqual(action.risk_factor_id, "risk_1")

    def test_export_risk_data(self):
        """Test exporting risk data"""
        # Create risk
        self.manager.assess_risk(
            factor_id="risk_1",
            factor_name="Security Risk",
            category=RiskCategory.SECURITY,
            description="Security",
            probability=0.8,
            impact=0.9
        )

        # Export data
        exported = self.manager.export_risk_data()

        self.assertIn('summary', exported)
        self.assertIn('risk_factors', exported)
        self.assertIn('alerts', exported)
        self.assertIn('risk_matrix', exported)


if __name__ == '__main__':
    unittest.main()
