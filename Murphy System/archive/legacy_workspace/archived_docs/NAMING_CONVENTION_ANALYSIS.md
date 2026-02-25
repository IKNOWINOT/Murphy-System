# Murphy System - Naming Convention Analysis & Standardization

## 🎯 Purpose
Ensure consistent naming across all Murphy System components to prevent import errors and enable seamless integration.

---

## 📊 Current Naming Conventions

### 1. **Domain Engine** (domain_engine.py)
```python
# Classes
class DomainType(Enum)
class ImpactLevel(Enum)
class DomainImpact
class Domain
class GenerativeDomainTemplate
class DomainEngine

# Usage in backend
from domain_engine import DomainEngine
self.domain_engine = DomainEngine()
```
✅ **Status:** Consistent and correct

---

### 2. **MFGC Core** (mfgc_core.py)
```python
# Classes
class Phase(Enum)
class MFGCSystemState
class ConfidenceEngine
class AuthorityController
class MurphyIndexMonitor
class GateCompiler
class SwarmGenerator
class MFGCController

# Current backend import
from mfgc_core import Phase, MFGCSystemState

# Backend usage
self.mfgc_state = MFGCSystemState()
```
✅ **Status:** Correct imports

---

### 3. **Advanced Swarm System** (advanced_swarm_system.py)
```python
# Classes
class SwarmType(Enum)
class GenerationDomain(Enum)
class SwarmCandidate
class SafetyGate
class AdvancedSwarmGenerator

# Current backend import
from advanced_swarm_system import SwarmType, AdvancedSwarmGenerator

# Backend usage
self.swarm_generator = AdvancedSwarmGenerator()
```
✅ **Status:** Correct imports

---

### 4. **Constraint System** (constraint_system.py)
```python
# Current backend import
from constraint_system import ConstraintSystem

# Backend usage
self.constraint_system = ConstraintSystem()
```
✅ **Status:** Correct imports

---

### 5. **Gate Builder** (gate_builder.py)
```python
# Current backend import
from gate_builder import GateBuilder

# Backend usage
self.gate_builder = GateBuilder()
```
✅ **Status:** Correct imports

---

### 6. **Organization Chart System** (organization_chart_system.py)
```python
# Classes
class Department(Enum)
class JobPosition
class OrgNode
class OrganizationChart

# Current backend import
from organization_chart_system import OrganizationChart

# Backend usage
self.org_chart_system = OrganizationChart()
```
✅ **Status:** Correct imports

---

## 🔍 Identified Issues

### Issue 1: Living Document Domain Confusion
**Location:** murphy_complete_backend.py

**Problem:**
```python
class LivingDocument:
    def magnify(self, domain: str) -> Dict[str, Any]:
        """Expand domain expertise"""
        self.domain_depth += 15  # This is a depth metric
        return {
            "domain": domain,  # This is a domain name string
            ...
        }
```

**Confusion:**
- `domain` parameter = domain name (string like "engineering")
- `self.domain_depth` = depth metric (integer)
- `DomainEngine.domains` = dictionary of Domain objects

**Solution:** Rename for clarity
```python
class LivingDocument:
    def magnify(self, domain_name: str) -> Dict[str, Any]:
        """Expand domain expertise"""
        self.expertise_depth += 15  # Renamed from domain_depth
        return {
            "domain_name": domain_name,  # Clear it's a string
            "expertise_depth": self.expertise_depth,
            ...
        }
```

---

### Issue 2: Domain vs Domain Engine Naming
**Location:** murphy_complete_backend.py

**Problem:**
```python
# In generate_prompts_from_document
domains = ["engineering", "financial", "regulatory", "sales", "operations"]
for domain in domains:
    domain_prompt = f"Generate specific {domain} requirements..."
    prompts[domain] = await self.llm_router.route_request(domain_prompt, "generative")
```

**Confusion:**
- `domains` = list of domain name strings
- `self.domain_engine.domains` = dict of Domain objects
- Variable name collision potential

**Solution:** Use more specific names
```python
# In generate_prompts_from_document
domain_names = ["engineering", "financial", "regulatory", "sales", "operations"]
for domain_name in domain_names:
    domain_prompt = f"Generate specific {domain_name} requirements..."
    prompts[domain_name] = await self.llm_router.route_request(domain_prompt, "generative")
```

---

### Issue 3: Swarm Task Domain Assignment
**Location:** murphy_complete_backend.py

**Problem:**
```python
for domain, prompt in prompts.items():
    if domain == "master":
        continue
    role = role_mapping.get(domain, "General Agent")
    tasks.append({
        "domain": domain,  # String
        "role": role,
        ...
    })
```

**Confusion:**
- Task `domain` field = domain name string
- Should reference Domain objects from DomainEngine

**Solution:** Clarify and link to Domain objects
```python
for domain_name, prompt in prompts.items():
    if domain_name == "master":
        continue
    
    # Get actual Domain object from engine
    domain_obj = self.domain_engine.domains.get(domain_name) if self.domain_engine else None
    
    role = role_mapping.get(domain_name, "General Agent")
    tasks.append({
        "domain_name": domain_name,  # String identifier
        "domain_object": domain_obj,  # Actual Domain object
        "role": role,
        ...
    })
```

---

## 🔧 Standardized Naming Conventions

### 1. **Domain-Related Variables**

| Variable Name | Type | Purpose | Example |
|--------------|------|---------|---------|
| `domain_name` | str | Domain identifier | "engineering" |
| `domain_obj` | Domain | Domain object | Domain(...) |
| `domain_type` | DomainType | Domain type enum | DomainType.ENGINEERING |
| `domain_names` | List[str] | List of domain identifiers | ["engineering", "financial"] |
| `domain_objects` | List[Domain] | List of Domain objects | [Domain(...), Domain(...)] |
| `domain_dict` | Dict[str, Domain] | Domain name to object mapping | {"engineering": Domain(...)} |

### 2. **Depth/Level Variables**

| Variable Name | Type | Purpose | Example |
|--------------|------|---------|---------|
| `expertise_depth` | int | Level of domain expertise | 15 |
| `detail_level` | int | Level of detail | 3 |
| `complexity_level` | int | Complexity measure | 5 |

### 3. **Engine/System Variables**

| Variable Name | Type | Purpose | Example |
|--------------|------|---------|---------|
| `domain_engine` | DomainEngine | Domain classification engine | DomainEngine() |
| `swarm_generator` | AdvancedSwarmGenerator | Swarm generation system | AdvancedSwarmGenerator() |
| `constraint_system` | ConstraintSystem | Constraint management | ConstraintSystem() |
| `gate_builder` | GateBuilder | Gate construction | GateBuilder() |
| `org_chart_system` | OrganizationChart | Org chart management | OrganizationChart() |

---

## 📋 Required Changes

### File: murphy_complete_backend.py

#### Change 1: LivingDocument class
```python
# BEFORE
class LivingDocument:
    def __init__(self, doc_id: str, title: str, content: str, doc_type: str):
        self.domain_depth = 0
    
    def magnify(self, domain: str) -> Dict[str, Any]:
        self.domain_depth += 15
        return {
            "domain": domain,
            "domain_depth": self.domain_depth,
        }
    
    def simplify(self) -> Dict[str, Any]:
        self.domain_depth = max(0, self.domain_depth - 10)

# AFTER
class LivingDocument:
    def __init__(self, doc_id: str, title: str, content: str, doc_type: str):
        self.expertise_depth = 0  # Renamed for clarity
    
    def magnify(self, domain_name: str) -> Dict[str, Any]:
        """Expand with domain expertise"""
        self.expertise_depth += 15
        return {
            "success": True,
            "domain_name": domain_name,
            "expertise_depth": self.expertise_depth,
            "content": self.content  # Updated content
        }
    
    def simplify(self) -> Dict[str, Any]:
        """Distill to essentials"""
        self.expertise_depth = max(0, self.expertise_depth - 10)
        return {
            "success": True,
            "expertise_depth": self.expertise_depth,
            "content": self.content
        }
    
    def to_dict(self):
        return {
            "id": self.doc_id,
            "title": self.title,
            "content": self.content,
            "type": self.doc_type,
            "state": self.state,
            "expertise_depth": self.expertise_depth,  # Updated
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
```

#### Change 2: generate_prompts_from_document method
```python
# BEFORE
async def generate_prompts_from_document(self, doc_id: str) -> List[str]:
    domains = ["engineering", "financial", "regulatory", "sales", "operations"]
    for domain in domains:
        domain_prompt = f"Generate specific {domain} requirements..."
        prompts[domain] = await self.llm_router.route_request(domain_prompt, "generative")

# AFTER
async def generate_prompts_from_document(self, doc_id: str) -> List[str]:
    """Generate domain-specific prompts from document"""
    doc = self.living_documents.get(doc_id)
    if not doc:
        return []
    
    prompts = {}
    
    # Use DomainEngine to determine relevant domains
    if self.domain_engine:
        analysis = self.domain_engine.analyze_request(doc.content)
        domain_names = list(analysis['matched_domains'].keys())
    else:
        # Fallback to default domains
        domain_names = ["engineering", "financial", "regulatory", "sales", "operations"]
    
    # Generate master prompt
    master_prompt = f"Based on this document: {doc.content}\nGenerate comprehensive requirements."
    prompts["master"] = await self.llm_router.route_request(master_prompt, "generative")
    
    # Generate domain-specific prompts
    for domain_name in domain_names:
        domain_obj = self.domain_engine.domains.get(domain_name) if self.domain_engine else None
        
        domain_prompt = f"""
        Document: {doc.title}
        Domain: {domain_name}
        
        Generate specific {domain_name} requirements and tasks.
        Consider: {domain_obj.purpose if domain_obj else 'general requirements'}
        """
        
        prompts[domain_name] = await self.llm_router.route_request(domain_prompt, "generative")
    
    return prompts
```

#### Change 3: assign_swarm_tasks method
```python
# BEFORE
def assign_swarm_tasks(self, prompts: Dict[str, str]) -> List[Dict]:
    for domain, prompt in prompts.items():
        role = role_mapping.get(domain, "General Agent")
        tasks.append({
            "domain": domain,
            "role": role,
        })

# AFTER
def assign_swarm_tasks(self, prompts: Dict[str, str]) -> List[Dict]:
    """Assign prompts to swarm tasks with domain context"""
    tasks = []
    task_id = 0
    
    role_mapping = {
        "engineering": "Technical Architect",
        "financial": "Financial Analyst",
        "regulatory": "Compliance Officer",
        "sales": "Sales Strategist",
        "operations": "Operations Manager",
        "marketing": "Marketing Specialist",
        "hr": "HR Manager",
        "legal": "Legal Counsel",
        "product": "Product Manager"
    }
    
    for domain_name, prompt in prompts.items():
        if domain_name == "master":
            continue
        
        # Get Domain object from engine
        domain_obj = None
        if self.domain_engine:
            domain_obj = self.domain_engine.domains.get(domain_name)
        
        role = role_mapping.get(domain_name, "General Agent")
        
        task = {
            "id": f"TASK-{task_id}",
            "domain_name": domain_name,  # String identifier
            "domain_object": domain_obj.to_dict() if domain_obj else None,  # Full domain info
            "role": role,
            "prompt": prompt,
            "swarm_type": "hybrid",
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        
        tasks.append(task)
        self.swarms.append(task)
        task_id += 1
    
    return tasks
```

#### Change 4: generate_domain_gates method
```python
# BEFORE
def generate_domain_gates(self, domain: str) -> List[Dict]:
    gates = []
    gate_types = {
        "engineering": ["Technical Feasibility", "Architecture Review"],
        "financial": ["Budget Approval", "ROI Validation"],
    }

# AFTER
def generate_domain_gates(self, domain_name: str) -> List[Dict]:
    """Generate validation gates for a specific domain"""
    gates = []
    
    # Get Domain object from engine
    domain_obj = None
    if self.domain_engine:
        domain_obj = self.domain_engine.domains.get(domain_name)
    
    # Use gates from Domain object if available
    if domain_obj and domain_obj.gates:
        for gate_name in domain_obj.gates:
            gate = {
                "id": f"GATE-{len(self.gates)}",
                "name": gate_name,
                "domain_name": domain_name,
                "domain_object": domain_obj.to_dict(),
                "type": "validation",
                "status": "active",
                "created_at": datetime.now().isoformat()
            }
            gates.append(gate)
            self.gates.append(gate)
    else:
        # Fallback to default gates
        default_gate_types = {
            "engineering": ["Technical Feasibility Gate", "Architecture Review Gate"],
            "financial": ["Budget Approval Gate", "ROI Validation Gate"],
            "regulatory": ["Compliance Validation Gate", "Legal Review Gate"],
            "sales": ["Sales Readiness Gate", "Pricing Approval Gate"],
            "operations": ["Operational Readiness Gate", "Quality Assurance Gate"]
        }
        
        gate_names = default_gate_types.get(domain_name, [f"{domain_name.title()} Validation Gate"])
        
        for gate_name in gate_names:
            gate = {
                "id": f"GATE-{len(self.gates)}",
                "name": gate_name,
                "domain_name": domain_name,
                "type": "validation",
                "status": "active",
                "created_at": datetime.now().isoformat()
            }
            gates.append(gate)
            self.gates.append(gate)
    
    return gates
```

---

## 🎯 API Endpoint Updates

### Endpoint: POST /api/documents/<doc_id>/magnify
```python
# BEFORE
@app.route('/api/documents/<doc_id>/magnify', methods=['POST'])
def magnify_document(doc_id):
    data = request.json
    domain = data.get('domain', 'general')
    result = doc.magnify(domain)

# AFTER
@app.route('/api/documents/<doc_id>/magnify', methods=['POST'])
def magnify_document(doc_id):
    """Magnify document with domain expertise"""
    data = request.json
    domain_name = data.get('domain_name', 'general')
    
    doc = runtime.living_documents.get(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    
    # Validate domain exists in engine
    if runtime.domain_engine:
        domain_obj = runtime.domain_engine.domains.get(domain_name)
        if not domain_obj:
            return jsonify({"error": f"Domain '{domain_name}' not found"}), 400
    
    result = doc.magnify(domain_name)
    return jsonify(result)
```

---

## ✅ Validation Checklist

- [ ] All `domain` variables renamed to `domain_name` when referring to strings
- [ ] All `domain_depth` renamed to `expertise_depth` for clarity
- [ ] Domain objects accessed via `domain_engine.domains[domain_name]`
- [ ] Task dictionaries include both `domain_name` (str) and `domain_object` (dict)
- [ ] Gate generation uses Domain object gates when available
- [ ] API endpoints use `domain_name` parameter
- [ ] Frontend updated to use `domain_name` in requests
- [ ] All imports verified and tested
- [ ] No variable name collisions
- [ ] Consistent naming across all files

---

## 📊 Impact Summary

### Files to Update:
1. ✅ murphy_complete_backend.py - Main backend (multiple changes)
2. ⏳ murphy_complete_ui.html - Frontend API calls
3. ⏳ Any other files that interact with domains

### Breaking Changes:
- API parameter `domain` → `domain_name`
- LivingDocument field `domain_depth` → `expertise_depth`
- Task dictionary structure updated

### Backward Compatibility:
- Can add parameter aliases for transition period
- Document migration path for existing data

---

**Status:** Analysis Complete - Ready for Implementation
**Priority:** HIGH - Prevents runtime errors
**Next Step:** Apply changes to murphy_complete_backend.py