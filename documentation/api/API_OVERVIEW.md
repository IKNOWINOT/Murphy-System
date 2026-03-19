# API Overview - Murphy System Runtime

**Complete API documentation and reference**

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Authentication](#authentication)
4. [Rate Limiting](#rate-limiting)
5. [Error Handling](#error-handling)
6. [Response Format](#response-format)
7. [Base URL](#base-url)
8. [API Endpoints](#api-endpoints)

---

## Overview

The Murphy System Runtime provides a comprehensive RESTful API for interacting with all system capabilities. The API is designed to be simple, intuitive, and powerful.

### Key Features

- **RESTful Design**: Standard HTTP methods and status codes
- **JSON Format**: All requests and responses in JSON
- **Comprehensive**: Access to all system capabilities
- **Secure**: Authentication and authorization support
- **Performant**: Sub-millisecond response times
- **Scalable**: Handles 20,000+ operations/second

### API Categories

1. **System APIs**: Build, validate, and manage systems
2. **Expert APIs**: Generate and manage expert teams
3. **Gate APIs**: Create and manage safety gates
4. **Constraint APIs**: Add and validate constraints
5. **Choice APIs**: Analyze technical choices
6. **Chat APIs**: Interactive chat interface
7. **Status APIs**: System health and monitoring
8. **Trigger APIs**: Manage human-in-the-loop triggers

---

## Architecture

### API Architecture

```
┌─────────────────────────────────────┐
│         API Gateway                 │
│  (nginx/HAProxy)                   │
└─────────────────────────────────────┘
              │
    ┌─────────┴─────────┐
    ↓                   ↓
┌─────────────┐   ┌─────────────┐
│ API Server  │   │ API Server  │
│  Instance 1 │   │  Instance 2 │
└─────────────┘   └─────────────┘
    │                   │
    └─────────┬─────────┘
              ↓
┌─────────────────────────────────────┐
│     System Integrator               │
│  (Business Logic Layer)             │
└─────────────────────────────────────┘
              │
    ┌─────────┼─────────┐
    ↓         ↓         ↓
┌───────┐ ┌───────┐ ┌───────┐
│Experts│ │ Gates │ │Conf.  │
│       │ │       │ │Engine │
└───────┘ └───────┘ └───────┘
```

### Request Flow

1. Client sends HTTP request to API Gateway
2. Gateway authenticates and validates request
3. Gateway routes request to appropriate API server
4. API server processes request through System Integrator
5. System Integrator coordinates with components
6. Response returned through same path

---

## Authentication

### API Key Authentication

The API supports API key authentication for secure access.

#### Header Format

```http
Authorization: Bearer YOUR_API_KEY
```

#### Example

```bash
curl -X POST http://localhost:8000/api/system/build \
  -H "Authorization: Bearer your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"description": "Build a system"}'
```

### API Key Generation

Generate API keys through the management interface:

```python
from src.auth import APIKeyManager

manager = APIKeyManager()
api_key = manager.generate_key(
    user_id="user_123",
    scopes=["system:build", "experts:generate", "gates:create"]
)
print(f"API Key: {api_key}")
```

### Scopes and Permissions

| Scope | Permission | Description |
|-------|-----------|-------------|
| `system:build` | Build systems | Create and build systems |
| `system:validate` | Validate systems | Validate system designs |
| `experts:generate` | Generate experts | Generate expert teams |
| `experts:read` | Read experts | View expert information |
| `gates:create` | Create gates | Create safety gates |
| `gates:read` | Read gates | View gate information |
| `constraints:add` | Add constraints | Add constraints to systems |
| `constraints:read` | Read constraints | View constraint information |
| `choices:analyze` | Analyze choices | Analyze technical choices |
| `chat:send` | Send messages | Send chat messages |
| `admin:read` | Read admin data | View system information |
| `admin:write` | Write admin data | Modify system configuration |

---

## Rate Limiting

### Rate Limit Policy

The API implements rate limiting to ensure fair usage and prevent abuse.

### Default Limits

| Tier | Requests | Time Window |
|------|----------|-------------|
| Free | 1,000 | 1 hour |
| Basic | 10,000 | 1 hour |
| Pro | 100,000 | 1 hour |
| Enterprise | Unlimited | - |

### Rate Limit Headers

All API responses include rate limit headers:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1609459200
```

### Handling Rate Limits

When rate limit is exceeded, the API returns:

```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded. Please retry after 3600 seconds."
}
```

**Status Code**: 429 Too Many Requests

**Retry-After Header**: Number of seconds to wait before retrying

---

## Error Handling

### Error Response Format

All errors follow a consistent format:

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    "field": "Additional error details",
    "value": "Invalid value"
  },
  "request_id": "req_abc123",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

### Common Error Codes

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `invalid_request` | 400 | Invalid request parameters |
| `unauthorized` | 401 | Invalid or missing authentication |
| `forbidden` | 403 | Insufficient permissions |
| `not_found` | 404 | Resource not found |
| `conflict` | 409 | Resource conflict |
| `rate_limit_exceeded` | 429 | Rate limit exceeded |
| `internal_error` | 500 | Internal server error |
| `service_unavailable` | 503 | Service temporarily unavailable |

### Error Examples

#### Invalid Request

```json
{
  "error": "invalid_request",
  "message": "Invalid parameter 'domain'. Must be one of: software, infrastructure, data",
  "details": {
    "field": "domain",
    "value": "invalid_domain"
  },
  "request_id": "req_abc123",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

#### Unauthorized

```json
{
  "error": "unauthorized",
  "message": "Invalid API key",
  "details": {},
  "request_id": "req_abc123",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

---

## Response Format

### Success Response Format

All successful responses follow this format:

```json
{
  "request_id": "req_abc123",
  "success": true,
  "data": {
    // Response data here
  },
  "message": "Success message",
  "warnings": [],
  "triggers": [],
  "timestamp": "2024-01-01T10:00:00Z"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Unique request identifier |
| `success` | boolean | Whether the request succeeded |
| `data` | object | Main response data |
| `message` | string | Human-readable message |
| `warnings` | array | Non-critical warnings |
| `triggers` | array | Human-in-the-loop triggers |
| `timestamp` | string | Response timestamp (ISO 8601) |

### Triggers

When the system detects a condition requiring human review, it creates triggers:

```json
{
  "triggers": [
    {
      "trigger_id": "trigger_1",
      "request_id": "req_abc123",
      "trigger_type": "disagreement",
      "severity": "high",
      "message": "Aristotle and Wulfrum disagree on mathematical validation",
      "context": {
        "aristotle_result": "...",
        "wulfrum_result": "..."
      },
      "options": [
        "Accept Aristotle",
        "Accept Wulfrum",
        "Request Re-evaluation",
        "Manual Override"
      ]
    }
  ]
}
```

---

## Base URL

### Development

```
http://localhost:8000
```

### Production

```
https://api.yourdomain.com
```

### API Versioning

The API is versioned using URL paths:

```
https://api.yourdomain.com/v1/system/build
```

Current version: **v1**

---

## API Endpoints

### System Endpoints

#### Build System

Build a complete system with experts, gates, and constraints.

```http
POST /api/system/build
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY

{
  "description": "Build a healthcare application",
  "requirements": {
    "domain": "software",
    "complexity": "complex",
    "budget": 30000,
    "timeline": 180,
    "regulatory_requirements": ["hipaa"]
  }
}
```

**Response**:

```json
{
  "request_id": "req_1",
  "success": true,
  "data": {
    "system_id": "system_1",
    "experts": [...],
    "gates": [...],
    "constraints": [...],
    "recommendations": [...]
  },
  "message": "System built successfully",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

#### Validate System

Validate a system against constraints and gates.

```http
POST /api/system/validate
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY

{
  "system_state": {
    "total_cost": 28000,
    "timeline": 160,
    "hipaa_aligned": true,
    "security_audit_passed": true
  }
}
```

#### Get System Report

Get a comprehensive system report.

```http
GET /api/system/report
Authorization: Bearer YOUR_API_KEY
```

### Expert Endpoints

#### Generate Experts

Generate a team of experts.

```http
POST /api/experts/generate
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY

{
  "description": "Need experts for a fintech platform",
  "parameters": {
    "domain": "software",
    "complexity": "very_complex",
    "budget": 20000,
    "timeline": 180
  }
}
```

#### Get All Experts

Get all experts in the system.

```http
GET /api/experts
Authorization: Bearer YOUR_API_KEY
```

#### Get Specific Expert

Get details of a specific expert.

```http
GET /api/experts/{expert_id}
Authorization: Bearer YOUR_API_KEY
```

### Gate Endpoints

#### Create Gates

Create safety gates for a system.

```http
POST /api/gates/create
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY

{
  "description": "Create gates for a financial application",
  "parameters": {
    "domain": "software",
    "regulatory_requirements": ["pci_dss", "soc2"],
    "security_focus": true
  }
}
```

#### Get All Gates

Get all gates in the system.

```http
GET /api/gates
Authorization: Bearer YOUR_API_KEY
```

#### Evaluate Gate

Evaluate a specific gate.

```http
POST /api/gates/{gate_id}/evaluate
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY

{
  "system_state": {
    "parameter": "value"
  }
}
```

### Constraint Endpoints

#### Add Constraint

Add a constraint to the system.

```http
POST /api/constraints/add
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY

{
  "type": "budget",
  "value": 50000,
  "priority": 9,
  "justification": "Maximum budget allocation"
}
```

#### Get All Constraints

Get all constraints in the system.

```http
GET /api/constraints
Authorization: Bearer YOUR_API_KEY
```

#### Validate Constraint

Validate a specific constraint.

```http
POST /api/constraints/{constraint_id}/validate
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY

{
  "system_state": {
    "current_value": 45000
  }
}
```

### Choice Endpoints

#### Analyze Choice

Analyze a technical choice.

```http
POST /api/choices/analyze
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY

{
  "question": "Should I use React or Angular for my frontend?",
  "type": "technical",
  "context": {
    "budget": 25000,
    "timeline": 120,
    "team_size": 5
  }
}
```

### Chat Endpoints

#### Send Message

Send a message to the system.

```http
POST /api/chat
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY

{
  "message": "Build a simple web application",
  "context": {
    "session_id": "session_1"
  }
}
```

### Status Endpoints

#### Health Check

Check system health.

```http
GET /api/health
```

**Response**:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "deploy_commit": "a1b2c3d"
}
```

> `deploy_commit` is the short git SHA injected via `MURPHY_DEPLOY_COMMIT` at
> service startup. Use `?deep=true` for a full readiness probe.

#### Get System State

Get current system state.

```http
GET /api/system/state
Authorization: Bearer YOUR_API_KEY
```

### Time Tracking Billing APIs
Base path: `/api/time/billing/`
- `GET /api/time/billing/summary` — Aggregate billing summary across all clients
- `GET /api/time/billing/summary/<client_id>` — Per-client billing summary
- `POST /api/time/billing/invoice` — Generate invoice from tracked time entries
- `POST /api/time/billing/invoice/preview` — Preview invoice before generation
- `GET /api/time/billing/rates` — List all billing rates
- `PUT /api/time/billing/rates/<client_id>` — Update billing rate for a specific client
- `GET /api/time/billing/audit-log` — Retrieve billing audit trail

### Time Tracking Dashboard APIs
Base path: `/api/time/dashboard/`
- `GET /api/time/dashboard/summary/user/<user_id>` — Individual user time dashboard
- `GET /api/time/dashboard/summary/team` — Team-level time dashboard
- `GET /api/time/dashboard/summary/project/<project_id>` — Project time dashboard
- `GET /api/time/dashboard/summary/system` — System-wide time dashboard
- `GET /api/time/team/<manager_id>/dashboard` — Manager's team dashboard view

### Time Tracking Settings APIs
Base path: `/api/time/settings/`
- `GET /api/time/settings` — Retrieve current time tracking settings
- `PUT /api/time/settings` — Update time tracking settings
- `GET /api/time/settings/validate` — Validate settings configuration

### Trigger Endpoints

#### Get Triggers

Get all pending triggers.

```http
GET /api/triggers
Authorization: Bearer YOUR_API_KEY
```

#### Resolve Trigger

Resolve a specific trigger.

```http
POST /api/triggers/{trigger_id}/resolve
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY

{
  "resolution": "Accept Aristotle",
  "notes": "Reasoning for resolution"
}
```

---

## Next Steps

- [Endpoints](ENDPOINTS.md) - Complete endpoint reference
- [Examples](EXAMPLES.md) - Usage examples
- [Authentication](AUTHENTICATION.md) - Authentication details

---

**© 2025 Corey Post InonI LLC. All rights reserved.**  
**Licensed under BSL 1.1 (converts to Apache 2.0 after 4 years)**  
**Contact: corey.gfc@gmail.com**