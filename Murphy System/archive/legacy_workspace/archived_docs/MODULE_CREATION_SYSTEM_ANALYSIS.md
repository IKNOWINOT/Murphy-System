# Module Creation System - Analysis Report

## Executive Summary

**The current Murphy System has NO module creation system.** However, the **original Murphy Runtime System** contains a **sophisticated Module Compiler** that can:

- Compile Python modules into safe, auditable execution modules
- Extract capabilities from code
- Generate sandbox profiles
- Detect failure modes
- Create verification checks
- Register modules in a module registry

---

## Current System Status

### What's NOT Available in Current Implementation

The current Murphy System (`murphy_backend_complete.py`) **does NOT include**:
- ❌ Module compilation system
- ❌ Capability extraction from code
- ❌ Sandbox profile generation
- ❌ Failure mode detection
- ❌ Module registry
- ❌ Module manager for dynamic loading
- ❌ Test vector generation

### What IS Available

The current system has:
- ✅ Artifact Generation System (generates documents, reports, code, etc.)
- ✅ Database Integration (stores artifacts, not modules)
- ✅ Living Document System (creates documents, not modules)
- ✅ Monitoring, Shadow Agents, Cooperative Swarm

---

## Original System Capability (Module Compiler)

### Location
`/workspace/murphy_test_extract/src/module_compiler/`

### Architecture

The **Module Compiler** is a comprehensive system with 6 core components:

```
Module Compiler
├── Models (module_spec.py)
│   ├── ModuleSpec - Complete module specification
│   ├── Capability - Executable capability
│   ├── ResourceProfile - Resource requirements
│   ├── FailureMode - Potential failure modes
│   └── SandboxProfile - Security sandbox configuration
│
├── Registry (module_registry.py)
│   ├── Module storage and indexing
│   ├── Capability search and discovery
│   ├── Version management
│   └── Persistence (JSON files)
│
├── Compiler (compiler.py)
│   ├── Main orchestration
│   ├── Static analysis
│   ├── Capability extraction
│   ├── Sandbox profile generation
│   ├── Dependency extraction
│   └── Verification check creation
│
└── Analyzers (analyzers/)
    ├── StaticAnalyzer - Code structure analysis
    ├── CapabilityExtractor - Extract executable capabilities
    ├── DeterminismClassifier - Classify execution behavior
    ├── SandboxGenerator - Generate security profiles
    ├── FailureModeDetector - Detect potential failures
    └── TestVectorGenerator - Generate test cases
```

### Key Components

#### 1. ModuleSpec (Module Specification)
```python
@dataclass
class ModuleSpec:
    module_id: str                    # Unique identifier
    source_path: str                  # Source file path
    version_hash: str                 # SHA256 hash of source
    capabilities: List[Capability]   # List of capabilities
    sandbox_profile: SandboxProfile   # Security profile
    compiler_version: str             # Compiler version
    build_steps: List[str]            # Build instructions
    dependencies: List[str]           # Required dependencies
    verification_checks: List[Dict]   # Verification procedures
    verification_status: str          # passed/failed/partial
    is_partial: bool                  # Partial compilation?
    requires_manual_review: bool      # Manual review needed?
    uncertainty_flags: List[str]      # Uncertainty indicators
```

#### 2. Capability
```python
@dataclass
class Capability:
    name: str                         # Capability name
    description: str                  # What it does
    input_schema: Dict                # JSON Schema for inputs
    output_schema: Dict               # JSON Schema for outputs
    determinism: DeterminismLevel     # Deterministic/Probabilistic
    resource_profile: ResourceProfile # CPU, memory, timeout
    failure_modes: List[FailureMode]  # Potential failures
    test_vectors: List[Dict]          # Test cases
    entry_point: Optional[str]        # Function name
    required_env_vars: List[str]      # Environment variables
    required_files: List[str]         # Required files
```

#### 3. ResourceProfile
```python
@dataclass
class ResourceProfile:
    cpu_limit: float = 1.0            # CPU cores
    memory_limit: str = "512MB"       # Memory limit
    disk_limit: str = "100MB"         # Disk space
    timeout_seconds: int = 60         # Execution timeout
    network_required: bool = False    # Network access
    gpu_required: bool = False        # GPU access
```

#### 4. SandboxProfile
```python
@dataclass
class SandboxProfile:
    profile_type: str                 # Type of sandbox
    allowed_imports: List[str]        # Allowed Python imports
    blocked_imports: List[str]        # Blocked imports
    environment_variables: Dict       # Allowed env vars
    file_access_rules: List[Dict]     # File access permissions
    network_rules: List[Dict]         # Network access rules
    resource_limits: ResourceProfile  # Resource constraints
```

### How It Works

#### Compilation Process

```
Input: Python source file
  ↓
Stage 1: Static Analysis
  - Parse AST
  - Extract functions, classes, imports
  - Identify dependencies
  ↓
Stage 2: Capability Extraction
  - Identify executable functions
  - Extract input/output schemas
  - Generate descriptions
  ↓
Stage 3: Sandbox Profile Generation
  - Analyze imports
  - Generate security rules
  - Set resource limits
  ↓
Stage 4: Dependency Extraction
  - Identify required packages
  - Pin versions
  ↓
Stage 5: Build Steps Generation
  - Installation instructions
  - Configuration steps
  ↓
Stage 6: Verification Checks
  - Create validation procedures
  - Generate test vectors
  ↓
Output: ModuleSpec (safe, auditable module)
```

### Key Features

#### 1. Static Analysis (No Execution)
**CRITICAL**: The compiler NEVER executes code. It only analyzes:

```python
class StaticAnalyzer:
    def analyze_file(self, source_path: str) -> CodeStructure:
        """
        Analyze Python file without executing
        Returns:
            - Functions found
            - Classes found
            - Imports
            - Dependencies
            - Code structure
        """
```

#### 2. Capability Extraction
Automatically discovers what the module can do:

```python
class CapabilityExtractor:
    def extract_capabilities(self, structure: CodeStructure) -> List[Capability]:
        """
        Extract executable capabilities from code structure
        Returns:
            - List of capabilities with:
              * Names and descriptions
              * Input/output schemas
              * Resource requirements
              * Test vectors
        """
```

#### 3. Determinism Classification
Classifies execution behavior:

```python
class DeterminismClassifier:
    def classify(self, function_node) -> DeterminismLevel:
        """
        Classify function as:
        - DETERMINISTIC: Same input → same output
        - PROBABILISTIC: Uses randomness
        - EXTERNAL_STATE: Depends on external state
        """
```

#### 4. Failure Mode Detection
Identifies potential failures:

```python
class FailureModeDetector:
    def detect_failure_modes(self, function_node) -> List[FailureMode]:
        """
        Detect potential failures:
        - Network timeouts
        - Division by zero
        - File I/O errors
        - Invalid input
        """
```

#### 5. Sandbox Generation
Creates security profiles:

```python
class SandboxGenerator:
    def generate_sandbox_profile(self, capabilities: List[Capability]) -> SandboxProfile:
        """
        Generate security profile:
        - Allowed/blocked imports
        - File access rules
        - Network rules
        - Resource limits
        """
```

#### 6. Test Vector Generation
Creates test cases:

```python
class TestVectorGenerator:
    def generate_test_vectors(self, capability: Capability) -> List[Dict]:
        """
        Generate test vectors:
        - Valid inputs
        - Edge cases
        - Error conditions
        """
```

### Module Registry

Stores and indexes compiled modules:

```python
class ModuleRegistry:
    def register(self, module_spec: ModuleSpec) -> bool:
        """
        Register compiled module
        - Save to storage
        - Update index
        - Index capabilities
        """
    
    def search_capabilities(self, capability_name: str) -> List[ModuleSpec]:
        """
        Find modules with specific capability
        """
    
    def get_by_id(self, module_id: str) -> Optional[ModuleSpec]:
        """
        Retrieve module by ID
        """
```

### Module Manager

Manages dynamic module loading:

```python
class ModuleManager:
    def register_module(self, name, path, description, capabilities):
        """
        Register module for loading
        """
    
    def load_module(self, name) -> bool:
        """
        Load and activate module
        """
    
    def unload_module(self, name) -> bool:
        """
        Unload module
        """
    
    def find_modules_by_capability(self, capability) -> List[str]:
        """
        Find modules with specific capability
        """
```

---

## Integration Options

### Option 1: Port Module Compiler to Current System (Recommended)

**Pros:**
- Full module creation capability
- Safe, auditable modules
- Integration with existing LLM system
- Can use Artifact Generation for module distribution

**Implementation Steps:**
1. Copy Module Compiler files to `/workspace/`
2. Adapt to work with current backend
3. Add API endpoints:
   - `POST /api/modules/compile` - Compile module
   - `GET /api/modules/{id}` - Get module spec
   - `GET /api/modules/search` - Search modules
   - `POST /api/modules/load` - Load module
   - `POST /api/modules/unload` - Unload module
4. Integrate with Artifact Generation (modules as artifacts)
5. Add UI panel for module management
6. Add terminal commands for module operations

**Estimated Time:** 6-8 hours

### Option 2: Create Simplified Module System

**Approach:**
- Create basic module registration
- Allow manual module YAML creation
- Skip advanced features (sandbox, failure detection)
- Focus on module discovery and loading

**Estimated Time:** 3-4 hours

### Option 3: Keep as Separate System

**Approach:**
- Use original Module Compiler as standalone
- Create interface to call it from Murphy
- Store results in Murphy database

**Estimated Time:** 2-3 hours

---

## Proposed Implementation (Option 1)

### File Structure
```
/workspace/
├── module_compiler/                    # Module Compiler
│   ├── models/
│   │   ├── module_spec.py             # Data models
│   │   └── capability.py
│   ├── analyzers/
│   │   ├── static_analyzer.py
│   │   ├── capability_extractor.py
│   │   ├── determinism_classifier.py
│   │   ├── sandbox_generator.py
│   │   └── failure_mode_detector.py
│   ├── compiler.py                    # Main compiler
│   └── registry.py                    # Module registry
├── module_manager.py                  # Dynamic loading
└── murphy_backend_complete.py         # Add endpoints
```

### API Endpoints to Add

```python
# Module Compilation
POST /api/modules/compile
  Input: { source_path, requested_capabilities }
  Output: { module_spec, capabilities, verification_status }

# Module Registry
GET /api/modules/{id}
  Output: { module_spec, capabilities, sandbox_profile }

GET /api/modules/search
  Input: { capability_name, category }
  Output: { modules }

POST /api/modules/register
  Input: { module_spec }
  Output: { success, module_id }

# Module Loading
POST /api/modules/load
  Input: { module_id }
  Output: { success, loaded_capabilities }

POST /api/modules/unload
  Input: { module_id }
  Output: { success }

# Module Analysis
POST /api/modules/analyze
  Input: { source_path }
  Output: { structure, capabilities, dependencies }
```

### UI Components to Add

```html
<!-- Module Compiler Panel -->
<div id="module-compiler-panel">
  <input type="file" id="source-file" accept=".py">
  <button onclick="compileModule()">Compile Module</button>
  <button onclick="analyzeModule()">Analyze Only</button>
  
  <div id="module-spec">
    <!-- Module specification -->
  </div>
  
  <div id="capabilities">
    <!-- Extracted capabilities -->
  </div>
  
  <div id="sandbox-profile">
    <!-- Security profile -->
  </div>
</div>

<!-- Module Registry Panel -->
<div id="module-registry-panel">
  <input type="text" id="search-capability" placeholder="Search capability">
  <button onclick="searchModules()">Search</button>
  
  <div id="module-list">
    <!-- Registered modules -->
  </div>
</div>
```

### Terminal Commands

```
/module compile <path>          # Compile Python file to module
/module analyze <path>          # Analyze module structure
/module list                    # List all registered modules
/module search <capability>     # Search for modules
/module load <id>               # Load module
/module unload <id>             # Unload module
/module spec <id>               # Show module specification
/module capabilities <id>       # Show module capabilities
/module sandbox <id>            # Show sandbox profile
```

---

## Use Cases

### 1. Safe Code Execution
- Compile user-submitted code into safe modules
- Analyze capabilities and sandbox requirements
- Execute in controlled environment

### 2. Module Marketplace
- Share modules between users
- Browse by capability
- Verify safety before loading

### 3. Dynamic System Extension
- Load/unload modules at runtime
- Discover capabilities dynamically
- Scale system based on needs

### 4. Compliance and Auditing
- Track all loaded modules
- Verify module integrity
- Audit module capabilities

---

## Comparison: Artifacts vs Modules

| Aspect | Artifacts | Modules |
|--------|-----------|---------|
| Purpose | Documents, reports, code | Executable units |
| Source | Living documents | Python source files |
| Output | PDF, DOCX, code files | ModuleSpec with capabilities |
| Safety | Validation checks | Sandbox profiles, failure modes |
| Execution | Not executable | Executable with constraints |
| Storage | File system + database | Registry + database |
| Versioning | Supported | Supported |
| Discovery | Search by name/type | Search by capability |

---

## Sample Implementation

### Basic Module Compiler (Simplified)

```python
import ast
import inspect
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class Capability:
    name: str
    description: str
    input_schema: Dict
    output_schema: Dict
    entry_point: str

@dataclass
class ModuleSpec:
    module_id: str
    source_path: str
    capabilities: List[Capability]
    dependencies: List[str]

class SimpleModuleCompiler:
    def compile_module(self, source_path: str) -> ModuleSpec:
        """
        Compile Python file into module spec
        """
        # Parse AST
        with open(source_path, 'r') as f:
            tree = ast.parse(f.read())
        
        # Extract functions
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    'name': node.name,
                    'args': [arg.arg for arg in node.args.args],
                    'lineno': node.lineno
                })
        
        # Extract capabilities
        capabilities = []
        for func in functions:
            capabilities.append(Capability(
                name=func['name'],
                description=f"Function {func['name']}",
                input_schema={'type': 'object', 'properties': {}},
                output_schema={'type': 'object'},
                entry_point=func['name']
            ))
        
        # Extract dependencies
        dependencies = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    dependencies.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                dependencies.append(node.module or '')
        
        # Create module spec
        module_spec = ModuleSpec(
            module_id=f"mod_{source_path.replace('/', '_')}",
            source_path=source_path,
            capabilities=capabilities,
            dependencies=list(set(dependencies))
        )
        
        return module_spec
```

---

## Conclusion

**Current State:**
- ❌ Module creation system NOT available in current Murphy implementation
- ✅ Original system has sophisticated Module Compiler (2,587 lines of analyzers)

**Recommended Action:**
Port the Module Compiler to the current Murphy System. This would provide:

1. **Safe Module Compilation**
   - Static analysis without execution
   - Capability extraction
   - Sandbox profile generation

2. **Module Registry**
   - Module storage and indexing
   - Capability-based search
   - Version management

3. **Dynamic Loading**
   - Load/unload modules at runtime
   - Discover capabilities
   - Scale system dynamically

**Estimated Implementation Time:** 6-8 hours for full port and integration.

---

**Would you like me to proceed with implementing the module creation system?**