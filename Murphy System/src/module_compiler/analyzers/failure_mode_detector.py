"""
Enhanced Failure Mode Detector

Detects capability-specific failure modes through code analysis.
Goes beyond generic failures to identify risks specific to each capability.
"""

import ast
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FailureMode:
    """
    Enhanced failure mode with detailed metadata.

    Attributes:
        category: Failure category (network, filesystem, computation, state, validation, dependency)
        description: Human-readable description
        likelihood: Probability of occurrence (0.0 to 1.0)
        impact: Severity of impact (0.0 to 1.0)
        risk_score: Overall risk (likelihood × impact)
        mitigation: Suggested mitigation strategy
        detection_method: How this failure was detected
        code_location: Where in code this failure can occur
        related_operations: Operations that can trigger this failure
    """

    category: str
    description: str
    likelihood: float
    impact: float
    risk_score: float
    mitigation: str
    detection_method: str
    code_location: Optional[str] = None
    related_operations: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate failure mode"""
        if self.likelihood < 0.0 or self.likelihood > 1.0:
            raise ValueError("Likelihood must be between 0.0 and 1.0")
        if self.impact < 0.0 or self.impact > 1.0:
            raise ValueError("Impact must be between 0.0 and 1.0")
        if self.risk_score < 0.0 or self.risk_score > 1.0:
            raise ValueError("Risk score must be between 0.0 and 1.0")


class EnhancedFailureModeDetector:
    """
    Detect capability-specific failure modes through code analysis.

    Analyzes:
    - Network operations
    - File system operations
    - External dependencies
    - Data validation
    - Resource usage
    - State management
    """

    def __init__(self):
        """Initialize detector"""
        self.network_modules = {'requests', 'urllib', 'http', 'socket', 'aiohttp'}
        self.filesystem_modules = {'os', 'pathlib', 'shutil', 'tempfile'}
        self.computation_modules = {'numpy', 'scipy', 'math', 'decimal'}

    def detect_failure_modes(self, code: str, capability_name: str = "") -> List[FailureMode]:
        """
        Detect all potential failure modes for a capability.

        Args:
            code: Source code to analyze
            capability_name: Name of capability (for context)

        Returns:
            List of detected failure modes with risk scores
        """
        failure_modes = []

        try:
            # Parse code into AST
            tree = ast.parse(code)

            # 1. Network failure modes
            if self._uses_network(tree):
                failure_modes.extend(self._detect_network_failures(tree))

            # 2. File system failure modes
            if self._uses_filesystem(tree):
                failure_modes.extend(self._detect_filesystem_failures(tree))

            # 3. Computation failure modes
            if self._is_computation_heavy(tree):
                failure_modes.extend(self._detect_computation_failures(tree))

            # 4. State corruption modes
            if self._is_stateful(tree):
                failure_modes.extend(self._detect_state_failures(tree))

            # 5. Input validation failures
            failure_modes.extend(self._detect_validation_failures(tree))

            # 6. Dependency failures
            failure_modes.extend(self._detect_dependency_failures(tree))

            # 7. Generic failures (always present)
            failure_modes.extend(self._detect_generic_failures())

        except SyntaxError as exc:
            # If code can't be parsed, return generic failures only
            logger.debug("Suppressed exception: %s", exc)
            failure_modes.extend(self._detect_generic_failures())

        return failure_modes

    # ========== Network Failure Detection ==========

    def _uses_network(self, tree: ast.AST) -> bool:
        """Check if code uses network operations"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(mod in alias.name for mod in self.network_modules):
                        return True
            elif isinstance(node, ast.ImportFrom):
                if node.module and any(mod in node.module for mod in self.network_modules):
                    return True
        return False

    def _detect_network_failures(self, tree: ast.AST) -> List[FailureMode]:
        """Detect network-related failure modes"""
        failures = []

        # Check for HTTP requests
        if self._uses_http(tree):
            failures.append(FailureMode(
                category="network",
                description="HTTP request timeout",
                likelihood=0.3,
                impact=0.7,
                risk_score=0.21,
                mitigation="Implement retry logic with exponential backoff",
                detection_method="AST analysis - found HTTP request calls",
                code_location=self._find_http_calls(tree),
                related_operations=["requests.get", "requests.post", "urllib.request"]
            ))

            failures.append(FailureMode(
                category="network",
                description="HTTP connection refused",
                likelihood=0.2,
                impact=0.8,
                risk_score=0.16,
                mitigation="Check service availability before request",
                detection_method="AST analysis - found HTTP library usage",
                code_location=self._find_http_calls(tree),
                related_operations=["requests.get", "requests.post"]
            ))

            failures.append(FailureMode(
                category="network",
                description="HTTP 4xx/5xx error response",
                likelihood=0.25,
                impact=0.6,
                risk_score=0.15,
                mitigation="Implement error response handling",
                detection_method="AST analysis - found HTTP requests",
                code_location=self._find_http_calls(tree),
                related_operations=["requests.get", "requests.post"]
            ))

        # Check for socket operations
        if self._uses_sockets(tree):
            failures.append(FailureMode(
                category="network",
                description="Socket connection failure",
                likelihood=0.25,
                impact=0.9,
                risk_score=0.225,
                mitigation="Implement connection pooling and health checks",
                detection_method="AST analysis - found socket operations",
                code_location=self._find_socket_calls(tree),
                related_operations=["socket.connect", "socket.send", "socket.recv"]
            ))

        return failures

    def _uses_http(self, tree: ast.AST) -> bool:
        """Check if code uses HTTP operations"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if node.attr in ['get', 'post', 'put', 'delete', 'request']:
                    return True
        return False

    def _uses_sockets(self, tree: ast.AST) -> bool:
        """Check if code uses socket operations"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if node.attr in ['connect', 'send', 'recv', 'socket']:
                    return True
        return False

    def _find_http_calls(self, tree: ast.AST) -> str:
        """Find location of HTTP calls"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['get', 'post', 'put', 'delete']:
                        return f"line {node.lineno}"
        return "unknown location"

    def _find_socket_calls(self, tree: ast.AST) -> str:
        """Find location of socket calls"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['connect', 'send', 'recv']:
                        return f"line {node.lineno}"
        return "unknown location"

    # ========== File System Failure Detection ==========

    def _uses_filesystem(self, tree: ast.AST) -> bool:
        """Check if code uses file system operations"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(mod in alias.name for mod in self.filesystem_modules):
                        return True
            elif isinstance(node, ast.ImportFrom):
                if node.module and any(mod in node.module for mod in self.filesystem_modules):
                    return True
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'open':
                    return True
        return False

    def _detect_filesystem_failures(self, tree: ast.AST) -> List[FailureMode]:
        """Detect file system-related failure modes"""
        failures = []

        failures.append(FailureMode(
            category="filesystem",
            description="File not found",
            likelihood=0.4,
            impact=0.6,
            risk_score=0.24,
            mitigation="Check file existence before access using os.path.exists()",
            detection_method="AST analysis - found file operations",
            code_location=self._find_file_operations(tree),
            related_operations=["open", "read", "write"]
        ))

        failures.append(FailureMode(
            category="filesystem",
            description="Permission denied",
            likelihood=0.2,
            impact=0.7,
            risk_score=0.14,
            mitigation="Verify file permissions in sandbox profile",
            detection_method="AST analysis - found file write operations",
            code_location=self._find_file_operations(tree),
            related_operations=["open", "write", "chmod"]
        ))

        failures.append(FailureMode(
            category="filesystem",
            description="Disk space exhausted",
            likelihood=0.1,
            impact=0.9,
            risk_score=0.09,
            mitigation="Monitor disk usage and set quotas",
            detection_method="AST analysis - found file write operations",
            code_location=self._find_file_operations(tree),
            related_operations=["write", "shutil.copy"]
        ))

        return failures

    def _find_file_operations(self, tree: ast.AST) -> str:
        """Find location of file operations"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'open':
                    return f"line {node.lineno}"
        return "unknown location"

    # ========== Computation Failure Detection ==========

    def _is_computation_heavy(self, tree: ast.AST) -> bool:
        """Check if code is computation-heavy"""
        # Check for math operations or numeric libraries
        for node in ast.walk(tree):
            if isinstance(node, (ast.BinOp, ast.UnaryOp)):
                return True
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(mod in alias.name for mod in self.computation_modules):
                        return True
        return False

    def _detect_computation_failures(self, tree: ast.AST) -> List[FailureMode]:
        """Detect computation-related failure modes"""
        failures = []

        # Check for division operations
        if self._has_division(tree):
            failures.append(FailureMode(
                category="computation",
                description="Division by zero",
                likelihood=0.3,
                impact=0.8,
                risk_score=0.24,
                mitigation="Add zero-check before division operations",
                detection_method="AST analysis - found division operators",
                code_location=self._find_divisions(tree),
                related_operations=["/", "//", "divmod"]
            ))

        # Check for numeric operations
        if self._has_numeric_ops(tree):
            failures.append(FailureMode(
                category="computation",
                description="Numeric overflow",
                likelihood=0.15,
                impact=0.6,
                risk_score=0.09,
                mitigation="Use arbitrary precision arithmetic (decimal.Decimal)",
                detection_method="AST analysis - found large number operations",
                code_location=self._find_numeric_ops(tree),
                related_operations=["**", "*", "+"]
            ))

            failures.append(FailureMode(
                category="computation",
                description="Floating point precision loss",
                likelihood=0.4,
                impact=0.4,
                risk_score=0.16,
                mitigation="Use decimal.Decimal for precise calculations",
                detection_method="AST analysis - found float operations",
                code_location=self._find_float_ops(tree),
                related_operations=["float", "/"]
            ))

        return failures

    def _has_division(self, tree: ast.AST) -> bool:
        """Check if code has division operations"""
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp):
                if isinstance(node.op, (ast.Div, ast.FloorDiv)):
                    return True
        return False

    def _has_numeric_ops(self, tree: ast.AST) -> bool:
        """Check if code has numeric operations"""
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp):
                return True
        return False

    def _find_divisions(self, tree: ast.AST) -> str:
        """Find location of division operations"""
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp):
                if isinstance(node.op, (ast.Div, ast.FloorDiv)):
                    return f"line {node.lineno}"
        return "unknown location"

    def _find_numeric_ops(self, tree: ast.AST) -> str:
        """Find location of numeric operations"""
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp):
                return f"line {node.lineno}"
        return "unknown location"

    def _find_float_ops(self, tree: ast.AST) -> str:
        """Find location of float operations"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'float':
                    return f"line {node.lineno}"
        return "unknown location"

    # ========== State Failure Detection ==========

    def _is_stateful(self, tree: ast.AST) -> bool:
        """Check if code maintains state"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                return True
            if isinstance(node, ast.Global):
                return True
        return False

    def _detect_state_failures(self, tree: ast.AST) -> List[FailureMode]:
        """Detect state-related failure modes"""
        failures = []

        failures.append(FailureMode(
            category="state",
            description="State corruption from concurrent access",
            likelihood=0.3,
            impact=0.8,
            risk_score=0.24,
            mitigation="Use thread-safe data structures and locks",
            detection_method="AST analysis - found stateful code",
            code_location="class or global variables detected",
            related_operations=["class", "global"]
        ))

        failures.append(FailureMode(
            category="state",
            description="Memory leak from unreleased resources",
            likelihood=0.2,
            impact=0.7,
            risk_score=0.14,
            mitigation="Use context managers (with statements)",
            detection_method="AST analysis - found resource allocation",
            code_location="resource allocation detected",
            related_operations=["open", "connect"]
        ))

        return failures

    # ========== Validation Failure Detection ==========

    def _detect_validation_failures(self, tree: ast.AST) -> List[FailureMode]:
        """Detect input validation failure modes"""
        failures = []

        # Check for function parameters
        has_params = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.args.args:
                    has_params = True
                    break

        if has_params:
            failures.append(FailureMode(
                category="validation",
                description="Invalid input type",
                likelihood=0.5,
                impact=0.5,
                risk_score=0.25,
                mitigation="Add type checking and validation",
                detection_method="AST analysis - found function parameters",
                code_location="function parameters",
                related_operations=["function parameters"]
            ))

            failures.append(FailureMode(
                category="validation",
                description="Input out of expected range",
                likelihood=0.4,
                impact=0.6,
                risk_score=0.24,
                mitigation="Add range validation for numeric inputs",
                detection_method="AST analysis - found function parameters",
                code_location="function parameters",
                related_operations=["function parameters"]
            ))

        return failures

    # ========== Dependency Failure Detection ==========

    def _detect_dependency_failures(self, tree: ast.AST) -> List[FailureMode]:
        """Detect dependency-related failure modes"""
        failures = []

        # Check for imports
        has_imports = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                has_imports = True
                break

        if has_imports:
            failures.append(FailureMode(
                category="dependency",
                description="Missing dependency",
                likelihood=0.2,
                impact=0.9,
                risk_score=0.18,
                mitigation="Verify all dependencies are installed",
                detection_method="AST analysis - found import statements",
                code_location="import statements",
                related_operations=["import"]
            ))

            failures.append(FailureMode(
                category="dependency",
                description="Incompatible dependency version",
                likelihood=0.15,
                impact=0.7,
                risk_score=0.105,
                mitigation="Pin dependency versions in requirements",
                detection_method="AST analysis - found import statements",
                code_location="import statements",
                related_operations=["import"]
            ))

        return failures

    # ========== Generic Failure Detection ==========

    def _detect_generic_failures(self) -> List[FailureMode]:
        """Detect generic failure modes (always present)"""
        return [
            FailureMode(
                category="generic",
                description="Execution timeout",
                likelihood=0.1,
                impact=0.5,
                risk_score=0.05,
                mitigation="Set appropriate timeout limits",
                detection_method="Generic failure mode",
                code_location="any code",
                related_operations=["all"]
            ),
            FailureMode(
                category="generic",
                description="Unexpected exception",
                likelihood=0.2,
                impact=0.6,
                risk_score=0.12,
                mitigation="Implement comprehensive error handling",
                detection_method="Generic failure mode",
                code_location="any code",
                related_operations=["all"]
            )
        ]
