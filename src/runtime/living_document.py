"""
Murphy System 1.0 - LivingDocument Model

Block-command workflow document model (magnify / simplify / solidify).
Extracted from the monolithic runtime for maintainability (INC-13 / H-04 / L-02).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class LivingDocument:
    """
    Living document model used for block-command workflows.

    - magnify: expands domain depth to increase context coverage
    - simplify: reduces complexity to improve clarity
    - solidify: locks the document and triggers swarm task generation
    - block_tree: hierarchical representation of pending/complete actions
    - org_chart_plan: populated by activation previews with position mappings
    """

    def __init__(self, doc_id: str, title: str, content: str, doc_type: str):
        self.doc_id = doc_id
        self.title = title
        self.content = content
        self.doc_type = doc_type
        self.state = "INITIAL"
        self.confidence = 0.45
        self.domain_depth = 0
        self.history: List[Dict[str, Any]] = []
        self.children: List[Dict[str, Any]] = []
        self.parent_id: Optional[str] = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.block_tree: Dict[str, Any] = {}
        self.gates: List[Dict[str, Any]] = []
        self.constraints: List[str] = []
        self.generated_tasks: List[Dict[str, Any]] = []
        self.gate_synthesis_gates: List[Dict[str, Any]] = []
        self.capability_tests: List[Dict[str, Any]] = []
        self.automation_summary: Dict[str, Any] = {}
        self.gate_policy: List[Dict[str, Any]] = []
        self.librarian_conditions: List[Dict[str, Any]] = []
        self.org_chart_plan: Dict[str, Any] = {}

    def magnify(self, domain: str) -> Dict[str, Any]:
        self.domain_depth += 15
        self.confidence = min(1.0, self.confidence + 0.1)
        self.history.append({
            "action": "magnify",
            "domain": domain,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return self.to_dict()

    def simplify(self) -> Dict[str, Any]:
        self.domain_depth = max(0, self.domain_depth - 10)
        self.confidence = min(1.0, self.confidence + 0.05)
        self.history.append({
            "action": "simplify",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return self.to_dict()

    def solidify(self) -> Dict[str, Any]:
        self.state = "SOLIDIFIED"
        self.confidence = min(1.0, self.confidence + 0.2)
        self.history.append({
            "action": "solidify",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "content": self.content,
            "doc_type": self.doc_type,
            "state": self.state,
            "confidence": self.confidence,
            "domain_depth": self.domain_depth,
            "history": self.history,
            "children": self.children,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "block_tree": self.block_tree,
            "gates": self.gates,
            "constraints": self.constraints,
            "generated_tasks": self.generated_tasks,
            "gate_synthesis_gates": self.gate_synthesis_gates,
            "capability_tests": self.capability_tests,
            "automation_summary": self.automation_summary,
            "gate_policy": self.gate_policy,
            "librarian_conditions": self.librarian_conditions,
            "org_chart_plan": self.org_chart_plan
        }

