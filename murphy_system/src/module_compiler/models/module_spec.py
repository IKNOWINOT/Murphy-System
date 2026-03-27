"""
Module Specification Data Models

Defines the structure of compiled modules and their capabilities.

Owner: INONI LLC / Corey Post (corey.gfc@gmail.com)
"""

import logging

logger = logging.getLogger(__name__)
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class DeterminismLevel(Enum):
    """Classification of capability determinism"""
    DETERMINISTIC = "deterministic"  # Same input → same output
    PROBABILISTIC = "probabilistic"  # Uses randomness
    EXTERNAL_STATE = "external_state"  # Depends on external state


class FailureSeverity(Enum):
    """Severity of potential failure modes"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ResourceProfile:
    """Resource requirements for capability execution"""
    cpu_limit: float = 1.0  # CPU cores
    memory_limit: str = "512MB"  # Memory limit
    disk_limit: str = "100MB"  # Disk space limit
    timeout_seconds: int = 60  # Execution timeout
    network_required: bool = False  # Network access needed
    gpu_required: bool = False  # GPU access needed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_limit": self.cpu_limit,
            "memory_limit": self.memory_limit,
            "disk_limit": self.disk_limit,
            "timeout_seconds": self.timeout_seconds,
            "network_required": self.network_required,
            "gpu_required": self.gpu_required,
        }


@dataclass
class FailureMode:
    """Potential failure mode for a capability"""
    type: str  # e.g., "network_timeout", "division_by_zero"
    severity: FailureSeverity
    description: str
    mitigation: Optional[str] = None
    probability: Optional[float] = None  # 0.0 to 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "severity": self.severity.value,
            "description": self.description,
            "mitigation": self.mitigation,
            "probability": self.probability,
        }


@dataclass
class Capability:
    """A single executable capability within a module"""
    name: str
    description: str
    input_schema: Dict[str, Any]  # JSON Schema
    output_schema: Dict[str, Any]  # JSON Schema
    determinism: DeterminismLevel
    resource_profile: ResourceProfile
    failure_modes: List[FailureMode] = field(default_factory=list)
    test_vectors: List[Dict[str, Any]] = field(default_factory=list)
    entry_point: Optional[str] = None  # Function/method name
    required_env_vars: List[str] = field(default_factory=list)
    required_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "determinism": self.determinism.value,
            "resource_profile": self.resource_profile.to_dict(),
            "failure_modes": [fm.to_dict() for fm in self.failure_modes],
            "test_vectors": self.test_vectors,
            "entry_point": self.entry_point,
            "required_env_vars": self.required_env_vars,
            "required_files": self.required_files,
        }

    def is_deterministic(self) -> bool:
        """Check if capability is deterministic"""
        return self.determinism == DeterminismLevel.DETERMINISTIC

    def requires_network(self) -> bool:
        """Check if capability requires network access"""
        return self.resource_profile.network_required

    def max_severity(self) -> FailureSeverity:
        """Get maximum failure severity"""
        if not self.failure_modes:
            return FailureSeverity.LOW

        # Map severity to numeric values for comparison
        severity_order = {
            FailureSeverity.LOW: 1,
            FailureSeverity.MEDIUM: 2,
            FailureSeverity.HIGH: 3,
            FailureSeverity.CRITICAL: 4,
        }

        max_sev = max(severity_order[fm.severity] for fm in self.failure_modes)

        # Return the corresponding severity
        for sev, val in severity_order.items():
            if val == max_sev:
                return sev

        return FailureSeverity.LOW


@dataclass
class SandboxProfile:
    """Sandbox configuration for module execution"""
    base_image: str = "python:3.11-slim"
    read_only_root: bool = True
    network_enabled: bool = False
    gpu_enabled: bool = False
    privileged: bool = False

    # Resource limits
    cpu_limit: float = 1.0
    memory_limit: str = "512MB"
    disk_limit: str = "100MB"

    # Filesystem mounts
    mounts: List[Dict[str, str]] = field(default_factory=list)

    # Environment variables (allowed)
    allowed_env_vars: List[str] = field(default_factory=list)

    # Capabilities (Linux capabilities)
    capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_image": self.base_image,
            "read_only_root": self.read_only_root,
            "network_enabled": self.network_enabled,
            "gpu_enabled": self.gpu_enabled,
            "privileged": self.privileged,
            "cpu_limit": self.cpu_limit,
            "memory_limit": self.memory_limit,
            "disk_limit": self.disk_limit,
            "mounts": self.mounts,
            "allowed_env_vars": self.allowed_env_vars,
            "capabilities": self.capabilities,
        }

    @classmethod
    def default_secure(cls) -> "SandboxProfile":
        """Create a default secure sandbox profile"""
        return cls(
            base_image="python:3.11-slim",
            read_only_root=True,
            network_enabled=False,
            gpu_enabled=False,
            privileged=False,
            cpu_limit=1.0,
            memory_limit="512MB",
            disk_limit="100MB",
            mounts=[
                {"source": "/tmp", "target": "/tmp", "readonly": False, "size": "10MB"}
            ],
            allowed_env_vars=[],
            capabilities=[],
        )


@dataclass
class ModuleSpec:
    """Complete specification for a compiled module"""
    module_id: str
    source_path: str
    version_hash: str
    capabilities: List[Capability]
    sandbox_profile: SandboxProfile

    # Metadata
    compiled_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    compiler_version: str = "1.0.0"

    # Build information
    build_steps: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    # Verification
    verification_checks: List[Dict[str, Any]] = field(default_factory=list)
    verification_status: str = "pending"  # pending, passed, failed

    # Flags
    is_partial: bool = False  # True if analysis was incomplete
    requires_manual_review: bool = False
    uncertainty_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "source_path": self.source_path,
            "version_hash": self.version_hash,
            "capabilities": [cap.to_dict() for cap in self.capabilities],
            "sandbox_profile": self.sandbox_profile.to_dict(),
            "compiled_at": self.compiled_at,
            "compiler_version": self.compiler_version,
            "build_steps": self.build_steps,
            "dependencies": self.dependencies,
            "verification_checks": self.verification_checks,
            "verification_status": self.verification_status,
            "is_partial": self.is_partial,
            "requires_manual_review": self.requires_manual_review,
            "uncertainty_flags": self.uncertainty_flags,
        }

    def to_json(self) -> str:
        """Serialize to JSON"""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModuleSpec":
        """Deserialize from dictionary"""
        # Reconstruct capabilities
        capabilities = [
            Capability(
                name=cap["name"],
                description=cap["description"],
                input_schema=cap["input_schema"],
                output_schema=cap["output_schema"],
                determinism=DeterminismLevel(cap["determinism"]),
                resource_profile=ResourceProfile(**cap["resource_profile"]),
                failure_modes=[
                    FailureMode(
                        type=fm["type"],
                        severity=FailureSeverity(fm["severity"]),
                        description=fm["description"],
                        mitigation=fm.get("mitigation"),
                        probability=fm.get("probability"),
                    )
                    for fm in cap.get("failure_modes", [])
                ],
                test_vectors=cap.get("test_vectors", []),
                entry_point=cap.get("entry_point"),
                required_env_vars=cap.get("required_env_vars", []),
                required_files=cap.get("required_files", []),
            )
            for cap in data["capabilities"]
        ]

        # Reconstruct sandbox profile
        sandbox_profile = SandboxProfile(**data["sandbox_profile"])

        return cls(
            module_id=data["module_id"],
            source_path=data["source_path"],
            version_hash=data["version_hash"],
            capabilities=capabilities,
            sandbox_profile=sandbox_profile,
            compiled_at=data.get("compiled_at", datetime.now(timezone.utc).isoformat()),
            compiler_version=data.get("compiler_version", "1.0.0"),
            build_steps=data.get("build_steps", []),
            dependencies=data.get("dependencies", []),
            verification_checks=data.get("verification_checks", []),
            verification_status=data.get("verification_status", "pending"),
            is_partial=data.get("is_partial", False),
            requires_manual_review=data.get("requires_manual_review", False),
            uncertainty_flags=data.get("uncertainty_flags", []),
        )

    @staticmethod
    def generate_module_id(source_path: str, version_hash: str) -> str:
        """Generate unique module ID"""
        # Extract module name from path
        import os
        module_name = os.path.basename(source_path).replace(".py", "")
        # Use first 8 chars of hash
        short_hash = version_hash[:8]
        return f"{module_name}-v1-{short_hash}"

    @staticmethod
    def compute_version_hash(source_path: str) -> str:
        """Compute SHA-256 hash of source file"""
        try:
            with open(source_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as exc:
            # If file can't be read, use path hash
            logger.debug("Suppressed exception: %s", exc)
            return hashlib.sha256(source_path.encode()).hexdigest()

    def get_capability(self, name: str) -> Optional[Capability]:
        """Get capability by name"""
        for cap in self.capabilities:
            if cap.name == name:
                return cap
        return None

    def has_deterministic_capabilities(self) -> bool:
        """Check if module has any deterministic capabilities"""
        return any(cap.is_deterministic() for cap in self.capabilities)

    def requires_network(self) -> bool:
        """Check if any capability requires network"""
        return any(cap.requires_network() for cap in self.capabilities)

    def max_failure_severity(self) -> FailureSeverity:
        """Get maximum failure severity across all capabilities"""
        if not self.capabilities:
            return FailureSeverity.LOW

        # Map severity to numeric values for comparison
        severity_order = {
            FailureSeverity.LOW: 1,
            FailureSeverity.MEDIUM: 2,
            FailureSeverity.HIGH: 3,
            FailureSeverity.CRITICAL: 4,
        }

        max_sev = max(severity_order[cap.max_severity()] for cap in self.capabilities)

        # Return the corresponding severity
        for sev, val in severity_order.items():
            if val == max_sev:
                return sev

        return FailureSeverity.LOW
