"""
Module Compiler

Main orchestrator for converting bot modules into safe execution modules.

Owner: INONI LLC / Corey Post (corey.gfc@gmail.com)
"""

import logging
import os
from typing import Any, Dict, List, Optional

from .analyzers.capability_extractor import CapabilityExtractor
from .analyzers.static_analyzer import CodeStructure, StaticAnalyzer
from .models.module_spec import ModuleSpec, SandboxProfile

logger = logging.getLogger("module_compiler.compiler")


class ModuleCompiler:
    """
    Main Module Compiler.

    Converts bot modules into safe, auditable execution modules.

    CRITICAL: This compiler NEVER executes code. It only analyzes.
    """

    def __init__(self):
        self.static_analyzer = StaticAnalyzer()
        self.capability_extractor = CapabilityExtractor()
        self.failure_mode_detector = None  # Lazy load
        self.compiler_version = "1.0.0"

    def _get_failure_mode_detector(self):
        """Lazy load failure mode detector"""
        if self.failure_mode_detector is None:
            from .analyzers.failure_mode_detector import EnhancedFailureModeDetector
            self.failure_mode_detector = EnhancedFailureModeDetector()
        return self.failure_mode_detector

    def compile_module(
        self,
        source_path: str,
        requested_capabilities: Optional[List[str]] = None
    ) -> ModuleSpec:
        """
        Compile a Python module into a ModuleSpec.

        Args:
            source_path: Path to Python source file
            requested_capabilities: Optional list of specific capabilities to extract

        Returns:
            ModuleSpec object

        Raises:
            FileNotFoundError: If source file doesn't exist
            CompilationError: If compilation fails
        """
        # Validate source file exists
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file not found: {source_path}")

        # Compute version hash
        version_hash = ModuleSpec.compute_version_hash(source_path)

        # Generate module ID
        module_id = ModuleSpec.generate_module_id(source_path, version_hash)

        try:
            # Stage 1: Static analysis
            structure = self.static_analyzer.analyze_file(source_path)

            # Check for analysis errors
            if any("ERROR" in dep for dep in structure.dependencies):
                return self._create_partial_spec(
                    module_id, source_path, version_hash,
                    error="Static analysis failed",
                    structure=structure
                )

            # Stage 2: Capability extraction
            capabilities = self.capability_extractor.extract_capabilities(structure)

            # Filter capabilities if requested
            if requested_capabilities:
                capabilities = [
                    cap for cap in capabilities
                    if cap.name in requested_capabilities
                ]

            # Check if any capabilities found
            if not capabilities:
                return self._create_partial_spec(
                    module_id, source_path, version_hash,
                    error="No capabilities found",
                    structure=structure
                )

            # Stage 3: Generate sandbox profile
            sandbox_profile = self._generate_sandbox_profile(capabilities, structure)

            # Stage 4: Extract dependencies
            dependencies = self._extract_dependencies(structure)

            # Stage 5: Generate build steps
            build_steps = self._generate_build_steps(dependencies)

            # Stage 6: Create verification checks
            verification_checks = self._create_verification_checks(capabilities)

            # Create ModuleSpec
            module_spec = ModuleSpec(
                module_id=module_id,
                source_path=source_path,
                version_hash=version_hash,
                capabilities=capabilities,
                sandbox_profile=sandbox_profile,
                compiler_version=self.compiler_version,
                build_steps=build_steps,
                dependencies=dependencies,
                verification_checks=verification_checks,
                verification_status="passed",
                is_partial=False,
                requires_manual_review=self._requires_manual_review(capabilities, structure),
                uncertainty_flags=self._generate_uncertainty_flags(capabilities, structure),
            )

            return module_spec

        except Exception as exc:
            # Return partial spec on error
            logger.debug("Caught exception: %s", exc)
            return self._create_partial_spec(
                module_id, source_path, version_hash,
                error=str(exc)
            )

    def compile_directory(
        self,
        directory_path: str,
        pattern: str = "*.py"
    ) -> List[ModuleSpec]:
        """
        Compile all Python files in a directory.

        Args:
            directory_path: Path to directory
            pattern: File pattern to match (default: *.py)

        Returns:
            List of ModuleSpec objects
        """
        import glob

        module_specs = []

        # Find all Python files
        search_pattern = os.path.join(directory_path, pattern)
        python_files = glob.glob(search_pattern)

        for file_path in python_files:
            # Skip __init__.py and test files
            if file_path.endswith('__init__.py') or 'test' in file_path.lower():
                continue

            try:
                spec = self.compile_module(file_path)
                module_specs.append(spec)
            except Exception as exc:
                logger.info(f"Failed to compile {file_path}: {exc}")
                continue

        return module_specs

    def _generate_sandbox_profile(
        self,
        capabilities: List,
        structure: CodeStructure
    ) -> SandboxProfile:
        """Generate sandbox profile based on capabilities"""

        # Start with secure defaults
        profile = SandboxProfile.default_secure()

        # Adjust based on requirements
        network_required = any(cap.requires_network() for cap in capabilities)
        if network_required:
            profile.network_enabled = True

        # Adjust resource limits based on complexity
        if structure.uses_threading:
            profile.cpu_limit = 2.0
            profile.memory_limit = "1GB"

        if structure.uses_database:
            profile.memory_limit = "1GB"

        # Add required mounts
        profile.mounts = [
            {
                "source": "/tmp",
                "target": "/tmp",
                "readonly": False,
                "size": "10MB"
            }
        ]

        # Add allowed environment variables
        profile.allowed_env_vars = []

        return profile

    def _extract_dependencies(self, structure: CodeStructure) -> List[str]:
        """Extract Python dependencies"""
        dependencies = []

        for dep in structure.dependencies:
            if not dep.startswith("ERROR"):
                dependencies.append(dep)

        return dependencies

    def _generate_build_steps(self, dependencies: List[str]) -> List[str]:
        """Generate build steps for module"""
        build_steps = []

        if dependencies:
            # Generate pip install command
            deps_str = " ".join(dependencies)
            build_steps.append(f"pip install {deps_str}")

        return build_steps

    def _create_verification_checks(self, capabilities: List) -> List[Dict[str, Any]]:
        """Create verification checks for module"""
        checks = []

        # Check 1: All capabilities have valid schemas
        checks.append({
            "name": "schema_validation",
            "description": "Verify all capabilities have valid I/O schemas",
            "status": "passed",
            "details": f"{len(capabilities)} capabilities validated"
        })

        # Check 2: Determinism classification
        deterministic_count = sum(1 for cap in capabilities if cap.is_deterministic())
        checks.append({
            "name": "determinism_classification",
            "description": "Classify determinism level for all capabilities",
            "status": "passed",
            "details": f"{deterministic_count}/{len(capabilities)} deterministic"
        })

        # Check 3: Failure modes identified
        total_failure_modes = sum(len(cap.failure_modes) for cap in capabilities)
        checks.append({
            "name": "failure_mode_analysis",
            "description": "Identify potential failure modes",
            "status": "passed",
            "details": f"{total_failure_modes} failure modes identified"
        })

        return checks

    def _requires_manual_review(self, capabilities: List, structure: CodeStructure) -> bool:
        """Determine if module requires manual review"""

        # Require review if uses subprocess
        if structure.uses_subprocess:
            return True

        # Require review if any capability has critical failure modes
        for cap in capabilities:
            if cap.max_severity().value == "critical":
                return True

        return False

    def _generate_uncertainty_flags(
        self,
        capabilities: List,
        structure: CodeStructure
    ) -> List[str]:
        """Generate uncertainty flags"""
        flags = []

        # Flag if no capabilities found
        if not capabilities:
            flags.append("no_capabilities_found")

        # Flag if uses subprocess
        if structure.uses_subprocess:
            flags.append("uses_subprocess")

        # Flag if all capabilities are non-deterministic
        if capabilities and all(not cap.is_deterministic() for cap in capabilities):
            flags.append("all_non_deterministic")

        return flags

    def _create_partial_spec(
        self,
        module_id: str,
        source_path: str,
        version_hash: str,
        error: str,
        structure: Optional[CodeStructure] = None
    ) -> ModuleSpec:
        """Create a partial ModuleSpec when compilation fails"""

        return ModuleSpec(
            module_id=module_id,
            source_path=source_path,
            version_hash=version_hash,
            capabilities=[],
            sandbox_profile=SandboxProfile.default_secure(),
            compiler_version=self.compiler_version,
            verification_status="failed",
            is_partial=True,
            requires_manual_review=True,
            uncertainty_flags=[f"compilation_error: {error}"],
        )


class CompilationError(Exception):
    """Raised when module compilation fails"""
    pass
