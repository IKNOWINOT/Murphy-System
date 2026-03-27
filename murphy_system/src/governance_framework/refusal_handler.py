"""
Refusal Handler Implementation

Implements refusal semantics as valid execution state:
- Refusal validation and handling
- Outcome propagation to dependent agents
- Audit trail management for refusals
- Integration with scheduler and stability controller
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Set, Union
from uuid import UUID, uuid4

from .stability_controller import ExecutionOutcome

logger = logging.getLogger(__name__)


@dataclass
class RefusalRecord:
    """Record of agent refusal for audit"""

    agent_id: str
    refusal_code: str
    refusal_reason: str
    timestamp: datetime
    refusing_authority: str
    blocked_dependencies: List[str]
    audit_signature: str

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "agent_id": self.agent_id,
            "refusal_code": self.refusal_code,
            "refusal_reason": self.refusal_reason,
            "timestamp": self.timestamp.isoformat(),
            "refusing_authority": self.refusing_authority,
            "blocked_dependencies": self.blocked_dependencies,
            "audit_signature": self.audit_signature
        }


class RefusalHandler:
    """Manages refusal as valid execution state"""

    VALID_REFUSAL_CODES = {
        "SAFETY_CONSTRAINT_VIOLATION": "Action violates immutable safety constraints",
        "INSUFFICIENT_GOVERNANCE_ARTIFACTS": "Essential governance artifact unavailable",
        "AUTHORITY_EXCEEDED": "Required authority level cannot be obtained",
        "DEPENDENCY_UNAVAILABLE": "Required external system permanently unavailable",
        "REGULATORY_PROHIBITION": "Action explicitly prohibited by regulation",
        "ETHICAL_BOUNDARY_VIOLATION": "Action crosses defined ethical boundaries",
        "RESOURCE_CONSTRAINT": "Insufficient resources for safe execution",
        "STABILITY_LIMIT_EXCEEDED": "Operation would exceed stability thresholds"
    }

    def __init__(self):
        self.refusal_history: Dict[str, List[RefusalRecord]] = {}
        self.blocked_agents: Dict[str, Dict] = {}

    def validate_refusal(self, agent_id: str, refusal_code: str, refusal_reason: str) -> bool:
        """Validate refusal meets system criteria"""
        return refusal_code in self.VALID_REFUSAL_CODES

    def handle_refusal(self, agent_id: str, refusal_code: str, refusal_reason: str,
                     authority_level: str, dependencies: List[str]) -> RefusalRecord:
        """Handle refusal as valid terminal state"""

        refusal_record = RefusalRecord(
            agent_id=agent_id,
            refusal_code=refusal_code,
            refusal_reason=refusal_reason,
            timestamp=datetime.now(timezone.utc),
            refusing_authority=authority_level,
            blocked_dependencies=dependencies,
            audit_signature=self._generate_audit_signature(agent_id, refusal_code, refusal_reason)
        )

        # Store in history
        if agent_id not in self.refusal_history:
            self.refusal_history[agent_id] = []
        self.refusal_history[agent_id].append(refusal_record)

        # Block dependent agents
        self._block_dependent_agents(agent_id, refusal_code, dependencies)

        return refusal_record

    def _block_dependent_agents(self, refusing_agent: str, refusal_code: str, dependencies: List[str]):
        """Block all agents that depend on refusing agent"""
        for dependent_id in dependencies:
            self.blocked_agents[dependent_id] = {
                "blocked_by": refusing_agent,
                "refusal_code": refusal_code,
                "blocked_time": datetime.now(timezone.utc)
            }

    def _generate_audit_signature(self, agent_id: str, refusal_code: str, refusal_reason: str) -> str:
        """Generate cryptographic signature for audit trail"""
        audit_data = {
            "agent_id": agent_id,
            "refusal_code": refusal_code,
            "refusal_reason": refusal_reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        json_str = json.dumps(audit_data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
