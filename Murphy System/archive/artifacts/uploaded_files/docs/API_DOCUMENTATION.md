# API Documentation

## Overview

The Automation Platform provides REST APIs for monitoring, health checks, and system management. All APIs return JSON responses and use standard HTTP status codes.

**Base URLs:**
- Health Check API: `http://localhost:8081`
- Monitoring API: `http://localhost:8082`
- n8n Webhooks: `http://localhost:5678/webhook`

---

## Health Check API

### GET /health

Returns overall system health status.

**Request:**
```bash
curl http://localhost:8081/health
```

**Response:**
```json
{
  "status": "healthy",
  "database": {
    "status": "healthy",
    "latency_ms": 7.56
  },
  "n8n": {
    "status": "healthy",
    "active_executions": 2
  },
  "storage": {
    "status": "healthy",
    "disk_usage_percent": 77.74
  }
}
```

**Status Codes:**
- `200 OK` - System is healthy
- `503 Service Unavailable` - System is unhealthy

---

### GET /ready

Returns readiness status (ready to accept requests).

**Request:**
```bash
curl http://localhost:8081/ready
```

**Response:**
```json
{
  "status": "ready"
}
```

**Status Codes:**
- `200 OK` - System is ready
- `503 Service Unavailable` - System is not ready

---

### GET /live

Returns liveness status (system is alive).

**Request:**
```bash
curl http://localhost:8081/live
```

**Response:**
```json
{
  "status": "alive"
}
```

**Status Codes:**
- `200 OK` - System is alive
- `503 Service Unavailable` - System is not responding

---

## Monitoring API

### GET /api/metrics

Returns recent system metrics (last 5 minutes).

**Request:**
```bash
curl http://localhost:8082/api/metrics
```

**Response:**
```json
[
  {
    "metric_name": "workflow_executions_total",
    "metric_value": 150.0,
    "metric_unit": "count",
    "recorded_at": "2026-01-29T16:15:06.768134"
  },
  {
    "metric_name": "workflow_executions_success",
    "metric_value": 142.0,
    "metric_unit": "count",
    "recorded_at": "2026-01-29T16:15:06.768134"
  }
]
```

**Status Codes:**
- `200 OK` - Metrics retrieved successfully
- `500 Internal Server Error` - Database error

---

### GET /api/alerts

Returns active alerts (last 24 hours).

**Request:**
```bash
curl http://localhost:8082/api/alerts
```

**Response:**
```json
[
  {
    "id": 1,
    "client_id": 1,
    "alert_type": "high_error_rate",
    "alert_severity": "high",
    "alert_title": "High Error Rate Detected",
    "alert_message": "INTAKE_v1_Capture_Leads workflow has 10% error rate in last hour",
    "source_workflow": "INTAKE_v1_Capture_Leads",
    "triggered_at": "2026-01-29T16:15:06.768925",
    "acknowledged": false,
    "acknowledged_at": null
  }
]
```

**Status Codes:**
- `200 OK` - Alerts retrieved successfully
- `500 Internal Server Error` - Database error

---

### GET /api/errors

Returns recent errors (last 24 hours).

**Request:**
```bash
curl http://localhost:8082/api/errors
```

**Response:**
```json
[
  {
    "id": 1,
    "client_id": 1,
    "workflow_id": "INTAKE_v1_Capture_Leads",
    "error_type": "ValidationError",
    "error_message": "Missing required field: email",
    "error_severity": "medium",
    "error_category": "validation",
    "occurred_at": "2026-01-29T16:15:08.965558",
    "resolved": false
  }
]
```

**Status Codes:**
- `200 OK` - Errors retrieved successfully
- `500 Internal Server Error` - Database error

---

### GET /api/dependencies

Returns dependency health status.

**Request:**
```bash
curl http://localhost:8082/api/dependencies
```

**Response:**
```json
[
  {
    "dependency_name": "postgresql",
    "dependency_type": "database",
    "health_status": "healthy",
    "last_check": "2026-01-29T16:13:46.278974",
    "response_time_ms": 7.5,
    "uptime_percentage": 100.0,
    "error_message": null
  },
  {
    "dependency_name": "n8n",
    "dependency_type": "service",
    "health_status": "healthy",
    "last_check": "2026-01-29T16:13:46.278974",
    "response_time_ms": 15.2,
    "uptime_percentage": 100.0,
    "error_message": null
  }
]
```

**Status Codes:**
- `200 OK` - Dependencies retrieved successfully
- `500 Internal Server Error` - Database error

---

### GET /api/health

Returns overall system health with critical counts.

**Request:**
```bash
curl http://localhost:8082/api/health
```

**Response:**
```json
{
  "status": "healthy",
  "database": "healthy",
  "critical_alerts": 0,
  "critical_errors": 0,
  "timestamp": "2026-01-29T16:22:56.554878"
}
```

**Status Codes:**
- `200 OK` - System is healthy
- `500 Internal Server Error` - System is unhealthy

---

### POST /api/alerts/:id/acknowledge

Acknowledges an alert.

**Request:**
```bash
curl -X POST http://localhost:8082/api/alerts/1/acknowledge
```

**Response:**
```json
{
  "success": true,
  "message": "Alert acknowledged"
}
```

**Status Codes:**
- `200 OK` - Alert acknowledged successfully
- `404 Not Found` - Alert not found
- `500 Internal Server Error` - Database error

---

## Webhook APIs (n8n)

### POST /webhook/intake-leads

Captures a new lead.

**Request:**
```bash
curl -X POST http://localhost:5678/webhook/intake-leads \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 1,
    "email": "john.doe@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "company_name": "Acme Corp",
    "phone": "+1234567890",
    "source": "website"
  }'
```

**Response:**
```json
{
  "success": true,
  "lead_id": 123,
  "message": "Lead captured successfully"
}
```

**Required Fields:**
- `client_id` (integer)
- `email` (string)
- `source` (string)

**Optional Fields:**
- `first_name` (string)
- `last_name` (string)
- `company_name` (string)
- `phone` (string)
- `job_title` (string)
- `source_details` (object)

**Status Codes:**
- `200 OK` - Lead captured successfully
- `400 Bad Request` - Invalid request data
- `500 Internal Server Error` - Processing error

---

### POST /webhook/intake-documents

Ingests a new document.

**Request:**
```bash
curl -X POST http://localhost:5678/webhook/intake-documents \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 1,
    "original_filename": "invoice_12345.pdf",
    "file_hash": "abc123def456",
    "file_size_bytes": 102400,
    "mime_type": "application/pdf",
    "storage_path": "/storage/documents/invoice_12345.pdf",
    "source": "email"
  }'
```

**Response:**
```json
{
  "success": true,
  "document_id": 456,
  "message": "Document ingested successfully"
}
```

**Required Fields:**
- `client_id` (integer)
- `original_filename` (string)
- `file_hash` (string)
- `file_size_bytes` (integer)
- `storage_path` (string)
- `source` (string)

**Optional Fields:**
- `mime_type` (string)
- `source_metadata` (object)

**Status Codes:**
- `200 OK` - Document ingested successfully
- `400 Bad Request` - Invalid request data
- `500 Internal Server Error` - Processing error

---

### POST /webhook/create-task

Creates a new task.

**Request:**
```bash
curl -X POST http://localhost:5678/webhook/create-task \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 1,
    "source_type": "lead",
    "source_id": 123,
    "title": "Follow up with lead",
    "description": "Contact John Doe about product demo",
    "priority": "high",
    "task_type": "follow_up",
    "due_date": "2026-02-01T10:00:00Z"
  }'
```

**Response:**
```json
{
  "success": true,
  "task_id": 789,
  "message": "Task created successfully"
}
```

**Required Fields:**
- `client_id` (integer)
- `source_type` (string)
- `title` (string)

**Optional Fields:**
- `source_id` (integer)
- `source_reference_id` (string)
- `description` (string)
- `priority` (string: low, medium, high, critical)
- `task_type` (string)
- `due_date` (ISO 8601 datetime)
- `custom_fields` (object)

**Status Codes:**
- `200 OK` - Task created successfully
- `400 Bad Request` - Invalid request data
- `500 Internal Server Error` - Processing error

---

### POST /webhook/process-error

Logs an error for monitoring.

**Request:**
```bash
curl -X POST http://localhost:5678/webhook/process-error \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 1,
    "workflow_id": "INTAKE_v1_Capture_Leads",
    "error_type": "ValidationError",
    "error_message": "Missing required field: email",
    "error_severity": "medium",
    "error_category": "validation",
    "context": {
      "lead_data": {"name": "John Doe"},
      "missing_fields": ["email"]
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "error_id": 101,
  "message": "Error logged successfully"
}
```

**Required Fields:**
- `client_id` (integer)
- `workflow_id` (string)
- `error_type` (string)
- `error_message` (string)
- `error_severity` (string: critical, high, medium, low)
- `error_category` (string: validation, network, api, database, system, business, other)

**Optional Fields:**
- `execution_id` (string)
- `error_stack` (string)
- `context` (object)

**Status Codes:**
- `200 OK` - Error logged successfully
- `400 Bad Request` - Invalid request data
- `500 Internal Server Error` - Processing error

---

## Error Responses

All APIs use standard error response format:

```json
{
  "error": "Error message description",
  "details": {
    "field": "Additional error details"
  }
}
```

### Common Error Codes

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad Request - Invalid input data |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Server error |
| 503 | Service Unavailable - Service is down |

---

## Rate Limiting

**Default Limits:**
- 100 requests per minute per IP
- 1000 requests per hour per IP

**Rate Limit Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1643472000
```

**Rate Limit Exceeded Response:**
```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60
}
```

---

## Authentication

### Webhook Authentication

Webhooks require client validation:

```bash
# Include client_id in request body
{
  "client_id": 1,
  ...
}
```

### n8n UI Authentication

n8n UI requires basic authentication:

```bash
# Access n8n UI
http://localhost:5678

# Credentials (configured during setup)
Username: admin
Password: your_password_here
```

---

## Pagination

APIs that return lists support pagination:

**Query Parameters:**
- `page` - Page number (default: 1)
- `limit` - Items per page (default: 50, max: 100)

**Example:**
```bash
curl "http://localhost:8082/api/metrics?page=2&limit=20"
```

**Response Headers:**
```
X-Total-Count: 150
X-Page: 2
X-Per-Page: 20
X-Total-Pages: 8
```

---

## Filtering

APIs support filtering via query parameters:

**Example:**
```bash
# Filter alerts by severity
curl "http://localhost:8082/api/alerts?severity=critical"

# Filter errors by category
curl "http://localhost:8082/api/errors?category=validation"

# Filter metrics by name
curl "http://localhost:8082/api/metrics?name=workflow_executions_total"
```

---

## Webhooks

### Webhook Registration

Webhooks are automatically registered when workflows are activated in n8n.

**Webhook URL Format:**
```
http://your-domain.com/webhook/{webhook-path}
```

**Example Webhooks:**
- `/webhook/intake-leads` - Lead capture
- `/webhook/intake-documents` - Document ingestion
- `/webhook/create-task` - Task creation
- `/webhook/process-error` - Error logging

### Webhook Security

**Best Practices:**
1. Use HTTPS in production
2. Validate client_id in all requests
3. Implement request signing (future enhancement)
4. Monitor webhook usage
5. Rate limit webhook endpoints

---

## Code Examples

### Python

```python
import requests

# Health check
response = requests.get('http://localhost:8081/health')
health = response.json()
print(f"System status: {health['status']}")

# Capture lead
lead_data = {
    'client_id': 1,
    'email': 'john@example.com',
    'first_name': 'John',
    'last_name': 'Doe',
    'source': 'api'
}
response = requests.post(
    'http://localhost:5678/webhook/intake-leads',
    json=lead_data
)
result = response.json()
print(f"Lead ID: {result['lead_id']}")

# Get metrics
response = requests.get('http://localhost:8082/api/metrics')
metrics = response.json()
for metric in metrics:
    print(f"{metric['metric_name']}: {metric['metric_value']}")
```

### JavaScript

```javascript
// Health check
fetch('http://localhost:8081/health')
  .then(response => response.json())
  .then(health => {
    console.log('System status:', health.status);
  });

// Capture lead
const leadData = {
  client_id: 1,
  email: 'john@example.com',
  first_name: 'John',
  last_name: 'Doe',
  source: 'api'
};

fetch('http://localhost:5678/webhook/intake-leads', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(leadData)
})
  .then(response => response.json())
  .then(result => {
    console.log('Lead ID:', result.lead_id);
  });

// Get metrics
fetch('http://localhost:8082/api/metrics')
  .then(response => response.json())
  .then(metrics => {
    metrics.forEach(metric => {
      console.log(`${metric.metric_name}: ${metric.metric_value}`);
    });
  });
```

### cURL

```bash
# Health check
curl http://localhost:8081/health

# Capture lead
curl -X POST http://localhost:5678/webhook/intake-leads \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 1,
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "source": "api"
  }'

# Get metrics
curl http://localhost:8082/api/metrics

# Get alerts
curl http://localhost:8082/api/alerts

# Acknowledge alert
curl -X POST http://localhost:8082/api/alerts/1/acknowledge
```

---

## Testing

### Test Endpoints

```bash
# Test health check
curl http://localhost:8081/health | jq

# Test monitoring API
curl http://localhost:8082/api/health | jq

# Test webhook (replace with actual URL)
curl -X POST http://localhost:5678/webhook/intake-leads \
  -H "Content-Type: application/json" \
  -d '{"client_id": 1, "email": "test@example.com", "source": "test"}' | jq
```

### Integration Tests

See `/workspace/tests/` for comprehensive integration tests.

---

## Support

**Documentation:**
- System Architecture: `/docs/SYSTEM_ARCHITECTURE.md`
- Operations Manual: `/docs/OPERATIONS_MANUAL.md`
- Deployment Guide: `/docs/DEPLOYMENT_GUIDE.md`

**Contact:**
- API Support: api-support@automation-platform.com
- Technical Support: support@automation-platform.com

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-29  
**Maintained By:** API Team