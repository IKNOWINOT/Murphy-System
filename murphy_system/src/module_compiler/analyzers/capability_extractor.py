"""
Capability Extractor

Extracts executable capabilities from analyzed code structure.

Owner: INONI LLC / Corey Post (corey.gfc@gmail.com)
"""

import logging
from typing import Any, Dict, List, Optional

from ..models.module_spec import Capability, DeterminismLevel, FailureMode, FailureSeverity, ResourceProfile
from .determinism_classifier import AdvancedDeterminismClassifier
from .static_analyzer import ClassInfo, CodeStructure, FunctionInfo

logger = logging.getLogger(__name__)


class CapabilityExtractor:
    """
    Extracts capabilities from code structure.

    Converts functions and methods into Capability objects with:
    - Input/output schemas
    - Determinism classification
    - Resource profiles
    - Failure modes
    """

    def __init__(self):
        self.determinism_classifier = AdvancedDeterminismClassifier()

    def extract_capabilities(self, structure: CodeStructure) -> List[Capability]:
        """
        Extract all capabilities from code structure.

        Args:
            structure: Analyzed code structure

        Returns:
            List of Capability objects
        """
        capabilities = []

        # Extract from top-level functions
        for func in structure.functions:
            if not func.name.startswith('_'):  # Only public functions
                cap = self._function_to_capability(func, structure)
                if cap:
                    capabilities.append(cap)

        # Extract from class methods
        for cls in structure.classes:
            for method in cls.methods:
                if not method.name.startswith('_') and method.name != '__init__':
                    cap = self._method_to_capability(method, cls, structure)
                    if cap:
                        capabilities.append(cap)

        return capabilities

    def _function_to_capability(
        self,
        func: FunctionInfo,
        structure: CodeStructure
    ) -> Optional[Capability]:
        """Convert function to capability"""

        # Generate input schema from parameters
        input_schema = self._generate_input_schema(func.parameters)

        # Generate output schema from return type
        output_schema = self._generate_output_schema(func.return_type)

        # Classify determinism
        determinism = self._classify_determinism(func, structure)

        # Generate resource profile
        resource_profile = self._generate_resource_profile(func, structure)

        # Model failure modes
        failure_modes = self._model_failure_modes(func, structure)

        # Extract description from docstring
        description = func.docstring or f"Execute {func.name}"
        if description:
            # Take first line of docstring
            description = description.split('\n')[0].strip()

        return Capability(
            name=func.name,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            determinism=determinism,
            resource_profile=resource_profile,
            failure_modes=failure_modes,
            entry_point=func.name,
            required_env_vars=self._extract_env_vars(func, structure),
            required_files=self._extract_required_files(func, structure),
        )

    def _method_to_capability(
        self,
        method: FunctionInfo,
        cls: ClassInfo,
        structure: CodeStructure
    ) -> Optional[Capability]:
        """Convert method to capability"""

        # Skip if method requires 'self' only (no other params)
        if len(method.parameters) <= 1:
            return None

        # Generate input schema (skip 'self' parameter)
        params = [p for p in method.parameters if p['name'] != 'self']
        input_schema = self._generate_input_schema(params)

        # Generate output schema
        output_schema = self._generate_output_schema(method.return_type)

        # Classify determinism
        determinism = self._classify_determinism(method, structure)

        # Generate resource profile
        resource_profile = self._generate_resource_profile(method, structure)

        # Model failure modes
        failure_modes = self._model_failure_modes(method, structure)

        # Extract description
        description = method.docstring or f"Execute {cls.name}.{method.name}"
        if description:
            description = description.split('\n')[0].strip()

        return Capability(
            name=f"{cls.name}.{method.name}",
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            determinism=determinism,
            resource_profile=resource_profile,
            failure_modes=failure_modes,
            entry_point=f"{cls.name}.{method.name}",
            required_env_vars=self._extract_env_vars(method, structure),
            required_files=self._extract_required_files(method, structure),
        )

    def _generate_input_schema(self, parameters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate JSON Schema for input parameters"""
        properties = {}
        required = []

        for param in parameters:
            param_name = param['name']
            param_type = param.get('type')
            param_default = param.get('default')

            # Map Python types to JSON Schema types
            json_type = self._python_type_to_json_type(param_type)

            properties[param_name] = {
                "type": json_type,
                "description": f"Parameter {param_name}"
            }

            # If no default, it's required
            if param_default is None:
                required.append(param_name)
            else:
                properties[param_name]["default"] = param_default

        schema = {
            "type": "object",
            "properties": properties
        }

        if required:
            schema["required"] = required

        return schema

    def _generate_output_schema(self, return_type: Optional[str]) -> Dict[str, Any]:
        """Generate JSON Schema for output"""
        if return_type is None or return_type == "None":
            return {"type": "null"}

        json_type = self._python_type_to_json_type(return_type)

        return {
            "type": json_type,
            "description": "Function return value"
        }

    def _python_type_to_json_type(self, python_type: Optional[str]) -> str:
        """Map Python type to JSON Schema type"""
        if python_type is None:
            return "string"  # Default to string

        type_map = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
            "List": "array",
            "Dict": "object",
            "tuple": "array",
            "Tuple": "array",
            "set": "array",
            "Set": "array",
            "Any": "string",
        }

        # Handle generic types like List[int]
        base_type = python_type.split('[')[0]

        return type_map.get(base_type, "string")

    def _classify_determinism(
        self,
        func: FunctionInfo,
        structure: CodeStructure
    ) -> DeterminismLevel:
        """Classify function determinism level using advanced classifier"""

        # Use advanced determinism classifier
        level = self.determinism_classifier.classify(func, structure)

        return level

    def _generate_resource_profile(
        self,
        func: FunctionInfo,
        structure: CodeStructure
    ) -> ResourceProfile:
        """Generate resource profile for function"""

        # Start with defaults
        cpu_limit = 1.0
        memory_limit = "512MB"
        timeout = 60
        network_required = False
        gpu_required = False

        # Adjust based on usage patterns
        if func.uses_network or structure.uses_network:
            network_required = True
            timeout = 120  # Longer timeout for network operations

        if structure.uses_threading:
            cpu_limit = 2.0  # More CPU for threading

        if func.is_async:
            timeout = 120  # Longer timeout for async operations

        return ResourceProfile(
            cpu_limit=cpu_limit,
            memory_limit=memory_limit,
            disk_limit="100MB",
            timeout_seconds=timeout,
            network_required=network_required,
            gpu_required=gpu_required,
        )

    def _model_failure_modes(
        self,
        func: FunctionInfo,
        structure: CodeStructure
    ) -> List[FailureMode]:
        """Model potential failure modes"""
        failure_modes = []

        # Network-related failures
        if func.uses_network or structure.uses_network:
            failure_modes.append(FailureMode(
                type="network_timeout",
                severity=FailureSeverity.MEDIUM,
                description="External API or network call may timeout",
                mitigation="Set timeout=30s, retry 3 times with exponential backoff",
                probability=0.1
            ))

            failure_modes.append(FailureMode(
                type="network_unavailable",
                severity=FailureSeverity.HIGH,
                description="Network may be unavailable",
                mitigation="Check network connectivity before execution",
                probability=0.05
            ))

        # Filesystem-related failures
        if func.uses_filesystem or structure.uses_filesystem:
            failure_modes.append(FailureMode(
                type="file_not_found",
                severity=FailureSeverity.MEDIUM,
                description="Required file may not exist",
                mitigation="Validate file existence before reading",
                probability=0.15
            ))

            failure_modes.append(FailureMode(
                type="permission_denied",
                severity=FailureSeverity.HIGH,
                description="Insufficient permissions for file operation",
                mitigation="Run with appropriate permissions or use read-only mode",
                probability=0.05
            ))

        # Database-related failures
        if structure.uses_database:
            failure_modes.append(FailureMode(
                type="database_connection_failed",
                severity=FailureSeverity.HIGH,
                description="Database connection may fail",
                mitigation="Implement connection pooling and retry logic",
                probability=0.1
            ))

        # Subprocess-related failures
        if structure.uses_subprocess:
            failure_modes.append(FailureMode(
                type="subprocess_failed",
                severity=FailureSeverity.CRITICAL,
                description="Subprocess execution may fail or hang",
                mitigation="Set timeout, validate command, sanitize inputs",
                probability=0.2
            ))

        # Type-related failures (always possible in Python)
        failure_modes.append(FailureMode(
            type="type_error",
            severity=FailureSeverity.MEDIUM,
            description="Invalid input type may cause TypeError",
            mitigation="Validate input types before execution",
            probability=0.1
        ))

        # Value-related failures
        failure_modes.append(FailureMode(
            type="value_error",
            severity=FailureSeverity.MEDIUM,
            description="Invalid input value may cause ValueError",
            mitigation="Validate input values and ranges",
            probability=0.1
        ))

        return failure_modes

    # ------------------------------------------------------------------
    # Environment variable and file extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_env_vars(func: FunctionInfo, structure: CodeStructure) -> List[str]:
        """Extract required environment variables from code analysis.

        Scans the function's docstring and known import patterns for
        references to environment variables (``os.environ``, ``os.getenv``).
        A simple heuristic catches the most common patterns.
        """
        env_vars: List[str] = []

        # Infer environment variables from function analysis flags and
        # well-known import patterns.
        if func.uses_external_api:
            env_vars.append('API_KEY')
        if func.uses_network:
            env_vars.append('API_BASE_URL')

        # Check module-level imports for known env-consuming libraries.
        for imp in structure.imports:
            mod_lower = imp.module.lower()
            if 'boto' in mod_lower or 'aws' in mod_lower:
                env_vars.extend(['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION'])
            elif 'openai' in mod_lower:
                env_vars.append('OPENAI_API_KEY')
            elif 'stripe' in mod_lower:
                env_vars.append('STRIPE_API_KEY')
            elif 'redis' in mod_lower:
                env_vars.append('REDIS_URL')
            elif 'sqlalchemy' in mod_lower or 'psycopg' in mod_lower:
                env_vars.append('DATABASE_URL')
            elif 'sendgrid' in mod_lower:
                env_vars.append('SENDGRID_API_KEY')
            elif 'twilio' in mod_lower:
                env_vars.extend(['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN'])

        # De-duplicate while preserving order.
        return list(dict.fromkeys(env_vars))

    @staticmethod
    def _extract_required_files(func: FunctionInfo, structure: CodeStructure) -> List[str]:
        """Extract required files from code analysis.

        Infers file dependencies from the function's analysis flags.
        """
        files: List[str] = []

        if func.uses_filesystem:
            files.append('config.json')  # common config pattern

        # Check imports for well-known file-loading libraries.
        for imp in structure.imports:
            mod_lower = imp.module.lower()
            if 'dotenv' in mod_lower:
                files.append('.env')
            elif 'yaml' in mod_lower or 'pyyaml' in mod_lower:
                files.append('config.yaml')
            elif 'toml' in mod_lower:
                files.append('config.toml')

        # De-duplicate.
        return list(dict.fromkeys(files))
