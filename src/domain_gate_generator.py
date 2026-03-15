"""
Domain Gate Generation System
Generates domain-specific gates with wired functions
Integrates with librarian system for knowledge reference
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("domain_gate_generator")


class GateType(Enum):
    """Types of gates"""
    VALIDATION = "validation"
    AUTHORIZATION = "authorization"
    CONSTRAINT = "constraint"
    QUALITY = "quality"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    PERFORMANCE = "performance"
    MONITORING = "monitoring"
    ARCHITECTURAL = "architectural"
    BUSINESS = "business"
    SAFETY = "safety"


class GateSeverity(Enum):
    """Gate severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class GateCondition:
    """Condition that must be met for gate to pass"""
    condition_id: str
    condition_type: str  # e.g., "threshold", "presence", "format", "custom"
    parameter: str
    operator: str  # e.g., ">", "<", "==", "!=", "contains", "matches"
    expected_value: Any
    description: str

    def to_dict(self) -> Dict:
        return {
            "condition_id": self.condition_id,
            "condition_type": self.condition_type,
            "parameter": self.parameter,
            "operator": self.operator,
            "expected_value": self.expected_value,
            "description": self.description
        }


@dataclass
class GateAction:
    """Action to take when gate passes or fails"""
    action_id: str
    action_type: str  # "proceed", "retry", "escalate", "block", "log", "notify"
    trigger: str  # "pass" or "fail"
    target: str  # what system or component to act on
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "trigger": self.trigger,
            "target": self.target,
            "parameters": self.parameters
        }


@dataclass
class DomainGate:
    """Domain-specific gate with wired function"""
    gate_id: str
    name: str
    description: str
    gate_type: GateType
    severity: GateSeverity
    conditions: List[GateCondition]
    pass_actions: List[GateAction]
    fail_actions: List[GateAction]
    wired_function: Optional[str] = None  # Reference to function in code
    function_signature: Optional[str] = None
    risk_reduction: float = 0.5  # 0.0 to 1.0
    confidence_threshold: float = 0.85
    knowledge_references: List[str] = field(default_factory=list)  # Links to librarian
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "gate_id": self.gate_id,
            "name": self.name,
            "description": self.description,
            "gate_type": self.gate_type.value,
            "severity": self.severity.value,
            "conditions": [c.to_dict() for c in self.conditions],
            "pass_actions": [a.to_dict() for a in self.pass_actions],
            "fail_actions": [a.to_dict() for a in self.fail_actions],
            "wired_function": self.wired_function,
            "function_signature": self.function_signature,
            "risk_reduction": self.risk_reduction,
            "confidence_threshold": self.confidence_threshold,
            "knowledge_references": self.knowledge_references,
            "metrics": self.metrics,
            "gate": self.name,
        }

    def __contains__(self, item):
        """Support 'in' operator for dict-like field access"""
        return hasattr(self, item) or item in self.to_dict()


class LibrarianKnowledgeBase:
    """
    Knowledge base integration with librarian system
    Provides best practices, regulatory standards, architectural requirements
    """

    def __init__(self):
        self.knowledge_base = self._initialize_knowledge_base()

    def _initialize_knowledge_base(self) -> Dict[str, Any]:
        """Initialize knowledge base with domain knowledge"""
        return {
            "software": {
                "best_practices": [
                    {"name": "code_review", "description": "All code must be reviewed before merge"},
                    {"name": "test_coverage", "description": "Minimum 80% test coverage required"},
                    {"name": "documentation", "description": "All APIs must be documented"},
                    {"name": "error_handling", "description": "Proper error handling required"},
                    {"name": "security_scanning", "description": "Security scans must pass"}
                ],
                "regulatory_standards": [
                    {"name": "gdpr", "description": "GDPR compliance for data handling"},
                    {"name": "hipaa", "description": "HIPAA compliance for healthcare data"},
                    {"name": "pci_dss", "description": "PCI DSS compliance for payment data"},
                    {"name": "soc2", "description": "SOC2 compliance for security"}
                ],
                "architectural_requirements": [
                    {"name": "scalability", "description": "System must support 10x growth"},
                    {"name": "availability", "description": "99.9% uptime required"},
                    {"name": "fault_tolerance", "description": "No single point of failure"},
                    {"name": "observability", "description": "Comprehensive logging and monitoring"}
                ]
            },
            "infrastructure": {
                "best_practices": [
                    {"name": "infrastructure_as_code", "description": "IaC for all infrastructure"},
                    {"name": "immutable_infrastructure", "description": "Replace don't modify"},
                    {"name": "least_privilege", "description": "Minimal access permissions"},
                    {"name": "backup_strategy", "description": "Automated backups"},
                    {"name": "disaster_recovery", "description": "DR plan in place"}
                ],
                "regulatory_standards": [
                    {"name": "iso27001", "description": "ISO 27001 security standard"},
                    {"name": "nist_csf", "description": "NIST Cybersecurity Framework"},
                    {"name": "cmmc", "description": "CMMC for defense contracts"}
                ],
                "architectural_requirements": [
                    {"name": "high_availability", "description": "Multi-region deployment"},
                    {"name": "autoscaling", "description": "Auto-scaling enabled"},
                    {"name": "load_balancing", "description": "Load balancers configured"},
                    {"name": "monitoring", "description": "Full stack monitoring"}
                ]
            },
            "data": {
                "best_practices": [
                    {"name": "data_governance", "description": "Data governance framework"},
                    {"name": "data_quality", "description": "Data quality checks"},
                    {"name": "privacy_by_design", "description": "Privacy considerations built in"},
                    {"name": "encryption_at_rest", "description": "Data encrypted at rest"},
                    {"name": "encryption_in_transit", "description": "Data encrypted in transit"}
                ],
                "regulatory_standards": [
                    {"name": "gdpr", "description": "GDPR data protection"},
                    {"name": "ccpa", "description": "CCPA privacy rights"},
                    {"name": "data_localization", "description": "Data residency requirements"}
                ],
                "architectural_requirements": [
                    {"name": "data_lake", "description": "Centralized data lake"},
                    {"name": "streaming", "description": "Real-time data streaming"},
                    {"name": "batch_processing", "description": "Batch processing capabilities"},
                    {"name": "ml_ops", "description": "MLOps pipeline in place"}
                ]
            }
        }

    def get_knowledge(
        self,
        domain: str,
        category: str
    ) -> List[Dict[str, str]]:
        """Get knowledge for a domain and category"""
        return self.knowledge_base.get(domain, {}).get(category, [])

    def search_knowledge(
        self,
        query: str,
        domain: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Search knowledge base for matching items"""
        results = []
        domains_to_search = [domain] if domain else self.knowledge_base.keys()

        for d in domains_to_search:
            for category in ["best_practices", "regulatory_standards", "architectural_requirements"]:
                for item in self.knowledge_base.get(d, {}).get(category, []):
                    if query.lower() in item["name"].lower() or query.lower() in item["description"].lower():
                        results.append({
                            "domain": d,
                            "category": category,
                            **item
                        })

        return results

    def get_gate_templates(self, domain: str) -> List[Dict[str, Any]]:
        """Get gate templates for a domain"""
        templates = []

        for category in ["best_practices", "regulatory_standards", "architectural_requirements"]:
            for item in self.knowledge_base.get(domain, {}).get(category, []):
                template = self._create_gate_template(item, category)
                templates.append(template)

        return templates

    def _create_gate_template(self, item: Dict, category: str) -> Dict[str, Any]:
        """Create a gate template from knowledge item"""
        gate_type_mapping = {
            "best_practices": GateType.VALIDATION,
            "regulatory_standards": GateType.COMPLIANCE,
            "architectural_requirements": GateType.ARCHITECTURAL
        }

        return {
            "name": item["name"],
            "description": item["description"],
            "gate_type": gate_type_mapping[category].value,
            "category": category,
            "knowledge_reference": f"{category}:{item['name']}"
        }


class DomainGateGenerator:
    """
    Generates domain-specific gates with wired functions
    Integrates with librarian system for knowledge reference
    """

    def __init__(self):
        self.gate_count = 0
        self.librarian = LibrarianKnowledgeBase()
        self.function_registry = self._initialize_function_registry()

    def _initialize_function_registry(self) -> Dict[str, Callable]:
        """Initialize registry of validation functions."""
        return {
            "validate_code_review": self._validate_code_review,
            "validate_test_coverage": self._validate_test_coverage,
            "validate_documentation": self._validate_documentation,
            "validate_security_scan": self._validate_security_scan,
            "validate_performance": self._validate_performance,
            "validate_compliance_gdpr": self._validate_compliance_gdpr,
            "validate_compliance_hipaa": self._validate_compliance_hipaa,
            "validate_scalability": self._validate_scalability,
            "validate_availability": self._validate_availability,
            "validate_backup": self._validate_backup,
        }

    def _build_result(self, validation_type: str, passed: bool, score: float, details: str) -> Dict[str, Any]:
        """Build a standardised validation result dict."""
        return {
            "validation_type": validation_type,
            "passed": passed,
            "score": score,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _validate_code_review(self, data: Dict) -> Dict[str, Any]:
        """Validate that a code review has been completed with sufficient approvals."""
        vtype = "code_review"
        try:
            reviewers = data.get("reviewers", [])
            approvals = data.get("approvals", 0)
            comments_resolved = data.get("comments_resolved", False)
            if not reviewers or approvals < 1 or not comments_resolved:
                issues = []
                if not reviewers:
                    issues.append("no reviewers listed")
                if approvals < 1:
                    issues.append(f"approvals={approvals} (need ≥1)")
                if not comments_resolved:
                    issues.append("unresolved comments")
                return self._build_result(vtype, False, 0.2, "; ".join(issues))
            score = min(1.0, 0.7 + 0.1 * min(approvals, 3))
            return self._build_result(vtype, True, score, f"{approvals} approval(s), all comments resolved")
        except Exception as exc:
            logger.warning("validate_code_review error: %s", exc)
            return self._build_result(vtype, False, 0.0, f"validation error: {exc}")

    def _validate_test_coverage(self, data: Dict, threshold: float = 80.0) -> Dict[str, Any]:
        """Validate that test coverage meets the required threshold."""
        vtype = "test_coverage"
        try:
            coverage = data.get("coverage_percent")
            if coverage is None:
                return self._build_result(vtype, False, 0.0, "coverage_percent not provided")
            coverage = float(coverage)
            passed = coverage >= threshold
            score = min(1.0, coverage / 100.0) if passed else max(0.0, coverage / 100.0 * 0.5)
            detail = f"coverage={coverage:.1f}% (threshold={threshold:.1f}%)"
            return self._build_result(vtype, passed, score, detail)
        except Exception as exc:
            logger.warning("validate_test_coverage error: %s", exc)
            return self._build_result(vtype, False, 0.0, f"validation error: {exc}")

    def _validate_documentation(self, data: Dict) -> Dict[str, Any]:
        """Validate that documentation files are present and README exists."""
        vtype = "documentation"
        try:
            doc_files = data.get("doc_files_present", [])
            has_readme = data.get("has_readme", False)
            if not doc_files or not has_readme:
                issues = []
                if not doc_files:
                    issues.append("no documentation files present")
                if not has_readme:
                    issues.append("README missing")
                return self._build_result(vtype, False, 0.2, "; ".join(issues))
            score = min(1.0, 0.75 + 0.05 * min(len(doc_files), 5))
            return self._build_result(vtype, True, score, f"{len(doc_files)} doc file(s) present, README exists")
        except Exception as exc:
            logger.warning("validate_documentation error: %s", exc)
            return self._build_result(vtype, False, 0.0, f"validation error: {exc}")

    def _validate_security_scan(self, data: Dict, high_threshold: int = 5) -> Dict[str, Any]:
        """Validate that security scan shows zero critical vulnerabilities."""
        vtype = "security_scan"
        try:
            critical = data.get("critical_vulnerabilities")
            high = data.get("high_vulnerabilities")
            if critical is None or high is None:
                return self._build_result(vtype, False, 0.0, "scan results not provided")
            critical = int(critical)
            high = int(high)
            if critical > 0 or high > high_threshold:
                issues = []
                if critical > 0:
                    issues.append(f"{critical} critical vulnerability(ies)")
                if high > high_threshold:
                    issues.append(f"{high} high vulnerability(ies) (threshold={high_threshold})")
                return self._build_result(vtype, False, 0.1, "; ".join(issues))
            score = 1.0 - (high * 0.05)
            score = max(0.85, score)
            return self._build_result(vtype, True, score, f"0 critical, {high} high vulnerability(ies)")
        except Exception as exc:
            logger.warning("validate_security_scan error: %s", exc)
            return self._build_result(vtype, False, 0.0, f"validation error: {exc}")

    def _validate_performance(self, data: Dict, latency_threshold_ms: float = 500.0, error_rate_threshold: float = 0.01) -> Dict[str, Any]:
        """Validate that performance metrics are within acceptable bounds."""
        vtype = "performance"
        try:
            p99 = data.get("p99_latency_ms")
            error_rate = data.get("error_rate")
            if p99 is None or error_rate is None:
                return self._build_result(vtype, False, 0.0, "performance metrics not provided")
            p99 = float(p99)
            error_rate = float(error_rate)
            if p99 > latency_threshold_ms or error_rate >= error_rate_threshold:
                issues = []
                if p99 > latency_threshold_ms:
                    issues.append(f"p99={p99}ms exceeds {latency_threshold_ms}ms")
                if error_rate >= error_rate_threshold:
                    issues.append(f"error_rate={error_rate:.3f} exceeds {error_rate_threshold}")
                return self._build_result(vtype, False, 0.2, "; ".join(issues))
            latency_score = max(0.0, 1.0 - p99 / latency_threshold_ms)
            error_score = max(0.0, 1.0 - error_rate / error_rate_threshold)
            score = 0.5 + 0.25 * latency_score + 0.25 * error_score
            return self._build_result(vtype, True, min(1.0, score), f"p99={p99}ms, error_rate={error_rate:.4f}")
        except Exception as exc:
            logger.warning("validate_performance error: %s", exc)
            return self._build_result(vtype, False, 0.0, f"validation error: {exc}")

    def _validate_compliance_gdpr(self, data: Dict) -> Dict[str, Any]:
        """Validate required GDPR compliance controls are present."""
        vtype = "gdpr_compliance"
        required_fields = ["data_inventory", "consent_mechanism", "dpo_assigned"]
        try:
            missing = [f for f in required_fields if not data.get(f)]
            if missing:
                return self._build_result(vtype, False, 0.2, f"missing GDPR controls: {', '.join(missing)}")
            score = 1.0 - (len(missing) * 0.15)
            return self._build_result(vtype, True, min(1.0, score), "all required GDPR controls present")
        except Exception as exc:
            logger.warning("validate_compliance_gdpr error: %s", exc)
            return self._build_result(vtype, False, 0.0, f"validation error: {exc}")

    def _validate_compliance_hipaa(self, data: Dict) -> Dict[str, Any]:
        """Validate required HIPAA compliance controls are present."""
        vtype = "hipaa_compliance"
        required_fields = ["encryption_at_rest", "access_controls", "audit_logging", "baa_signed"]
        try:
            missing = [f for f in required_fields if not data.get(f)]
            if missing:
                return self._build_result(vtype, False, 0.2, f"missing HIPAA controls: {', '.join(missing)}")
            return self._build_result(vtype, True, 0.95, "all required HIPAA controls present")
        except Exception as exc:
            logger.warning("validate_compliance_hipaa error: %s", exc)
            return self._build_result(vtype, False, 0.0, f"validation error: {exc}")

    def _validate_scalability(self, data: Dict, threshold: int = 1000) -> Dict[str, Any]:
        """Validate that the system can handle the required concurrent user load."""
        vtype = "scalability"
        try:
            max_users = data.get("max_concurrent_users")
            if max_users is None:
                return self._build_result(vtype, False, 0.0, "max_concurrent_users not provided")
            max_users = int(max_users)
            if max_users < threshold:
                return self._build_result(vtype, False, 0.3, f"max_concurrent_users={max_users} below threshold={threshold}")
            score = min(1.0, 0.85 + 0.15 * min(max_users / threshold, 1.0))
            return self._build_result(vtype, True, score, f"max_concurrent_users={max_users} (threshold={threshold})")
        except Exception as exc:
            logger.warning("validate_scalability error: %s", exc)
            return self._build_result(vtype, False, 0.0, f"validation error: {exc}")

    def _validate_availability(self, data: Dict) -> Dict[str, Any]:
        """Validate that system uptime meets the 99.5% availability target."""
        vtype = "availability"
        try:
            uptime = data.get("uptime_percent")
            if uptime is None:
                return self._build_result(vtype, False, 0.0, "uptime_percent not provided")
            uptime = float(uptime)
            if uptime < 99.5:
                return self._build_result(vtype, False, 0.3, f"uptime={uptime:.3f}% below 99.5% target")
            score = min(1.0, 0.85 + (uptime - 99.5) / 10.0)
            return self._build_result(vtype, True, score, f"uptime={uptime:.3f}%")
        except Exception as exc:
            logger.warning("validate_availability error: %s", exc)
            return self._build_result(vtype, False, 0.0, f"validation error: {exc}")

    def _validate_backup(self, data: Dict) -> Dict[str, Any]:
        """Validate that backups are taken at least daily and restores have been tested."""
        vtype = "backup"
        try:
            freq = data.get("backup_frequency_hours")
            tested = data.get("restore_tested")
            if freq is None or tested is None:
                missing = []
                if freq is None:
                    missing.append("backup_frequency_hours")
                if tested is None:
                    missing.append("restore_tested")
                return self._build_result(vtype, False, 0.0, f"missing fields: {', '.join(missing)}")
            freq = float(freq)
            if freq > 24 or not tested:
                issues = []
                if freq > 24:
                    issues.append(f"backup_frequency_hours={freq} exceeds 24h limit")
                if not tested:
                    issues.append("restore not tested")
                return self._build_result(vtype, False, 0.2, "; ".join(issues))
            score = min(1.0, 0.85 + (24.0 - freq) / 48.0)
            return self._build_result(vtype, True, score, f"backup every {freq}h, restore tested")
        except Exception as exc:
            logger.warning("validate_backup error: %s", exc)
            return self._build_result(vtype, False, 0.0, f"validation error: {exc}")

    def generate_gate(
        self,
        name: str,
        description: str,
        gate_type: GateType = None,
        severity: GateSeverity = GateSeverity.MEDIUM,
        conditions: List[GateCondition] = None,
        wired_function: Optional[str] = None,
        knowledge_references: List[str] = None,
        risk_reduction: float = 0.5
    ) -> DomainGate:
        """
        Generate a single domain gate

        Args:
            name: Gate name
            description: Gate description
            gate_type: Type of gate (defaults to SAFETY)
            severity: Severity level
            conditions: List of conditions (auto-generated if None)
            wired_function: Name of wired function
            knowledge_references: Links to librarian knowledge
            risk_reduction: Risk reduction percentage (0.0 to 1.0)

        Returns:
            DomainGate object
        """
        if gate_type is None:
            gate_type = GateType.SAFETY
        self.gate_count += 1
        gate_id = f"gate_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{self.gate_count}"

        # Auto-generate conditions if not provided
        if conditions is None:
            conditions = self._generate_conditions(gate_type, name)

        # Generate actions
        pass_actions = self._generate_pass_actions(gate_type)
        fail_actions = self._generate_fail_actions(gate_type, severity)

        # Get function signature if wired
        function_signature = None
        if wired_function and wired_function in self.function_registry:
            function_signature = self._get_function_signature(wired_function)

        # Create gate
        gate = DomainGate(
            gate_id=gate_id,
            name=name,
            description=description,
            gate_type=gate_type,
            severity=severity,
            conditions=conditions,
            pass_actions=pass_actions,
            fail_actions=fail_actions,
            wired_function=wired_function,
            function_signature=function_signature,
            risk_reduction=risk_reduction,
            confidence_threshold=0.85,
            knowledge_references=knowledge_references or [],
            metrics={
                "total_checks": 0,
                "passed": 0,
                "failed": 0,
                "last_check": None
            }
        )

        return gate

    def _generate_conditions(
        self,
        gate_type: GateType,
        name: str
    ) -> List[GateCondition]:
        """Generate default conditions based on gate type"""
        conditions = []

        if gate_type == GateType.VALIDATION:
            conditions.append(GateCondition(
                condition_id=f"cond_{uuid.uuid4().hex[:8]}",
                condition_type="threshold",
                parameter="score",
                operator=">=",
                expected_value=0.8,
                description="Validation score must meet threshold"
            ))

        elif gate_type == GateType.COMPLIANCE:
            conditions.append(GateCondition(
                condition_id=f"cond_{uuid.uuid4().hex[:8]}",
                condition_type="presence",
                parameter="compliance_check",
                operator="==",
                expected_value=True,
                description="Compliance check must pass"
            ))

        elif gate_type == GateType.PERFORMANCE:
            conditions.append(GateCondition(
                condition_id=f"cond_{uuid.uuid4().hex[:8]}",
                condition_type="threshold",
                parameter="response_time",
                operator="<=",
                expected_value=500,
                description="Response time must be under threshold"
            ))

        elif gate_type == GateType.SECURITY:
            conditions.append(GateCondition(
                condition_id=f"cond_{uuid.uuid4().hex[:8]}",
                condition_type="presence",
                parameter="security_scan",
                operator="==",
                expected_value="pass",
                description="Security scan must pass"
            ))

        else:
            # Default condition
            conditions.append(GateCondition(
                condition_id=f"cond_{uuid.uuid4().hex[:8]}",
                condition_type="threshold",
                parameter="score",
                operator=">=",
                expected_value=0.7,
                description="Must meet minimum threshold"
            ))

        return conditions

    def _generate_pass_actions(self, gate_type: GateType) -> List[GateAction]:
        """Generate actions for when gate passes"""
        actions = []

        actions.append(GateAction(
            action_id=f"action_{uuid.uuid4().hex[:8]}",
            action_type="proceed",
            trigger="pass",
            target="next_step"
        ))

        actions.append(GateAction(
            action_id=f"action_{uuid.uuid4().hex[:8]}",
            action_type="log",
            trigger="pass",
            target="system",
            parameters={"level": "info", "message": f"{gate_type.value} gate passed"}
        ))

        return actions

    def _generate_fail_actions(
        self,
        gate_type: GateType,
        severity: GateSeverity
    ) -> List[GateAction]:
        """Generate actions for when gate fails"""
        actions = []

        # Always log failure
        actions.append(GateAction(
            action_id=f"action_{uuid.uuid4().hex[:8]}",
            action_type="log",
            trigger="fail",
            target="system",
            parameters={"level": "warning", "message": f"{gate_type.value} gate failed"}
        ))

        # Block for critical/high severity
        if severity in [GateSeverity.CRITICAL, GateSeverity.HIGH]:
            actions.append(GateAction(
                action_id=f"action_{uuid.uuid4().hex[:8]}",
                action_type="block",
                trigger="fail",
                target="execution",
                parameters={"reason": f"{severity.value} severity gate failed"}
            ))
        else:
            # Escalate for medium severity
            actions.append(GateAction(
                action_id=f"action_{uuid.uuid4().hex[:8]}",
                action_type="escalate",
                trigger="fail",
                target="supervisor",
                parameters={"severity": severity.value}
            ))

        return actions

    def _get_function_signature(self, function_name: str) -> str:
        """Get function signature for wired function"""
        signatures = {
            "validate_code_review": "validate_code_review(code: str, reviewers: List[str]) -> Dict[str, Any]",
            "validate_test_coverage": "validate_test_coverage(test_results: Dict) -> Dict[str, Any]",
            "validate_documentation": "validate_documentation(docs: List[str]) -> Dict[str, Any]",
            "validate_security_scan": "validate_security_scan(scan_results: Dict) -> Dict[str, Any]",
            "validate_performance": "validate_performance(metrics: Dict) -> Dict[str, Any]",
            "validate_compliance_gdpr": "validate_compliance_gdpr(data_handling: Dict) -> Dict[str, Any]",
            "validate_compliance_hipaa": "validate_compliance_hipaa(healthcare_data: Dict) -> Dict[str, Any]",
            "validate_scalability": "validate_scalability(load_test_results: Dict) -> Dict[str, Any]",
            "validate_availability": "validate_availability(uptime_data: Dict) -> Dict[str, Any]",
            "validate_backup": "validate_backup(backup_config: Dict) -> Dict[str, Any]"
        }
        return signatures.get(function_name, f"{function_name}(data: Any) -> Dict[str, Any]")

    def generate_gates_for_domain(
        self,
        domain: str = "software",
        system_requirements: Dict[str, Any] = None,
    ) -> List[DomainGate]:
        """Convenience method: generate gates for a domain."""
        reqs = system_requirements or {}
        reqs.setdefault("domain", domain)
        reqs.setdefault("complexity", "medium")
        gates, _ = self.generate_gates_for_system(reqs)
        return gates

    def generate_gates_for_system(
        self,
        system_requirements: Dict[str, Any]
    ) -> Tuple[List[DomainGate], Dict[str, Any]]:
        """
        Generate all gates for a system based on requirements

        Args:
            system_requirements: System requirements dict including:
                - domain: software/infrastructure/data
                - complexity: simple/medium/complex/very_complex
                - budget: optional budget constraint
                - regulatory_requirements: list of regulatory standards
                - architectural_requirements: list of architectural requirements
                - security_focus: boolean
                - performance_requirements: dict

        Returns:
            Tuple of (gates_list, gate_analysis)
        """
        gates = []

        domain = system_requirements.get("domain", "software")
        complexity = system_requirements.get("complexity", "medium")

        # Get gate templates from librarian
        templates = self.librarian.get_gate_templates(domain)

        # Generate gates from templates
        for template in templates:
            gate = self._create_gate_from_template(template, system_requirements)
            if gate:
                gates.append(gate)

        # Add domain-specific gates
        gates.extend(self._generate_domain_specific_gates(domain, system_requirements))

        # Add complexity-based gates
        gates.extend(self._generate_complexity_gates(complexity, system_requirements))

        # Add constraint-based gates
        if system_requirements.get("budget"):
            gates.append(self._generate_budget_gate(system_requirements["budget"]))

        # Add security gates if focused
        if system_requirements.get("security_focus"):
            gates.extend(self._generate_security_gates(system_requirements))

        # Add performance gates if required
        if system_requirements.get("performance_requirements"):
            gates.extend(self._generate_performance_gates(system_requirements))

        # Generate gate analysis
        gate_analysis = {
            "total_gates": len(gates),
            "by_type": self._count_gates_by_type(gates),
            "by_severity": self._count_gates_by_severity(gates),
            "average_risk_reduction": sum(g.risk_reduction for g in gates) / (len(gates) or 1) if gates else 0.0,
            "gates_with_wired_functions": sum(1 for g in gates if g.wired_function),
            "knowledge_coverage": self._calculate_knowledge_coverage(gates, system_requirements)
        }

        return gates, gate_analysis

    def _create_gate_from_template(
        self,
        template: Dict,
        requirements: Dict
    ) -> Optional[DomainGate]:
        """Create a gate from librarian template"""
        # Check if this gate is relevant based on requirements
        if not self._is_gate_relevant(template, requirements):
            return None

        # Determine severity
        severity = self._determine_gate_severity(template, requirements)

        # Get wired function
        wired_function = self._get_wired_function_for_gate(template["name"])

        # Create gate
        return self.generate_gate(
            name=template["name"],
            description=template["description"],
            gate_type=GateType(template["gate_type"]),
            severity=severity,
            wired_function=wired_function,
            knowledge_references=[template["knowledge_reference"]],
            risk_reduction=0.5
        )

    def _is_gate_relevant(self, template: Dict, requirements: Dict) -> bool:
        """Determine if a gate template is relevant to requirements"""
        # Check regulatory requirements
        regulatory_reqs = requirements.get("regulatory_requirements", [])
        if template["category"] == "regulatory_standards":
            if not regulatory_reqs:
                return False
            if template["name"].lower() not in [r.lower() for r in regulatory_reqs]:
                return False

        return True

    def _determine_gate_severity(self, template: Dict, requirements: Dict) -> GateSeverity:
        """Determine severity of gate based on context"""
        # Regulatory gates are high severity
        if template["category"] == "regulatory_standards":
            return GateSeverity.HIGH

        # Architectural gates for complex systems are high severity
        if template["category"] == "architectural_requirements":
            if requirements.get("complexity") in ["complex", "very_complex"]:
                return GateSeverity.HIGH
            return GateSeverity.MEDIUM

        # Default to medium
        return GateSeverity.MEDIUM

    def _get_wired_function_for_gate(self, gate_name: str) -> Optional[str]:
        """Get wired function name for a gate"""
        function_mapping = {
            "code_review": "validate_code_review",
            "test_coverage": "validate_test_coverage",
            "documentation": "validate_documentation",
            "security_scanning": "validate_security_scan",
            "gdpr": "validate_compliance_gdpr",
            "hipaa": "validate_compliance_hipaa",
            "scalability": "validate_scalability",
            "availability": "validate_availability",
            "backup": "validate_backup"
        }

        for key, func in function_mapping.items():
            if key in gate_name.lower():
                return func

        return None

    def _generate_domain_specific_gates(
        self,
        domain: str,
        requirements: Dict
    ) -> List[DomainGate]:
        """Generate domain-specific gates"""
        gates = []

        if domain == "software":
            gates.append(self.generate_gate(
                name="code_quality_gate",
                description="Ensure code quality standards are met",
                gate_type=GateType.QUALITY,
                severity=GateSeverity.HIGH,
                wired_function="validate_code_review",
                risk_reduction=0.7
            ))

            gates.append(self.generate_gate(
                name="dependency_vulnerability_gate",
                description="Check for vulnerable dependencies",
                gate_type=GateType.SECURITY,
                severity=GateSeverity.HIGH,
                wired_function="validate_security_scan",
                risk_reduction=0.8
            ))

        elif domain == "infrastructure":
            gates.append(self.generate_gate(
                name="infrastructure_compliance_gate",
                description="Ensure infrastructure meets compliance standards",
                gate_type=GateType.COMPLIANCE,
                severity=GateSeverity.HIGH,
                wired_function="validate_compliance_gdpr",
                risk_reduction=0.75
            ))

        elif domain == "data":
            gates.append(self.generate_gate(
                name="data_quality_gate",
                description="Ensure data quality standards",
                gate_type=GateType.QUALITY,
                severity=GateSeverity.HIGH,
                risk_reduction=0.7
            ))

            gates.append(self.generate_gate(
                name="data_privacy_gate",
                description="Ensure data privacy requirements",
                gate_type=GateType.COMPLIANCE,
                severity=GateSeverity.HIGH,
                wired_function="validate_compliance_gdpr",
                risk_reduction=0.85
            ))

        elif domain == "sales":
            gates.append(self.generate_gate(
                name="lead_data_validation_gate",
                description="Validate lead data has required fields (email, company, industry)",
                gate_type=GateType.VALIDATION,
                severity=GateSeverity.HIGH,
                risk_reduction=0.6
            ))

            gates.append(self.generate_gate(
                name="can_spam_compliance_gate",
                description="Ensure outreach emails comply with CAN-SPAM and GDPR",
                gate_type=GateType.COMPLIANCE,
                severity=GateSeverity.CRITICAL,
                risk_reduction=0.9
            ))

            gates.append(self.generate_gate(
                name="scoring_output_validation_gate",
                description="Validate lead scores are within expected range (0-100)",
                gate_type=GateType.VALIDATION,
                severity=GateSeverity.MEDIUM,
                risk_reduction=0.5
            ))

            gates.append(self.generate_gate(
                name="proposal_authority_gate",
                description="Verify proposer has authority for the recommended edition pricing",
                gate_type=GateType.AUTHORIZATION,
                severity=GateSeverity.HIGH,
                risk_reduction=0.7
            ))

        return gates

    def _generate_complexity_gates(
        self,
        complexity: str,
        requirements: Dict
    ) -> List[DomainGate]:
        """Generate gates based on system complexity"""
        gates = []

        if complexity in ["complex", "very_complex"]:
            gates.append(self.generate_gate(
                name="architecture_review_gate",
                description="Complex systems require architecture review",
                gate_type=GateType.ARCHITECTURAL,
                severity=GateSeverity.HIGH,
                risk_reduction=0.6
            ))

            gates.append(self.generate_gate(
                name="integration_test_gate",
                description="Comprehensive integration testing required",
                gate_type=GateType.QUALITY,
                severity=GateSeverity.MEDIUM,
                risk_reduction=0.5
            ))

        if complexity == "very_complex":
            gates.append(self.generate_gate(
                name="expert_review_gate",
                description="Very complex systems require expert review",
                gate_type=GateType.VALIDATION,
                severity=GateSeverity.CRITICAL,
                risk_reduction=0.7
            ))

        return gates

    def _generate_budget_gate(self, budget: float) -> DomainGate:
        """Generate budget constraint gate"""
        return self.generate_gate(
            name="budget_compliance_gate",
            description=f"Ensure costs stay within ${budget} budget",
            gate_type=GateType.BUSINESS,
            severity=GateSeverity.MEDIUM,
            conditions=[
                GateCondition(
                    condition_id=f"cond_{uuid.uuid4().hex[:8]}",
                    condition_type="threshold",
                    parameter="cost",
                    operator="<=",
                    expected_value=budget,
                    description="Cost must not exceed budget"
                )
            ],
            risk_reduction=0.5
        )

    def _generate_security_gates(self, requirements: Dict) -> List[DomainGate]:
        """Generate security-focused gates"""
        gates = []

        gates.append(self.generate_gate(
            name="security_vulnerability_scan_gate",
            description="Security vulnerability scan must pass",
            gate_type=GateType.SECURITY,
            severity=GateSeverity.CRITICAL,
            wired_function="validate_security_scan",
            risk_reduction=0.9
        ))

        gates.append(self.generate_gate(
            name="penetration_test_gate",
            description="Penetration testing required",
            gate_type=GateType.SECURITY,
            severity=GateSeverity.HIGH,
            risk_reduction=0.8
        ))

        return gates

    def _generate_performance_gates(self, requirements: Dict) -> List[DomainGate]:
        """Generate performance requirement gates"""
        gates = []
        perf_reqs = requirements.get("performance_requirements", {})

        if "response_time" in perf_reqs:
            gates.append(self.generate_gate(
                name="response_time_gate",
                description=f"Response time must be under {perf_reqs['response_time']}ms",
                gate_type=GateType.PERFORMANCE,
                severity=GateSeverity.HIGH,
                wired_function="validate_performance",
                conditions=[
                    GateCondition(
                        condition_id=f"cond_{uuid.uuid4().hex[:8]}",
                        condition_type="threshold",
                        parameter="response_time_ms",
                        operator="<=",
                        expected_value=perf_reqs["response_time"],
                        description="Response time threshold"
                    )
                ],
                risk_reduction=0.7
            ))

        return gates

    def _count_gates_by_type(self, gates: List[DomainGate]) -> Dict[str, int]:
        """Count gates by type"""
        counts = {}
        for gate in gates:
            gate_type = gate.gate_type.value
            counts[gate_type] = counts.get(gate_type, 0) + 1
        return counts

    def _count_gates_by_severity(self, gates: List[DomainGate]) -> Dict[str, int]:
        """Count gates by severity"""
        counts = {}
        for gate in gates:
            severity = gate.severity.value
            counts[severity] = counts.get(severity, 0) + 1
        return counts

    def _calculate_knowledge_coverage(
        self,
        gates: List[DomainGate],
        requirements: Dict
    ) -> Dict[str, Any]:
        """Calculate how well gates cover requirements"""
        coverage = {
            "regulatory_requirements": [],
            "architectural_requirements": []
        }

        regulatory_reqs = requirements.get("regulatory_requirements", [])
        for req in regulatory_reqs:
            covered = any(req.lower() in gate.name.lower() for gate in gates)
            coverage["regulatory_requirements"].append({
                "requirement": req,
                "covered": covered
            })

        arch_reqs = requirements.get("architectural_requirements", [])
        for req in arch_reqs:
            covered = any(req.lower() in gate.name.lower() for gate in gates)
            coverage["architectural_requirements"].append({
                "requirement": req,
                "covered": covered
            })

        return coverage

    def execute_gate(
        self,
        gate: DomainGate,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a gate with provided data

        Args:
            gate: DomainGate to execute
            data: Data to validate against gate

        Returns:
            Execution result dict
        """
        result = {
            "gate_id": gate.gate_id,
            "gate_name": gate.name,
            "passed": True,
            "conditions_results": [],
            "actions_taken": [],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Check conditions
        for condition in gate.conditions:
            condition_result = self._check_condition(condition, data)
            result["conditions_results"].append(condition_result)

            if not condition_result["passed"]:
                result["passed"] = False

        # Execute wired function if available
        if gate.wired_function and gate.wired_function in self.function_registry:
            try:
                func_result = self.function_registry[gate.wired_function](data)
                result["wired_function_result"] = func_result
                if not func_result.get("passed", True):
                    result["passed"] = False
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                result["wired_function_error"] = str(exc)
                result["passed"] = False

        # Execute actions
        actions = gate.pass_actions if result["passed"] else gate.fail_actions
        for action in actions:
            result["actions_taken"].append({
                "action_type": action.action_type,
                "trigger": action.trigger,
                "target": action.target,
                "executed": True
            })

        # Update gate metrics
        gate.metrics["total_checks"] += 1
        if result["passed"]:
            gate.metrics["passed"] += 1
        else:
            gate.metrics["failed"] += 1
        gate.metrics["last_check"] = datetime.now(timezone.utc).isoformat()

        return result


if __name__ == "__main__":
    # Test domain gate generation
    generator = DomainGateGenerator()

    # Test 1: Generate single gate
    logger.info("=== Test 1: Generate Single Gate ===")
    gate = generator.generate_gate(
        name="code_review_gate",
        description="Code must be reviewed before merge",
        gate_type=GateType.VALIDATION,
        severity=GateSeverity.HIGH,
        wired_function="validate_code_review",
        risk_reduction=0.7
    )
    logger.info(json.dumps(gate.to_dict(), indent=2))

    # Test 2: Generate gates for system
    logger.info("\n=== Test 2: Generate Gates for System ===")
    requirements = {
        "domain": "software",
        "complexity": "complex",
        "security_focus": True,
        "regulatory_requirements": ["gdpr", "hipaa"],
        "architectural_requirements": ["microservices", "scalability"],
        "budget": 10000,
        "performance_requirements": {"response_time": 200}
    }

    gates, analysis = generator.generate_gates_for_system(requirements)
    logger.info(f"Total Gates: {analysis['total_gates']}")
    logger.info(f"By Type: {analysis['by_type']}")
    logger.info(f"By Severity: {analysis['by_severity']}")
    logger.info(f"Avg Risk Reduction: {analysis['average_risk_reduction']:.2%}")
    logger.info(f"Gates with Wired Functions: {analysis['gates_with_wired_functions']}")

    # Test 3: Execute gate
    logger.info("\n=== Test 3: Execute Gate ===")
    result = generator.execute_gate(
        gate,
        data={"score": 0.85, "reviewers": ["alice", "bob"]}
    )
    logger.info(json.dumps(result, indent=2))
