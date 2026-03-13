"""
Human Oversight System for Murphy System Runtime

This module provides human oversight and intervention capabilities:
- Approval workflows for critical operations
- Monitoring of autonomous decisions
- Human-in-the-loop integration
- Audit logging and compliance tracking
"""

import json
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    """Approval status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    AUTO_APPROVED = "auto_approved"


class OversightLevel(Enum):
    """Oversight level"""
    FULL = "full"  # Requires human approval for all operations
    HIGH_RISK = "high_risk"  # Human approval only for high-risk operations
    MONITORING = "monitoring"  # Autonomous but monitored
    AUTONOMOUS = "autonomous"  # Fully autonomous


@dataclass
class ApprovalRequest:
    """Represents an approval request"""
    request_id: str
    operation_type: str
    operation_id: str
    requester: str
    description: str
    risk_level: str  # low, medium, high, critical
    details: Dict[str, Any]
    created_at: datetime
    expires_at: Optional[datetime] = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    auto_approved: bool = False
    auto_approve_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OversightEvent:
    """Represents an oversight event"""
    event_id: str
    event_type: str  # operation, approval, intervention, alert
    event_data: Dict[str, Any]
    timestamp: datetime
    severity: str  # info, warning, error, critical
    source: str  # system, human, automated
    requires_action: bool = False
    action_taken: Optional[str] = None
    action_taken_by: Optional[str] = None
    action_taken_at: Optional[datetime] = None


@dataclass
class Intervention:
    """Represents a human intervention"""
    intervention_id: str
    intervention_type: str  # override, pause, abort, modify
    target_operation_id: str
    target_operation_type: str
    reason: str
    intervenor: str
    timestamp: datetime
    original_action: Dict[str, Any]
    modified_action: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ApprovalQueue:
    """Manages approval requests"""

    def __init__(self, max_queue_size: int = 1000):
        self.max_queue_size = max_queue_size
        self.queue: deque = deque(maxlen=max_queue_size)
        self.requests_by_id: Dict[str, ApprovalRequest] = {}
        self.requests_by_operation: Dict[str, List[str]] = {}
        self.lock = threading.Lock()

    def submit_request(self, request: ApprovalRequest) -> str:
        """Submit an approval request"""
        with self.lock:
            self.queue.append(request)
            self.requests_by_id[request.request_id] = request

            if request.operation_id not in self.requests_by_operation:
                self.requests_by_operation[request.operation_id] = []
            self.requests_by_operation[request.operation_id].append(request.request_id)

            return request.request_id

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID"""
        return self.requests_by_id.get(request_id)

    def get_requests_for_operation(self, operation_id: str) -> List[ApprovalRequest]:
        """Get approval requests for a specific operation"""
        with self.lock:
            request_ids = self.requests_by_operation.get(operation_id, [])
            return [self.requests_by_id[rid] for rid in request_ids]

    def get_pending_requests(self) -> List[ApprovalRequest]:
        """Get all pending approval requests"""
        with self.lock:
            now = datetime.now(timezone.utc)
            pending = []

            for request in self.queue:
                if request.status == ApprovalStatus.PENDING:
                    # Check if expired
                    if request.expires_at and now > request.expires_at:
                        request.status = ApprovalStatus.EXPIRED
                    else:
                        pending.append(request)

            return pending

    def approve_request(self, request_id: str, approved_by: str,
                       auto_approve: bool = False,
                       auto_approve_reason: Optional[str] = None) -> bool:
        """Approve an approval request"""
        with self.lock:
            request = self.requests_by_id.get(request_id)
            if not request or request.status != ApprovalStatus.PENDING:
                return False

            request.status = ApprovalStatus.APPROVED
            request.approved_by = approved_by
            request.approved_at = datetime.now(timezone.utc)
            request.auto_approved = auto_approve
            request.auto_approve_reason = auto_approve_reason

            return True

    def reject_request(self, request_id: str, rejection_reason: str,
                      rejected_by: str) -> bool:
        """Reject an approval request"""
        with self.lock:
            request = self.requests_by_id.get(request_id)
            if not request or request.status != ApprovalStatus.PENDING:
                return False

            request.status = ApprovalStatus.REJECTED
            request.rejection_reason = rejection_reason
            request.approved_by = rejected_by  # Use approved_by field for rejected_by
            request.approved_at = datetime.now(timezone.utc)

            return True

    def cleanup_expired_requests(self) -> int:
        """Clean up expired requests"""
        with self.lock:
            now = datetime.now(timezone.utc)
            expired_count = 0

            for request in self.queue:
                if request.status == ApprovalStatus.PENDING and request.expires_at and now > request.expires_at:
                    request.status = ApprovalStatus.EXPIRED
                    expired_count += 1

            return expired_count


class EventLogger:
    """Logs oversight events"""

    def __init__(self, max_events: int = 10000):
        self.max_events = max_events
        self.events: deque = deque(maxlen=max_events)
        self.events_by_type: Dict[str, List[str]] = {}
        self.events_by_severity: Dict[str, List[str]] = {}
        self.lock = threading.Lock()

    def log_event(self, event: OversightEvent) -> None:
        """Log an oversight event"""
        with self.lock:
            event.event_id = f"event_{len(self.events)}"
            self.events.append(event)

            # Index by type
            if event.event_type not in self.events_by_type:
                self.events_by_type[event.event_type] = []
            self.events_by_type[event.event_type].append(event.event_id)

            # Index by severity
            if event.severity not in self.events_by_severity:
                self.events_by_severity[event.severity] = []
            self.events_by_severity[event.severity].append(event.event_id)

    def get_events_by_type(self, event_type: str,
                          limit: int = 100) -> List[OversightEvent]:
        """Get events by type"""
        with self.lock:
            event_ids = self.events_by_type.get(event_type, [])
            events = [e for e in self.events if e.event_id in event_ids]
            return events[-limit:]

    def get_events_by_severity(self, severity: str,
                              limit: int = 100) -> List[OversightEvent]:
        """Get events by severity"""
        with self.lock:
            event_ids = self.events_by_severity.get(severity, [])
            events = [e for e in self.events if e.event_id in event_ids]
            return events[-limit:]

    def get_recent_events(self, limit: int = 100) -> List[OversightEvent]:
        """Get recent events"""
        with self.lock:
            events_list = list(self.events)
            return events_list[-limit:]


class InterventionManager:
    """Manages human interventions"""

    def __init__(self):
        self.interventions: Dict[str, Intervention] = {}
        self.interventions_by_operation: Dict[str, List[str]] = {}
        self.lock = threading.Lock()

    def record_intervention(self, intervention: Intervention) -> None:
        """Record a human intervention"""
        with self.lock:
            self.interventions[intervention.intervention_id] = intervention

            if intervention.target_operation_id not in self.interventions_by_operation:
                self.interventions_by_operation[intervention.target_operation_id] = []
            self.interventions_by_operation[intervention.target_operation_id].append(
                intervention.intervention_id
            )

    def get_intervention(self, intervention_id: str) -> Optional[Intervention]:
        """Get an intervention by ID"""
        return self.interventions.get(intervention_id)

    def get_interventions_for_operation(self, operation_id: str) -> List[Intervention]:
        """Get interventions for a specific operation"""
        with self.lock:
            intervention_ids = self.interventions_by_operation.get(operation_id, [])
            return [self.interventions[iid] for iid in intervention_ids]

    def get_recent_interventions(self, limit: int = 50) -> List[Intervention]:
        """Get recent interventions"""
        with self.lock:
            interventions = sorted(
                self.interventions.values(),
                key=lambda i: i.timestamp,
                reverse=True
            )
            return interventions[:limit]


class HumanOversightSystem:
    """
    Main human oversight system that coordinates oversight activities

    The oversight system:
    - Manages approval workflows
    - Monitors autonomous operations
    - Records human interventions
    - Logs all oversight events
    - Provides audit trail
    """

    def __init__(self, enable_oversight: bool = True,
                 oversight_level: OversightLevel = OversightLevel.HIGH_RISK):
        self.enable_oversight = enable_oversight
        self.oversight_level = oversight_level
        self.approval_queue = ApprovalQueue()
        self.event_logger = EventLogger()
        self.intervention_manager = InterventionManager()
        self.lock = threading.Lock()

        # Configuration
        self.auto_approve_threshold = 0.95  # Confidence threshold for auto-approval
        self.approval_timeout = timedelta(hours=24)  # Default approval timeout
        self.high_risk_threshold = 0.7  # Risk level threshold for requiring approval

        # Statistics
        self.total_requests = 0
        self.auto_approvals = 0
        self.human_approvals = 0
        self.rejections = 0
        self.interventions = 0

    def request_approval(self, operation_type: str, operation_id: str,
                        requester: str, description: str, risk_level: str,
                        details: Dict[str, Any],
                        timeout: Optional[timedelta] = None,
                        metadata: Dict[str, Any] = None) -> str:
        """Request approval for an operation"""
        if not self.enable_oversight:
            # Auto-approve if oversight disabled
            return "auto_approved"

        # Check if approval is needed based on oversight level
        needs_approval = self._needs_approval(risk_level, operation_type)

        if not needs_approval:
            # Auto-approve
            self._log_auto_approval(operation_type, operation_id, risk_level)
            return "auto_approved"

        # Create approval request
        request = ApprovalRequest(
            request_id=f"approval_{self.total_requests}",
            operation_type=operation_type,
            operation_id=operation_id,
            requester=requester,
            description=description,
            risk_level=risk_level,
            details=details,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + (timeout or self.approval_timeout),
            metadata=metadata or {}
        )

        # Submit to queue
        request_id = self.approval_queue.submit_request(request)

        # Log event
        event = OversightEvent(
            event_id="",
            event_type="approval_request",
            event_data={
                'request_id': request_id,
                'operation_type': operation_type,
                'operation_id': operation_id,
                'risk_level': risk_level,
                'description': description
            },
            timestamp=datetime.now(timezone.utc),
            severity="info",
            source="system",
            requires_action=True
        )
        self.event_logger.log_event(event)

        with self.lock:
            self.total_requests += 1

        return request_id

    def _needs_approval(self, risk_level: str, operation_type: str) -> bool:
        """Determine if approval is needed"""
        if self.oversight_level == OversightLevel.FULL:
            return True

        elif self.oversight_level == OversightLevel.HIGH_RISK:
            return risk_level in ["high", "critical"]

        elif self.oversight_level == OversightLevel.MONITORING:
            return risk_level == "critical"

        else:  # AUTONOMOUS
            return False

    def _log_auto_approval(self, operation_type: str, operation_id: str,
                          risk_level: str) -> None:
        """Log an auto-approval"""
        with self.lock:
            self.auto_approvals += 1

        event = OversightEvent(
            event_id="",
            event_type="auto_approval",
            event_data={
                'operation_type': operation_type,
                'operation_id': operation_id,
                'risk_level': risk_level,
                'reason': 'Below approval threshold'
            },
            timestamp=datetime.now(timezone.utc),
            severity="info",
            source="automated",
            requires_action=False
        )
        self.event_logger.log_event(event)

    def approve(self, request_id: str, approved_by: str,
               reason: Optional[str] = None) -> bool:
        """Approve a pending request"""
        success = self.approval_queue.approve_request(
            request_id, approved_by, auto_approve=False
        )

        if success:
            with self.lock:
                self.human_approvals += 1

            # Log approval event
            request = self.approval_queue.get_request(request_id)
            event = OversightEvent(
                event_id="",
                event_type="approval",
                event_data={
                    'request_id': request_id,
                    'approved_by': approved_by,
                    'reason': reason,
                    'operation_type': request.operation_type,
                    'operation_id': request.operation_id
                },
                timestamp=datetime.now(timezone.utc),
                severity="info",
                source="human",
                requires_action=False,
                action_taken="approved",
                action_taken_by=approved_by,
                action_taken_at=datetime.now(timezone.utc)
            )
            self.event_logger.log_event(event)

        return success

    def reject(self, request_id: str, rejection_reason: str,
              rejected_by: str) -> bool:
        """Reject a pending request"""
        success = self.approval_queue.reject_request(
            request_id, rejection_reason, rejected_by
        )

        if success:
            with self.lock:
                self.rejections += 1

            # Log rejection event
            request = self.approval_queue.get_request(request_id)
            event = OversightEvent(
                event_id="",
                event_type="rejection",
                event_data={
                    'request_id': request_id,
                    'rejection_reason': rejection_reason,
                    'rejected_by': rejected_by,
                    'operation_type': request.operation_type,
                    'operation_id': request.operation_id
                },
                timestamp=datetime.now(timezone.utc),
                severity="warning",
                source="human",
                requires_action=False,
                action_taken="rejected",
                action_taken_by=rejected_by,
                action_taken_at=datetime.now(timezone.utc)
            )
            self.event_logger.log_event(event)

        return success

    def intervene(self, intervention_type: str, target_operation_id: str,
                target_operation_type: str, reason: str, intervenor: str,
                original_action: Dict[str, Any],
                modified_action: Optional[Dict[str, Any]] = None) -> str:
        """Record a human intervention"""
        intervention = Intervention(
            intervention_id=f"intervention_{self.interventions}",
            intervention_type=intervention_type,
            target_operation_id=target_operation_id,
            target_operation_type=target_operation_type,
            reason=reason,
            intervenor=intervenor,
            timestamp=datetime.now(timezone.utc),
            original_action=original_action,
            modified_action=modified_action
        )

        self.intervention_manager.record_intervention(intervention)

        with self.lock:
            self.interventions += 1

        # Log intervention event
        event = OversightEvent(
            event_id="",
            event_type="intervention",
            event_data={
                'intervention_id': intervention.intervention_id,
                'intervention_type': intervention_type,
                'target_operation_id': target_operation_id,
                'target_operation_type': target_operation_type,
                'reason': reason,
                'intervenor': intervenor
            },
            timestamp=datetime.now(timezone.utc),
            severity="warning",
            source="human",
            requires_action=False,
            action_taken=intervention_type,
            action_taken_by=intervenor,
            action_taken_at=datetime.now(timezone.utc)
        )
        self.event_logger.log_event(event)

        return intervention.intervention_id

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get all pending approval requests"""
        requests = self.approval_queue.get_pending_requests()
        return [
            {
                'request_id': r.request_id,
                'operation_type': r.operation_type,
                'operation_id': r.operation_id,
                'requester': r.requester,
                'description': r.description,
                'risk_level': r.risk_level,
                'created_at': r.created_at.isoformat(),
                'expires_at': r.expires_at.isoformat() if r.expires_at else None
            }
            for r in requests
        ]

    def get_approval_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an approval request"""
        request = self.approval_queue.get_request(request_id)
        if not request:
            return None

        return {
            'request_id': request.request_id,
            'status': request.status.value,
            'approved_by': request.approved_by,
            'approved_at': request.approved_at.isoformat() if request.approved_at else None,
            'rejection_reason': request.rejection_reason,
            'auto_approved': request.auto_approved,
            'auto_approve_reason': request.auto_approve_reason
        }

    def get_events(self, event_type: Optional[str] = None,
                  severity: Optional[str] = None,
                  limit: int = 100) -> List[Dict[str, Any]]:
        """Get oversight events"""
        if event_type:
            events = self.event_logger.get_events_by_type(event_type, limit)
        elif severity:
            events = self.event_logger.get_events_by_severity(severity, limit)
        else:
            events = self.event_logger.get_recent_events(limit)

        return [
            {
                'event_id': e.event_id,
                'event_type': e.event_type,
                'timestamp': e.timestamp.isoformat(),
                'severity': e.severity,
                'source': e.source,
                'requires_action': e.requires_action,
                'action_taken': e.action_taken,
                'action_taken_by': e.action_taken_by,
                'event_data': e.event_data
            }
            for e in events
        ]

    def get_interventions(self, operation_id: Optional[str] = None,
                        limit: int = 50) -> List[Dict[str, Any]]:
        """Get human interventions"""
        if operation_id:
            interventions = self.intervention_manager.get_interventions_for_operation(operation_id)
        else:
            interventions = self.intervention_manager.get_recent_interventions(limit)

        return [
            {
                'intervention_id': i.intervention_id,
                'intervention_type': i.intervention_type,
                'target_operation_id': i.target_operation_id,
                'target_operation_type': i.target_operation_type,
                'reason': i.reason,
                'intervenor': i.intervenor,
                'timestamp': i.timestamp.isoformat(),
                'result': i.result
            }
            for i in interventions[:limit]
        ]

    def get_oversight_statistics(self) -> Dict[str, Any]:
        """Get oversight statistics"""
        with self.lock:
            return {
                'total_requests': self.total_requests,
                'auto_approvals': self.auto_approvals,
                'human_approvals': self.human_approvals,
                'rejections': self.rejections,
                'interventions': self.interventions,
                'pending_approvals': len(self.approval_queue.get_pending_requests()),
                'oversight_level': self.oversight_level.value,
                'auto_approve_rate': (
                    self.auto_approvals / self.total_requests
                    if self.total_requests > 0 else 0.0
                )
            }

    def export_audit_trail(self, start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Export audit trail for compliance"""
        # Get events in date range
        all_events = self.event_logger.get_recent_events(limit=10000)

        if start_date or end_date:
            filtered_events = []
            for event in all_events:
                if start_date and event.timestamp < start_date:
                    continue
                if end_date and event.timestamp > end_date:
                    continue
                filtered_events.append(event)
            events = filtered_events
        else:
            events = all_events

        return {
            'export_timestamp': datetime.now(timezone.utc).isoformat(),
            'date_range': {
                'start': start_date.isoformat() if start_date else None,
                'end': end_date.isoformat() if end_date else None
            },
            'statistics': self.get_oversight_statistics(),
            'events': [
                {
                    'event_id': e.event_id,
                    'event_type': e.event_type,
                    'timestamp': e.timestamp.isoformat(),
                    'severity': e.severity,
                    'source': e.source,
                    'event_data': e.event_data
                }
                for e in events
            ],
            'interventions': self.get_interventions(limit=1000)
        }
