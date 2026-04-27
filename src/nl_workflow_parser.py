"""
PATCH-114 — src/nl_workflow_parser.py
Murphy System — Swarm Rosetta NL→Workflow Parser

Extends the LCM pipeline: natural language IN → WorkflowSpec → DAGGraph OUT.

Pipeline:
  1. Parse NL text → extract intent, entities, domain, urgency, stake
  2. Check pattern library for known intent → load template DAG if found
  3. LLM-generate DAG nodes for unknown intents
  4. Safety gate: PCC check on stake level
  5. Emit DAGGraph ready for execution by DAGExecutor

This is the core Rosetta translation: human language → machine action.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.nl_workflow_parser")


@dataclass
class WorkflowSpec:
    """Parsed intermediate representation between NL and a DAGGraph."""
    intent: str
    entities: List[str]
    domain: str          # exec_admin | prod_ops | data | comms | system
    urgency: str         # immediate | scheduled | recurring | ambient
    stake: str           # low | medium | high | critical
    constraints: List[str]   # "notify_before", "require_approval", "dry_run"
    steps: List[Dict]    # [{name, action, args, depends_on}]
    raw_text: str
    confidence: float = 0.0
    pattern_id: Optional[str] = None  # if matched a known pattern


class NLWorkflowParser:
    """
    PATCH-114: Natural Language → Workflow DAG parser.
    Uses LLM to extract WorkflowSpec from any NL input.
    Falls back to pattern library for known intents.
    """

    # Known domain keywords
    DOMAIN_SIGNALS = {
        "exec_admin": [
            "meeting", "schedule", "calendar", "email", "draft", "send",
            "report", "brief", "summary", "approve", "review", "delegate",
        ],
        "prod_ops": [
            "deploy", "restart", "rollback", "health", "incident", "monitor",
            "scale", "patch", "backup", "restore", "log", "alert",
        ],
        "data": [
            "analyze", "export", "import", "query", "aggregate", "chart",
            "dashboard", "metric", "trend",
        ],
        "comms": [
            "notify", "slack", "message", "post", "announce", "broadcast",
        ],
    }

    URGENCY_SIGNALS = {
        "immediate": ["now", "urgent", "asap", "immediately", "right now", "critical"],
        "scheduled": ["at ", "on ", "tomorrow", "next ", "in 1 hour", "in 30 min"],
        "recurring": ["every day", "every week", "daily", "weekly", "each morning"],
        "ambient": [],
    }

    STAKE_SIGNALS = {
        "critical": ["production", "all users", "delete all", "shutdown", "irreversible"],
        "high":     ["deploy", "rollback", "payment", "email all", "send to everyone"],
        "medium":   ["report", "schedule", "notify team", "restart service"],
        "low":      ["draft", "check", "summarize", "analyze", "review"],
    }

    def __init__(self, llm_provider=None):
        self._llm = llm_provider
        self._pattern_library = None  # will be wired from PATCH-119

    def _infer_domain(self, text: str) -> str:
        text_lower = text.lower()
        scores = {domain: 0 for domain in self.DOMAIN_SIGNALS}
        for domain, keywords in self.DOMAIN_SIGNALS.items():
            for kw in keywords:
                if kw in text_lower:
                    scores[domain] += 1
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "system"

    def _infer_urgency(self, text: str) -> str:
        text_lower = text.lower()
        for urgency, signals in self.URGENCY_SIGNALS.items():
            for s in signals:
                if s in text_lower:
                    return urgency
        return "ambient"

    def _infer_stake(self, text: str) -> str:
        text_lower = text.lower()
        for stake, signals in self.STAKE_SIGNALS.items():
            for s in signals:
                if s in text_lower:
                    return stake
        return "low"

    def _extract_entities(self, text: str) -> List[str]:
        """Simple entity extraction: capitalized words, email addresses, URLs."""
        entities = []
        # Capitalized proper nouns
        entities += re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b", text)
        # Email addresses
        entities += re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        # Deduplicate
        return list(dict.fromkeys(entities))[:10]

    def parse(self, nl_text: str, account: str = "unknown") -> WorkflowSpec:
        """
        Parse natural language into a WorkflowSpec.
        Uses keyword heuristics + LLM for step generation.
        """
        domain = self._infer_domain(nl_text)
        urgency = self._infer_urgency(nl_text)
        stake = self._infer_stake(nl_text)
        entities = self._extract_entities(nl_text)
        constraints = []
        if stake in ("high", "critical"):
            constraints.append("require_approval")
        if urgency == "immediate" and stake == "critical":
            constraints.append("dry_run_first")

        steps = self._generate_steps(nl_text, domain, stake)

        return WorkflowSpec(
            intent=nl_text[:200],
            entities=entities,
            domain=domain,
            urgency=urgency,
            stake=stake,
            constraints=constraints,
            steps=steps,
            raw_text=nl_text,
            confidence=0.7 if self._llm else 0.4,
        )

    def _generate_steps(self, text: str, domain: str, stake: str) -> List[Dict]:
        """Generate workflow steps. Uses LLM if available, else heuristics."""
        if self._llm:
            return self._llm_steps(text, domain, stake)
        return self._heuristic_steps(text, domain)

    def _llm_steps(self, text: str, domain: str, stake: str) -> List[Dict]:
        prompt = f"""You are Murphy. Convert this request into workflow steps.

Request: "{text}"
Domain: {domain}
Stake: {stake}

Output ONLY a JSON array of steps:
[
  {{"name": "step_name", "action": "what_to_do", "args": {{}}, "depends_on": []}},
  ...
]

Rules:
- 3-7 steps maximum
- Each step must have a clear action verb
- High/critical stake: include a "require_human_approval" step
- Last step: always a "log_outcome" step
- depends_on: list of name values of prerequisite steps (empty for first step)
- Return ONLY the JSON array, no other text"""

        try:
            result = self._llm.complete(prompt=prompt, max_tokens=500)
            content = result.content.strip()
            # Extract JSON array
            match = re.search(r"\[.*\]", content, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as exc:
            logger.warning("LLM step generation failed: %s", exc)

        return self._heuristic_steps(text, domain)

    def _heuristic_steps(self, text: str, domain: str) -> List[Dict]:
        """Fallback heuristic steps when LLM unavailable."""
        if domain == "exec_admin":
            return [
                {"name": "analyze_request", "action": "parse_intent", "args": {"text": text[:100]}, "depends_on": []},
                {"name": "prepare_action",  "action": "prepare_exec_admin_action", "args": {}, "depends_on": ["analyze_request"]},
                {"name": "execute_action",  "action": "run_exec_admin_task", "args": {}, "depends_on": ["prepare_action"]},
                {"name": "log_outcome",     "action": "record_to_pattern_library", "args": {}, "depends_on": ["execute_action"]},
            ]
        elif domain == "prod_ops":
            return [
                {"name": "validate_safety",  "action": "pcc_gate_check", "args": {}, "depends_on": []},
                {"name": "prepare_prodop",   "action": "prepare_production_action", "args": {"text": text[:100]}, "depends_on": ["validate_safety"]},
                {"name": "execute_prodop",   "action": "run_prod_ops_task", "args": {}, "depends_on": ["prepare_prodop"]},
                {"name": "verify_outcome",   "action": "check_health_post_action", "args": {}, "depends_on": ["execute_prodop"]},
                {"name": "log_outcome",      "action": "record_to_pattern_library", "args": {}, "depends_on": ["verify_outcome"]},
            ]
        else:
            return [
                {"name": "process_request", "action": "handle_generic_request", "args": {"text": text[:100]}, "depends_on": []},
                {"name": "log_outcome",     "action": "record_to_pattern_library", "args": {}, "depends_on": ["process_request"]},
            ]

    def parse_and_build_dag(self, nl_text: str, account: str = "unknown"):
        """Full pipeline: NL → WorkflowSpec → DAGGraph (ready for execution)."""
        from src.workflow_dag import DAGGraph, DAGNode, NodeType, build_dag, task_node
        import uuid

        spec = self.parse(nl_text, account=account)
        dag = build_dag(
            name=spec.intent[:60],
            description=nl_text[:200],
            domain=spec.domain,
            stake=spec.stake,
            account=account,
        )
        dag.origin_nl_text = nl_text

        # Add GATE node first if high/critical stake
        if spec.stake in ("high", "critical"):
            gate = DAGNode(
                node_id=f"gate-{uuid.uuid4().hex[:6]}",
                node_type=NodeType.GATE,
                name="safety_gate",
                description="PCC stake-level safety check",
                config={"stake": spec.stake, "override": spec.stake != "critical"},
                depends_on=[],
            )
            dag.add_node(gate)

        # Add HITL node if require_approval in constraints
        if "require_approval" in spec.constraints:
            hitl = DAGNode(
                node_id=f"hitl-{uuid.uuid4().hex[:6]}",
                node_type=NodeType.HITL,
                name="human_approval",
                description=f"Human approval required: {spec.intent[:80]}",
                config={"stake": spec.stake, "requester": account},
                depends_on=["safety_gate"] if spec.stake in ("high","critical") else [],
            )
            dag.add_node(hitl)

        # Add task nodes from spec steps
        node_map = {}
        for step in spec.steps:
            deps = step.get("depends_on", [])
            # Translate step name refs to actual node_ids
            resolved_deps = [node_map.get(d, d) for d in deps if d in node_map]
            n = task_node(step["name"], step["action"], step.get("args",{}), resolved_deps)
            node_map[step["name"]] = n.node_id
            dag.add_node(n)

        logger.info("NLWorkflowParser: built DAG %s with %d nodes [domain=%s stake=%s]",
                    dag.dag_id, len(dag.nodes), dag.domain, dag.stake)
        return spec, dag


# ── Singleton ─────────────────────────────────────────────────────────────────
_parser: Optional[NLWorkflowParser] = None

def get_parser() -> NLWorkflowParser:
    global _parser
    if _parser is None:
        try:
            from src.llm_provider import MurphyLLMProvider
            _parser = NLWorkflowParser(llm_provider=MurphyLLMProvider())
        except Exception:
            _parser = NLWorkflowParser()
    return _parser
