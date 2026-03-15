"""
Integration Engine - Unified system for adding integrations with HITL safety

This module provides:
- SwissKiss integration (repository analysis)
- Automatic capability extraction
- Module/agent generation
- Safety testing before commitment
- Human-in-the-loop approval workflow
- Sandbox Quarantine Protocol (Step 5.5)
"""

# Lightweight, always-available imports
from .hitl_approval import HITLApprovalSystem
from .safety_tester import SafetyTester
from .sandbox_quarantine import QuarantineReport, SandboxQuarantine, ThreatFinding

# Heavy imports (require optional deps like numpy, pydantic, etc.)
# Wrapped so that the lightweight modules above can still be used in test contexts
try:
    from .agent_generator import AgentGenerator
    from .capability_extractor import CapabilityExtractor
    from .module_generator import ModuleGenerator
    from .unified_engine import UnifiedIntegrationEngine
except ImportError:
    UnifiedIntegrationEngine = None  # type: ignore[assignment,misc]
    CapabilityExtractor = None  # type: ignore[assignment,misc]
    ModuleGenerator = None  # type: ignore[assignment,misc]
    AgentGenerator = None  # type: ignore[assignment,misc]

__all__ = [
    'UnifiedIntegrationEngine',
    'CapabilityExtractor',
    'ModuleGenerator',
    'AgentGenerator',
    'SafetyTester',
    'HITLApprovalSystem',
    'SandboxQuarantine',
    'QuarantineReport',
    'ThreatFinding',
]
