"""
Integration Engine - Unified system for adding integrations with HITL safety

This module provides:
- SwissKiss integration (repository analysis)
- Automatic capability extraction
- Module/agent generation
- Safety testing before commitment
- Human-in-the-loop approval workflow
"""

from .unified_engine import UnifiedIntegrationEngine
from .capability_extractor import CapabilityExtractor
from .module_generator import ModuleGenerator
from .agent_generator import AgentGenerator
from .safety_tester import SafetyTester
from .hitl_approval import HITLApprovalSystem

__all__ = [
    'UnifiedIntegrationEngine',
    'CapabilityExtractor',
    'ModuleGenerator',
    'AgentGenerator',
    'SafetyTester',
    'HITLApprovalSystem'
]