"""
Deterministic Routing Engine for Murphy System

Implements policy-driven compute routing that enforces deterministic vs. LLM
routing by task tag, promotes MFGC fallback output into the main execution
graph, and hardens runtime guardrails for compute-session wiring parity.

References:
  - Section 3 item 2: broader policy-driven compute routing
  - Section 12 Step 1 items 2-3: MFGC fallback promotion, deterministic vs. LLM routing
  - Section 14.1 items 1-2: compute-session wiring parity, runtime guardrail hardening
"""

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


@dataclass
class RoutingPolicy:
    """A policy that maps task tags to a routing strategy."""
    policy_id: str
    name: str
    task_tags: List[str]
    route_type: str  # "deterministic", "llm", "hybrid"
    priority: int = 0
    fallback_route: str = "deterministic"
    guardrails: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class RoutingDecision:
    """Record of a single routing decision."""
    decision_id: str
    task_type: str
    matched_policy: Optional[str]
    route_type: str
    confidence: float
    reason: str
    guardrails_applied: List[str]
    timestamp: str


# Default policies for common task categories
_DEFAULT_POLICIES = [
    RoutingPolicy(
        policy_id="policy-math",
        name="Math / Compute",
        task_tags=["math", "compute", "calculation", "arithmetic"],
        route_type="deterministic",
        priority=10,
        fallback_route="deterministic",
        guardrails={"max_iterations": 1000, "timeout_s": 30},
    ),
    RoutingPolicy(
        policy_id="policy-validation",
        name="Validation",
        task_tags=["validation", "verify", "check", "audit"],
        route_type="deterministic",
        priority=10,
        fallback_route="deterministic",
        guardrails={"strict_mode": True},
    ),
    RoutingPolicy(
        policy_id="policy-creative",
        name="Creative / Generation",
        task_tags=["creative", "generation", "writing", "brainstorm"],
        route_type="llm",
        priority=5,
        fallback_route="deterministic",
        guardrails={"content_filter": True, "max_tokens": 4096},
    ),
    RoutingPolicy(
        policy_id="policy-analysis",
        name="Analysis",
        task_tags=["analysis", "research", "investigate", "evaluate"],
        route_type="hybrid",
        priority=7,
        fallback_route="deterministic",
        guardrails={"require_sources": True},
    ),
]


class DeterministicRoutingEngine:
    """Policy-driven routing engine that decides deterministic vs. LLM execution."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._policies: Dict[str, RoutingPolicy] = {}
        self._decisions: List[Dict[str, Any]] = []
        self._promotions: List[Dict[str, Any]] = []
        self._route_counts: Dict[str, int] = defaultdict(int)
        self._policy_hits: Dict[str, int] = defaultdict(int)
        self._load_defaults()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_defaults(self) -> None:
        for p in _DEFAULT_POLICIES:
            self._policies[p.policy_id] = RoutingPolicy(
                policy_id=p.policy_id,
                name=p.name,
                task_tags=list(p.task_tags),
                route_type=p.route_type,
                priority=p.priority,
                fallback_route=p.fallback_route,
                guardrails=dict(p.guardrails),
                enabled=p.enabled,
            )

    def _match_policy(self, task_type: str, tags: List[str]) -> Optional[RoutingPolicy]:
        """Return the highest-priority enabled policy whose tags overlap."""
        candidates: List[RoutingPolicy] = []
        lookup = set(t.lower() for t in tags)
        lookup.add(task_type.lower())
        for policy in self._policies.values():
            if not policy.enabled:
                continue
            policy_tags = set(t.lower() for t in policy.task_tags)
            if policy_tags & lookup:
                candidates.append(policy)
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.priority, reverse=True)
        return candidates[0]

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _gen_id(self, prefix: str = "rt") -> str:
        return f"{prefix}-{uuid4().hex[:12]}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_policy(self, policy: RoutingPolicy) -> str:
        """Register a routing policy. Returns the policy_id."""
        with self._lock:
            if not policy.policy_id:
                policy.policy_id = self._gen_id("policy")
            self._policies[policy.policy_id] = policy
            logger.info("Registered routing policy %s (%s)", policy.policy_id, policy.name)
            return policy.policy_id

    def route_task(
        self,
        task_type: str,
        tags: Optional[List[str]] = None,
        confidence: float = 0.5,
        context: Optional[Dict[str, Any]] = None,
        runtime_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Determine routing for a task and record the decision."""
        tags = tags or []
        context = context or {}

        # Apply runtime_config route override if present
        if runtime_config is not None:
            override_key = f"route:{task_type}"
            if override_key in runtime_config:
                override_route = runtime_config[override_key]
                decision_dict = {
                    "decision_id": self._gen_id("dec"),
                    "task_type": task_type,
                    "matched_policy": None,
                    "route_type": override_route,
                    "confidence": confidence,
                    "reason": f"runtime_config override: {override_key}={override_route}",
                    "guardrails_applied": ["timeout_enforcement"],
                    "timestamp": self._now(),
                    "status": "routed",
                }
                with self._lock:
                    capped_append(self._decisions, decision_dict)
                    self._route_counts[override_route] += 1
                logger.debug("Routed task '%s' → %s (runtime_config override)", task_type, override_route)
                return decision_dict
        with self._lock:
            matched = self._match_policy(task_type, tags)
            if matched:
                route_type = matched.route_type
                reason = f"Matched policy '{matched.name}' (priority={matched.priority})"
                matched_id = matched.policy_id
                self._policy_hits[matched.policy_id] += 1
            else:
                route_type = "deterministic"
                reason = "No matching policy; defaulting to deterministic"
                matched_id = None

            guardrails_applied = self._evaluate_guardrails_locked(route_type, context)

            decision = RoutingDecision(
                decision_id=self._gen_id("dec"),
                task_type=task_type,
                matched_policy=matched_id,
                route_type=route_type,
                confidence=confidence,
                reason=reason,
                guardrails_applied=guardrails_applied,
                timestamp=self._now(),
            )
            decision_dict = {
                "decision_id": decision.decision_id,
                "task_type": decision.task_type,
                "matched_policy": decision.matched_policy,
                "route_type": decision.route_type,
                "confidence": decision.confidence,
                "reason": decision.reason,
                "guardrails_applied": decision.guardrails_applied,
                "timestamp": decision.timestamp,
                "status": "routed",
            }
            capped_append(self._decisions, decision_dict)
            self._route_counts[route_type] += 1
            logger.debug("Routed task '%s' → %s", task_type, route_type)
            return decision_dict

    def evaluate_guardrails(self, route_type: str, task_context: Dict[str, Any]) -> List[str]:
        """Evaluate safety guardrails for a routing decision."""
        with self._lock:
            return self._evaluate_guardrails_locked(route_type, task_context)

    def _evaluate_guardrails_locked(self, route_type: str, task_context: Dict[str, Any]) -> List[str]:
        applied: List[str] = []

        # Universal guardrail: timeout enforcement
        applied.append("timeout_enforcement")

        if route_type == "deterministic":
            applied.append("deterministic_output_validation")
            if task_context.get("strict"):
                applied.append("strict_mode_enabled")
        elif route_type == "llm":
            applied.append("content_filter")
            applied.append("token_limit_enforcement")
            if task_context.get("sensitive"):
                applied.append("pii_redaction")
        elif route_type == "hybrid":
            applied.append("deterministic_output_validation")
            applied.append("content_filter")

        # Runtime guardrail hardening (Section 14.1 item 2)
        if task_context.get("production"):
            applied.append("production_safety_gate")

        return applied

    def promote_fallback(self, task_id: str, fallback_output: Dict[str, Any]) -> Dict[str, Any]:
        """Promote MFGC fallback output into the main execution graph."""
        with self._lock:
            promotion = {
                "promotion_id": self._gen_id("promo"),
                "task_id": task_id,
                "original_output": fallback_output,
                "promoted": True,
                "promoted_at": self._now(),
                "source": "mfgc_fallback",
                "status": "promoted",
            }
            capped_append(self._promotions, promotion)
            logger.info("Promoted fallback output for task %s", task_id)
            return promotion

    def get_routing_stats(self) -> Dict[str, Any]:
        """Return aggregate routing statistics."""
        with self._lock:
            total = len(self._decisions)
            avg_conf = 0.0
            if total:
                avg_conf = sum(d["confidence"] for d in self._decisions) / total
            return {
                "decisions_count": total,
                "route_type_distribution": dict(self._route_counts),
                "policy_hit_rates": dict(self._policy_hits),
                "average_confidence": round(avg_conf, 4),
                "promotions_count": len(self._promotions),
                "status": "ok",
            }

    def get_decision_history(
        self, task_type: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Return recent routing decisions, optionally filtered."""
        with self._lock:
            history = self._decisions
            if task_type:
                history = [d for d in history if d["task_type"] == task_type]
            return list(reversed(history[-limit:]))

    def validate_route_parity(self, task_type: str) -> Dict[str, Any]:
        """Check that a task_type routes consistently (session wiring parity)."""
        with self._lock:
            relevant = [d for d in self._decisions if d["task_type"] == task_type]
            if not relevant:
                return {
                    "task_type": task_type,
                    "parity": True,
                    "samples": 0,
                    "route_types_seen": [],
                    "variance": 0.0,
                    "status": "no_data",
                }
            route_types = [d["route_type"] for d in relevant]
            unique_routes = list(set(route_types))
            parity = len(unique_routes) == 1
            confidences = [d["confidence"] for d in relevant]
            mean_conf = sum(confidences) / (len(confidences) or 1)
            variance = sum((c - mean_conf) ** 2 for c in confidences) / (len(confidences) or 1)
            return {
                "task_type": task_type,
                "parity": parity,
                "samples": len(relevant),
                "route_types_seen": unique_routes,
                "variance": round(variance, 6),
                "status": "consistent" if parity else "inconsistent",
            }

    def get_policy(self, policy_id: str) -> Dict[str, Any]:
        """Return details for a single policy."""
        with self._lock:
            policy = self._policies.get(policy_id)
            if not policy:
                return {"status": "not_found", "policy_id": policy_id}
            return {
                "policy_id": policy.policy_id,
                "name": policy.name,
                "task_tags": policy.task_tags,
                "route_type": policy.route_type,
                "priority": policy.priority,
                "fallback_route": policy.fallback_route,
                "guardrails": policy.guardrails,
                "enabled": policy.enabled,
                "status": "ok",
            }

    def list_policies(self) -> List[Dict[str, Any]]:
        """Return all registered policies."""
        with self._lock:
            return [
                {
                    "policy_id": p.policy_id,
                    "name": p.name,
                    "task_tags": p.task_tags,
                    "route_type": p.route_type,
                    "priority": p.priority,
                    "enabled": p.enabled,
                }
                for p in self._policies.values()
            ]

    def get_status(self) -> Dict[str, Any]:
        """Return full engine status."""
        with self._lock:
            return {
                "engine": "DeterministicRoutingEngine",
                "policies_registered": len(self._policies),
                "total_decisions": len(self._decisions),
                "total_promotions": len(self._promotions),
                "route_type_distribution": dict(self._route_counts),
                "status": "active",
            }

    def clear(self) -> None:
        """Reset all state and re-load default policies."""
        with self._lock:
            self._policies.clear()
            self._decisions.clear()
            self._promotions.clear()
            self._route_counts.clear()
            self._policy_hits.clear()
            self._load_defaults()
            logger.info("Routing engine cleared and defaults reloaded")

    # ------------------------------------------------------------------
    # Permutation Calibration Integration (Spec Section 3.3)
    # ------------------------------------------------------------------

    def register_permutation_policy(
        self,
        domain: str,
        sequence_id: str,
        ordering: List[str],
        route_type: str = "hybrid",
        priority: int = 15,
    ) -> str:
        """Register a routing policy derived from permutation learning.

        This implements spec Section 3.3: Take promoted sequence policies from
        learning, use them as routing defaults.

        Args:
            domain: The domain this policy applies to
            sequence_id: The promoted sequence ID from permutation registry
            ordering: The learned optimal ordering
            route_type: The routing strategy (deterministic, llm, hybrid)
            priority: Policy priority (higher = higher priority)

        Returns:
            The policy_id for the registered policy
        """
        policy_id = f"perm-{domain}-{sequence_id[:8]}"
        policy = RoutingPolicy(
            policy_id=policy_id,
            name=f"Permutation Policy: {domain}",
            task_tags=[domain, f"seq:{sequence_id}"],
            route_type=route_type,
            priority=priority,
            fallback_route="deterministic",
            guardrails={
                "permutation_ordering": ordering,
                "sequence_id": sequence_id,
                "learned_policy": True,
            },
            enabled=True,
        )
        return self.register_policy(policy)

    def route_with_permutation_awareness(
        self,
        task_type: str,
        domain: str,
        tags: Optional[List[str]] = None,
        confidence: float = 0.5,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Route a task with awareness of learned permutation policies.

        This method checks if a learned permutation policy exists for the domain
        and includes the ordering information in the routing decision.

        Args:
            task_type: Type of task being routed
            domain: Domain for permutation policy lookup
            tags: Additional tags for policy matching
            confidence: Confidence score for the routing
            context: Additional context for guardrail evaluation

        Returns:
            Routing decision with permutation ordering if available
        """
        tags = tags or []
        context = context or {}

        # Check for permutation policies for this domain
        permutation_policies = []
        with self._lock:
            for policy in self._policies.values():
                if policy.enabled and policy.guardrails.get("learned_policy"):
                    if domain in policy.task_tags:
                        permutation_policies.append(policy)

        # Standard routing first
        decision = self.route_task(task_type, tags + [domain], confidence, context)

        # Enrich with permutation information if available
        if permutation_policies:
            best_policy = max(permutation_policies, key=lambda p: p.priority)
            decision["permutation_policy_applied"] = True
            decision["permutation_ordering"] = best_policy.guardrails.get("permutation_ordering", [])
            decision["sequence_id"] = best_policy.guardrails.get("sequence_id")
            logger.info(
                "Applied permutation policy %s for domain %s",
                best_policy.policy_id, domain
            )
        else:
            decision["permutation_policy_applied"] = False
            decision["permutation_ordering"] = None
            decision["sequence_id"] = None

        return decision

    def switch_routing_mode(
        self,
        domain: str,
        mode: str,  # "exploratory" or "procedural"
    ) -> Dict[str, Any]:
        """Switch between exploratory (Mode A) and procedural (Mode B) routing.

        This implements the spec requirement to switch between deterministic,
        hybrid, and exploratory behavior based on learning state.

        Args:
            domain: The domain to switch modes for
            mode: Either "exploratory" (Mode A) or "procedural" (Mode B)

        Returns:
            Status of the mode switch
        """
        with self._lock:
            affected_policies = []
            for policy in self._policies.values():
                if policy.guardrails.get("learned_policy") and domain in policy.task_tags:
                    if mode == "exploratory":
                        # Disable procedural policies in Mode A
                        policy.enabled = False
                        affected_policies.append(policy.policy_id)
                    elif mode == "procedural":
                        # Enable procedural policies in Mode B
                        policy.enabled = True
                        affected_policies.append(policy.policy_id)

        logger.info("Switched domain %s to %s mode, affected policies: %s",
                    domain, mode, affected_policies)

        return {
            "status": "ok",
            "domain": domain,
            "mode": mode,
            "affected_policies": affected_policies,
        }

    def get_permutation_routing_stats(self) -> Dict[str, Any]:
        """Get statistics specific to permutation-based routing.

        Returns:
            Stats on permutation policies and their usage
        """
        with self._lock:
            permutation_policies = [
                p for p in self._policies.values()
                if p.guardrails.get("learned_policy")
            ]
            enabled = [p for p in permutation_policies if p.enabled]
            disabled = [p for p in permutation_policies if not p.enabled]

            # Count decisions that used permutation policies
            perm_policy_ids = {p.policy_id for p in permutation_policies}
            perm_decisions = [
                d for d in self._decisions
                if d.get("matched_policy") in perm_policy_ids
            ]

        return {
            "status": "ok",
            "total_permutation_policies": len(permutation_policies),
            "enabled_policies": len(enabled),
            "disabled_policies": len(disabled),
            "permutation_routing_decisions": len(perm_decisions),
            "domains_with_policies": list(set(
                tag for p in permutation_policies
                for tag in p.task_tags if not tag.startswith("seq:")
            )),
        }
