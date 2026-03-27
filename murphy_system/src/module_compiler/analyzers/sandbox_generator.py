"""
Intelligent Sandbox Generator

Generates optimized sandbox profiles based on capability analysis.
Dynamically allocates resources and synthesizes security constraints.
"""

import ast
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class OptimizedSandboxProfile:
    """
    Optimized sandbox profile with detailed constraints.

    Attributes:
        cpu_cores: CPU allocation (0.1 to 4.0)
        memory_mb: Memory allocation (64 to 4096 MB)
        disk_quota_mb: Disk quota (0 to 1024 MB)
        timeout_seconds: Execution timeout (1 to 300 seconds)
        network_enabled: Whether network access is allowed
        allowed_domains: List of allowed domains for network access
        blocked_ports: List of blocked ports
        filesystem_enabled: Whether filesystem access is allowed
        read_paths: List of allowed read paths
        write_paths: List of allowed write paths
        allowed_syscalls: List of allowed system calls
        blocked_syscalls: List of blocked system calls
        environment_variables: Environment variables to set
        log_level: Logging level (debug, info, warning, error)
        metrics_enabled: Whether to collect metrics
        optimization_score: How well optimized this profile is (0.0 to 1.0)
        resource_efficiency: Resource efficiency score (0.0 to 1.0)
        security_level: Security level (low, medium, high)
    """

    # Resource limits
    cpu_cores: float
    memory_mb: int
    disk_quota_mb: int
    timeout_seconds: int

    # Network access
    network_enabled: bool
    filesystem_enabled: bool

    # Network details
    allowed_domains: List[str] = field(default_factory=list)
    blocked_ports: List[int] = field(default_factory=list)

    # File system details
    read_paths: List[str] = field(default_factory=list)
    write_paths: List[str] = field(default_factory=list)

    # Security constraints
    allowed_syscalls: List[str] = field(default_factory=list)
    blocked_syscalls: List[str] = field(default_factory=list)
    environment_variables: Dict[str, str] = field(default_factory=dict)

    # Monitoring
    log_level: str = "info"
    metrics_enabled: bool = True

    # Metadata
    optimization_score: float = 0.0
    resource_efficiency: float = 0.0
    security_level: str = "medium"

    def __post_init__(self):
        """Validate profile parameters"""
        if self.cpu_cores < 0.1 or self.cpu_cores > 4.0:
            raise ValueError("CPU cores must be between 0.1 and 4.0")
        if self.memory_mb < 64 or self.memory_mb > 4096:
            raise ValueError("Memory must be between 64 and 4096 MB")
        if self.disk_quota_mb < 0 or self.disk_quota_mb > 1024:
            raise ValueError("Disk quota must be between 0 and 1024 MB")
        if self.timeout_seconds < 1 or self.timeout_seconds > 300:
            raise ValueError("Timeout must be between 1 and 300 seconds")
        if self.optimization_score < 0.0 or self.optimization_score > 1.0:
            raise ValueError("Optimization score must be between 0.0 and 1.0")
        if self.resource_efficiency < 0.0 or self.resource_efficiency > 1.0:
            raise ValueError("Resource efficiency must be between 0.0 and 1.0")


class IntelligentSandboxGenerator:
    """
    Generate optimized sandbox profiles based on capability analysis.

    Analyzes:
    - Resource requirements (CPU, memory, disk, timeout)
    - Network access needs
    - Filesystem access needs
    - Security constraints
    - Performance characteristics
    """

    def __init__(self):
        """Initialize sandbox generator"""
        self.base_cpu = 0.5
        self.base_memory = 256
        self.base_disk = 100
        self.base_timeout = 30

    def generate_profile(
        self,
        code: str,
        failure_modes: List[Any] = None,
        determinism_level: str = "external_state",
        capability_name: str = ""
    ) -> OptimizedSandboxProfile:
        """
        Generate optimized sandbox profile.

        Args:
            code: Source code to analyze
            failure_modes: Detected failure modes
            determinism_level: Determinism level (deterministic, probabilistic, external_state)
            capability_name: Name of capability

        Returns:
            Optimized sandbox profile
        """
        failure_modes = failure_modes or []

        try:
            # Parse code
            tree = ast.parse(code)

            # 1. Analyze resource requirements
            resources = self._analyze_resource_requirements(tree)

            # 2. Determine network access
            network = self._determine_network_access(failure_modes, tree)

            # 3. Determine filesystem access
            filesystem = self._determine_filesystem_access(failure_modes, tree)

            # 4. Generate security constraints
            security = self._generate_security_constraints(failure_modes, tree)

            # 5. Optimize resource allocation
            optimized = self._optimize_resources(resources, determinism_level)

            # 6. Build profile
            profile = OptimizedSandboxProfile(
                cpu_cores=optimized['cpu'],
                memory_mb=optimized['memory'],
                disk_quota_mb=optimized['disk'],
                timeout_seconds=optimized['timeout'],
                network_enabled=network['enabled'],
                allowed_domains=network['allowed_domains'],
                blocked_ports=network['blocked_ports'],
                filesystem_enabled=filesystem['enabled'],
                read_paths=filesystem['read_paths'],
                write_paths=filesystem['write_paths'],
                allowed_syscalls=security['allowed_syscalls'],
                blocked_syscalls=security['blocked_syscalls'],
                environment_variables=security['env_vars'],
                log_level=self._determine_log_level(failure_modes),
                metrics_enabled=True,
                optimization_score=self._compute_optimization_score(optimized, resources),
                resource_efficiency=self._compute_efficiency(optimized, resources),
                security_level=self._determine_security_level(failure_modes)
            )

            return profile

        except SyntaxError:
            # If code can't be parsed, return conservative profile
            return self._get_conservative_profile()

    # ========== Resource Analysis ==========

    def _analyze_resource_requirements(self, tree: ast.AST) -> Dict[str, Any]:
        """Analyze resource requirements from code"""

        requirements = {
            'cpu_intensity': 0.0,  # 0.0 to 1.0
            'memory_intensity': 0.0,  # 0.0 to 1.0
            'io_intensity': 0.0,  # 0.0 to 1.0
            'network_intensity': 0.0,  # 0.0 to 1.0
            'estimated_runtime': 0.0  # seconds
        }

        # Analyze CPU intensity
        if self._has_loops(tree):
            requirements['cpu_intensity'] += 0.3
        if self._has_recursion(tree):
            requirements['cpu_intensity'] += 0.4
        if self._has_computation(tree):
            requirements['cpu_intensity'] += 0.3

        # Analyze memory intensity
        if self._has_large_data_structures(tree):
            requirements['memory_intensity'] += 0.5
        if self._has_caching(tree):
            requirements['memory_intensity'] += 0.3

        # Analyze I/O intensity
        if self._has_file_operations(tree):
            requirements['io_intensity'] += 0.5
        if self._has_database_operations(tree):
            requirements['io_intensity'] += 0.5

        # Analyze network intensity
        if self._has_network_operations(tree):
            requirements['network_intensity'] += 0.7

        # Estimate runtime
        requirements['estimated_runtime'] = self._estimate_runtime(tree)

        # Cap values at 1.0
        for key in requirements:
            if key != 'estimated_runtime':
                requirements[key] = min(1.0, requirements[key])

        return requirements

    def _has_loops(self, tree: ast.AST) -> bool:
        """Check if code has loops"""
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While)):
                return True
        return False

    def _has_recursion(self, tree: ast.AST) -> bool:
        """Check if code has recursion"""
        # Simple heuristic: function calls itself
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_name = node.name
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Name) and child.func.id == func_name:
                            return True
        return False

    def _has_computation(self, tree: ast.AST) -> bool:
        """Check if code has heavy computation"""
        computation_count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp):
                computation_count += 1
        return computation_count > 5

    def _has_large_data_structures(self, tree: ast.AST) -> bool:
        """Check if code uses large data structures"""
        for node in ast.walk(tree):
            if isinstance(node, (ast.List, ast.Dict, ast.Set)):
                if len(node.elts if hasattr(node, 'elts') else node.keys) > 100:
                    return True
        return False

    def _has_caching(self, tree: ast.AST) -> bool:
        """Check if code uses caching"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check for cache-like attributes
                for child in node.body:
                    if isinstance(child, ast.Assign):
                        for target in child.targets:
                            if isinstance(target, ast.Name):
                                if 'cache' in target.id.lower():
                                    return True
        return False

    def _has_file_operations(self, tree: ast.AST) -> bool:
        """Check if code has file operations"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'open':
                    return True
        return False

    def _has_database_operations(self, tree: ast.AST) -> bool:
        """Check if code has database operations"""
        db_modules = {'sqlite3', 'psycopg2', 'pymongo', 'sqlalchemy'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(mod in alias.name for mod in db_modules):
                        return True
        return False

    def _has_network_operations(self, tree: ast.AST) -> bool:
        """Check if code has network operations"""
        network_modules = {'requests', 'urllib', 'http', 'socket', 'aiohttp'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(mod in alias.name for mod in network_modules):
                        return True
        return False

    def _estimate_runtime(self, tree: ast.AST) -> float:
        """Estimate runtime in seconds"""
        # Simple heuristic based on code complexity
        complexity = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While)):
                complexity += 10
            elif isinstance(node, ast.FunctionDef):
                complexity += 5
            elif isinstance(node, ast.Call):
                complexity += 1

        # Estimate: 0.1s per complexity point
        return min(120.0, complexity * 0.1)

    # ========== Resource Optimization ==========

    def _optimize_resources(
        self,
        requirements: Dict[str, Any],
        determinism_level: str
    ) -> Dict[str, Any]:
        """Optimize resource allocation"""

        # Scale based on intensity
        cpu = self.base_cpu + (requirements['cpu_intensity'] * 3.5)  # 0.5 to 4.0
        memory = self.base_memory + int(requirements['memory_intensity'] * 3840)  # 256 to 4096
        disk = self.base_disk + int(requirements['io_intensity'] * 924)  # 100 to 1024
        timeout = self.base_timeout + int(requirements['estimated_runtime'] * 2)  # 30 to 300

        # Apply determinism-specific adjustments
        if determinism_level == "deterministic":
            # Deterministic capabilities are more predictable
            cpu *= 0.8
            memory *= 0.8
            timeout *= 0.7
        elif determinism_level == "probabilistic":
            # Probabilistic capabilities need more resources
            cpu *= 1.2
            memory *= 1.2
            timeout *= 1.3
        elif determinism_level == "external_state":
            # External state capabilities need even more resources
            cpu *= 1.5
            memory *= 1.5
            timeout *= 1.5

        # Ensure within bounds
        cpu = max(0.1, min(4.0, cpu))
        memory = max(64, min(4096, int(memory)))
        disk = max(0, min(1024, int(disk)))
        timeout = max(1, min(300, int(timeout)))

        return {
            'cpu': round(cpu, 1),
            'memory': memory,
            'disk': disk,
            'timeout': timeout
        }

    # ========== Network Access ==========

    def _determine_network_access(
        self,
        failure_modes: List[Any],
        tree: ast.AST
    ) -> Dict[str, Any]:
        """Determine network access requirements"""

        network = {
            'enabled': False,
            'allowed_domains': [],
            'blocked_ports': [22, 23, 3389]  # SSH, Telnet, RDP
        }

        # Check if code uses network
        if self._has_network_operations(tree):
            network['enabled'] = True

            # Extract domains from code (simple heuristic)
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if 'http://' in node.value or 'https://' in node.value:
                        # Extract domain
                        domain = node.value.split('/')[2] if '/' in node.value else node.value
                        network['allowed_domains'].append(domain)

        # Check failure modes for network risks
        network_failures = [f for f in failure_modes if hasattr(f, 'category') and f.category == "network"]
        if network_failures:
            # High risk - restrict network
            high_risk = any(f.risk_score > 0.2 for f in network_failures)
            if high_risk:
                network['enabled'] = False

        return network

    # ========== Filesystem Access ==========

    def _determine_filesystem_access(
        self,
        failure_modes: List[Any],
        tree: ast.AST
    ) -> Dict[str, Any]:
        """Determine filesystem access requirements"""

        filesystem = {
            'enabled': False,
            'read_paths': [],
            'write_paths': []
        }

        # Check if code uses filesystem
        if self._has_file_operations(tree):
            filesystem['enabled'] = True
            filesystem['read_paths'] = ['/tmp', '/data']
            filesystem['write_paths'] = ['/tmp/output']

        # Check failure modes for filesystem risks
        fs_failures = [f for f in failure_modes if hasattr(f, 'category') and f.category == "filesystem"]
        if fs_failures:
            # High risk - restrict filesystem
            high_risk = any(f.risk_score > 0.2 for f in fs_failures)
            if high_risk:
                filesystem['write_paths'] = []  # Read-only

        return filesystem

    # ========== Security Constraints ==========

    def _generate_security_constraints(
        self,
        failure_modes: List[Any],
        tree: ast.AST
    ) -> Dict[str, Any]:
        """Generate security constraints based on failure modes"""

        constraints = {
            'allowed_syscalls': [],
            'blocked_syscalls': [],
            'env_vars': {}
        }

        # Analyze failure modes for security risks
        high_risk_failures = [f for f in failure_modes if hasattr(f, 'risk_score') and f.risk_score > 0.2]

        # Network security
        if any(hasattr(f, 'category') and f.category == "network" for f in high_risk_failures):
            constraints['blocked_syscalls'].extend(['socket', 'connect', 'bind'])

        # Filesystem security
        if any(hasattr(f, 'category') and f.category == "filesystem" for f in high_risk_failures):
            constraints['blocked_syscalls'].extend(['unlink', 'rmdir', 'chmod'])

        # Process security
        if any(hasattr(f, 'category') and f.category == "state" for f in high_risk_failures):
            constraints['blocked_syscalls'].extend(['fork', 'exec', 'kill'])

        # Add safe syscalls
        constraints['allowed_syscalls'] = [
            'read', 'write', 'open', 'close',
            'stat', 'fstat', 'lstat',
            'mmap', 'munmap',
            'brk', 'sbrk'
        ]

        # Environment variables
        constraints['env_vars'] = {
            'PYTHONHASHSEED': '0',  # Deterministic hashing
            'PYTHONDONTWRITEBYTECODE': '1',  # No .pyc files
            'PYTHONUNBUFFERED': '1'  # Unbuffered output
        }

        return constraints

    # ========== Metadata Computation ==========

    def _determine_log_level(self, failure_modes: List[Any]) -> str:
        """Determine appropriate log level"""
        if not failure_modes:
            return "info"

        high_risk = any(hasattr(f, 'risk_score') and f.risk_score > 0.3 for f in failure_modes)
        if high_risk:
            return "debug"

        medium_risk = any(hasattr(f, 'risk_score') and f.risk_score > 0.15 for f in failure_modes)
        if medium_risk:
            return "info"

        return "warning"

    def _compute_optimization_score(
        self,
        optimized: Dict[str, Any],
        requirements: Dict[str, Any]
    ) -> float:
        """Compute optimization score"""
        # Score based on how well resources match requirements

        # CPU match
        cpu_target = 0.5 + (requirements['cpu_intensity'] * 3.5)
        cpu_match = 1.0 - abs(optimized['cpu'] - cpu_target) / 4.0

        # Memory match
        memory_target = 256 + (requirements['memory_intensity'] * 3840)
        memory_match = 1.0 - abs(optimized['memory'] - memory_target) / 4096

        # Average match
        score = (cpu_match + memory_match) / 2
        return max(0.0, min(1.0, score))

    def _compute_efficiency(
        self,
        optimized: Dict[str, Any],
        requirements: Dict[str, Any]
    ) -> float:
        """Compute resource efficiency"""
        # Efficiency = how little resources we use while meeting requirements

        # Lower resources = higher efficiency
        cpu_efficiency = 1.0 - (optimized['cpu'] / 4.0)
        memory_efficiency = 1.0 - (optimized['memory'] / 4096)

        # But must meet requirements
        if requirements['cpu_intensity'] > 0.5 and optimized['cpu'] < 1.0:
            cpu_efficiency *= 0.5
        if requirements['memory_intensity'] > 0.5 and optimized['memory'] < 512:
            memory_efficiency *= 0.5

        efficiency = (cpu_efficiency + memory_efficiency) / 2
        return max(0.0, min(1.0, efficiency))

    def _determine_security_level(self, failure_modes: List[Any]) -> str:
        """Determine security level"""
        if not failure_modes:
            return "low"

        max_risk = max((f.risk_score for f in failure_modes if hasattr(f, 'risk_score')), default=0.0)

        if max_risk > 0.3:
            return "high"
        elif max_risk > 0.15:
            return "medium"
        else:
            return "low"

    def _get_conservative_profile(self) -> OptimizedSandboxProfile:
        """Get conservative profile for unparseable code"""
        return OptimizedSandboxProfile(
            cpu_cores=1.0,
            memory_mb=512,
            disk_quota_mb=100,
            timeout_seconds=60,
            network_enabled=False,
            filesystem_enabled=False,
            allowed_syscalls=['read', 'write', 'open', 'close'],
            blocked_syscalls=['socket', 'connect', 'fork', 'exec'],
            environment_variables={
                'PYTHONHASHSEED': '0',
                'PYTHONDONTWRITEBYTECODE': '1',
                'PYTHONUNBUFFERED': '1'
            },
            log_level="debug",
            metrics_enabled=True,
            optimization_score=0.5,
            resource_efficiency=0.5,
            security_level="high"
        )
