"""Bridge: src.bridge_layer.hypothesis

Re-exports HypothesisArtifact with a simplified constructor for e2e tests.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


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
