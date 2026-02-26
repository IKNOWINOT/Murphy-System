"""Bridge: src.bridge_layer.hypothesis

Re-exports HypothesisArtifact with a simplified constructor for e2e tests.
"""

from dataclasses import dataclass, field
from typing import List, Any, Dict, Optional
from datetime import datetime
import uuid


@dataclass
class HypothesisArtifact:
    """Simplified HypothesisArtifact for e2e test workflows."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    plan_summary: str = ""
    assumptions: List[str] = field(default_factory=list)
    created_by: str = ""
    status: str = "sandbox"


__all__ = ["HypothesisArtifact"]
