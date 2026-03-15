# Quick Start Guide - Murphy System Runtime

**Get up and running in 5 minutes**

---

## Prerequisites

Before you begin, ensure you have:

- **Python 3.10+** installed
- **4GB RAM** minimum (8GB recommended)
- **500MB disk space** available
- **Git** (optional, for cloning the repository)

---

## Step 1: Installation

### Option A: From Source

```bash
# Clone the repository (if using git)
git clone <repository-url>
cd murphy-system-runtime

# Install dependencies
pip install -r requirements_murphy_1.0.txt
```

### Option B: From Package

```bash
# Extract the package
unzip murphy_system_runtime.zip
cd murphy_system_runtime

# Install dependencies
pip install -r requirements_murphy_1.0.txt
```

### Dependencies Required

The system requires the following Python packages:

```
rich                  # Terminal UI
prompt-toolkit        # Interactive prompts
pyyaml                # Configuration files
networkx              # Graph operations
cryptography          # HMAC signing
numpy                 # Numerical operations
torch                 # PyTorch (optional, for advanced features)
transformers          # Transformers (optional, for advanced features)
sentencepiece         # Tokenization (optional, for advanced features)
```

---

## Step 2: Start the API Server

The API server provides the main interface to the system.

```bash
python murphy_system_1.0_runtime.py
```

The server will start on `http://localhost:8000`

**Expected Output:**
```
Starting Murphy System Runtime API Server...
Server running on http://localhost:8000
Press Ctrl+C to stop
```

---

## Step 3: Test the System

Open a new terminal and test the health endpoint:

```bash
curl http://localhost:8000/api/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "system_id": "murphy_system_20260117_100000",
  "timestamp": "2026-01-17T10:00:00"
}
```

---

## Step 4: Build Your First System

Use the chat API to build a system:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Build a simple web application for tracking workouts"
  }'
```

**What Happens Automatically:**

1. ✅ Generates a team of experts
2. ✅ Creates safety gates
3. ✅ Adds constraints
4. ✅ Provides recommendations
5. ✅ Validates the design

---

## Step 5: Explore the Features

### Generate Experts

```bash
curl -X POST http://localhost:8000/api/experts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Need experts for a mobile app",
    "parameters": {
      "domain": "software",
      "budget": 8000
    }
  }'
```

### Create Safety Gates

```bash
curl -X POST http://localhost:8000/api/gates/create \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Create gates for a financial system",
    "parameters": {
      "domain": "software",
      "regulatory_requirements": ["pci_dss"],
      "security_focus": true
    }
  }'
```

### Analyze a Choice

```bash
curl -X POST http://localhost:8000/api/choices/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Should I use React or Angular for my frontend?",
    "type": "technical"
  }'
```

---

## Common Use Cases

### 1. Building a New System

**Input:** "I need to build a complex e-commerce platform with millions of users"

**System Automatically:**
- Generates 4-6 experts (Architect, Frontend, Backend, Security, DevOps)
- Creates 8-12 safety gates (GDPR, PCI DSS, security, performance)
- Adds budget and timeline constraints
- Provides architectural recommendations
- Validates design against best practices

### 2. Generating Expert Teams

**Input:** "Need a team for a healthcare application"

**System Automatically:**
- Creates specialized healthcare experts
- Includes regulatory compliance experts
- Sets up security gates (HIPAA compliance)
- Configures privacy constraints
- Provides implementation guidance

### 3. Adding Safety Gates

**Input:** "Create gates for a banking application"

**System Automatically:**
- Generates regulatory gates (PCI DSS, SOC2)
- Creates security gates (vulnerability scanning, penetration testing)
- Adds performance gates (response time, throughput)
- Sets up compliance gates (audit logging, encryption)
- Wires all gates to validation functions

### 4. Analyzing Technical Choices

**Input:** "Which cloud provider should I use for my startup?"

**System Automatically:**
- Evaluates AWS, GCP, Azure options
- Provides cost analysis
- Considers technical requirements
- Factors in budget constraints
- Recommends best option with confidence score

### 5. Validating System Design

**Input:** "Validate my system design"

**System Automatically:**
- Checks all constraints
- Validates all gates
- Runs math/physics validation through Aristotle
- Cross-validates with Wulfrum
- Triggers human review if disagreements found

---

## Understanding the Response

Every API response includes:

```json
{
  "request_id": "req_1",
  "success": true,
  "data": {
    "experts": [...],
    "gates": [...],
    "recommendations": [...]
  },
  "message": "System built successfully",
  "warnings": [],
  "triggers": [],
  "timestamp": "2026-01-17T10:00:00"
}
```

### Key Fields

- **request_id**: Unique identifier for tracking
- **success**: Whether the request succeeded
- **data**: The main response data (experts, gates, etc.)
- **message**: Human-readable message
- **warnings**: Any warnings (non-critical issues)
- **triggers**: Human-in-the-loop triggers requiring review
- **timestamp**: When the response was generated

---

## Handling Triggers

When Aristotle and Wulfrum disagree on math/physics validation, a trigger is created:

```json
{
  "trigger_id": "trigger_1",
  "request_id": "req_1",
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
```

### Resolving a Trigger

```bash
curl -X POST http://localhost:8000/api/triggers/trigger_1/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "resolution": "Accept Aristotle"
  }'
```

---

## Tips for Best Results

### 1. Be Specific with Requirements

**Good:** "Build a complex e-commerce platform with 1M users, $50K budget, PCI DSS compliance"

**Better than:** "Build a website"

### 2. Include Constraints

Always mention:
- Budget (if applicable)
- Timeline (if applicable)
- Security requirements
- Regulatory compliance (GDPR, HIPAA, PCI DSS)
- Scale (number of users, traffic)

### 3. Specify Domain

Let the system know what type of system:
- Software (web apps, mobile apps)
- Infrastructure (cloud, networks)
- Data (analytics, ML)

### 4. Check for Triggers

Always check for pending triggers after complex operations:

```bash
curl http://localhost:8000/api/triggers
```

### 5. Review Recommendations

Get all recommendations and review them:

```bash
curl http://localhost:8000/api/recommendations
```

---

## Example Workflows

### Workflow 1: Complete System Build

```bash
# 1. Build system
curl -X POST http://localhost:8000/api/system/build \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Build a healthcare app",
    "requirements": {
      "domain": "software",
      "complexity": "complex",
      "budget": 30000,
      "regulatory_requirements": ["hipaa"]
    }
  }'

# 2. Check for triggers
curl http://localhost:8000/api/triggers

# 3. Validate system
curl -X POST http://localhost:8000/api/system/validate \
  -H "Content-Type: application/json" \
  -d '{
    "system_state": {
      "total_cost": 28000,
      "hipaa_aligned": true
    }
  }'

# 4. Get report
curl http://localhost:8000/api/system/report
```

### Workflow 2: Expert Team Generation

```bash
# 1. Generate team
curl -X POST http://localhost:8000/api/experts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Team for fintech platform",
    "parameters": {
      "domain": "software",
      "complexity": "very_complex",
      "budget": 20000
    }
  }'

# 2. Get all experts
curl http://localhost:8000/api/experts

# 3. Add constraints
curl -X POST http://localhost:8000/api/constraints/add \
  -H "Content-Type: application/json" \
  -d '{
    "type": "budget",
    "value": 20000,
    "priority": 9,
    "justification": "Fintech budget limit"
  }'
```

### Workflow 3: Choice Analysis

```bash
# 1. Analyze choice
curl -X POST http://localhost:8000/api/choices/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Use microservices or monolith?",
    "type": "architectural",
    "context": {
      "budget": 25000,
      "timeline": 180,
      "team_size": 5
    }
  }'

# 2. Get recommendations
curl http://localhost:8000/api/recommendations

# 3. Create gates based on choice
curl -X POST http://localhost:8000/api/gates/create \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Gates for microservices architecture",
    "parameters": {
      "architectural_requirements": ["microservices"]
    }
  }'
```

---

## Troubleshooting

### Server Won't Start

**Problem**: Port 8000 already in use

**Solution:**
```bash
# Find process using port
lsof -i :8000

# Kill the process
kill -9 <PID>
```

### API Returns Errors

**Problem**: 500 Internal Server Error

**Solution**: Check the server logs for detailed error messages

### No Experts Generated

**Problem**: Empty experts list

**Solution**: Ensure you provide valid domain and complexity parameters

### Gates Not Working

**Problem**: Gates always fail

**Solution**: Check that system state values match gate conditions

---

## Next Steps

1. 📖 Read the [Complete User Guide](../user_guides/USER_GUIDE.md)
2. 🔧 Explore the [API Documentation](../api/ENDPOINTS.md)
3. 🚀 Test with your own requirements
4. 💻 Integrate with your frontend application
5. 🌐 Configure production deployment

---

## Support

For issues or questions:
- Check the system logs
- Review the complete documentation
- Test with the example workflows
- Validate your API requests

---

## Summary

The Murphy System Runtime is designed to be:

- **Simple**: Just send natural language requests
- **Automatic**: Generates experts, gates, constraints automatically
- **Safe**: Built-in validation with human-in-the-loop triggers
- **Standards-compliant**: Uses stringent legal and regulatory standards
- **Intelligent**: LLM-powered reasoning and recommendations

**Start building your systems today!**

---

**© 2025 Corey Post InonI LLC. All rights reserved.**  
**Licensed under BSL 1.1 (converts to Apache 2.0 after 4 years)**  
**Contact: corey.gfc@gmail.com**