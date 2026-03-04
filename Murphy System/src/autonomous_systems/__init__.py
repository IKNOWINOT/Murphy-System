"""
Autonomous Systems Module for Murphy System Runtime

This module provides comprehensive autonomous operation capabilities:
- Autonomous task scheduling
- Risk management and mitigation
- Human oversight and intervention

Components:
- AutonomousScheduler: Self-scheduling task execution
- RiskManager: Risk assessment and mitigation
- HumanOversightSystem: Human-in-the-loop oversight
"""

from .autonomous_scheduler import (
    AutonomousScheduler,
    Task,
    TaskPriority,
    TaskStatus,
    ResourcePool,
    DependencyGraph
)

from .risk_manager import (
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

from .human_oversight_system import (
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

__all__ = [
    # Autonomous Scheduler
    'AutonomousScheduler',
    'Task',
    'TaskPriority',
    'TaskStatus',
    'ResourcePool',
    'DependencyGraph',

    # Risk Manager
    'RiskManager',
    'RiskAssessment',
    'RiskMonitor',
    'MitigationPlanner',
    'RiskFactor',
    'RiskSeverity',
    'RiskCategory',
    'RiskAlert',
    'MitigationAction',

    # Human Oversight System
    'HumanOversightSystem',
    'ApprovalQueue',
    'EventLogger',
    'InterventionManager',
    'ApprovalRequest',
    'ApprovalStatus',
    'OversightLevel',
    'OversightEvent',
    'Intervention'
]
