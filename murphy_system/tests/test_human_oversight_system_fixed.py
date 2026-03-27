"""
Tests for Human Oversight System component - FIXED VERSION

Tests:
- Human oversight functionality
- Approval workflow
- Event logging
- Intervention tracking

Note: Tests updated to match actual API implementation
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

    def test_cleanup_expired_requests(self):
        """Test cleaning up expired requests"""
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

        # Cleanup expired requests
        expired_count = self.queue.cleanup_expired_requests()

        self.assertEqual(expired_count, 1)

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
        self.queue.approve_request("req_0", approved_by="manager")

        # Get pending
        pending = self.queue.get_pending_requests()

        self.assertEqual(len(pending), 4)


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
        self.assertGreater(len(events), 0)

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
        op_events = self.logger.get_events_by_type("operation", limit=10)

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
        warning_events = self.logger.get_events_by_severity("warning", limit=10)

        self.assertEqual(len(warning_events), 3)


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

    def test_get_interventions_for_operation(self):
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

    def test_approve(self):
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
        success = self.system.approve(request_id, approved_by="manager")

        self.assertTrue(success)

        # Check no pending
        pending = self.system.get_pending_approvals()
        self.assertEqual(len(pending), 0)

    def test_reject(self):
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
        success = self.system.reject(request_id, rejection_reason="Not ready", rejected_by="manager")

        self.assertTrue(success)

    def test_intervene(self):
        """Test recording human intervention"""
        success = self.system.intervene(
            intervention_type="override",
            target_operation_id="op_1",
            target_operation_type="deployment",
            reason="Manual override",
            intervenor="admin",
            original_action={"action": "deploy"},
            modified_action={"action": "deploy", "flag": "manual"}
        )

        self.assertTrue(success)

    def test_get_interventions(self):
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

    def test_get_oversight_statistics(self):
        """Test getting oversight statistics"""
        # Request approval
        self.system.request_approval(
            operation_type="deployment",
            operation_id="deploy_1",
            requester="admin",
            description="Deploy",
            risk_level="high",
            details={}
        )

        # Get statistics
        stats = self.system.get_oversight_statistics()

        self.assertIn('pending_approvals', stats)
        self.assertIn('interventions', stats)


if __name__ == '__main__':
    unittest.main()
