"""
Multi-Factor Constraint System
Handles budget, regulatory, architectural, and other constraints
Provides validation, prioritization, conflict resolution, and impact analysis
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("constraint_system")


class ConstraintType(Enum):
    """Types of constraints"""
    BUDGET = "budget"
    REGULATORY = "regulatory"
    ARCHITECTURAL = "architectural"
    PERFORMANCE = "performance"
    SECURITY = "security"
    TIME = "time"
    RESOURCE = "resource"
    BUSINESS = "business"


class ConstraintSeverity(Enum):
    """Constraint severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConstraintStatus(Enum):
    """Constraint status"""
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    WARNING = "warning"
    PENDING = "pending"


@dataclass
class Constraint:
    """Represents a system constraint"""
    constraint_id: str
    name: str
    constraint_type: ConstraintType
    severity: ConstraintSeverity
    description: str
    parameter: str
    operator: str  # <=, >=, ==, !=, contains, matches
    threshold_value: Any
    current_value: Optional[Any] = None
    status: ConstraintStatus = ConstraintStatus.PENDING
    priority: int = 5  # 1-10, higher is more important
    flexible: bool = False  # Can be negotiated
    flex_amount: float = 0.0  # Amount of flexibility if flexible
    dependencies: List[str] = field(default_factory=list)  # Other constraints this depends on
    source: str = "user"  # user, system, regulatory, best_practice
    justification: str = ""
    jurisdiction: str = "GLOBAL"  # jurisdiction code (e.g. "US", "EU", "GLOBAL")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict:
        d = {
            "constraint_id": self.constraint_id,
            "name": self.name,
            "constraint_type": self.constraint_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "parameter": self.parameter,
            "operator": self.operator,
            "threshold_value": self.threshold_value,
            "current_value": self.current_value,
            "status": self.status.value,
            "priority": self.priority,
            "flexible": self.flexible,
            "flex_amount": self.flex_amount,
            "dependencies": self.dependencies,
            "source": self.source,
            "justification": self.justification,
            "jurisdiction": self.jurisdiction,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "success": True,
        }
        return d

    def get(self, key, default=None):
        """Dict-like get for test compatibility"""
        return self.to_dict().get(key, default)


@dataclass
class ConstraintConflict:
    """Represents a conflict between constraints"""
    conflict_id: str
    constraint_1: str  # Constraint ID
    constraint_2: str  # Constraint ID
    conflict_type: str  # "direct", "indirect", "priority", "resource"
    description: str
    severity: str
    suggested_resolution: str
    auto_resolvable: bool = False

    def to_dict(self) -> Dict:
        return {
            "conflict_id": self.conflict_id,
            "constraint_1": self.constraint_1,
            "constraint_2": self.constraint_2,
            "conflict_type": self.conflict_type,
            "description": self.description,
            "severity": self.severity,
            "suggested_resolution": self.suggested_resolution,
            "auto_resolvable": self.auto_resolvable
        }


@dataclass
class ConstraintImpact:
    """Impact of constraint on system"""
    constraint_id: str
    impact_type: str  # "cost", "time", "quality", "scope"
    impact_level: str  # "low", "medium", "high", "critical"
    description: str
    affected_components: List[str]
    mitigation_strategies: List[str]

    def to_dict(self) -> Dict:
        return {
            "constraint_id": self.constraint_id,
            "impact_type": self.impact_type,
            "impact_level": self.impact_level,
            "description": self.description,
            "affected_components": self.affected_components,
            "mitigation_strategies": self.mitigation_strategies
        }


class ConstraintSystem:
    """
    Multi-factor constraint management system
    Handles validation, prioritization, conflict resolution, and impact analysis
    """

    def __init__(self):
        self.constraints: Dict[str, Constraint] = {}
        self.constraint_count = 0
        self.constraint_templates = self._load_constraint_templates()

    def _load_constraint_templates(self) -> Dict:
        """Load constraint templates for common scenarios"""
        return {
            "budget": {
                "templates": [
                    {
                        "name": "total_cost",
                        "description": "Total project cost must not exceed budget",
                        "parameter": "total_cost",
                        "operator": "<=",
                        "flexible": True,
                        "flex_amount": 0.1  # 10% flexibility
                    }
                ]
            },
            "regulatory": {
                "templates": [
                    {
                        "name": "gdpr_compliance",
                        "description": "Must comply with GDPR regulations",
                        "parameter": "gdpr_compliant",
                        "operator": "==",
                        "flexible": False
                    },
                    {
                        "name": "hipaa_compliance",
                        "description": "Must comply with HIPAA regulations",
                        "parameter": "hipaa_compliant",
                        "operator": "==",
                        "flexible": False
                    }
                ]
            },
            "architectural": {
                "templates": [
                    {
                        "name": "scalability",
                        "description": "System must support required scalability",
                        "parameter": "max_users",
                        "operator": ">=",
                        "flexible": True,
                        "flex_amount": 0.05
                    },
                    {
                        "name": "availability",
                        "description": "System must meet availability SLA",
                        "parameter": "uptime_percentage",
                        "operator": ">=",
                        "flexible": False
                    }
                ]
            },
            "performance": {
                "templates": [
                    {
                        "name": "response_time",
                        "description": "Response time must meet SLA",
                        "parameter": "response_time_ms",
                        "operator": "<=",
                        "flexible": True,
                        "flex_amount": 0.2
                    },
                    {
                        "name": "throughput",
                        "description": "System must handle required throughput",
                        "parameter": "requests_per_second",
                        "operator": ">=",
                        "flexible": True,
                        "flex_amount": 0.1
                    }
                ]
            },
            "security": {
                "templates": [
                    {
                        "name": "encryption",
                        "description": "Data must be encrypted at rest and in transit",
                        "parameter": "encryption_enabled",
                        "operator": "==",
                        "flexible": False
                    },
                    {
                        "name": "authentication",
                        "description": "Must implement secure authentication",
                        "parameter": "auth_strength",
                        "operator": ">=",
                        "flexible": False
                    }
                ]
            },
            "time": {
                "templates": [
                    {
                        "name": "deadline",
                        "description": "Project must be completed by deadline",
                        "parameter": "completion_date",
                        "operator": "<=",
                        "flexible": True,
                        "flex_amount": 0.05  # 5% time flexibility
                    }
                ]
            }
        }

    def add_constraint(
        self,
        name_or_dict=None,
        constraint_type=None,
        parameter: str = None,
        operator: str = None,
        threshold_value: Any = None,
        severity: ConstraintSeverity = ConstraintSeverity.MEDIUM,
        description: str = "",
        priority: int = 5,
        flexible: bool = False,
        flex_amount: float = 0.0,
        source: str = "user",
        justification: str = "",
        *,
        name: str = None,
    ) -> Constraint:
        """
        Add a new constraint

        Args:
            name: Constraint name
            constraint_type: Type of constraint
            parameter: Parameter to check
            operator: Comparison operator
            threshold_value: Threshold value
            severity: Severity level
            description: Description
            priority: Priority (1-10)
            flexible: Whether constraint is flexible
            flex_amount: Amount of flexibility
            source: Source of constraint
            justification: Justification for constraint

        Returns:
            Constraint object
        """
        # Handle dict-style calling: add_constraint({"type": "budget", ...})
        if isinstance(name_or_dict, dict):
            d = name_or_dict
            name = d.get("name", d.get("type", "unnamed"))
            ct = d.get("type", d.get("constraint_type", "business"))
            try:
                constraint_type = ConstraintType(ct.lower()) if isinstance(ct, str) else ct
            except ValueError:
                constraint_type = ConstraintType.BUSINESS
            parameter = d.get("parameter", name)
            operator = d.get("operator", "<=")
            threshold_value = d.get("limit", d.get("threshold_value", d.get("value", 0)))
            description = d.get("description", "")
        else:
            # Positional first arg is name (str) or use keyword name
            if name_or_dict is not None:
                name = name_or_dict
            # name may also come from keyword-only arg
            if name is None:
                name = "unnamed"
            # Resolve constraint_type from string if needed
            if isinstance(constraint_type, str):
                try:
                    constraint_type = ConstraintType(constraint_type.lower())
                except ValueError:
                    constraint_type = ConstraintType.BUSINESS
            if constraint_type is None:
                constraint_type = ConstraintType.BUSINESS
            if parameter is None:
                parameter = name
            if operator is None:
                operator = "<="
            if threshold_value is None:
                threshold_value = 0

        self.constraint_count += 1
        constraint_id = f"constraint_{self.constraint_count}"

        constraint = Constraint(
            constraint_id=constraint_id,
            name=name,
            constraint_type=constraint_type,
            severity=severity,
            description=description or f"{name} constraint",
            parameter=parameter,
            operator=operator,
            threshold_value=threshold_value,
            priority=priority,
            flexible=flexible,
            flex_amount=flex_amount,
            source=source,
            justification=justification
        )

        self.constraints[constraint_id] = constraint
        return constraint

    def add_constraint_from_template(
        self,
        template_type: str,
        template_name: str,
        threshold_value: Any,
        priority: int = 5,
        justification: str = ""
    ) -> Optional[Constraint]:
        """
        Add constraint from predefined template

        Args:
            template_type: Type category (budget, regulatory, etc.)
            template_name: Name of template
            threshold_value: Threshold value
            priority: Priority
            justification: Justification

        Returns:
            Constraint object or None if template not found
        """
        templates = self.constraint_templates.get(template_type, {})
        template_data = None

        for template in templates.get("templates", []):
            if template["name"] == template_name:
                template_data = template
                break

        if not template_data:
            return None

        # Map template type to ConstraintType
        type_mapping = {
            "budget": ConstraintType.BUDGET,
            "regulatory": ConstraintType.REGULATORY,
            "architectural": ConstraintType.ARCHITECTURAL,
            "performance": ConstraintType.PERFORMANCE,
            "security": ConstraintType.SECURITY,
            "time": ConstraintType.TIME
        }

        constraint_type = type_mapping.get(template_type, ConstraintType.BUSINESS)

        # Determine severity based on flexibility
        severity = ConstraintSeverity.HIGH if not template_data.get("flexible") else ConstraintSeverity.MEDIUM

        return self.add_constraint(
            name=template_name,
            constraint_type=constraint_type,
            parameter=template_data["parameter"],
            operator=template_data["operator"],
            threshold_value=threshold_value,
            severity=severity,
            description=template_data["description"],
            priority=priority,
            flexible=template_data.get("flexible", False),
            flex_amount=template_data.get("flex_amount", 0.0),
            source="template",
            justification=justification
        )

    def select_constraints(self, jurisdiction: str) -> List[Constraint]:
        """
        Return constraints that apply in the given *jurisdiction*.

        A constraint matches if its ``jurisdiction`` field equals *jurisdiction*
        or is ``"GLOBAL"``.
        """
        return [
            c for c in self.constraints.values()
            if c.jurisdiction in (jurisdiction, "GLOBAL")
        ]

    def validate_constraints(
        self,
        system_state: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Validate all constraints against current system state

        Args:
            system_state: Current system state with parameter values

        Returns:
            Tuple of (validation_results, warnings)
        """
        results = {
            "total_constraints": len(self.constraints),
            "satisfied": 0,
            "violated": 0,
            "warnings": 0,
            "pending": 0,
            "constraints": {}
        }

        warnings = []

        for constraint_id, constraint in self.constraints.items():
            # Get current value from system state
            current_value = system_state.get(constraint.parameter)
            constraint.current_value = current_value

            if current_value is None:
                constraint.status = ConstraintStatus.PENDING
                results["pending"] += 1
                warnings.append(f"Constraint {constraint.name}: No value provided for {constraint.parameter}")
                continue

            # Check constraint
            passed = self._check_constraint_value(
                current_value,
                constraint.operator,
                constraint.threshold_value
            )

            if passed:
                constraint.status = ConstraintStatus.SATISFIED
                results["satisfied"] += 1
            else:
                # Check if flexible constraint can be satisfied with flexibility
                if constraint.flexible and self._check_with_flexibility(
                    current_value,
                    constraint.operator,
                    constraint.threshold_value,
                    constraint.flex_amount
                ):
                    constraint.status = ConstraintStatus.WARNING
                    results["warnings"] += 1
                    warnings.append(
                        f"Constraint {constraint.name}: Slightly violated but within flexibility "
                        f"({constraint.flex_amount:.1%})"
                    )
                else:
                    constraint.status = ConstraintStatus.VIOLATED
                    results["violated"] += 1
                    warnings.append(f"Constraint {constraint.name}: Violated")

            results["constraints"][constraint_id] = {
                "name": constraint.name,
                "status": constraint.status.value,
                "current_value": current_value,
                "threshold_value": constraint.threshold_value,
                "passed": constraint.status == ConstraintStatus.SATISFIED
            }

            # Update timestamp
            constraint.updated_at = datetime.now(timezone.utc).isoformat()

        return results, warnings

    def _check_constraint_value(
        self,
        current: Any,
        operator: str,
        threshold: Any
    ) -> bool:
        """Check if constraint value passes"""
        try:
            if operator == "<=":
                return float(current) <= float(threshold)
            elif operator == ">=":
                return float(current) >= float(threshold)
            elif operator == "<":
                return float(current) < float(threshold)
            elif operator == ">":
                return float(current) > float(threshold)
            elif operator == "==":
                return current == threshold
            elif operator == "!=":
                return current != threshold
            elif operator == "contains":
                return str(threshold) in str(current)
            elif operator == "matches":
                import re
                return bool(re.match(str(threshold), str(current)))
            else:
                return False
        except (TypeError, ValueError):
            return False

    def _check_with_flexibility(
        self,
        current: Any,
        operator: str,
        threshold: Any,
        flex_amount: float
    ) -> bool:
        """Check if constraint passes with flexibility applied"""
        try:
            current_float = float(current)
            threshold_float = float(threshold)

            # Apply flexibility to threshold
            if operator in ["<=", "<"]:
                # For less-than constraints, increase threshold by flex_amount
                adjusted_threshold = threshold_float * (1 + flex_amount)
                return current_float <= adjusted_threshold
            elif operator in [">=", ">"]:
                # For greater-than constraints, decrease threshold by flex_amount
                adjusted_threshold = threshold_float * (1 - flex_amount)
                return current_float >= adjusted_threshold
            else:
                return False
        except (TypeError, ValueError):
            return False

    def prioritize_constraints(
        self,
        constraints: Optional[List[Constraint]] = None
    ) -> List[Constraint]:
        """
        Prioritize constraints by severity and priority

        Args:
            constraints: List of constraints (default: all constraints)

        Returns:
            Prioritized list of constraints
        """
        constraints_to_sort = constraints if constraints else list(self.constraints.values())

        # Sort by severity then priority
        severity_order = {
            ConstraintSeverity.CRITICAL: 0,
            ConstraintSeverity.HIGH: 1,
            ConstraintSeverity.MEDIUM: 2,
            ConstraintSeverity.LOW: 3
        }

        return sorted(
            constraints_to_sort,
            key=lambda c: (severity_order.get(c.severity, 4), -c.priority)
        )

    def detect_conflicts(
        self,
        constraints: Optional[List[Constraint]] = None
    ) -> List[ConstraintConflict]:
        """
        Detect conflicts between constraints

        Args:
            constraints: List of constraints to check (default: all)

        Returns:
            List of conflicts
        """
        constraints_to_check = constraints if constraints else list(self.constraints.values())
        conflicts = []
        conflict_count = 0

        for i, c1 in enumerate(constraints_to_check):
            for c2 in constraints_to_check[i+1:]:
                conflict = self._check_pair_conflict(c1, c2)
                if conflict:
                    conflict_count += 1
                    conflict.conflict_id = f"conflict_{conflict_count}"
                    conflicts.append(conflict)

        return conflicts

    def _check_pair_conflict(
        self,
        c1: Constraint,
        c2: Constraint
    ) -> Optional[ConstraintConflict]:
        """Check if two constraints conflict"""
        # Check for parameter conflicts
        if c1.parameter == c2.parameter:
            if c1.operator != c2.operator:
                # Opposite operators on same parameter
                if (c1.operator in ["<=", "<"] and c2.operator in [">=", ">"]) or \
                   (c1.operator in [">=", ">"] and c2.operator in ["<=", "<"]):
                    return ConstraintConflict(
                        conflict_id="",
                        constraint_1=c1.constraint_id,
                        constraint_2=c2.constraint_id,
                        conflict_type="direct",
                        description=f"Conflicting constraints on {c1.parameter}: "
                                   f"{c1.name} ({c1.operator} {c1.threshold_value}) vs "
                                   f"{c2.name} ({c2.operator} {c2.threshold_value})",
                        severity="high",
                        suggested_resolution="Review and adjust thresholds or remove one constraint",
                        auto_resolvable=False
                    )

        # Check for resource conflicts
        if c1.constraint_type in [ConstraintType.BUDGET, ConstraintType.RESOURCE] and \
           c2.constraint_type in [ConstraintType.BUDGET, ConstraintType.RESOURCE]:
            # Both constraining resources, may conflict
            return ConstraintConflict(
                conflict_id="",
                constraint_1=c1.constraint_id,
                constraint_2=c2.constraint_id,
                conflict_type="resource",
                description=f"Resource constraint conflict between {c1.name} and {c2.name}",
                severity="medium",
                suggested_resolution="Evaluate resource allocation and prioritize constraints",
                auto_resolvable=True
            )

        # Check for priority conflicts
        if c1.priority != c2.priority and c1.severity == c2.severity:
            # Same severity but different priorities
            return ConstraintConflict(
                conflict_id="",
                constraint_1=c1.constraint_id,
                constraint_2=c2.constraint_id,
                conflict_type="priority",
                description=f"Priority mismatch: {c1.name} (priority {c1.priority}) vs "
                           f"{c2.name} (priority {c2.priority})",
                severity="low",
                suggested_resolution="Review priority assignments to ensure alignment",
                auto_resolvable=True
            )

        return None

    def resolve_conflicts(
        self,
        conflicts: List[ConstraintConflict],
        resolution_strategy: str = "priority"
    ) -> List[Dict[str, Any]]:
        """
        Resolve conflicts between constraints

        Args:
            conflicts: List of conflicts to resolve
            resolution_strategy: Strategy to use (priority, flexible, negotiate)

        Returns:
            List of resolution results
        """
        resolutions = []

        for conflict in conflicts:
            if conflict.auto_resolvable and resolution_strategy == "priority":
                # Auto-resolve by priority
                c1 = self.constraints.get(conflict.constraint_1)
                c2 = self.constraints.get(conflict.constraint_2)

                if c1 and c2:
                    higher_priority = c1 if c1.priority >= c2.priority else c2
                    lower_priority = c2 if c1.priority >= c2.priority else c1

                    resolutions.append({
                        "conflict_id": conflict.conflict_id,
                        "resolved": True,
                        "strategy": "priority",
                        "action": f"Kept {higher_priority.name}, marked {lower_priority.name} as review",
                        "higher_priority": higher_priority.name,
                        "lower_priority": lower_priority.name
                    })

            elif resolution_strategy == "flexible":
                # Try to resolve with flexibility
                c1 = self.constraints.get(conflict.constraint_1)
                c2 = self.constraints.get(conflict.constraint_2)

                if c1 and c2:
                    if c1.flexible and not c2.flexible:
                        resolutions.append({
                            "conflict_id": conflict.conflict_id,
                            "resolved": True,
                            "strategy": "flexible",
                            "action": f"Applied flexibility to {c1.name} to satisfy {c2.name}",
                            "flexible_constraint": c1.name,
                            "fixed_constraint": c2.name
                        })
                    elif c2.flexible and not c1.flexible:
                        resolutions.append({
                            "conflict_id": conflict.conflict_id,
                            "resolved": True,
                            "strategy": "flexible",
                            "action": f"Applied flexibility to {c2.name} to satisfy {c1.name}",
                            "flexible_constraint": c2.name,
                            "fixed_constraint": c1.name
                        })
                    else:
                        resolutions.append({
                            "conflict_id": conflict.conflict_id,
                            "resolved": False,
                            "strategy": "flexible",
                            "action": "Cannot resolve - both constraints fixed or both flexible",
                            "requires_manual_review": True
                        })

            else:
                # Manual negotiation required
                resolutions.append({
                    "conflict_id": conflict.conflict_id,
                    "resolved": False,
                    "strategy": "manual",
                    "action": "Manual negotiation required",
                    "requires_user_input": True
                })

        return resolutions

    def analyze_impact(
        self,
        constraint_id: str,
        system_components: Dict[str, Any]
    ) -> Optional[ConstraintImpact]:
        """
        Analyze impact of a constraint on system

        Args:
            constraint_id: Constraint to analyze
            system_components: System components that could be affected

        Returns:
            ConstraintImpact object or None if constraint not found
        """
        constraint = self.constraints.get(constraint_id)
        if not constraint:
            return None

        # Determine impact type based on constraint type
        impact_mapping = {
            ConstraintType.BUDGET: "cost",
            ConstraintType.TIME: "time",
            ConstraintType.REGULATORY: "quality",
            ConstraintType.SECURITY: "quality",
            ConstraintType.ARCHITECTURAL: "scope",
            ConstraintType.PERFORMANCE: "quality"
        }

        impact_type = impact_mapping.get(constraint.constraint_type, "scope")

        # Determine impact level based on severity
        impact_level_mapping = {
            ConstraintSeverity.CRITICAL: "critical",
            ConstraintSeverity.HIGH: "high",
            ConstraintSeverity.MEDIUM: "medium",
            ConstraintSeverity.LOW: "low"
        }

        impact_level = impact_level_mapping.get(constraint.severity, "medium")

        # Identify affected components
        affected_components = []
        if constraint.constraint_type == ConstraintType.BUDGET:
            affected_components = ["team_size", "resource_allocation", "feature_scope"]
        elif constraint.constraint_type == ConstraintType.TIME:
            affected_components = ["development_phases", "testing", "deployment"]
        elif constraint.constraint_type == ConstraintType.PERFORMANCE:
            affected_components = ["architecture", "database", "caching", "cdn"]
        elif constraint.constraint_type == ConstraintType.SECURITY:
            affected_components = ["authentication", "encryption", "data_handling", "api"]
        elif constraint.constraint_type == ConstraintType.REGULATORY:
            affected_components = ["data_storage", "user_consent", "audit_logs", "compliance"]
        elif constraint.constraint_type == ConstraintType.ARCHITECTURAL:
            affected_components = ["system_design", "technology_stack", "integration"]

        # Generate mitigation strategies
        mitigation_strategies = self._generate_mitigation_strategies(constraint)

        return ConstraintImpact(
            constraint_id=constraint_id,
            impact_type=impact_type,
            impact_level=impact_level,
            description=f"Constraint {constraint.name} affects {impact_type} at {impact_level} level",
            affected_components=affected_components,
            mitigation_strategies=mitigation_strategies
        )

    def _generate_mitigation_strategies(self, constraint: Constraint) -> List[str]:
        """Generate mitigation strategies for a constraint"""
        strategies = []

        if constraint.constraint_type == ConstraintType.BUDGET:
            strategies = [
                "Prioritize features by business value",
                "Consider phased implementation",
                "Explore cost-effective alternatives",
                "Negotiate flexible constraint if possible"
            ]
        elif constraint.constraint_type == ConstraintType.TIME:
            strategies = [
                "Parallelize development activities",
                "Reduce scope to critical features",
                "Increase team size if budget allows",
                "Consider agile methodology with MVP approach"
            ]
        elif constraint.constraint_type == ConstraintType.PERFORMANCE:
            strategies = [
                "Implement caching strategies",
                "Optimize database queries",
                "Use CDN for static content",
                "Consider horizontal scaling"
            ]
        elif constraint.constraint_type == ConstraintType.SECURITY:
            strategies = [
                "Implement security best practices",
                "Conduct regular security audits",
                "Use established security libraries",
                "Educate team on security protocols"
            ]
        elif constraint.constraint_type == ConstraintType.REGULATORY:
            strategies = [
                "Consult with compliance experts",
                "Implement compliance by design",
                "Maintain audit trails",
                "Regular compliance reviews"
            ]
        else:
            strategies = [
                "Review constraint feasibility",
                "Consider alternative approaches",
                "Document constraint rationale",
                "Monitor constraint impact"
            ]

        return strategies

    def generate_constraint_report(
        self,
        include_details: bool = True
    ) -> Dict[str, Any]:
        """
        Generate comprehensive constraint report

        Args:
            include_details: Include detailed constraint information

        Returns:
            Report dictionary
        """
        # Count by type
        by_type = {}
        for constraint in self.constraints.values():
            constraint_type = constraint.constraint_type.value
            by_type[constraint_type] = by_type.get(constraint_type, 0) + 1

        # Count by severity
        by_severity = {}
        for constraint in self.constraints.values():
            severity = constraint.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1

        # Count by status
        by_status = {}
        for constraint in self.constraints.values():
            status = constraint.status.value
            by_status[status] = by_status.get(status, 0) + 1

        report = {
            "total_constraints": len(self.constraints),
            "by_type": by_type,
            "by_severity": by_severity,
            "by_status": by_status,
            "flexible_constraints": sum(1 for c in self.constraints.values() if c.flexible),
            "fixed_constraints": sum(1 for c in self.constraints.values() if not c.flexible),
            "high_priority": sum(1 for c in self.constraints.values() if c.priority >= 8)
        }

        if include_details:
            report["constraints"] = {
                constraint_id: constraint.to_dict()
                for constraint_id, constraint in self.constraints.items()
            }

        return report


if __name__ == "__main__":
    # Test constraint system
    system = ConstraintSystem()

    # Test 1: Add constraints
    logger.info("=== Test 1: Add Constraints ===")

    # Budget constraint
    budget_constraint = system.add_constraint_from_template(
        "budget", "total_cost", 10000,
        priority=9,
        justification="Project budget limit"
    )
    logger.info(f"Added: {budget_constraint.name}")

    # Performance constraint
    perf_constraint = system.add_constraint_from_template(
        "performance", "response_time", 200,
        priority=8,
        justification="User experience requirement"
    )
    logger.info(f"Added: {perf_constraint.name}")

    # Regulatory constraint
    reg_constraint = system.add_constraint_from_template(
        "regulatory", "gdpr_compliance", True,
        priority=10,
        justification="Legal requirement"
    )
    logger.info(f"Added: {reg_constraint.name}")

    # Architectural constraint
    arch_constraint = system.add_constraint_from_template(
        "architectural", "availability", 99.9,
        priority=8,
        justification="SLA requirement"
    )
    logger.info(f"Added: {arch_constraint.name}")

    # Test 2: Validate constraints
    logger.info("\n=== Test 2: Validate Constraints ===")
    system_state = {
        "total_cost": 9500,
        "response_time_ms": 180,
        "gdpr_compliant": True,
        "uptime_percentage": 99.8
    }

    results, warnings = system.validate_constraints(system_state)
    logger.info(f"Satisfied: {results['satisfied']}")
    logger.info(f"Violated: {results['violated']}")
    logger.info(f"Warnings: {results['warnings']}")
    logger.info(f"Pending: {results['pending']}")

    for warning in warnings:
        logger.info(f"  - {warning}")

    # Test 3: Detect conflicts
    logger.info("\n=== Test 3: Detect Conflicts ===")
    conflicts = system.detect_conflicts()
    logger.info(f"Found {len(conflicts)} conflicts")
    for conflict in conflicts:
        logger.info(f"  - {conflict.description}")

    # Test 4: Prioritize constraints
    logger.info("\n=== Test 4: Prioritize Constraints ===")
    prioritized = system.prioritize_constraints()
    logger.info("Prioritized order:")
    for constraint in prioritized:
        logger.info(f"  {constraint.priority}. {constraint.name} ({constraint.severity.value})")

    # Test 5: Analyze impact
    logger.info("\n=== Test 5: Analyze Impact ===")
    impact = system.analyze_impact(budget_constraint.constraint_id, {})
    if impact:
        logger.info(f"Impact of {budget_constraint.name}:")
        logger.info(f"  Type: {impact.impact_type}")
        logger.info(f"  Level: {impact.impact_level}")
        logger.info(f"  Affected Components: {', '.join(impact.affected_components)}")
        logger.info("  Mitigation Strategies:")
        for strategy in impact.mitigation_strategies:
            logger.info(f"    - {strategy}")

    # Test 6: Generate report
    logger.info("\n=== Test 6: Generate Report ===")
    report = system.generate_constraint_report(include_details=False)
    logger.info(json.dumps(report, indent=2))
