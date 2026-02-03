# Murphy System - Naming Conventions Fixed

## ✅ Changes Applied

### 1. **LivingDocument Class**
- `domain_depth` → `expertise_depth` (clarity)
- `magnify(domain)` → `magnify(domain_name)` (explicit string parameter)
- Updated `to_dict()` to use `expertise_depth`
- Updated history tracking to use `domain_name`

### 2. **MurphySystemRuntime Methods**

#### generate_prompts_from_document()
- `domains` → `domain_names` (list of strings)
- `domain` → `domain_name` (loop variable)
- Added DomainEngine integration for domain selection
- Added Domain object retrieval for context

#### assign_swarm_tasks()
- `domain` → `domain_name` (parameter and dictionary key)
- Added `domain_object` field with full Domain info
- Expanded role_mapping to include all 9 domains
- Added Domain object retrieval from engine

#### generate_domain_gates()
- `domain` → `domain_name` (parameter)
- Added Domain object retrieval
- Uses Domain.gates when available
- Falls back to templates with expanded coverage
- Added `domain_name` and `domain_object` to gate dict

### 3. **API Endpoints**

#### POST /api/documents/<doc_id>/magnify
- Parameter: `domain` → `domain_name` (with backward compatibility)
- Added domain validation against DomainEngine
- Returns error if domain not found

### 4. **Consistent Naming Throughout**

| Old Name | New Name | Type | Purpose |
|----------|----------|------|---------|
| `domain` | `domain_name` | str | Domain identifier |
| `domain_depth` | `expertise_depth` | int | Level of expertise |
| `domains` | `domain_names` | List[str] | List of domain identifiers |
| N/A | `domain_obj` | Domain | Domain object reference |
| N/A | `domain_object` | dict | Serialized Domain object |

## 🔗 Integration Points

### With DomainEngine
```python
# Get domain names from analysis
if self.domain_engine:
    analysis = self.domain_engine.analyze_request(content)
    domain_names = list(analysis['matched_domains'].keys())

# Get Domain object
domain_obj = self.domain_engine.domains.get(domain_name)

# Use Domain properties
purpose = domain_obj.purpose
gates = domain_obj.gates
```

### Task Structure
```python
task = {
    "task_id": "TASK-0",
    "domain_name": "engineering",  # String identifier
    "domain_object": domain_obj.to_dict(),  # Full domain info
    "role": "Chief Engineer",
    "prompt": "...",
    "status": "assigned"
}
```

### Gate Structure
```python
gate = {
    "gate_id": "GATE-0",
    "name": "Technical Feasibility Gate",
    "domain_name": "engineering",  # String identifier
    "domain_object": domain_obj.to_dict(),  # Full domain info
    "severity": 0.9,
    "status": "active"
}
```

## ✅ Benefits

1. **No Name Collisions** - Clear distinction between strings and objects
2. **Type Safety** - Explicit parameter types
3. **Better Integration** - Seamless DomainEngine integration
4. **Backward Compatible** - API supports both old and new parameter names
5. **Consistent** - Same naming pattern throughout codebase
6. **Maintainable** - Clear what each variable represents

## 📋 Testing Checklist

- [ ] LivingDocument.magnify() works with domain_name
- [ ] LivingDocument.to_dict() returns expertise_depth
- [ ] generate_prompts_from_document() uses DomainEngine
- [ ] assign_swarm_tasks() includes domain_object
- [ ] generate_domain_gates() uses Domain.gates
- [ ] API endpoint accepts domain_name parameter
- [ ] API endpoint validates against DomainEngine
- [ ] Backward compatibility with 'domain' parameter

## 🚀 Next Steps

1. Update frontend to use `domain_name` parameter
2. Test all API endpoints
3. Verify DomainEngine integration
4. Update documentation
5. Create migration guide for existing data

---

**Status:** ✅ COMPLETE
**Date:** January 20, 2026
**Impact:** Prevents runtime errors, enables DomainEngine integration