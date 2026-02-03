# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Integrated Module Creation System
Combines best features from SwissKiss and Module Compiler

Features from SwissKiss:
- GitHub repository analysis
- License detection and validation
- Risk scanning
- Dependency extraction
- Language detection

Features from Module Compiler:
- Static code analysis
- Capability extraction
- Sandbox profile generation
- Failure mode detection
- Test vector generation
- Module specification generation
"""

import os
import re
import json
import ast
import hashlib
import requests
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import importlib.util


# ============================================================================
# ENUMS
# ============================================================================

class LicenseType(Enum):
    """Supported license types"""
    MIT = "MIT"
    BSD = "BSD"
    APACHE = "Apache"
    APACHE2 = "Apache-2.0"
    ISC = "ISC"
    UNLICENSE = "Unlicense"
    CC0 = "CC0"
    GPL = "GPL"
    LGPL = "LGPL"
    AGPL = "AGPL"
    MPL = "MPL"
    UNKNOWN = "UNKNOWN"
    MISSING = "MISSING"

class DeterminismLevel(Enum):
    """Classification of capability determinism"""
    DETERMINISTIC = "deterministic"
    PROBABILISTIC = "probabilistic"
    EXTERNAL_STATE = "external_state"

class FailureSeverity(Enum):
    """Severity of potential failure modes"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class ResourceProfile:
    """Resource requirements for capability execution"""
    cpu_limit: float = 1.0
    memory_limit: str = "512MB"
    disk_limit: str = "100MB"
    timeout_seconds: int = 60
    network_required: bool = False
    gpu_required: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_limit": self.cpu_limit,
            "memory_limit": self.memory_limit,
            "disk_limit": self.disk_limit,
            "timeout_seconds": self.timeout_seconds,
            "network_required": self.network_required,
            "gpu_required": self.gpu_required
        }


@dataclass
class FailureMode:
    """Potential failure mode for a capability"""
    type: str
    severity: FailureSeverity
    description: str
    mitigation: Optional[str] = None
    probability: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "severity": self.severity.value,
            "description": self.description,
            "mitigation": self.mitigation,
            "probability": self.probability
        }


@dataclass
class Capability:
    """A single executable capability within a module"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    determinism: DeterminismLevel
    resource_profile: ResourceProfile
    failure_modes: List[FailureMode] = field(default_factory=list)
    test_vectors: List[Dict[str, Any]] = field(default_factory=list)
    entry_point: Optional[str] = None
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
            "required_files": self.required_files
        }


@dataclass
class SandboxProfile:
    """Security sandbox configuration for module"""
    profile_type: str = "restricted"
    allowed_imports: List[str] = field(default_factory=list)
    blocked_imports: List[str] = field(default_factory=list)
    environment_variables: Dict[str, str] = field(default_factory=dict)
    file_access_rules: List[Dict[str, str]] = field(default_factory=list)
    network_rules: List[Dict[str, str]] = field(default_factory=list)
    resource_limits: ResourceProfile = field(default_factory=ResourceProfile)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_type": self.profile_type,
            "allowed_imports": self.allowed_imports,
            "blocked_imports": self.blocked_imports,
            "environment_variables": self.environment_variables,
            "file_access_rules": self.file_access_rules,
            "network_rules": self.network_rules,
            "resource_limits": self.resource_limits.to_dict()
        }


@dataclass
class RiskIssue:
    """A security risk found in code"""
    file: str
    line: int
    pattern: str
    description: str
    severity: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "pattern": self.pattern,
            "description": self.description,
            "severity": self.severity
        }


@dataclass
class ModuleSpec:
    """Complete module specification combining SwissKiss and Module Compiler"""
    # Basic Info
    module_id: str
    module_name: str
    source_path: str
    version_hash: str
    
    # GitHub Info (from SwissKiss)
    github_url: Optional[str] = None
    license_type: LicenseType = LicenseType.MISSING
    license_allowed: bool = False
    languages: Dict[str, int] = field(default_factory=dict)
    readme_summary: str = ""
    
    # Dependencies (from SwissKiss)
    dependencies: List[Dict[str, Any]] = field(default_factory=list)
    
    # Risks (from SwissKiss)
    risk_issues: List[RiskIssue] = field(default_factory=list)
    risk_score: float = 0.0
    
    # Capabilities (from Module Compiler)
    capabilities: List[Capability] = field(default_factory=list)
    
    # Sandbox (from Module Compiler)
    sandbox_profile: SandboxProfile = field(default_factory=SandboxProfile)
    
    # Commands (NEW - Integration with Command System)
    commands: List[Dict[str, Any]] = field(default_factory=list)
    
    # Build Info
    compiler_version: str = "1.0.0"
    build_steps: List[str] = field(default_factory=list)
    
    # Verification
    verification_status: str = "pending"
    verification_checks: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    is_partial: bool = False
    requires_manual_review: bool = False
    uncertainty_flags: List[str] = field(default_factory=list)
    compiled_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "module_name": self.module_name,
            "source_path": self.source_path,
            "version_hash": self.version_hash,
            "github_url": self.github_url,
            "license_type": self.license_type.value if isinstance(self.license_type, LicenseType) else self.license_type,
            "license_allowed": self.license_allowed,
            "languages": self.languages,
            "readme_summary": self.readme_summary,
            "dependencies": self.dependencies,
            "risk_issues": [issue.to_dict() for issue in self.risk_issues],
            "risk_score": self.risk_score,
            "capabilities": [cap.to_dict() for cap in self.capabilities],
            "sandbox_profile": self.sandbox_profile.to_dict(),
            "commands": self.commands,  # NEW: Include commands
            "compiler_version": self.compiler_version,
            "build_steps": self.build_steps,
            "verification_status": self.verification_status,
            "verification_checks": self.verification_checks,
            "is_partial": self.is_partial,
            "requires_manual_review": self.requires_manual_review,
            "uncertainty_flags": self.uncertainty_flags,
            "compiled_at": self.compiled_at
        }
    
    @staticmethod
    def compute_version_hash(source_path: str) -> str:
        """Compute SHA256 hash of source file"""
        with open(source_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    
    @staticmethod
    def generate_module_id(source_path: str, version_hash: str) -> str:
        """Generate unique module ID"""
        path_hash = hashlib.sha256(source_path.encode()).hexdigest()[:8]
        version_hash_short = version_hash[:8]
        return f"mod_{path_hash}_{version_hash_short}"


# ============================================================================
# GITHUB REPOSITORY ANALYZER (from SwissKiss)
# ============================================================================

class GitHubRepoAnalyzer:
    """Analyzes GitHub repositories (SwissKiss features)"""
    
    ALLOWED_LICENSES = {
        'MIT', 'BSD', 'Apache', 'Apache-2.0', 'ISC', 
        'Unlicense', 'CC0', 'GPL', 'LGPL', 'AGPL', 'MPL'
    }
    
    RISKY_PATTERNS = [
        (r'subprocess\.run', 'subprocess usage', 'medium'),
        (r'os\.system', 'os.system usage', 'high'),
        (r'eval\(', 'eval() usage', 'critical'),
        (r'exec\(', 'exec() usage', 'critical'),
        (r'input\(', 'input() usage', 'low'),
        (r'pickle\.load', 'pickle deserialization', 'high'),
        (r'shutil\.rmtree', 'rmtree usage', 'medium'),
        (r'os\.remove', 'file deletion', 'medium'),
        (r'__import__', 'dynamic import', 'medium'),
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Murphy-Module-System/1.0',
            'Accept': 'application/vnd.github.v3+json'
        })
    
    def parse_github_url(self, url: str) -> Optional[Dict[str, str]]:
        """Parse GitHub URL into owner and repo"""
        try:
            pattern = r'github\.com/([^/]+)/([^/]+?)(\.git)?$'
            match = re.search(pattern, url)
            if match:
                return {
                    'owner': match.group(1),
                    'repo': match.group(2),
                    'url': url
                }
            return None
        except (re.error, AttributeError, IndexError):
            return None
    
    def fetch_raw_file(self, owner: str, repo: str, path: str) -> Optional[str]:
        """Fetch raw file from GitHub"""
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}"
        try:
            response = self.session.get(url, timeout=10)
            return response.text if response.status_code == 200 else None
        except (requests.RequestException, requests.Timeout):
            return None
    
    def analyze_readme(self, owner: str, repo: str) -> str:
        """Fetch and summarize README"""
        for fname in ['README.md', 'README', 'readme.md']:
            content = self.fetch_raw_file(owner, repo, fname)
            if content:
                lines = content.split('\n')[:20]
                return '\n'.join(lines)
        return "No README found"
    
    def detect_license(self, owner: str, repo: str) -> Tuple[LicenseType, bool]:
        """Detect repository license"""
        for fname in ['LICENSE', 'LICENSE.txt', 'LICENSE.md', 'COPYING']:
            content = self.fetch_raw_file(owner, repo, fname)
            if content:
                for license_name in self.ALLOWED_LICENSES:
                    if license_name.lower() in content.lower():
                        return LicenseType(license_name), True
                return LicenseType.UNKNOWN, False
        return LicenseType.MISSING, False
    
    def parse_requirements(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """Parse requirements.txt, package.json, pyproject.toml"""
        dependencies = []
        
        # requirements.txt
        content = self.fetch_raw_file(owner, repo, 'requirements.txt')
        if content:
            for line in content.strip().split('\n'):
                if line and not line.startswith('#'):
                    deps = {'file': 'requirements.txt', 'name': line, 'version': ''}
                    if '==' in line:
                        deps['name'], deps['version'] = line.split('==', 1)
                    dependencies.append(deps)
        
        # package.json
        content = self.fetch_raw_file(owner, repo, 'package.json')
        if content:
            try:
                pkg_data = json.loads(content)
                for name, version in pkg_data.get('dependencies', {}).items():
                    dependencies.append({
                        'file': 'package.json',
                        'name': name,
                        'version': version
                    })
            except (json.JSONDecodeError, KeyError, AttributeError):
                pass
        
        # pyproject.toml
        content = self.fetch_raw_file(owner, repo, 'pyproject.toml')
        if content:
            # Simple parsing for dependencies
            if 'dependencies' in content:
                for line in content.split('\n'):
                    if '=' in line and not line.startswith('#'):
                        dep = line.split('=')[0].strip()
                        dependencies.append({
                            'file': 'pyproject.toml',
                            'name': dep,
                            'version': ''
                        })
        
        return dependencies
    
    def get_languages(self, owner: str, repo: str) -> Dict[str, int]:
        """Get language statistics from GitHub API"""
        url = f"https://api.github.com/repos/{owner}/{repo}/languages"
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except (requests.RequestException, json.JSONDecodeError):
            pass
        return {}
    
    def scan_risks(self, owner: str, repo: str, sample_files: List[str] = None) -> Tuple[List[RiskIssue], float]:
        """Scan for security risks in repository files"""
        if sample_files is None:
            sample_files = ['*.py', '*.js', '*.ts']
        
        issues = []
        
        # Get file list (simplified - in real implementation would use GitHub API)
        for fname in ['main.py', 'app.py', 'index.js', 'utils.py']:
            content = self.fetch_raw_file(owner, repo, fname)
            if content:
                lines = content.split('\n')
                for idx, line in enumerate(lines, 1):
                    for pattern, description, severity in self.RISKY_PATTERNS:
                        if re.search(pattern, line):
                            issues.append(RiskIssue(
                                file=fname,
                                line=idx,
                                pattern=pattern,
                                description=description,
                                severity=severity
                            ))
        
        # Calculate risk score
        if issues:
            critical = sum(1 for i in issues if i.severity == 'critical')
            high = sum(1 for i in issues if i.severity == 'high')
            medium = sum(1 for i in issues if i.severity == 'medium')
            risk_score = (critical * 1.0 + high * 0.7 + medium * 0.4) / len(issues)
        else:
            risk_score = 0.0
        
        return issues, min(risk_score, 1.0)


# ============================================================================
# STATIC CODE ANALYZER (from Module Compiler)
# ============================================================================

class StaticCodeAnalyzer:
    """Static code analysis (Module Compiler features)"""
    
    def __init__(self):
        pass
    
    def analyze_file(self, source_path: str) -> Dict[str, Any]:
        """Analyze Python file without executing"""
        with open(source_path, 'r') as f:
            tree = ast.parse(f.read())
        
        result = {
            'functions': [],
            'classes': [],
            'imports': [],
            'global_vars': [],
            'dependencies': set()
        }
        
        for node in ast.walk(tree):
            # Functions
            if isinstance(node, ast.FunctionDef):
                args = [arg.arg for arg in node.args.args]
                result['functions'].append({
                    'name': node.name,
                    'args': args,
                    'lineno': node.lineno,
                    'decorators': [self._get_decorator_name(d) for d in node.decorator_list]
                })
            
            # Classes
            elif isinstance(node, ast.ClassDef):
                result['classes'].append({
                    'name': node.name,
                    'lineno': node.lineno,
                    'bases': [self._get_name(base) for base in node.bases]
                })
            
            # Imports
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    result['imports'].append(alias.name)
                    result['dependencies'].add(alias.name)
            
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    full_import = f"{module}.{alias.name}" if module else alias.name
                    result['imports'].append(full_import)
                    if module:
                        result['dependencies'].add(module)
        
        result['dependencies'] = list(result['dependencies'])
        return result
    
    def _get_decorator_name(self, decorator) -> str:
        """Get decorator name"""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return f"{self._get_name(decorator.value)}.{decorator.attr}"
        elif isinstance(decorator, ast.Call):
            return self._get_decorator_name(decorator.func)
        return "unknown"
    
    def _get_name(self, node) -> str:
        """Get name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return "unknown"


# ============================================================================
# CAPABILITY EXTRACTOR (from Module Compiler)
# ============================================================================

class CapabilityExtractor:
    """Extract executable capabilities from code"""
    
    def __init__(self):
        pass
    
    def extract_capabilities(self, analysis: Dict[str, Any]) -> List[Capability]:
        """Extract capabilities from static analysis"""
        capabilities = []
        
        for func in analysis['functions']:
            # Skip private/internal functions
            if func['name'].startswith('_'):
                continue
            
            # Generate description
            description = f"Executes {func['name']} with arguments: {', '.join(func['args'])}"
            
            # Generate input schema
            input_schema = {
                "type": "object",
                "properties": {},
                "required": func['args'] if len(func['args']) <= 5 else []
            }
            for arg in func['args']:
                input_schema["properties"][arg] = {
                    "type": "string",
                    "description": f"Argument {arg}"
                }
            
            # Generate output schema
            output_schema = {
                "type": "object",
                "properties": {
                    "result": {"type": "any"},
                    "success": {"type": "boolean"}
                }
            }
            
            # Determine determinism (simplified)
            determinism = DeterminismLevel.DETERMINISTIC
            if 'random' in func['name'].lower() or func['name'].startswith('generate'):
                determinism = DeterminismLevel.PROBABILISTIC
            elif 'fetch' in func['name'].lower() or 'get' in func['name'].lower():
                determinism = DeterminismLevel.EXTERNAL_STATE
            
            # Create capability
            capability = Capability(
                name=func['name'],
                description=description,
                input_schema=input_schema,
                output_schema=output_schema,
                determinism=determinism,
                resource_profile=ResourceProfile(),
                entry_point=func['name']
            )
            
            capabilities.append(capability)
        
        return capabilities


# ============================================================================
# SANDBOX GENERATOR (from Module Compiler)
# ============================================================================

class SandboxGenerator:
    """Generate security sandbox profiles"""
    
    BLOCKED_IMPORTS = [
        'subprocess', 'os', 'sys', 'shutil', 'tempfile',
        'pickle', 'marshal', 'imp', 'importlib.util'
    ]
    
    RISKY_IMPORTS = [
        'requests', 'urllib', 'http', 'socket', 'ssl',
        'sqlite3', 'json', 'yaml', 'configparser'
    ]
    
    def __init__(self):
        pass
    
    def generate_sandbox_profile(self, capabilities: List[Capability], 
                                   dependencies: List[str]) -> SandboxProfile:
        """Generate sandbox profile based on capabilities and dependencies"""
        profile = SandboxProfile()
        
        # Analyze dependencies
        for dep in dependencies:
            dep_lower = dep.lower()
            
            # Blocked imports
            if any(blocked in dep_lower for blocked in self.BLOCKED_IMPORTS):
                profile.blocked_imports.append(dep)
            # Risky imports (allowed but monitored)
            elif any(risky in dep_lower for risky in self.RISKY_IMPORTS):
                if dep not in profile.allowed_imports:
                    profile.allowed_imports.append(dep)
        
        # Set profile type based on risk
        if profile.blocked_imports:
            profile.profile_type = "restricted"
        else:
            profile.profile_type = "standard"
        
        # Set resource limits based on capabilities
        if capabilities:
            profile.resource_limits = ResourceProfile(
                cpu_limit=1.0,
                memory_limit="512MB",
                timeout_seconds=60,
                network_required=any(dep.lower() in ['requests', 'urllib', 'http'] 
                                   for dep in dependencies)
            )
        
        return profile


# ============================================================================
# FAILURE MODE DETECTOR (from Module Compiler)
# ============================================================================

class FailureModeDetector:
    """Detect potential failure modes in code"""
    
    # Severity constants
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    
    FAILURE_PATTERNS = [
        (r'open\(', 'file_operation', 'File I/O error', MEDIUM),
        (r'\.split\(\)', 'string_operation', 'String split on None', LOW),
        (r'\.get\(', 'dict_operation', 'Dictionary key missing', LOW),
        (r'requests\.', 'network_operation', 'Network timeout', MEDIUM),
        (r'json\.loads', 'parsing_operation', 'JSON parsing error', MEDIUM),
        (r'int\(', 'type_conversion', 'Type conversion error', LOW),
        (r'float\(', 'type_conversion', 'Type conversion error', LOW),
    ]
    
    def __init__(self):
        pass
    
    def detect_failure_modes(self, source_path: str) -> List[FailureMode]:
        """Detect potential failure modes"""
        with open(source_path, 'r') as f:
            lines = f.readlines()
        
        failure_modes = []
        
        for idx, line in enumerate(lines, 1):
            for pattern, failure_type, description, severity in self.FAILURE_PATTERNS:
                if re.search(pattern, line):
                    failure_modes.append(FailureMode(
                        type=failure_type,
                        severity=FailureSeverity(severity),
                        description=f"{description} at line {idx}",
                        mitigation=f"Add try-except block or validation"
                    ))
        
        return failure_modes


# ============================================================================
# TEST VECTOR GENERATOR (from Module Compiler)
# ============================================================================

class TestVectorGenerator:
    """Generate test vectors for capabilities"""
    
    def __init__(self):
        pass
    
    def generate_test_vectors(self, capability: Capability) -> List[Dict[str, Any]]:
        """Generate test vectors for a capability"""
        test_vectors = []
        
        # Generate valid input test
        valid_input = {}
        for prop_name, prop_schema in capability.input_schema.get('properties', {}).items():
            prop_type = prop_schema.get('type', 'string')
            if prop_type == 'string':
                valid_input[prop_name] = f"test_{prop_name}"
            elif prop_type == 'number':
                valid_input[prop_name] = 123
            elif prop_type == 'boolean':
                valid_input[prop_name] = True
        
        test_vectors.append({
            "name": "valid_input",
            "description": "Test with valid input",
            "input": valid_input,
            "expected": {"success": True}
        })
        
        # Generate empty input test
        test_vectors.append({
            "name": "empty_input",
            "description": "Test with empty input",
            "input": {},
            "expected": {"success": False}
        })
        
        # Generate invalid type test
        if capability.input_schema.get('properties'):
            invalid_input = {k: None for k in capability.input_schema['properties'].keys()}
            test_vectors.append({
                "name": "invalid_types",
                "description": "Test with invalid types",
                "input": invalid_input,
                "expected": {"success": False}
            })
        
        return test_vectors


class CommandExtractor:
    """Extract command definitions from source code for integration with Command System"""
    
    def __init__(self):
        pass
    
    def extract_commands(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract commands from source code analysis
        
        Looks for:
        - Functions with @command decorator
        - Functions following naming pattern cmd_* or *_command
        - Docstrings with command syntax (/command)
        """
        commands = []
        
        ast_info = analysis.get("ast_info", {})
        functions = ast_info.get("functions", [])
        
        for func in functions:
            cmd_data = self._extract_command_from_function(func, analysis)
            if cmd_data:
                commands.append(cmd_data)
        
        return commands
    
    def _extract_command_from_function(self, func: Dict[str, Any], analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract command metadata from a function"""
        name = func.get("name", "")
        docstring = func.get("docstring", "")
        decorators = func.get("decorators", [])
        args = func.get("args", [])
        
        # Check if this is a command function
        if not self._is_command_function(name, docstring, decorators):
            return None
        
        # Extract command name
        cmd_name = self._extract_command_name(name, docstring, decorators)
        if not cmd_name:
            return None
        
        # Extract description
        description = self._extract_command_description(docstring)
        
        # Extract parameters
        parameters = self._extract_command_parameters(args)
        
        # Extract examples
        examples = self._extract_command_examples(docstring, cmd_name)
        
        # Determine risk level
        risk_level = self._extract_risk_level(docstring, name)
        
        return {
            "name": cmd_name,
            "description": description,
            "category": "MODULE",  # Commands from modules are MODULE category
            "parameters": parameters,
            "examples": examples,
            "requires_auth": False,  # Default, can be overridden by decorator
            "risk_level": risk_level,
            "implemented": True
        }
    
    def _is_command_function(self, name: str, docstring: str, decorators: List[str]) -> bool:
        """Check if function is a command"""
        # Check for @command decorator
        if any("@command" in dec for dec in decorators):
            return True
        
        # Check for naming patterns
        if name.startswith("cmd_") or name.endswith("_command"):
            return True
        
        # Check docstring for command syntax
        if docstring and "/" in docstring:
            lines = docstring.strip().split("\n")
            for line in lines[:3]:  # Check first 3 lines
                line = line.strip()
                if line.startswith("/") and " " in line:
                    return True
        
        return False
    
    def _extract_command_name(self, name: str, docstring: str, decorators: List[str]) -> Optional[str]:
        """Extract command name"""
        # Check decorator
        for dec in decorators:
            if "@command" in dec:
                # Extract name from @command("name") or @command(name="name")
                import re
                match = re.search(r'@command\s*\(\s*["\']([^"\']+)["\']', dec)
                if match:
                    return match.group(1)
                match = re.search(r'@command\s*\(\s*name\s*=\s*["\']([^"\']+)["\']', dec)
                if match:
                    return match.group(1)
        
        # Check docstring
        if docstring:
            lines = docstring.strip().split("\n")
            for line in lines[:3]:
                line = line.strip()
                if line.startswith("/") and " " in line:
                    # Extract "/command" from line
                    parts = line.split()
                    if parts:
                        cmd = parts[0].strip()
                        if cmd.startswith("/"):
                            return cmd[1:]  # Remove leading slash
        
        # Extract from function name
        if name.startswith("cmd_"):
            return name[4:]  # Remove "cmd_" prefix
        if name.endswith("_command"):
            return name[:-8]  # Remove "_command" suffix
        
        return None
    
    def _extract_command_description(self, docstring: str) -> str:
        """Extract command description from docstring"""
        if not docstring:
            return "No description available"
        
        lines = docstring.strip().split("\n")
        
        # Skip command syntax lines
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith("/") and " " in line:
                continue
            if line and not line.startswith("-"):
                return line
        
        return "No description available"
    
    def _extract_command_parameters(self, args: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract command parameters from function arguments"""
        parameters = []
        
        for arg in args:
            arg_name = arg.get("name", "")
            arg_type = arg.get("type", "any")
            
            # Skip 'self' parameter
            if arg_name == "self":
                continue
            
            parameters.append({
                "name": arg_name,
                "type": arg_type,
                "required": arg.get("default", None) is None,
                "description": f"Parameter: {arg_name}"
            })
        
        return parameters
    
    def _extract_command_examples(self, docstring: str, cmd_name: str) -> List[str]:
        """Extract command usage examples"""
        examples = []
        
        if not docstring:
            return examples
        
        # Look for "Examples:" or "Usage:" section
        lines = docstring.split("\n")
        in_examples = False
        
        for line in lines:
            line = line.strip()
            
            if line.lower().startswith("examples:") or line.lower().startswith("usage:"):
                in_examples = True
                continue
            
            if in_examples:
                if line.startswith("-") or line.startswith("*"):
                    example = line.lstrip("-*").strip()
                    if example.startswith("/"):
                        examples.append(example)
                elif not line:  # Empty line ends examples section
                    break
        
        # If no examples found, generate default example
        if not examples:
            examples.append(f"/{cmd_name}")
        
        return examples
    
    def _extract_risk_level(self, docstring: str, func_name: str) -> str:
        """Extract risk level from docstring or infer from function name"""
        # Check docstring for risk annotations
        if docstring:
            docstring_lower = docstring.lower()
            if "@critical" in docstring_lower or "risk: critical" in docstring_lower:
                return "CRITICAL"
            if "@high" in docstring_lower or "risk: high" in docstring_lower:
                return "HIGH"
            if "@medium" in docstring_lower or "risk: medium" in docstring_lower:
                return "MEDIUM"
            if "@low" in docstring_lower or "risk: low" in docstring_lower:
                return "LOW"
        
        # Infer from function name
        func_name_lower = func_name.lower()
        if any(word in func_name_lower for word in ["delete", "remove", "destroy", "reset"]):
            return "HIGH"
        if any(word in func_name_lower for word in ["modify", "update", "change", "override"]):
            return "MEDIUM"
        
        return "LOW"


# ============================================================================
# INTEGRATED MODULE COMPILER
# ============================================================================

class IntegratedModuleCompiler:
    """
    Main compiler combining SwissKiss and Module Compiler features
    
    Workflow:
    1. If GitHub URL provided, analyze repository (SwissKiss)
    2. Perform static code analysis (Module Compiler)
    3. Extract capabilities (Module Compiler)
    4. Generate sandbox profile (Module Compiler)
    5. Detect failure modes (Module Compiler)
    6. Generate test vectors (Module Compiler)
    7. Create comprehensive ModuleSpec
    """
    
    def __init__(self):
        self.github_analyzer = GitHubRepoAnalyzer()
        self.static_analyzer = StaticCodeAnalyzer()
        self.capability_extractor = CapabilityExtractor()
        self.command_extractor = CommandExtractor()  # NEW
        self.sandbox_generator = SandboxGenerator()
        self.failure_detector = FailureModeDetector()
        self.test_vector_generator = TestVectorGenerator()
    
    def compile_from_github(self, github_url: str, 
                              file_path: str = None,
                              category: str = "general") -> ModuleSpec:
        """
        Compile module from GitHub repository
        
        Args:
            github_url: GitHub repository URL
            file_path: Optional specific file path within repo
            category: Module category
        
        Returns:
            ModuleSpec object
        """
        # Parse GitHub URL
        repo_info = self.github_analyzer.parse_github_url(github_url)
        if not repo_info:
            raise ValueError("Invalid GitHub URL")
        
        owner, repo = repo_info['owner'], repo_info['repo']
        
        # Determine source path
        if file_path:
            source_path = file_path
        else:
            # Download main file (simplified)
            source_path = f"/workspace/temp/{owner}_{repo}_main.py"
            self._download_main_file(owner, repo, source_path)
        
        # Get repository info
        readme = self.github_analyzer.analyze_readme(owner, repo)
        license_type, license_allowed = self.github_analyzer.detect_license(owner, repo)
        dependencies = self.github_analyzer.parse_requirements(owner, repo)
        languages = self.github_analyzer.get_languages(owner, repo)
        risk_issues, risk_score = self.github_analyzer.scan_risks(owner, repo)
        
        # Static analysis
        analysis = self.static_analyzer.analyze_file(source_path)
        
        # Extract capabilities
        capabilities = self.capability_extractor.extract_capabilities(analysis)
        
        # Extract commands (NEW)
        commands = self.command_extractor.extract_commands(analysis)
        
        # Generate sandbox profile
        sandbox_profile = self.sandbox_generator.generate_sandbox_profile(
            capabilities, 
            [dep.get('name', dep) for dep in dependencies]
        )
        
        # Detect failure modes
        failure_modes = self.failure_detector.detect_failure_modes(source_path)
        
        # Generate test vectors
        for capability in capabilities:
            capability.test_vectors = self.test_vector_generator.generate_test_vectors(capability)
        
        # Create module spec
        version_hash = ModuleSpec.compute_version_hash(source_path)
        module_id = ModuleSpec.generate_module_id(source_path, version_hash)
        
        module_spec = ModuleSpec(
            module_id=module_id,
            module_name=repo,
            source_path=source_path,
            version_hash=version_hash,
            github_url=github_url,
            license_type=license_type,
            license_allowed=license_allowed,
            languages=languages,
            readme_summary=readme,
            dependencies=dependencies,
            risk_issues=risk_issues,
            risk_score=risk_score,
            capabilities=capabilities,
            commands=commands,  # NEW: Include commands
            sandbox_profile=sandbox_profile,
            verification_status="passed" if license_allowed else "failed",
            requires_manual_review=risk_score > 0.5 or not license_allowed,
            uncertainty_flags=[]
        )
        
        return module_spec
    
    def compile_from_file(self, source_path: str, 
                          category: str = "general") -> ModuleSpec:
        """
        Compile module from local file
        
        Args:
            source_path: Path to Python source file
            category: Module category
        
        Returns:
            ModuleSpec object
        """
        # Static analysis
        analysis = self.static_analyzer.analyze_file(source_path)
        
        # Extract capabilities
        capabilities = self.capability_extractor.extract_capabilities(analysis)
        
        # Generate sandbox profile
        sandbox_profile = self.sandbox_generator.generate_sandbox_profile(
            capabilities, 
            analysis['dependencies']
        )
        
        # Detect failure modes
        failure_modes = self.failure_detector.detect_failure_modes(source_path)
        
        # Generate test vectors
        for capability in capabilities:
            capability.test_vectors = self.test_vector_generator.generate_test_vectors(capability)
        
        # Create module spec
        version_hash = ModuleSpec.compute_version_hash(source_path)
        module_id = ModuleSpec.generate_module_id(source_path, version_hash)
        module_name = os.path.basename(source_path).replace('.py', '')
        
        module_spec = ModuleSpec(
            module_id=module_id,
            module_name=module_name,
            source_path=source_path,
            version_hash=version_hash,
            dependencies=[{'name': dep} for dep in analysis['dependencies']],
            capabilities=capabilities,
            commands=commands,  # NEW: Include commands
            sandbox_profile=sandbox_profile,
            verification_status="passed",
            requires_manual_review=False,
            uncertainty_flags=[]
        )
        
        return module_spec
    
    def _download_main_file(self, owner: str, repo: str, dest_path: str):
        """Download main file from GitHub (simplified)"""
        content = self.github_analyzer.fetch_raw_file(owner, repo, 'main.py')
        if not content:
            content = self.github_analyzer.fetch_raw_file(owner, repo, 'app.py')
        if not content:
            raise ValueError("Could not find main.py or app.py in repository")
        
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, 'w') as f:
            f.write(content)


# ============================================================================
# MODULE REGISTRY
# ============================================================================

class ModuleRegistry:
    """Registry for compiled modules"""
    
    def __init__(self, storage_path: str = "/workspace/module_registry"):
        self.storage_path = storage_path
        self.modules_path = os.path.join(storage_path, "modules")
        self.index_path = os.path.join(storage_path, "index.json")
        
        # Create storage directories
        os.makedirs(self.modules_path, exist_ok=True)
        
        # Load or create index
        self.index = self._load_index()
    
    def _load_index(self) -> Dict:
        """Load module index"""
        if os.path.exists(self.index_path):
            with open(self.index_path, 'r') as f:
                return json.load(f)
        return {"modules": {}, "capabilities": {}}
    
    def _save_index(self):
        """Save module index"""
        with open(self.index_path, 'w') as f:
            json.dump(self.index, f, indent=2)
    
    def register(self, module_spec: ModuleSpec) -> bool:
        """Register a compiled module"""
        try:
            # Save module spec to file
            module_file = os.path.join(self.modules_path, f"{module_spec.module_id}.json")
            with open(module_file, 'w') as f:
                json.dump(module_spec.to_dict(), f, indent=2)
            
            # Update index
            self.index["modules"][module_spec.module_id] = {
                "module_id": module_spec.module_id,
                "module_name": module_spec.module_name,
                "source_path": module_spec.source_path,
                "version_hash": module_spec.version_hash,
                "github_url": module_spec.github_url,
                "license_type": module_spec.license_type.value if isinstance(module_spec.license_type, LicenseType) else module_spec.license_type,
                "license_allowed": module_spec.license_allowed,
                "capabilities": [cap.name for cap in module_spec.capabilities],
                "risk_score": module_spec.risk_score,
                "compiled_at": module_spec.compiled_at,
                "verification_status": module_spec.verification_status
            }
            
            # Update capability index
            for cap in module_spec.capabilities:
                if cap.name not in self.index["capabilities"]:
                    self.index["capabilities"][cap.name] = []
                self.index["capabilities"][cap.name].append({
                    "module_id": module_spec.module_id,
                    "deterministic": cap.determinism.value == "deterministic"
                })
            
            # Save index
            self._save_index()
            
            return True
        except Exception as e:
            logger.error(f"Failed to register module {module_spec.module_id}: {e}")
            return False
    
    def get(self, module_id: str) -> Optional[ModuleSpec]:
        """Get module spec by ID"""
        module_file = os.path.join(self.modules_path, f"{module_id}.json")
        if os.path.exists(module_file):
            with open(module_file, 'r') as f:
                data = json.load(f)
                return self._dict_to_module_spec(data)
        return None
    
    def search_capabilities(self, capability_name: str) -> List[Dict]:
        """Find modules with specific capability"""
        if capability_name in self.index["capabilities"]:
            module_ids = [m["module_id"] for m in self.index["capabilities"][capability_name]]
            return [self.index["modules"][mid] for mid in module_ids if mid in self.index["modules"]]
        return []
    
    def list_all(self) -> List[Dict]:
        """List all registered modules"""
        return list(self.index["modules"].values())
    
    def _dict_to_module_spec(self, data: Dict) -> ModuleSpec:
        """Convert dictionary to ModuleSpec"""
        return ModuleSpec(
            module_id=data["module_id"],
            module_name=data["module_name"],
            source_path=data["source_path"],
            version_hash=data["version_hash"],
            github_url=data.get("github_url"),
            license_type=data.get("license_type", "MISSING"),
            license_allowed=data.get("license_allowed", False),
            languages=data.get("languages", {}),
            readme_summary=data.get("readme_summary", ""),
            dependencies=data.get("dependencies", []),
            risk_issues=[RiskIssue(**issue) for issue in data.get("risk_issues", [])],
            risk_score=data.get("risk_score", 0.0),
            capabilities=[self._dict_to_capability(cap) for cap in data.get("capabilities", [])],
            sandbox_profile=SandboxProfile(**data.get("sandbox_profile", {})),
            compiler_version=data.get("compiler_version", "1.0.0"),
            build_steps=data.get("build_steps", []),
            verification_status=data.get("verification_status", "pending"),
            verification_checks=data.get("verification_checks", []),
            is_partial=data.get("is_partial", False),
            requires_manual_review=data.get("requires_manual_review", False),
            uncertainty_flags=data.get("uncertainty_flags", []),
            compiled_at=data.get("compiled_at", "")
        )
    
    def _dict_to_capability(self, data: Dict) -> Capability:
        """Convert dictionary to Capability"""
        return Capability(
            name=data["name"],
            description=data["description"],
            input_schema=data["input_schema"],
            output_schema=data["output_schema"],
            determinism=DeterminismLevel(data["determinism"]),
            resource_profile=ResourceProfile(**data["resource_profile"]),
            failure_modes=[FailureMode(**fm) for fm in data.get("failure_modes", [])],
            test_vectors=data.get("test_vectors", []),
            entry_point=data.get("entry_point"),
            required_env_vars=data.get("required_env_vars", []),
            required_files=data.get("required_files", [])
        )


# ============================================================================
# MODULE MANAGER (Dynamic Loading)
# ============================================================================

class ModuleManager:
    """Manages dynamic module loading and command registration"""
    
    def __init__(self, registry: ModuleRegistry, command_registry=None):
        self.registry = registry
        self.command_registry = command_registry  # NEW
        self.loaded_modules: Dict[str, Any] = {}
        self.loaded_capabilities: Dict[str, List[str]] = {}
        self.loaded_commands: Dict[str, List[str]] = {}  # NEW
    
    def load_module(self, module_id: str) -> bool:
        """Load and activate a module"""
        if module_id in self.loaded_modules:
            logger.info(f"Module {module_id} is already loaded")
            return True
        
        # Get module spec
        module_spec = self.registry.get(module_id)
        if not module_spec:
            logger.error(f"Module {module_id} not found in registry")
            return False
        
        # Check verification status
        if module_spec.verification_status != "passed":
            logger.error(f"Module {module_id} failed verification")
            return False
        
        # Check manual review requirement
        if module_spec.requires_manual_review:
            logger.warning(f"Module {module_id} requires manual review")
            return False
        
        try:
            # Import the module
            spec = importlib.util.spec_from_file_location(module_spec.module_name, module_spec.source_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Add to loaded modules
                self.loaded_modules[module_id] = module
                self.loaded_capabilities[module_id] = [cap.name for cap in module_spec.capabilities]
                
                # NEW: Register module commands
                if self.command_registry and module_spec.commands:
                    self.command_registry.register_module_commands(module_spec.to_dict())
                    self.loaded_commands[module_id] = [cmd['name'] for cmd in module_spec.commands]
                    logger.info(f"✓ Registered {len(module_spec.commands)} commands from module: {module_id}")
                
                logger.info(f"✓ Loaded module: {module_id}")
                return True
            else:
                logger.error(f"✗ Failed to load module {module_id}: Invalid spec")
                return False
        except Exception as e:
            logger.error(f"✗ Failed to load module {module_id}: {e}")
            return False
    
    def unload_module(self, module_id: str) -> bool:
        """Unload a module"""
        if module_id not in self.loaded_modules:
            logger.warning(f"Module {module_id} is not loaded")
            return False
        
        try:
            # NEW: Unregister module commands
            if self.command_registry and module_id in self.loaded_commands:
                for cmd_name in self.loaded_commands[module_id]:
                    self.command_registry.unregister_command(cmd_name)
                del self.loaded_commands[module_id]
                logger.info(f"✓ Unregistered commands from module: {module_id}")
            
            del self.loaded_modules[module_id]
            del self.loaded_capabilities[module_id]
            logger.info(f"✓ Unloaded module: {module_id}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to unload module {module_id}: {e}")
            return False
    
    def find_modules_by_capability(self, capability_name: str) -> List[str]:
        """Find loaded modules with specific capability"""
        result = []
        for module_id, capabilities in self.loaded_capabilities.items():
            if capability_name in capabilities:
                result.append(module_id)
        return result
    
    def list_loaded(self) -> List[Dict]:
        """List all loaded modules"""
        return [
            {
                "module_id": module_id,
                "module_name": getattr(module, '__name__', 'unknown'),
                "capabilities": capabilities
            }
            for module_id, (module, capabilities) in zip(
                self.loaded_modules.keys(),
                zip(self.loaded_modules.values(), self.loaded_capabilities.values())
            )
        ]


# ============================================================================
# MAIN EXPORTS
# ============================================================================

__all__ = [
    'IntegratedModuleCompiler',
    'ModuleRegistry',
    'ModuleManager',
    'ModuleSpec',
    'Capability',
    'SandboxProfile',
    'RiskIssue',
    'GitHubRepoAnalyzer',
    'StaticCodeAnalyzer',
    'CapabilityExtractor',
    'SandboxGenerator',
    'FailureModeDetector',
    'TestVectorGenerator',
]


if __name__ == "__main__":
    # Test the integrated system
    logger.info("Integrated Module Creation System")
    logger.info("=" * 50)
    
    # Create components
    compiler = IntegratedModuleCompiler()
    registry = ModuleRegistry()
    manager = ModuleManager(registry)
    
    logger.info("\n✓ System initialized")
    logger.info(f"✓ Registry path: {registry.storage_path}")
    logger.info(f"✓ Loaded modules: {len(manager.loaded_modules)}")