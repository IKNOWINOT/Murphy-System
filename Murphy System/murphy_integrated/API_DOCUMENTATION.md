# Murphy System - Complete API Documentation

## Base URL
```
http://localhost:6666/api
```

## Authentication
Currently, no authentication is required. In production, implement appropriate authentication mechanisms.

---

## Form Endpoints

### 1. Upload Plan
Upload a pre-existing plan for execution.

**Endpoint:** `POST /api/forms/plan-upload`

**Request Body:**
```json
{
  "plan_name": "string",
  "plan_data": {
    "tasks": [...],
    "dependencies": [...]
  },
  "format": "json|yaml|markdown"
}
```

**Response:**
```json
{
  "success": true,
  "submission_id": "sub_12345",
  "plan_id": "plan_67890",
  "tasks_count": 5,
  "timestamp": "2024-01-01T12:00:00"
}
```

**Status Codes:**
- `200` - Success
- `400` - Invalid request data
- `500` - Server error

---

### 2. Generate Plan
Generate a plan from natural language description.

**Endpoint:** `POST /api/forms/plan-generation`

**Request Body:**
```json
{
  "description": "string",
  "domain": "string",
  "constraints": ["constraint1", "constraint2"],
  "preferences": {
    "priority": "speed|quality",
    "max_tasks": 10
  }
}
```

**Response:**
```json
{
  "success": true,
  "submission_id": "sub_12345",
  "plan_id": "plan_67890",
  "generated_plan": {
    "tasks": [...],
    "dependencies": [...]
  },
  "tasks_count": 5,
  "timestamp": "2024-01-01T12:00:00"
}
```

**Status Codes:**
- `200` - Success
- `400` - Invalid request data
- `500` - Server error

---

### 3. Execute Task
Execute a task with Murphy validation.

**Endpoint:** `POST /api/forms/task-execution`

**Request Body:**
```json
{
  "task_type": "general|data_processing|analysis|generation",
  "description": "string",
  "parameters": {
    "key": "value"
  },
  "constraints": ["constraint1"],
  "validation_required": true
}
```

**Response (Success):**
```json
{
  "success": true,
  "task_id": "task_12345",
  "status": "COMPLETED",
  "output": {
    "result": "..."
  },
  "confidence_report": {
    "combined_confidence": 0.85,
    "uncertainty_scores": {
      "UD": 0.1,
      "UA": 0.15,
      "UI": 0.05,
      "UR": 0.1,
      "UG": 0.05,
      "total": 0.45
    }
  },
  "timestamp": "2024-01-01T12:00:00"
}
```

**Response (Rejected):**
```json
{
  "success": false,
  "status": "rejected",
  "reason": "Confidence too low (0.45 < 0.60)",
  "confidence_report": {
    "combined_confidence": 0.45,
    "uncertainty_scores": {...},
    "gate_result": {
      "approved": false,
      "reason": "High uncertainty in data and resources"
    }
  }
}
```

**Status Codes:**
- `200` - Success
- `403` - Task rejected by Murphy Gate
- `400` - Invalid request data
- `500` - Server error

---

### 4. Validate Task
Validate a task without executing it.

**Endpoint:** `POST /api/forms/validation`

**Request Body:**
```json
{
  "task_data": {
    "task_type": "general",
    "description": "string",
    "parameters": {}
  },
  "validation_criteria": ["criterion1"]
}
```

**Response:**
```json
{
  "success": true,
  "approved": true,
  "confidence": 0.85,
  "gdh_confidence": 0.80,
  "uncertainty_scores": {
    "UD": 0.1,
    "UA": 0.15,
    "UI": 0.05,
    "UR": 0.1,
    "UG": 0.05,
    "total": 0.45
  },
  "gate_result": {
    "approved": true,
    "reason": "All validation criteria met",
    "recommendations": ["Monitor execution closely"]
  },
  "timestamp": "2024-01-01T12:00:00"
}
```

**Status Codes:**
- `200` - Success
- `400` - Invalid request data
- `500` - Server error

---

### 5. Submit Correction
Submit a correction for a completed task.

**Endpoint:** `POST /api/forms/correction`

**Request Body:**
```json
{
  "task_id": "task_12345",
  "correction_type": "output_error|parameter_adjustment|logic_correction|validation_override",
  "original_output": "string or object",
  "corrected_output": "string or object",
  "explanation": "string",
  "severity": "low|medium|high|critical"
}
```

**Response:**
```json
{
  "success": true,
  "correction_id": "corr_67890",
  "task_id": "task_12345",
  "patterns_extracted": 3,
  "timestamp": "2024-01-01T12:00:00"
}
```

**Status Codes:**
- `200` - Success
- `400` - Invalid request data
- `500` - Server error

---

### 6. Get Submission Status
Get the status of a form submission.

**Endpoint:** `GET /api/forms/submission/{submission_id}`

**Response:**
```json
{
  "success": true,
  "submission": {
    "id": "sub_12345",
    "type": "task_execution",
    "status": "completed|pending|failed",
    "created_at": "2024-01-01T12:00:00",
    "completed_at": "2024-01-01T12:05:00",
    "result": {...}
  }
}
```

**Status Codes:**
- `200` - Success
- `404` - Submission not found
- `500` - Server error

---

## Correction Endpoints

### 7. Get Correction Patterns
Get extracted correction patterns.

**Endpoint:** `GET /api/corrections/patterns`

**Query Parameters:**
- `task_type` (optional) - Filter by task type
- `min_frequency` (optional, default: 2) - Minimum pattern frequency

**Response:**
```json
{
  "success": true,
  "patterns": [
    {
      "pattern_id": "pat_12345",
      "pattern_type": "frequent_correction",
      "description": "Common parameter adjustment",
      "frequency": 15,
      "confidence": 0.85,
      "examples": [...]
    }
  ],
  "count": 10
}
```

**Status Codes:**
- `200` - Success
- `500` - Server error

---

### 8. Get Correction Statistics
Get correction system statistics.

**Endpoint:** `GET /api/corrections/statistics`

**Response:**
```json
{
  "success": true,
  "statistics": {
    "total_corrections": 150,
    "total_patterns": 25,
    "corrections_by_type": {
      "output_error": 80,
      "parameter_adjustment": 40,
      "logic_correction": 20,
      "validation_override": 10
    },
    "corrections_by_severity": {
      "low": 50,
      "medium": 70,
      "high": 25,
      "critical": 5
    },
    "patterns_by_type": {
      "frequent_correction": 10,
      "common_error": 8,
      "systematic_issue": 7
    },
    "has_learning_system": true
  }
}
```

**Status Codes:**
- `200` - Success
- `500` - Server error

---

### 9. Get Training Data
Get training data for shadow agent.

**Endpoint:** `GET /api/corrections/training-data`

**Query Parameters:**
- `task_type` (optional) - Filter by task type
- `limit` (optional) - Maximum number of examples

**Response:**
```json
{
  "success": true,
  "training_data": [
    {
      "task_id": "task_12345",
      "original_output": "...",
      "corrected_output": "...",
      "correction_type": "output_error",
      "metadata": {...},
      "timestamp": "2024-01-01T12:00:00"
    }
  ],
  "count": 50
}
```

**Status Codes:**
- `200` - Success
- `500` - Server error

---

## HITL (Human-in-the-Loop) Endpoints

### 10. Get Pending Interventions
Get all pending intervention requests.

**Endpoint:** `GET /api/hitl/interventions/pending`

**Response:**
```json
{
  "success": true,
  "interventions": [
    {
      "request_id": "int_12345",
      "task_id": "task_67890",
      "intervention_type": "approval_required",
      "urgency": "high",
      "reason": "High-risk operation detected",
      "created_at": "2024-01-01T12:00:00",
      "status": "pending"
    }
  ],
  "count": 5
}
```

**Status Codes:**
- `200` - Success
- `500` - Server error

---

### 11. Respond to Intervention
Respond to an intervention request.

**Endpoint:** `POST /api/hitl/interventions/{request_id}/respond`

**Request Body:**
```json
{
  "decision": "approve|reject|modify",
  "comments": "string",
  "modifications": {
    "parameter": "new_value"
  }
}
```

**Response:**
```json
{
  "success": true,
  "response": {
    "request_id": "int_12345",
    "decision": "approve",
    "responded_by": "user_id",
    "responded_at": "2024-01-01T12:05:00",
    "comments": "Approved after review"
  }
}
```

**Status Codes:**
- `200` - Success
- `404` - Intervention not found
- `400` - Invalid request data
- `500` - Server error

---

### 12. Get HITL Statistics
Get HITL checkpoint statistics.

**Endpoint:** `GET /api/hitl/statistics`

**Response:**
```json
{
  "success": true,
  "statistics": {
    "total_interventions": 100,
    "pending_interventions": 5,
    "approved": 80,
    "rejected": 15,
    "average_response_time": "5m 30s",
    "by_type": {
      "approval_required": 60,
      "review_requested": 30,
      "clarification_needed": 10
    },
    "supervisor": {
      "total_supervisions": 500,
      "interventions_triggered": 100
    }
  }
}
```

**Status Codes:**
- `200` - Success
- `500` - Server error

---

## System Endpoints

### 13. Get System Info
Get integrated system information.

**Endpoint:** `GET /api/system/info`

**Response:**
```json
{
  "success": true,
  "system": {
    "name": "Murphy System - Integrated",
    "version": "2.0.0",
    "components": {
      "murphy_runtime": true,
      "domain_engine": true,
      "form_intake": true,
      "murphy_validation": true,
      "correction_capture": true,
      "shadow_agent": true,
      "hitl_monitor": true
    },
    "endpoints": {
      "original": "All original endpoints preserved",
      "forms": "/api/forms/*",
      "corrections": "/api/corrections/*",
      "hitl": "/api/hitl/*",
      "system": "/api/system/*"
    }
  }
}
```

**Status Codes:**
- `200` - Success

---

## Error Responses

All endpoints may return error responses in the following format:

```json
{
  "success": false,
  "error": "Error message describing what went wrong",
  "details": {
    "field": "Additional error details"
  }
}
```

**Common Error Codes:**
- `400` - Bad Request (invalid input)
- `403` - Forbidden (rejected by Murphy Gate)
- `404` - Not Found
- `500` - Internal Server Error

---

## Rate Limiting

Currently, no rate limiting is implemented. In production, consider implementing:
- Rate limiting per IP/user
- Request throttling
- Queue management for long-running tasks

---

## Webhooks (Future)

Future versions may support webhooks for:
- Task completion notifications
- Intervention requests
- Pattern detection alerts
- System health updates

---

## SDK Examples

### Python
```python
import requests

API_BASE = "http://localhost:6666/api"

# Execute a task
response = requests.post(
    f"{API_BASE}/forms/task-execution",
    json={
        "task_type": "analysis",
        "description": "Analyze sales data",
        "parameters": {"quarter": "Q4"}
    }
)

result = response.json()
print(f"Task ID: {result['task_id']}")
print(f"Confidence: {result['confidence_report']['combined_confidence']}")
```

### JavaScript
```javascript
const API_BASE = 'http://localhost:6666/api';

// Execute a task
async function executeTask() {
  const response = await fetch(`${API_BASE}/forms/task-execution`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      task_type: 'analysis',
      description: 'Analyze sales data',
      parameters: { quarter: 'Q4' }
    })
  });
  
  const result = await response.json();
  console.log('Task ID:', result.task_id);
  console.log('Confidence:', result.confidence_report.combined_confidence);
}
```

### cURL
```bash
# Execute a task
curl -X POST http://localhost:6666/api/forms/task-execution \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "analysis",
    "description": "Analyze sales data",
    "parameters": {"quarter": "Q4"}
  }'
```

---

## Best Practices

1. **Always validate tasks** before execution in production
2. **Monitor confidence scores** - reject tasks with confidence < 0.60
3. **Submit corrections** to improve system learning
4. **Handle interventions promptly** to avoid blocking
5. **Use appropriate task types** for better validation
6. **Provide detailed descriptions** for better results
7. **Check system info** to verify component availability

---

## Support

For API issues or questions:
- Check the START_INTEGRATED_SYSTEM.md guide
- Review integration documentation
- Test with the provided UI at murphy_ui_integrated.html