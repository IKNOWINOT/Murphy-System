# Murphy System API Documentation

## Overview
The Murphy System provides a RESTful API for task execution, correction capture, and shadow agent predictions.

**Base URL:** `https://api.murphy-system.com`
**Version:** v1
**Authentication:** API Key (Header: `X-API-Key`)

---

## Table of Contents
1. [Authentication](#authentication)
2. [Form Submission](#form-submission)
3. [Task Execution](#task-execution)
4. [Correction Capture](#correction-capture)
5. [Shadow Agent](#shadow-agent)
6. [Monitoring](#monitoring)

---

## Authentication

All API requests require authentication using an API key.

### Headers
```
X-API-Key: your-api-key-here
Content-Type: application/json
```

### Example
```bash
curl -H "X-API-Key: your-api-key" \
     -H "Content-Type: application/json" \
     https://api.murphy-system.com/health
```

---

## Form Submission

### Submit Plan Upload Form

**Endpoint:** `POST /api/forms/plan-upload`

**Description:** Upload a pre-defined task plan for execution.

**Request Body:**
```json
{
  "plan_file": "base64_encoded_file_content",
  "plan_format": "json",
  "metadata": {
    "source": "user_upload",
    "version": "1.0"
  }
}
```

**Response:**
```json
{
  "submission_id": "uuid",
  "status": "accepted",
  "plan_id": "uuid",
  "tasks_count": 10,
  "estimated_duration_minutes": 30
}
```

**Status Codes:**
- `200 OK` - Plan accepted
- `400 Bad Request` - Invalid plan format
- `401 Unauthorized` - Invalid API key
- `413 Payload Too Large` - Plan exceeds size limit

---

### Submit Plan Generation Form

**Endpoint:** `POST /api/forms/plan-generation`

**Description:** Generate a task plan from natural language description.

**Request Body:**
```json
{
  "description": "Create a blog post about AI and publish it",
  "constraints": {
    "max_duration_minutes": 60,
    "required_approvals": ["content_review"]
  },
  "preferences": {
    "style": "professional",
    "tone": "informative"
  }
}
```

**Response:**
```json
{
  "submission_id": "uuid",
  "status": "generated",
  "plan_id": "uuid",
  "tasks": [
    {
      "id": "uuid",
      "name": "Research topic",
      "type": "research",
      "estimated_duration_minutes": 15
    }
  ]
}
```

---

### Submit Task Execution Form

**Endpoint:** `POST /api/forms/task-execution`

**Description:** Execute a specific task.

**Request Body:**
```json
{
  "task_id": "uuid",
  "execution_mode": "automatic",
  "parameters": {
    "input_data": "...",
    "options": {}
  }
}
```

**Response:**
```json
{
  "submission_id": "uuid",
  "status": "executing",
  "task_id": "uuid",
  "execution_id": "uuid",
  "estimated_completion": "2024-01-15T10:30:00Z"
}
```

---

## Task Execution

### Get Task Status

**Endpoint:** `GET /api/tasks/{task_id}/status`

**Description:** Get current status of a task.

**Response:**
```json
{
  "task_id": "uuid",
  "status": "completed",
  "progress": 100,
  "result": {
    "output": "...",
    "metrics": {}
  },
  "started_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:30:00Z"
}
```

---

### Cancel Task

**Endpoint:** `POST /api/tasks/{task_id}/cancel`

**Description:** Cancel a running task.

**Response:**
```json
{
  "task_id": "uuid",
  "status": "cancelled",
  "cancelled_at": "2024-01-15T10:15:00Z"
}
```

---

## Correction Capture

### Submit Correction

**Endpoint:** `POST /api/corrections`

**Description:** Submit a correction for a task execution.

**Request Body:**
```json
{
  "task_id": "uuid",
  "correction_type": "output_modification",
  "original_value": "incorrect output",
  "corrected_value": "correct output",
  "reason": "The output had incorrect formatting",
  "severity": "medium"
}
```

**Response:**
```json
{
  "correction_id": "uuid",
  "status": "recorded",
  "quality_score": 0.85,
  "will_be_used_for_training": true
}
```

---

### Submit Feedback

**Endpoint:** `POST /api/feedback`

**Description:** Submit feedback on task execution.

**Request Body:**
```json
{
  "task_id": "uuid",
  "feedback_type": "quality",
  "rating": 4,
  "comment": "Good result but could be faster",
  "category": "performance"
}
```

**Response:**
```json
{
  "feedback_id": "uuid",
  "status": "recorded",
  "thank_you": true
}
```

---

### Get Corrections

**Endpoint:** `GET /api/corrections`

**Query Parameters:**
- `task_id` (optional) - Filter by task
- `status` (optional) - Filter by status (pending, approved, rejected)
- `limit` (optional) - Number of results (default: 50)
- `offset` (optional) - Pagination offset

**Response:**
```json
{
  "corrections": [
    {
      "id": "uuid",
      "task_id": "uuid",
      "type": "output_modification",
      "status": "approved",
      "created_at": "2024-01-15T10:00:00Z"
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

---

## Shadow Agent

### Make Prediction

**Endpoint:** `POST /api/shadow-agent/predict`

**Description:** Get a prediction from the shadow agent.

**Request Body:**
```json
{
  "input_features": {
    "task_type": "validation",
    "complexity": 5,
    "context": {}
  },
  "task_id": "uuid",
  "use_fallback": true
}
```

**Response:**
```json
{
  "prediction_id": "uuid",
  "prediction": true,
  "confidence": 0.92,
  "source": "shadow_agent",
  "model_version": "1.2.0",
  "prediction_time_ms": 45
}
```

---

### Get Shadow Agent Stats

**Endpoint:** `GET /api/shadow-agent/stats`

**Description:** Get statistics about shadow agent performance.

**Response:**
```json
{
  "total_predictions": 10000,
  "avg_confidence": 0.87,
  "high_confidence_rate": 0.75,
  "avg_prediction_time_ms": 52,
  "fallback_rate": 0.15,
  "current_model": {
    "id": "uuid",
    "version": "1.2.0",
    "accuracy": 0.91
  }
}
```

---

### Train Model

**Endpoint:** `POST /api/shadow-agent/train`

**Description:** Trigger model training from recent corrections.

**Request Body:**
```json
{
  "model_name": "shadow_agent_v2",
  "model_version": "2.0.0",
  "tune_hyperparameters": true,
  "min_corrections": 1000
}
```

**Response:**
```json
{
  "training_id": "uuid",
  "status": "started",
  "estimated_duration_minutes": 30,
  "model_id": "uuid"
}
```

---

### Deploy Model

**Endpoint:** `POST /api/shadow-agent/deploy`

**Description:** Deploy a trained model to production.

**Request Body:**
```json
{
  "model_id": "uuid",
  "environment": "production",
  "use_ab_test": true,
  "use_gradual_rollout": true
}
```

**Response:**
```json
{
  "deployment_id": "uuid",
  "status": "deploying",
  "model_id": "uuid",
  "environment": "production",
  "rollout_strategy": "gradual"
}
```

---

## Monitoring

### Health Check

**Endpoint:** `GET /health`

**Description:** Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:00:00Z",
  "components": {
    "database": "healthy",
    "redis": "healthy",
    "shadow_agent": "healthy"
  }
}
```

---

### Get Metrics

**Endpoint:** `GET /metrics`

**Description:** Get Prometheus metrics.

**Response:** (Prometheus format)
```
# HELP murphy_api_requests_total Total API requests
# TYPE murphy_api_requests_total counter
murphy_api_requests_total{method="GET",endpoint="/health"} 1000

# HELP murphy_model_accuracy Current model accuracy
# TYPE murphy_model_accuracy gauge
murphy_model_accuracy 0.91
```

---

### Get System Status

**Endpoint:** `GET /api/status`

**Description:** Get complete system status.

**Response:**
```json
{
  "system": {
    "status": "operational",
    "uptime_seconds": 86400,
    "version": "1.0.0"
  },
  "shadow_agent": {
    "model_loaded": true,
    "model_version": "1.2.0",
    "accuracy": 0.91
  },
  "monitoring": {
    "active_alerts": 0,
    "last_check": "2024-01-15T10:00:00Z"
  }
}
```

---

## Error Responses

All error responses follow this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "Additional context"
    }
  }
}
```

### Common Error Codes

- `INVALID_REQUEST` - Request validation failed
- `UNAUTHORIZED` - Invalid or missing API key
- `NOT_FOUND` - Resource not found
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `INTERNAL_ERROR` - Server error

---

## Rate Limiting

- **Rate Limit:** 1000 requests per hour per API key
- **Headers:**
  - `X-RateLimit-Limit`: Maximum requests per hour
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Time when limit resets (Unix timestamp)

---

## Webhooks

### Configure Webhook

**Endpoint:** `POST /api/webhooks`

**Description:** Configure a webhook for events.

**Request Body:**
```json
{
  "url": "https://your-server.com/webhook",
  "events": ["task.completed", "correction.submitted"],
  "secret": "webhook-secret"
}
```

### Webhook Events

- `task.completed` - Task execution completed
- `task.failed` - Task execution failed
- `correction.submitted` - New correction submitted
- `model.deployed` - New model deployed
- `alert.triggered` - Alert triggered

---

## SDKs

### Python SDK

```python
from murphy_client import MurphyClient

client = MurphyClient(api_key="your-api-key")

# Submit task
result = client.tasks.execute(
    task_id="uuid",
    parameters={"input": "data"}
)

# Get prediction
prediction = client.shadow_agent.predict(
    input_features={"task_type": "validation"}
)
```

### JavaScript SDK

```javascript
const Murphy = require('murphy-client');

const client = new Murphy({ apiKey: 'your-api-key' });

// Submit task
const result = await client.tasks.execute({
  taskId: 'uuid',
  parameters: { input: 'data' }
});

// Get prediction
const prediction = await client.shadowAgent.predict({
  inputFeatures: { taskType: 'validation' }
});
```

---

## Support

- **Documentation:** https://docs.murphy-system.com
- **API Status:** https://status.murphy-system.com
- **Support Email:** support@murphy-system.com
- **Community:** https://community.murphy-system.com