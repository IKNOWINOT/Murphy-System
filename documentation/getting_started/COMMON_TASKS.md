# Common Tasks - Quick Reference Guide

**Frequently used operations and commands**

---

## Table of Contents

1. [System Operations](#system-operations)
2. [Expert Management](#expert-management)
3. [Gate Management](#gate-management)
4. [Constraint Management](#constraint-management)
5. [System Validation](#system-validation)
6. [Choice Analysis](#choice-analysis)
7. [Reporting](#reporting)
8. [Monitoring](#monitoring)

---

## System Operations

### Start the API Server

```bash
# Default port (8000)
python murphy_system_1.0_runtime.py

# Custom port
python murphy_system_1.0_runtime.py --port 8053

# With logging
python murphy_system_1.0_runtime.py --log-level DEBUG
```

### Check System Health

```bash
curl http://localhost:8000/api/health
```

### Get System State

```bash
curl http://localhost:8000/api/system/state
```

### Get Full System Report

```bash
curl http://localhost:8000/api/system/report
```

### Build a Complete System

```bash
curl -X POST http://localhost:8000/api/system/build \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Build a web application",
    "requirements": {
      "domain": "software",
      "complexity": "medium",
      "budget": 10000,
      "timeline": 90
    }
  }'
```

### Validate a System

```bash
curl -X POST http://localhost:8000/api/system/validate \
  -H "Content-Type: application/json" \
  -d '{
    "system_state": {
      "total_cost": 9500,
      "security_compliant": true,
      "performance_met": true
    }
  }'
```

---

## Expert Management

### Generate Experts

```bash
curl -X POST http://localhost:8000/api/experts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Need experts for a fintech platform",
    "parameters": {
      "domain": "software",
      "complexity": "very_complex",
      "budget": 50000,
      "timeline": 180
    }
  }'
```

### Get All Experts

```bash
curl http://localhost:8000/api/experts
```

### Get Specific Expert

```bash
curl http://localhost:8000/api/experts/{expert_id}
```

### Update Expert

```bash
curl -X PUT http://localhost:8000/api/experts/{expert_id} \
  -H "Content-Type: application/json" \
  -d '{
    "specialization": "Updated specialization",
    "expertise_level": "senior"
  }'
```

### Delete Expert

```bash
curl -X DELETE http://localhost:8000/api/experts/{expert_id}
```

---

## Gate Management

### Create Gates

```bash
curl -X POST http://localhost:8000/api/gates/create \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Create gates for a healthcare app",
    "parameters": {
      "domain": "software",
      "regulatory_requirements": ["hipaa"],
      "security_focus": true,
      "performance_requirements": ["response_time", "throughput"]
    }
  }'
```

### Get All Gates

```bash
curl http://localhost:8000/api/gates
```

### Get Specific Gate

```bash
curl http://localhost:8000/api/gates/{gate_id}
```

### Evaluate Gate

```bash
curl -X POST http://localhost:8000/api/gates/{gate_id}/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "system_state": {
      "parameter": "value"
    }
  }'
```

### Delete Gate

```bash
curl -X DELETE http://localhost:8000/api/gates/{gate_id}
```

---

## Constraint Management

### Add Constraint

```bash
curl -X POST http://localhost:8000/api/constraints/add \
  -H "Content-Type: application/json" \
  -d '{
    "type": "budget",
    "value": 50000,
    "priority": 9,
    "justification": "Maximum budget allocation",
    "parameters": {
      "flexible": false
    }
  }'
```

### Get All Constraints

```bash
curl http://localhost:8000/api/constraints
```

### Get Specific Constraint

```bash
curl http://localhost:8000/api/constraints/{constraint_id}
```

### Validate Constraint

```bash
curl -X POST http://localhost:8000/api/constraints/{constraint_id}/validate \
  -H "Content-Type: application/json" \
  -d '{
    "system_state": {
      "current_value": 45000
    }
  }'
```

### Delete Constraint

```bash
curl -X DELETE http://localhost:8000/api/constraints/{constraint_id}
```

---

## System Validation

### Validate Against All Constraints

```bash
curl -X POST http://localhost:8000/api/constraints/validate \
  -H "Content-Type: application/json" \
  -d '{
    "system_state": {
      "total_cost": 45000,
      "timeline": 85,
      "security_compliant": true
    }
  }'
```

### Validate Against All Gates

```bash
curl -X POST http://localhost:8000/api/gates/validate \
  -H "Content-Type: application/json" \
  -d '{
    "system_state": {
      "parameter": "value"
    }
  }'
```

### Get Validation Results

```bash
curl http://localhost:8000/api/system/validation-results
```

---

## Choice Analysis

### Analyze a Choice

```bash
curl -X POST http://localhost:8000/api/choices/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Should I use React or Angular for my frontend?",
    "type": "technical",
    "context": {
      "budget": 25000,
      "timeline": 120,
      "team_size": 5,
      "requirements": ["fast_prototyping", "large_ecosystem"]
    }
  }'
```

### Get Analysis Results

```bash
curl http://localhost:8000/api/choices/{analysis_id}
```

### Compare Multiple Options

```bash
curl -X POST http://localhost:8000/api/choices/compare \
  -H "Content-Type: application/json" \
  -d '{
    "options": ["AWS", "GCP", "Azure"],
    "criteria": ["cost", "performance", "features"],
    "context": {
      "budget": 10000,
      "region": "us-east-1"
    }
  }'
```

---

## Reporting

### Get All Recommendations

```bash
curl http://localhost:8000/api/recommendations
```

### Get Recommendations by Category

```bash
curl http://localhost:8000/api/recommendations?category=architecture
```

### Get System Report

```bash
curl http://localhost:8000/api/system/report
```

### Get Performance Report

```bash
curl http://localhost:8000/api/system/performance-report
```

### Export Report

```bash
# Export as JSON
curl http://localhost:8000/api/system/report?format=json

# Export as PDF
curl http://localhost:8000/api/system/report?format=pdf

# Export as Markdown
curl http://localhost:8000/api/system/report?format=markdown
```

---

## Monitoring

### Get System Metrics

```bash
curl http://localhost:8000/api/telemetry/metrics
```

### Get Metrics by Type

```bash
curl http://localhost:8000/api/telemetry/metrics?type=performance
```

### Get Metrics by Time Range

```bash
curl http://localhost:8000/api/telemetry/metrics?start_time=2024-01-01&end_time=2024-12-31
```

### Get LLM Statistics

```bash
curl http://localhost:8000/api/llm/stats
```

### Get Active Sessions

```bash
curl http://localhost:8000/api/sessions
```

### Get Pending Triggers

```bash
curl http://localhost:8000/api/triggers
```

---

## Trigger Management

### Get All Triggers

```bash
curl http://localhost:8000/api/triggers
```

### Get Specific Trigger

```bash
curl http://localhost:8000/api/triggers/{trigger_id}
```

### Resolve a Trigger

```bash
curl -X POST http://localhost:8000/api/triggers/{trigger_id}/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "resolution": "Accept Aristotle",
    "notes": "Reasoning for resolution"
  }'
```

### Escalate Trigger

```bash
curl -X POST http://localhost:8000/api/triggers/{trigger_id}/escalate \
  -H "Content-Type: application/json" \
  -d '{
    "escalation_level": "high",
    "reason": "Requires urgent attention"
  }'
```

---

## Chat Interface

### Send Message to System

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Build a mobile app for fitness tracking",
    "context": {
      "session_id": "optional_session_id"
    }
  }'
```

### Get Chat History

```bash
curl http://localhost:8000/api/chat/history?session_id={session_id}
```

### Clear Chat History

```bash
curl -X DELETE http://localhost:8000/api/chat/history?session_id={session_id}
```

---

## Common Workflows

### Workflow 1: Build and Validate System

```bash
# 1. Build system
BUILD_RESPONSE=$(curl -s -X POST http://localhost:8000/api/system/build \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Build a healthcare app",
    "requirements": {
      "domain": "software",
      "complexity": "complex",
      "budget": 30000,
      "regulatory_requirements": ["hipaa"]
    }
  }')

echo "$BUILD_RESPONSE"

# 2. Check for triggers
curl -s http://localhost:8000/api/triggers

# 3. Validate system
curl -s -X POST http://localhost:8000/api/system/validate \
  -H "Content-Type: application/json" \
  -d '{
    "system_state": {
      "total_cost": 28000,
      "hipaa_aligned": true
    }
  }'

# 4. Get report
curl -s http://localhost:8000/api/system/report
```

### Workflow 2: Generate Experts and Add Constraints

```bash
# 1. Generate experts
curl -s -X POST http://localhost:8000/api/experts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Team for fintech platform",
    "parameters": {
      "domain": "software",
      "complexity": "very_complex",
      "budget": 20000
    }
  }' > experts.json

# 2. Extract expert IDs
EXPERT_IDS=$(jq -r '.data.experts[].id' experts.json)

# 3. Add budget constraint
curl -s -X POST http://localhost:8000/api/constraints/add \
  -H "Content-Type: application/json" \
  -d '{
    "type": "budget",
    "value": 20000,
    "priority": 9,
    "justification": "Fintech budget limit"
  }'

# 4. Add timeline constraint
curl -s -X POST http://localhost:8000/api/constraints/add \
  -H "Content-Type: application/json" \
  -d '{
    "type": "timeline",
    "value": 180,
    "priority": 8,
    "justification": "6 month delivery target"
  }'

# 5. Validate all constraints
curl -s -X POST http://localhost:8000/api/constraints/validate \
  -H "Content-Type: application/json" \
  -d '{
    "system_state": {
      "total_cost": 18000,
      "timeline": 160
    }
  }'
```

### Workflow 3: Analyze Choice and Create Gates

```bash
# 1. Analyze choice
curl -s -X POST http://localhost:8000/api/choices/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Use microservices or monolith?",
    "type": "architectural",
    "context": {
      "budget": 25000,
      "timeline": 180,
      "team_size": 5
    }
  }' > analysis.json

# 2. Extract recommendation
RECOMMENDATION=$(jq -r '.data.recommendation' analysis.json)
echo "Recommendation: $RECOMMENDATION"

# 3. Create gates based on choice
curl -s -X POST http://localhost:8000/api/gates/create \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Gates for microservices architecture",
    "parameters": {
      "architectural_requirements": ["microservices"],
      "performance_requirements": ["latency", "throughput"]
    }
  }'

# 4. Validate gates
curl -s -X POST http://localhost:8000/api/gates/validate \
  -H "Content-Type: application/json" \
  -d '{
    "system_state": {
      "latency_ms": 50,
      "throughput_rps": 1000
    }
  }'
```

### Workflow 4: Monitor System Performance

```bash
# 1. Get system health (shallow — fast liveness check)
curl -s http://localhost:8000/api/health

# 1b. Deep health — includes Ollama status and all subsystem checks
curl -s 'http://localhost:8000/api/health?deep=true' | python3 -m json.tool

# 2. Get performance metrics
curl -s http://localhost:8000/api/telemetry/metrics?type=performance

# 3. Get LLM statistics
curl -s http://localhost:8000/api/llm/stats

# 4. Get active sessions
curl -s http://localhost:8000/api/sessions

# 5. Check for pending triggers
curl -s http://localhost:8000/api/triggers
```

---

## Tips and Best Practices

### 1. Always Check Triggers After Complex Operations

```bash
# After any complex operation, check for triggers
curl http://localhost:8000/api/triggers
```

### 2. Use Specific Parameters for Better Results

```bash
# Good: Specific with constraints
curl -X POST http://localhost:8000/api/experts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Healthcare app team",
    "parameters": {
      "domain": "software",
      "complexity": "complex",
      "budget": 30000,
      "timeline": 180,
      "regulatory_requirements": ["hipaa"]
    }
  }'

# Better than: Generic request
```

### 3. Validate System Before Deployment

```bash
# Always validate before deploying to production
curl -X POST http://localhost:8000/api/system/validate \
  -H "Content-Type: application/json" \
  -d '{
    "system_state": {
      "all_parameters": "verified_values"
    }
  }'
```

### 4. Monitor Performance Regularly

```bash
# Regular performance monitoring
curl http://localhost:8000/api/telemetry/metrics?type=performance
```

### 5. Review Recommendations

```bash
# Get and review all recommendations
curl http://localhost:8000/api/recommendations
```

---

## Error Handling

### Handle API Errors

```bash
# Check response and handle errors
RESPONSE=$(curl -s http://localhost:8000/api/health)
SUCCESS=$(echo "$RESPONSE" | jq -r '.success')

if [ "$SUCCESS" = "true" ]; then
  echo "Operation successful"
else
  echo "Operation failed"
  echo "$RESPONSE" | jq -r '.message'
fi
```

### Retry Failed Requests

```bash
# Retry mechanism with exponential backoff
for i in {1..3}; do
  RESPONSE=$(curl -s -X POST http://localhost:8000/api/experts/generate \
    -H "Content-Type: application/json" \
    -d '{"description": "Test"}')
  
  SUCCESS=$(echo "$RESPONSE" | jq -r '.success')
  
  if [ "$SUCCESS" = "true" ]; then
    break
  else
    echo "Retry $i..."
    sleep $((2 ** i))
  fi
done
```

---

## Next Steps

- 📖 Read the [User Guide](../user_guides/USER_GUIDE.md)
- 🔧 Explore the [API Documentation](../api/ENDPOINTS.md)
- 🚀 Try the example workflows
- 📊 Review the [Deployment Guide](../deployment/DEPLOYMENT_GUIDE.md)

---

**© 2025 Corey Post InonI LLC. All rights reserved.**  
**Licensed under BSL 1.1 (converts to Apache 2.0 after 4 years)**  
**Contact: corey.gfc@gmail.com**