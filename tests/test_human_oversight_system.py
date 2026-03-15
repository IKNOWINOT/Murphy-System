"""
Tests for Human Oversight System component

Tests:
- Human oversight functionality
- Approval workflow
- Event logging
- Intervention tracking
"""

import unittest
from datetime import datetime, timedelta
from src.autonomous_systems import (
    HumanOversightSystem,
    ApprovalQueue,
    EventLogger,
    InterventionManager,
    ApprovalRequest,
    ApprovalStatus,
    OversightLevel,
    OversightEvent,
    Intervention
)


class TestApprovalQueue(unittest.TestCase):
    """Test ApprovalQueue functionality"""

    def setUp(self):
        self.queue = ApprovalQueue(max_queue_size=10)

    def test_submit_request(self):
        """Test submitting approval request"""
        request = ApprovalRequest(
            request_id="req_1",
            operation_type="deployment",
            operation_id="deploy_1",
            requester="admin",
            description="Deploy to production",
            risk_level="high",
            details={"environment": "production"},
            created_at=datetime.now()
        )

        request_id = self.queue.submit_request(request)

        self.assertEqual(request_id, "req_1")
        self.assertEqual(len(self.queue.get_pending_requests()), 1)

    def test_get_request(self):
        """Test getting approval request"""
        request = ApprovalRequest(
            request_id="req_1",
            operation_type="deployment",
            operation_id="deploy_1",
            requester="admin",
            description="Deploy to production",
            risk_level="high",
            details={},
            created_at=datetime.now()
        )

        self.queue.submit_request(request)
        retrieved = self.queue.get_request("req_1")

        self.assertEqual(retrieved.request_id, "req_1")
        self.assertEqual(retrieved.status, ApprovalStatus.PENDING)

    def test_approve_request(self):
        """Test approving a request"""
        request = ApprovalRequest(
            request_id="req_1",
            operation_type="deployment",
            operation_id="deploy_1",
            requester="admin",
            description="Deploy to production",
            risk_level="high",
            details={},
            created_at=datetime.now()
        )

        self.queue.submit_request(request)
        success = self.queue.approve_request("req_1", approved_by="manager")

        self.assertTrue(success)

        # Check status
        approved = self.queue.get_request("req_1")
        self.assertEqual(approved.status, ApprovalStatus.APPROVED)
        self.assertEqual(approved.approved_by, "manager")

    def test_reject_request(self):
        """Test rejecting a request"""
        request = ApprovalRequest(
            request_id="req_1",
            operation_type="deployment",
            operation_id="deploy_1",
            requester="admin",
            description="Deploy to production",
            risk_level="high",
            details={},
            created_at=datetime.now()
        )

        self.queue.submit_request(request)
        success = self.queue.reject_request("req_1", rejection_reason="Not ready", rejected_by="manager")

        self.assertTrue(success)

        # Check status
        rejected = self.queue.get_request("req_1")
        self.assertEqual(rejected.status, ApprovalStatus.REJECTED)

    def test_auto_approve_request(self):
        """Test auto-approving a request"""
        request = ApprovalRequest(
            request_id="req_1",
            operation_type="deployment",
            operation_id="deploy_1",
            requester="admin",
            description="Deploy to production",
            risk_level="low",
            details={},
            created_at=datetime.now()
        )

        self.queue.submit_request(request)
        success = self.queue.approve_request("req_1", approved_by="system", auto_approve=True, auto_approve_reason="Low risk operation")

        self.assertTrue(success)

        # Check status
        auto_approved = self.queue.get_request("req_1")
        self.assertEqual(auto_approved.status, ApprovalStatus.APPROVED)
        self.assertTrue(auto_approved.auto_approved)
        self.assertEqual(auto_approved.auto_approve_reason, "Low risk operation")

    def test_get_pending_requests(self):
        """Test getting pending requests"""
        # Submit multiple requests
        for i in range(5):
            request = ApprovalRequest(
                request_id=f"req_{i}",
                operation_type="deployment",
                operation_id=f"deploy_{i}",
                requester="admin",
                description=f"Deploy {i}",
                risk_level="medium",
                details={},
                created_at=datetime.now()
            )
            self.queue.submit_request(request)

        # Approve one
        self.queue.approve_request("req_0", "manager")

        # Get pending
        pending = self.queue.get_pending_requests()

        self.assertEqual(len(pending), 4)

    def test_expire_requests(self):
        """Test expiring old requests"""
        # Create old request
        old_request = ApprovalRequest(
            request_id="req_old",
            operation_type="deployment",
            operation_id="deploy_old",
            requester="admin",
            description="Old deployment",
            risk_level="medium",
            details={},
            created_at=datetime.now() - timedelta(hours=25),
            expires_at=datetime.now() - timedelta(hours=1)
        )

        # Create recent request
        recent_request = ApprovalRequest(
            request_id="req_recent",
            operation_type="deployment",
            operation_id="deploy_recent",
            requester="admin",
            description="Recent deployment",
            risk_level="medium",
            details={},
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24)
        )

        self.queue.submit_request(old_request)
        self.queue.submit_request(recent_request)

        # Expire old requests
        expired_count = self.queue.cleanup_expired_requests()

        self.assertEqual(expired_count, 1)
        old = self.queue.get_request("req_old")
        self.assertEqual(old.status, ApprovalStatus.EXPIRED)


class TestEventLogger(unittest.TestCase):
    """Test EventLogger functionality"""

    def setUp(self):
        self.logger = EventLogger()

    def test_log_event(self):
        """Test logging an event"""
        event = OversightEvent(
            event_id="event_1",
            event_type="operation",
            event_data={"operation_id": "op_1"},
            timestamp=datetime.now(),
            severity="info",
            source="system"
        )

        self.logger.log_event(event)

        events = self.logger.get_recent_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_id, "event_0")

    def test_get_events_by_type(self):
        """Test getting events by type"""
        # Log different types
        for i in range(3):
            event = OversightEvent(
                event_id=f"event_{i}",
                event_type="operation",
                event_data={"id": i},
                timestamp=datetime.now(),
                severity="info",
                source="system"
            )
            self.logger.log_event(event)

        for i in range(3, 6):
            event = OversightEvent(
                event_id=f"event_{i}",
                event_type="approval",
                event_data={"id": i},
                timestamp=datetime.now(),
                severity="info",
                source="system"
            )
            self.logger.log_event(event)

        # Get operation events
        op_events = self.logger.get_events_by_type("operation")

        self.assertEqual(len(op_events), 3)

    def test_get_events_by_severity(self):
        """Test getting events by severity"""
        # Log events with different severities
        for i in range(3):
            event = OversightEvent(
                event_id=f"event_{i}",
                event_type="operation",
                event_data={},
                timestamp=datetime.now(),
                severity="warning",
                source="system"
            )
            self.logger.log_event(event)

        for i in range(3, 6):
            event = OversightEvent(
                event_id=f"event_{i}",
                event_type="operation",
                event_data={},
                timestamp=datetime.now(),
                severity="error",
                source="system"
            )
            self.logger.log_event(event)

        # Get warning events
        warning_events = self.logger.get_events_by_severity("warning")

        self.assertEqual(len(warning_events), 3)

    def test_get_events_in_range(self):
        """Test getting events in time range"""
        now = datetime.now()

        # Log events at different times
        old_event = OversightEvent(
            event_id="event_old",
            event_type="operation",
            event_data={},
            timestamp=now - timedelta(hours=2),
            severity="info",
            source="system"
        )

        recent_event = OversightEvent(
            event_id="event_recent",
            event_type="operation",
            event_data={},
            timestamp=now - timedelta(minutes=30),
            severity="info",
            source="system"
        )

        self.logger.log_event(old_event)
        self.logger.log_event(recent_event)

        # Get events from last hour
        start_time = now - timedelta(hours=1)
        end_time = now
        all_events = self.logger.get_recent_events()
        events = [e for e in all_events if start_time <= e.timestamp <= end_time]

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_id, "event_1")


class TestInterventionManager(unittest.TestCase):
    """Test InterventionManager functionality"""

    def setUp(self):
        self.manager = InterventionManager()

    def test_record_intervention(self):
        """Test recording an intervention"""
        intervention = Intervention(
            intervention_id="int_1",
            intervention_type="override",
            target_operation_id="op_1",
            target_operation_type="deployment",
            reason="Manual override needed",
            intervenor="admin",
            timestamp=datetime.now(),
            original_action={"action": "deploy"}
        )

        self.manager.record_intervention(intervention)

        interventions = self.manager.get_recent_interventions()
        self.assertEqual(len(interventions), 1)
        self.assertEqual(interventions[0].intervention_id, "int_1")

    def test_get_interventions_by_operation(self):
        """Test getting interventions for an operation"""
        # Record interventions for same operation
        for i in range(3):
            intervention = Intervention(
                intervention_id=f"int_{i}",
                intervention_type="override",
                target_operation_id="op_1",
                target_operation_type="deployment",
                reason=f"Reason {i}",
                intervenor="admin",
                timestamp=datetime.now(),
                original_action={}
            )
            self.manager.record_intervention(intervention)

        # Get interventions for operation
        op_interventions = self.manager.get_interventions_for_operation("op_1")

        self.assertEqual(len(op_interventions), 3)

    def test_get_interventions_by_type(self):
        """Test getting interventions by type"""
        # Record different types
        for i in range(3):
            intervention = Intervention(
                intervention_id=f"int_{i}",
                intervention_type="override",
                target_operation_id=f"op_{i}",
                target_operation_type="deployment",
                reason="",
                intervenor="admin",
                timestamp=datetime.now(),
                original_action={}
            )
            self.manager.record_intervention(intervention)

        for i in range(3, 6):
            intervention = Intervention(
                intervention_id=f"int_{i}",
                intervention_type="pause",
                target_operation_id=f"op_{i}",
                target_operation_type="deployment",
                reason="",
                intervenor="admin",
                timestamp=datetime.now(),
                original_action={}
            )
            self.manager.record_intervention(intervention)

        # Get override interventions
        all_interventions = self.manager.get_recent_interventions()
        overrides = [i for i in all_interventions if i.intervention_type == "override"]

        self.assertEqual(len(overrides), 3)


class TestHumanOversightSystem(unittest.TestCase):
    """Test HumanOversightSystem functionality"""

    def setUp(self):
        self.system = HumanOversightSystem(enable_oversight=True)

    def test_request_approval(self):
        """Test requesting approval for operation"""
        request_id = self.system.request_approval(
            operation_type="deployment",
            operation_id="deploy_1",
            requester="admin",
            description="Deploy to production",
            risk_level="high",
            details={"environment": "production"}
        )

        self.assertIsNotNone(request_id)

        # Check pending
        pending = self.system.get_pending_approvals()
        self.assertEqual(len(pending), 1)

    def test_grant_approval(self):
        """Test granting approval"""
        # Request approval
        request_id = self.system.request_approval(
            operation_type="deployment",
            operation_id="deploy_1",
            requester="admin",
            description="Deploy to production",
            risk_level="high",
            details={}
        )

        # Grant approval
        success = self.system.approve(request_id, "manager")

        self.assertTrue(success)

        # Check no pending
        pending = self.system.get_pending_approvals()
        self.assertEqual(len(pending), 0)

    def test_reject_approval(self):
        """Test rejecting approval"""
        # Request approval
        request_id = self.system.request_approval(
            operation_type="deployment",
            operation_id="deploy_1",
            requester="admin",
            description="Deploy to production",
            risk_level="high",
            details={}
        )

        # Reject approval
        success = self.system.reject(request_id, "Not ready", "manager")

        self.assertTrue(success)

    def test_check_approval_required(self):
        """Test checking if approval is required"""
        # Set oversight level to HIGH_RISK
        self.system.oversight_level = OversightLevel.HIGH_RISK

        # Check if approval required for high risk
        required = self.system._needs_approval(
            risk_level="high",
            operation_type="deployment"
        )

        self.assertTrue(required)

    def test_check_approval_not_required(self):
        """Test checking if approval is not required for low risk"""
        # Set oversight level to HIGH_RISK
        self.system.oversight_level = OversightLevel.HIGH_RISK

        # Check if approval required for low risk
        required = self.system._needs_approval(
            risk_level="low",
            operation_type="deployment"
        )

        self.assertFalse(required)

    def test_record_intervention(self):
        """Test recording human intervention"""
        result = self.system.intervene(
            intervention_type="override",
            target_operation_id="op_1",
            target_operation_type="deployment",
            reason="Manual override",
            intervenor="admin",
            original_action={"action": "deploy"},
            modified_action={"action": "deploy", "flag": "manual"}
        )

        self.assertIsNotNone(result)

    def test_get_intervention_history(self):
        """Test getting intervention history"""
        # Record intervention
        self.system.intervene(
            intervention_type="override",
            target_operation_id="op_1",
            target_operation_type="deployment",
            reason="Test",
            intervenor="admin",
            original_action={}
        )

        # Get history
        history = self.system.get_interventions()

        self.assertEqual(len(history), 1)

    def test_get_oversight_summary(self):
        """Test getting oversight summary"""
        # Request approval
        self.system.request_approval(
            operation_type="deployment",
            operation_id="deploy_1",
            requester="admin",
            description="Deploy",
            risk_level="high",
            details={}
        )

        # Get summary
        summary = self.system.get_oversight_statistics()

        self.assertIn('pending_approvals', summary)
        self.assertIn('interventions', summary)
        self.assertIn('oversight_level', summary)


if __name__ == '__main__':
    unittest.main()
