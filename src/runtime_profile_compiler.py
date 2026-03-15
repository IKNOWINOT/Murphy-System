"""
Runtime Execution Profile Compiler for Murphy System

This module compiles onboarding responses and org-chart information into a
RuntimeExecutionProfile that governs task execution, providing:
- Safety level and autonomy level inference from onboarding data
- Escalation policy configuration
- Budget constraint enforcement
- Tool permission management
- Audit requirements based on compliance frameworks
- Thread-safe profile persistence and lookup
- Pre-invocation execution permission checks
"""

import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class RuntimeMode(str, Enum):
    """Runtime execution mode governing overall system behaviour."""
    STRICT = "strict"
    BALANCED = "balanced"
    DYNAMIC = "dynamic"


class SafetyLevel(str, Enum):
    """Safety classification for task execution."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AutonomyLevel(str, Enum):
    """Degree of autonomous operation permitted."""
    FULL_HUMAN = "full_human"
    HUMAN_SUPERVISED = "human_supervised"
    CONFIDENCE_GATED = "confidence_gated"
    AUTONOMOUS = "autonomous"


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class EscalationPolicy:
    """Defines when and how tasks escalate to human operators."""
    escalation_threshold: float = 0.7
    escalation_chain: List[str] = field(default_factory=lambda: ["manager", "director"])
    auto_escalate_on_failure: bool = True
    max_retries_before_escalation: int = 3

    def __post_init__(self):
        self.escalation_threshold = max(0.0, min(1.0, self.escalation_threshold))


@dataclass
class BudgetConstraints:
    """Financial limits for task and session execution."""
    max_cost_per_task: float = 10.0
    max_cost_per_session: float = 100.0
    daily_budget_limit: float = 500.0
    require_approval_above: float = 50.0


@dataclass
class ToolPermissions:
    """Controls which tools may be invoked."""
    allowed_tools: Set[str] = field(default_factory=set)
    denied_tools: Set[str] = field(default_factory=set)
    require_approval_tools: Set[str] = field(default_factory=set)


@dataclass
class AuditRequirements:
    """Audit and compliance tracking configuration."""
    audit_all_executions: bool = False
    retention_days: int = 90
    require_compliance_check: bool = False
    frameworks: List[str] = field(default_factory=list)


@dataclass
class RuntimeExecutionProfile:
    """Compiled profile that governs all task execution for an organisation."""
    profile_id: str
    org_id: str
    runtime_mode: RuntimeMode
    safety_level: SafetyLevel
    autonomy_level: AutonomyLevel
    escalation_policy: EscalationPolicy
    budget_constraints: BudgetConstraints
    tool_permissions: ToolPermissions
    audit_requirements: AuditRequirements
    confidence_threshold: float = 0.8
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ------------------------------------------------------------------
# Industries that trigger strict mode
# ------------------------------------------------------------------

_STRICT_INDUSTRIES = {"healthcare", "finance", "government"}
_BALANCED_INDUSTRIES = {"technology", "saas"}


class RuntimeProfileCompiler:
    """Compiles onboarding data into RuntimeExecutionProfiles and enforces them.

    Profiles are persisted in-memory and referenced before every tool
    invocation to ensure safety, budget, and autonomy constraints are met.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._profiles: Dict[str, RuntimeExecutionProfile] = {}
        self._org_index: Dict[str, str] = {}  # org_id -> profile_id

    # ------------------------------------------------------------------
    # Profile compilation
    # ------------------------------------------------------------------

    def compile_profile(
        self,
        org_id: str,
        onboarding_data: Dict[str, Any],
    ) -> RuntimeExecutionProfile:
        """Compile a RuntimeExecutionProfile from onboarding data.

        Infers runtime mode, safety level, escalation policy, budget
        constraints, tool permissions, and audit requirements from the
        provided onboarding responses and org-chart information.
        """
        industry = onboarding_data.get("industry", "").lower().strip()

        # --- runtime mode & safety level ---
        runtime_mode, safety_level = self._infer_mode_and_safety(industry)

        # --- autonomy level ---
        autonomy_level = self._infer_autonomy(onboarding_data, runtime_mode)

        # --- escalation policy ---
        escalation_policy = self._build_escalation_policy(onboarding_data, runtime_mode)

        # --- budget constraints ---
        budget_constraints = self._build_budget_constraints(onboarding_data)

        # --- tool permissions ---
        tool_permissions = self._build_tool_permissions(onboarding_data)

        # --- audit requirements ---
        audit_requirements = self._build_audit_requirements(onboarding_data, industry)

        # --- confidence threshold ---
        confidence_threshold = self._infer_confidence_threshold(runtime_mode)

        profile_id = f"prof-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        profile = RuntimeExecutionProfile(
            profile_id=profile_id,
            org_id=org_id,
            runtime_mode=runtime_mode,
            safety_level=safety_level,
            autonomy_level=autonomy_level,
            escalation_policy=escalation_policy,
            budget_constraints=budget_constraints,
            tool_permissions=tool_permissions,
            audit_requirements=audit_requirements,
            confidence_threshold=confidence_threshold,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._profiles[profile_id] = profile
            self._org_index[org_id] = profile_id

        logger.info(
            "Compiled profile %s for org %s (mode=%s, safety=%s)",
            profile_id, org_id, runtime_mode.value, safety_level.value,
        )
        return profile

    # ------------------------------------------------------------------
    # Profile retrieval
    # ------------------------------------------------------------------

    def get_profile(self, profile_id: str) -> Optional[RuntimeExecutionProfile]:
        """Return a profile by its unique ID, or None if not found."""
        with self._lock:
            return self._profiles.get(profile_id)

    def get_org_profile(self, org_id: str) -> Optional[RuntimeExecutionProfile]:
        """Return the active profile for an organisation, or None."""
        with self._lock:
            pid = self._org_index.get(org_id)
            if pid is None:
                return None
            return self._profiles.get(pid)

    # ------------------------------------------------------------------
    # Profile updates
    # ------------------------------------------------------------------

    def update_profile(
        self,
        profile_id: str,
        updates: Dict[str, Any],
    ) -> Optional[RuntimeExecutionProfile]:
        """Apply partial updates to an existing profile.

        Supports updating scalar fields on the profile as well as nested
        fields on sub-objects (escalation_policy, budget_constraints, etc.).
        Returns the updated profile or None if not found.
        """
        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                logger.warning("Profile %s not found for update", profile_id)
                return None

            for key, value in updates.items():
                if key == "runtime_mode" and isinstance(value, str):
                    profile.runtime_mode = RuntimeMode(value)
                elif key == "safety_level" and isinstance(value, str):
                    profile.safety_level = SafetyLevel(value)
                elif key == "autonomy_level" and isinstance(value, str):
                    profile.autonomy_level = AutonomyLevel(value)
                elif key == "confidence_threshold" and isinstance(value, (int, float)):
                    profile.confidence_threshold = float(value)
                elif key == "escalation_policy" and isinstance(value, dict):
                    for ek, ev in value.items():
                        if hasattr(profile.escalation_policy, ek):
                            setattr(profile.escalation_policy, ek, ev)
                elif key == "budget_constraints" and isinstance(value, dict):
                    for bk, bv in value.items():
                        if hasattr(profile.budget_constraints, bk):
                            setattr(profile.budget_constraints, bk, bv)
                elif key == "audit_requirements" and isinstance(value, dict):
                    for ak, av in value.items():
                        if hasattr(profile.audit_requirements, ak):
                            setattr(profile.audit_requirements, ak, av)
                elif hasattr(profile, key):
                    setattr(profile, key, value)

            profile.updated_at = datetime.now(timezone.utc)

        logger.info("Updated profile %s", profile_id)
        return profile

    # ------------------------------------------------------------------
    # Execution permission checks
    # ------------------------------------------------------------------

    def check_execution_allowed(
        self,
        profile_id: str,
        tool_name: str,
        estimated_cost: float = 0.0,
        confidence: float = 1.0,
    ) -> Tuple[bool, str]:
        """Check whether a tool invocation is allowed under the given profile.

        Returns a (allowed, reason) tuple.
        """
        with self._lock:
            profile = self._profiles.get(profile_id)

        if profile is None:
            return False, "profile_not_found"

        # --- tool permission check ---
        perms = profile.tool_permissions
        if perms.denied_tools and tool_name in perms.denied_tools:
            return False, f"tool '{tool_name}' is denied"
        if perms.allowed_tools and tool_name not in perms.allowed_tools:
            return False, f"tool '{tool_name}' is not in allowed list"
        if perms.require_approval_tools and tool_name in perms.require_approval_tools:
            return False, f"tool '{tool_name}' requires approval"

        # --- budget check ---
        budget = profile.budget_constraints
        if estimated_cost > budget.max_cost_per_task:
            return False, (
                f"estimated cost {estimated_cost} exceeds max per-task "
                f"budget {budget.max_cost_per_task}"
            )

        # --- confidence check ---
        if confidence < profile.confidence_threshold:
            return False, (
                f"confidence {confidence} below threshold "
                f"{profile.confidence_threshold}"
            )

        return True, "allowed"

    def check_autonomy(
        self,
        profile_id: str,
        confidence: float,
    ) -> Tuple[bool, str]:
        """Determine if autonomous execution is permitted at the given confidence.

        Returns (autonomous_ok, reason).
        """
        with self._lock:
            profile = self._profiles.get(profile_id)

        if profile is None:
            return False, "profile_not_found"

        autonomy = profile.autonomy_level

        if autonomy == AutonomyLevel.FULL_HUMAN:
            return False, "full human control required"

        if autonomy == AutonomyLevel.HUMAN_SUPERVISED:
            return False, "human supervision required"

        if autonomy == AutonomyLevel.CONFIDENCE_GATED:
            if confidence >= profile.confidence_threshold:
                return True, "confidence meets threshold"
            return False, (
                f"confidence {confidence} below threshold "
                f"{profile.confidence_threshold}"
            )

        # AUTONOMOUS
        return True, "autonomous execution permitted"

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return overall compiler status."""
        with self._lock:
            total_profiles = len(self._profiles)
            total_orgs = len(self._org_index)
            mode_counts: Dict[str, int] = {}
            for p in self._profiles.values():
                mode_counts[p.runtime_mode.value] = mode_counts.get(p.runtime_mode.value, 0) + 1

        return {
            "total_profiles": total_profiles,
            "total_orgs": total_orgs,
            "mode_distribution": mode_counts,
        }

    # ------------------------------------------------------------------
    # Internal inference helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_mode_and_safety(
        industry: str,
    ) -> Tuple[RuntimeMode, SafetyLevel]:
        """Determine runtime mode and safety level from industry."""
        if industry in _STRICT_INDUSTRIES:
            return RuntimeMode.STRICT, SafetyLevel.CRITICAL
        if industry in _BALANCED_INDUSTRIES:
            return RuntimeMode.BALANCED, SafetyLevel.MEDIUM
        return RuntimeMode.BALANCED, SafetyLevel.MEDIUM

    @staticmethod
    def _infer_autonomy(
        data: Dict[str, Any],
        mode: RuntimeMode,
    ) -> AutonomyLevel:
        """Infer autonomy level from onboarding data and runtime mode."""
        explicit = data.get("autonomy_level")
        if explicit is not None:
            try:
                return AutonomyLevel(explicit)
            except ValueError as exc:
                logger.debug("Suppressed %s: %s", type(exc).__name__, exc)  # noqa: E501

        if mode == RuntimeMode.STRICT:
            return AutonomyLevel.HUMAN_SUPERVISED
        if mode == RuntimeMode.DYNAMIC:
            return AutonomyLevel.CONFIDENCE_GATED
        return AutonomyLevel.CONFIDENCE_GATED

    @staticmethod
    def _infer_confidence_threshold(mode: RuntimeMode) -> float:
        """Return the default confidence threshold for a runtime mode."""
        if mode == RuntimeMode.STRICT:
            return 0.95
        if mode == RuntimeMode.DYNAMIC:
            return 0.7
        return 0.8

    @staticmethod
    def _build_escalation_policy(
        data: Dict[str, Any],
        mode: RuntimeMode,
    ) -> EscalationPolicy:
        """Build an escalation policy from onboarding data."""
        chain = data.get("escalation_chain", ["manager", "director"])
        if mode == RuntimeMode.STRICT:
            return EscalationPolicy(
                escalation_threshold=0.5,
                escalation_chain=list(chain),
                auto_escalate_on_failure=True,
                max_retries_before_escalation=1,
            )
        return EscalationPolicy(
            escalation_threshold=0.7,
            escalation_chain=list(chain),
            auto_escalate_on_failure=True,
            max_retries_before_escalation=3,
        )

    @staticmethod
    def _build_budget_constraints(data: Dict[str, Any]) -> BudgetConstraints:
        """Build budget constraints from onboarding data."""
        budget = data.get("budget", {})
        if not isinstance(budget, dict):
            return BudgetConstraints()
        return BudgetConstraints(
            max_cost_per_task=float(budget.get("max_cost_per_task", 10.0)),
            max_cost_per_session=float(budget.get("max_cost_per_session", 100.0)),
            daily_budget_limit=float(budget.get("daily_budget_limit", 500.0)),
            require_approval_above=float(budget.get("require_approval_above", 50.0)),
        )

    @staticmethod
    def _build_tool_permissions(data: Dict[str, Any]) -> ToolPermissions:
        """Build tool permissions from onboarding data."""
        perms = data.get("tool_permissions", {})
        if not isinstance(perms, dict):
            return ToolPermissions()
        return ToolPermissions(
            allowed_tools=set(perms.get("allowed_tools", [])),
            denied_tools=set(perms.get("denied_tools", [])),
            require_approval_tools=set(perms.get("require_approval_tools", [])),
        )

    @staticmethod
    def _build_audit_requirements(
        data: Dict[str, Any],
        industry: str,
    ) -> AuditRequirements:
        """Build audit requirements from onboarding data and industry."""
        frameworks = data.get("compliance_frameworks", [])
        if not isinstance(frameworks, list):
            frameworks = []

        if industry in _STRICT_INDUSTRIES:
            return AuditRequirements(
                audit_all_executions=True,
                retention_days=365,
                require_compliance_check=True,
                frameworks=list(frameworks),
            )

        if frameworks:
            return AuditRequirements(
                audit_all_executions=True,
                retention_days=180,
                require_compliance_check=True,
                frameworks=list(frameworks),
            )

        return AuditRequirements()
