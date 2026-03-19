# API Endpoints - Complete Reference

**Comprehensive API endpoint reference for the Murphy System Runtime**

---

## Table of Contents

1. [System Endpoints](#system-endpoints)
2. [Expert Endpoints](#expert-endpoints)
3. [Gate Endpoints](#gate-endpoints)
4. [Constraint Endpoints](#constraint-endpoints)
5. [Choice Endpoints](#choice-endpoints)
6. [Chat Endpoints](#chat-endpoints)
7. [Status Endpoints](#status-endpoints)
8. [Trigger Endpoints](#trigger-endpoints)

---

## System Endpoints

### POST /api/system/build

Build a complete system with experts, gates, and constraints.

**Authentication**: Required  
**Scope**: `system:build`

#### Request

```json
{
  "description": "Build a healthcare application",
  "requirements": {
    "domain": "software",
    "complexity": "complex",
    "budget": 30000,
    "timeline": 180,
    "regulatory_requirements": ["hipaa"],
    "security_requirements": true,
    "performance_requirements": ["response_time", "throughput"]
  }
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| description | string | Yes | Description of the system to build |
| requirements.domain | string | Yes | Domain: software, infrastructure, data |
| requirements.complexity | string | No | Complexity: simple, medium, complex, very_complex |
| requirements.budget | number | No | Budget in USD |
| requirements.timeline | number | No | Timeline in days |
| requirements.regulatory_requirements | array | No | Regulatory requirements (hipaa, pci_dss, soc2, gdpr) |
| requirements.security_requirements | boolean | No | Security focus |
| requirements.performance_requirements | array | No | Performance requirements |

#### Response

```json
{
  "request_id": "req_1",
  "success": true,
  "data": {
    "system_id": "system_1",
    "experts": [
      {
        "id": "exp_1",
        "name": "Frontend Engineer",
        "specialization": "React/TypeScript",
        "expertise_level": "senior"
      }
    ],
    "gates": [
      {
        "id": "gate_1",
        "name": "HIPAA Compliance Gate",
        "type": "regulatory",
        "severity": "critical"
      }
    ],
    "constraints": [
      {
        "id": "constraint_1",
        "type": "budget",
        "value": 30000,
        "priority": 9
      }
    ],
    "recommendations": [
      "Use React for frontend",
      "Implement JWT authentication"
    ]
  },
  "message": "System built successfully",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

### POST /api/system/validate

Validate a system against constraints and gates.

**Authentication**: Required  
**Scope**: `system:validate`

#### Request

```json
{
  "system_state": {
    "total_cost": 28000,
    "timeline": 160,
    "hipaa_aligned": true,
    "security_audit_passed": true,
    "performance_met": true
  }
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| system_state | object | Yes | Current system state |

#### Response

```json
{
  "request_id": "req_2",
  "success": true,
  "data": {
    "validation": {
      "overall_status": "passed",
      "constraint_validation": {
        "status": "passed",
        "results": [
          {
            "constraint": "Budget",
            "status": "passed",
            "value": 28000,
            "limit": 30000
          }
        ]
      },
      "gate_validation": {
        "status": "passed",
        "results": [
          {
            "gate": "HIPAA Compliance Gate",
            "status": "passed",
            "conditions_met": [
              "Encryption at rest enabled",
              "Audit logging enabled"
            ]
          }
        ]
      }
    }
  },
  "message": "System validation passed",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

### GET /api/system/report

Get a comprehensive system report.

**Authentication**: Required  
**Scope**: `admin:read`

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| format | string | No | Output format: json, pdf, markdown (default: json) |

#### Response

```json
{
  "request_id": "req_3",
  "success": true,
  "data": {
    "system_id": "system_1",
    "created_at": "2024-01-01T10:00:00Z",
    "experts_count": 4,
    "gates_count": 6,
    "constraints_count": 3,
    "validation_status": "passed",
    "performance_metrics": {
      "compilation_time": 0.027,
      "memory_usage": 150,
      "confidence_score": 0.85
    }
  },
  "message": "Report generated successfully",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

### GET /api/system/state

Get current system state.

**Authentication**: Required  
**Scope**: `admin:read`

#### Response

```json
{
  "request_id": "req_4",
  "success": true,
  "data": {
    "system_id": "system_1",
    "status": "healthy",
    "total_experts": 4,
    "total_gates": 6,
    "total_constraints": 3,
    "last_updated": "2024-01-01T10:00:00Z",
    "confidence_score": 0.85
  },
  "message": "System state retrieved",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

## Expert Endpoints

### POST /api/experts/generate

Generate a team of experts.

**Authentication**: Required  
**Scope**: `experts:generate`

#### Request

```json
{
  "description": "Need experts for a fintech platform",
  "parameters": {
    "domain": "software",
    "complexity": "very_complex",
    "budget": 20000,
    "timeline": 180,
    "regulatory_requirements": ["pci_dss"],
    "team_size": 6
  }
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| description | string | Yes | Description of expert needs |
| parameters.domain | string | Yes | Domain: software, infrastructure, data |
| parameters.complexity | string | No | Complexity level |
| parameters.budget | number | No | Budget in USD |
| parameters.timeline | number | No | Timeline in days |
| parameters.regulatory_requirements | array | No | Regulatory requirements |
| parameters.team_size | number | No | Desired team size |

#### Response

```json
{
  "request_id": "req_5",
  "success": true,
  "data": {
    "experts": [
      {
        "id": "exp_1",
        "name": "Fintech Architect",
        "specialization": "Financial Systems Architecture",
        "expertise_level": "expert",
        "regulatory_knowledge": ["PCI DSS", "SOC2"]
      },
      {
        "id": "exp_2",
        "name": "Security Engineer",
        "specialization": "Financial Security",
        "expertise_level": "senior",
        "regulatory_knowledge": ["PCI DSS", "GDPR"]
      }
    ]
  },
  "message": "Experts generated successfully",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

### GET /api/experts

Get all experts in the system.

**Authentication**: Required  
**Scope**: `experts:read`

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | No | Page number (default: 1) |
| page_size | integer | No | Page size (default: 50) |
| sort_by | string | No | Sort field: name, specialization, expertise_level |
| order | string | No | Sort order: asc, desc |

#### Response

```json
{
  "request_id": "req_6",
  "success": true,
  "data": {
    "experts": [
      {
        "id": "exp_1",
        "name": "Fintech Architect",
        "specialization": "Financial Systems Architecture"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 50,
      "total": 100,
      "total_pages": 2
    }
  },
  "message": "Experts retrieved",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

### GET /api/experts/{expert_id}

Get details of a specific expert.

**Authentication**: Required  
**Scope**: `experts:read`

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| expert_id | string | Yes | Expert ID |

#### Response

```json
{
  "request_id": "req_7",
  "success": true,
  "data": {
    "id": "exp_1",
    "name": "Fintech Architect",
    "specialization": "Financial Systems Architecture",
    "expertise_level": "expert",
    "regulatory_knowledge": ["PCI DSS", "SOC2"],
    "skills": ["System Design", "Security Architecture"],
    "experience": 15,
    "certifications": ["CISSP", "CEH"]
  },
  "message": "Expert retrieved",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

## Gate Endpoints

### POST /api/gates/create

Create safety gates for a system.

**Authentication**: Required  
**Scope**: `gates:create`

#### Request

```json
{
  "description": "Create gates for a financial application",
  "parameters": {
    "domain": "software",
    "regulatory_requirements": ["pci_dss", "soc2"],
    "security_focus": true,
    "performance_requirements": ["response_time", "throughput"]
  }
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| description | string | Yes | Description of gates needed |
| parameters.domain | string | Yes | Domain |
| parameters.regulatory_requirements | array | No | Regulatory requirements |
| parameters.security_focus | boolean | No | Security focus |
| parameters.performance_requirements | array | No | Performance requirements |

#### Response

```json
{
  "request_id": "req_8",
  "success": true,
  "data": {
    "gates": [
      {
        "id": "gate_1",
        "name": "PCI DSS Compliance Gate",
        "type": "regulatory",
        "severity": "critical",
        "conditions": [
          "Encryption at rest enabled",
          "Encryption in transit enabled",
          "Secure key management"
        ]
      },
      {
        "id": "gate_2",
        "name": "SOC2 Compliance Gate",
        "type": "regulatory",
        "severity": "critical",
        "conditions": [
          "Access controls implemented",
          "Audit logging enabled"
        ]
      }
    ]
  },
  "message": "Gates created successfully",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

### GET /api/gates

Get all gates in the system.

**Authentication**: Required  
**Scope**: `gates:read`

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| type | string | No | Filter by type: regulatory, security, performance |
| severity | string | No | Filter by severity: critical, high, medium, low |

#### Response

```json
{
  "request_id": "req_9",
  "success": true,
  "data": {
    "gates": [
      {
        "id": "gate_1",
        "name": "PCI DSS Compliance Gate",
        "type": "regulatory",
        "severity": "critical"
      }
    ],
    "total": 6
  },
  "message": "Gates retrieved",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

### POST /api/gates/{gate_id}/evaluate

Evaluate a specific gate.

**Authentication**: Required  
**Scope**: `gates:read`

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| gate_id | string | Yes | Gate ID |

#### Request

```json
{
  "system_state": {
    "encryption_enabled": true,
    "key_management": "secure",
    "audit_logging": true
  }
}
```

#### Response

```json
{
  "request_id": "req_10",
  "success": true,
  "data": {
    "gate_id": "gate_1",
    "gate_name": "PCI DSS Compliance Gate",
    "evaluation_result": "passed",
    "conditions_evaluated": [
      {
        "condition": "Encryption at rest enabled",
        "status": "passed",
        "value": true
      },
      {
        "condition": "Secure key management",
        "status": "passed",
        "value": "secure"
      }
    ]
  },
  "message": "Gate evaluation completed",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

## Constraint Endpoints

### POST /api/constraints/add

Add a constraint to the system.

**Authentication**: Required  
**Scope**: `constraints:add`

#### Request

```json
{
  "type": "budget",
  "value": 50000,
  "priority": 9,
  "justification": "Maximum budget allocation",
  "parameters": {
    "flexible": false,
    "currency": "USD"
  }
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| type | string | Yes | Constraint type: budget, timeline, scope, quality |
| value | number | Yes | Constraint value |
| priority | integer | No | Priority 1-10 (default: 5) |
| justification | string | No | Justification for constraint |
| parameters | object | No | Additional parameters |

#### Response

```json
{
  "request_id": "req_11",
  "success": true,
  "data": {
    "id": "constraint_1",
    "type": "budget",
    "value": 50000,
    "priority": 9,
    "created_at": "2024-01-01T10:00:00Z"
  },
  "message": "Constraint added successfully",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

### GET /api/constraints

Get all constraints in the system.

**Authentication**: Required  
**Scope**: `constraints:read`

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| type | string | No | Filter by type |
| priority | string | No | Filter by priority (high, medium, low) |

#### Response

```json
{
  "request_id": "req_12",
  "success": true,
  "data": {
    "constraints": [
      {
        "id": "constraint_1",
        "type": "budget",
        "value": 50000,
        "priority": 9
      }
    ],
    "total": 3
  },
  "message": "Constraints retrieved",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

### POST /api/constraints/{constraint_id}/validate

Validate a specific constraint.

**Authentication**: Required  
**Scope**: `constraints:read`

#### Request

```json
{
  "system_state": {
    "current_value": 45000
  }
}
```

#### Response

```json
{
  "request_id": "req_13",
  "success": true,
  "data": {
    "constraint_id": "constraint_1",
    "constraint_type": "budget",
    "validation_result": "passed",
    "current_value": 45000,
    "limit": 50000,
    "message": "Within budget"
  },
  "message": "Constraint validation completed",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

## Choice Endpoints

### POST /api/choices/analyze

Analyze a technical choice.

**Authentication**: Required  
**Scope**: `choices:analyze`

#### Request

```json
{
  "question": "Should I use React or Angular for my frontend?",
  "type": "technical",
  "context": {
    "budget": 25000,
    "timeline": 120,
    "team_size": 5,
    "requirements": ["fast_prototyping", "large_ecosystem"]
  }
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| question | string | Yes | The question to analyze |
| type | string | Yes | Type: technical, architectural, strategic |
| context | object | No | Additional context |

#### Response

```json
{
  "request_id": "req_14",
  "success": true,
  "data": {
    "question": "Should I use React or Angular for my frontend?",
    "analysis": {
      "react": {
        "score": 8.5,
        "pros": [
          "Large ecosystem and community",
          "Fast development cycle"
        ],
        "cons": [
          "Requires additional libraries",
          "Learning curve for JSX"
        ]
      },
      "angular": {
        "score": 7.0,
        "pros": [
          "Complete framework",
          "Strong TypeScript support"
        ],
        "cons": [
          "Steeper learning curve",
          "Less flexible"
        ]
      }
    },
    "recommendation": {
      "choice": "React",
      "confidence": 0.85,
      "reasoning": "React better matches your requirements"
    }
  },
  "message": "Choice analysis completed",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

## Chat Endpoints

### POST /api/chat

Send a message to the system.

**Authentication**: Required  
**Scope**: `chat:send`

#### Request

```json
{
  "message": "Build a simple web application",
  "context": {
    "session_id": "session_1"
  }
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| message | string | Yes | The message to send |
| context.session_id | string | No | Session ID for conversation continuity |

#### Response

```json
{
  "request_id": "req_15",
  "success": true,
  "data": {
    "response": "I'll help you build a web application. Let me generate the necessary experts and create safety gates...",
    "experts_generated": 3,
    "gates_created": 4,
    "session_id": "session_1"
  },
  "message": "Response generated",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

## Status Endpoints

### GET /api/health

Check system health.

**Authentication**: Not required

#### Response

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "deploy_commit": "a1b2c3d"
}
```

> `deploy_commit` reflects the short git SHA set via the `MURPHY_DEPLOY_COMMIT`
> environment variable at service startup. It is `"unknown"` when the variable is
> not set (e.g. local development). After each production deploy the value updates
> automatically, so you can confirm which commit is live by hitting this endpoint.
>
> Pass `?deep=true` for a full readiness probe that checks persistence, database,
> Redis, LLM provider, and loaded modules.

---

## Trigger Endpoints

### GET /api/triggers

Get all pending triggers.

**Authentication**: Required  
**Scope**: `admin:read`

#### Response

```json
{
  "request_id": "req_16",
  "success": true,
  "data": {
    "triggers": [
      {
        "id": "trigger_1",
        "type": "disagreement",
        "severity": "high",
        "message": "Aristotle and Wulfrum disagree on validation",
        "created_at": "2024-01-01T10:00:00Z"
      }
    ],
    "total": 1
  },
  "message": "Triggers retrieved",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

### POST /api/triggers/{trigger_id}/resolve

Resolve a specific trigger.

**Authentication**: Required  
**Scope**: `admin:write`

#### Request

```json
{
  "resolution": "Accept Aristotle",
  "notes": "Reasoning for resolution"
}
```

#### Response

```json
{
  "request_id": "req_17",
  "success": true,
  "data": {
    "trigger_id": "trigger_1",
    "resolution": "Accept Aristotle",
    "resolved_at": "2024-01-01T10:00:00Z"
  },
  "message": "Trigger resolved successfully",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

## Next Steps

- [Examples](EXAMPLES.md) - Usage examples
- [Authentication](AUTHENTICATION.md) - Authentication details

---

**© 2025 Corey Post InonI LLC. All rights reserved.**  
**Licensed under BSL 1.1 (converts to Apache 2.0 after 4 years)**  
**Contact: corey.gfc@gmail.com**
---

## Murphy Foundation Model (MFM) Endpoints

The Murphy Foundation Model (MFM) is Murphy's self-trained local language model. These endpoints manage its lifecycle: deployment mode, training, version promotion, and rollback.

**Environment variable prerequisites:**
- `MFM_ENABLED=true` — activates MFM inference.
- `MFM_MODE` — one of `shadow`, `canary`, `production`, `disabled`.
- `MFM_BASE_MODEL` — base model identifier (default: `microsoft/Phi-3-mini-4k-instruct`).

---

### GET /api/mfm/status

Return the current MFM deployment status.

**Authentication**: Required

#### Response

```json
{
  "enabled": true,
  "mode": "shadow",
  "base_model": "microsoft/Phi-3-mini-4k-instruct",
  "device": "cuda"
}
```

| Field | Type | Description |
|-------|------|-------------|
| enabled | boolean | Whether MFM inference is active |
| mode | string | `shadow` / `canary` / `production` / `disabled` |
| base_model | string | HuggingFace model identifier |
| device | string | Compute device (`cuda`, `cpu`, `auto`) |

---

### GET /api/mfm/metrics

Return training metrics and shadow-mode comparison statistics.

**Authentication**: Required

#### Response

```json
{
  "metrics": {
    "shadow_requests": 1420,
    "shadow_agreements": 1391,
    "agreement_rate": 0.9796,
    "avg_latency_ms": 312,
    "training_loss": 0.042
  }
}
```

---

### GET /api/mfm/traces/stats

Return action-trace collection statistics used for self-improvement training.

**Authentication**: Required

#### Response

```json
{
  "total_traces": 8420,
  "labelled_traces": 6100,
  "unlabelled_traces": 2320,
  "oldest_trace": "2026-01-01T00:00:00Z",
  "newest_trace": "2026-03-16T06:00:00Z"
}
```

---

### POST /api/mfm/retrain

Trigger a manual MFM retraining cycle using collected action traces.

**Authentication**: Required  
**Scope**: `admin:write`

#### Request body

No body required.

#### Response

```json
{
  "status": "started",
  "cycle_id": "retrain-20260316-0600",
  "estimated_duration_minutes": 45
}
```

---

### POST /api/mfm/promote

Promote an MFM version through the deployment pipeline: `shadow` → `canary` → `production`.

**Authentication**: Required  
**Scope**: `admin:write`

#### Request

```json
{
  "version_id": "mfm-v0.3.1-20260316"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| version_id | string | Yes | Version identifier to promote |

#### Response

```json
{
  "promoted": true,
  "version_id": "mfm-v0.3.1-20260316",
  "new_status": "canary"
}
```

---

### POST /api/mfm/rollback

Roll back to the previous MFM production version.

**Authentication**: Required  
**Scope**: `admin:write`

#### Request body

No body required.

#### Response

```json
{
  "rolled_back": true,
  "current_version": "mfm-v0.3.0-20260310"
}
```

---

### GET /api/mfm/versions

List all MFM versions with their deployment status and metrics.

**Authentication**: Required

#### Response

```json
{
  "versions": [
    {
      "version_id": "mfm-v0.3.1-20260316",
      "version_str": "0.3.1",
      "status": "canary",
      "created_at": "2026-03-16T06:00:00Z",
      "metrics": {
        "agreement_rate": 0.9796,
        "avg_latency_ms": 312
      }
    },
    {
      "version_id": "mfm-v0.3.0-20260310",
      "version_str": "0.3.0",
      "status": "production",
      "created_at": "2026-03-10T08:00:00Z",
      "metrics": {
        "agreement_rate": 0.9751,
        "avg_latency_ms": 298
      }
    }
  ]
}
```
