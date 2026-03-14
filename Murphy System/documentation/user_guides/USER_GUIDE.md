# User Guide - Murphy System Runtime

**Comprehensive user guide for the Murphy System Runtime**

---

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Core Concepts](#core-concepts)
4. [Building Systems](#building-systems)
5. [Managing Experts](#managing-experts)
6. [Working with Gates](#working-with-gates)
7. [Using Constraints](#using-constraints)
8. [Analyzing Choices](#analyzing-choices)
9. [Chat Interface](#chat-interface)
10. [Best Practices](#best-practices)

---

## Introduction

The Murphy System Runtime is a fully functional autonomous AI system that helps you build, validate, and manage complex systems with provable safety guarantees.

### What Can You Do?

✅ **Build Complete Systems** - Generate complete system architectures with experts, gates, and constraints  
✅ **Generate Expert Teams** - Create specialized expert teams automatically  
✅ **Create Safety Gates** - Implement comprehensive safety gates  
✅ **Add Constraints** - Add and validate constraints  
✅ **Analyze Choices** - Analyze and recommend technical decisions  
✅ **Validate Systems** - Validate system designs against requirements  
✅ **Chat Interface** - Interactive chat for natural language interaction  

### Who Is This Guide For?

- **System Architects** - Designing complex systems
- **Technical Leads** - Managing technical decisions
- **Developers** - Building and validating systems
- **Compliance Officers** - Ensuring regulatory compliance
- **Project Managers** - Managing system development

---

## Getting Started

### Quick Start

1. **Start the API Server**:
   ```bash
   python murphy_system_1.0_runtime.py
   ```

2. **Test the System**:
   ```bash
   curl http://localhost:8000/api/health
   ```

3. **Build Your First System**:
   ```bash
   curl -X POST http://localhost:8000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Build a simple web application"}'
   ```

### Installation

See the [Installation Guide](../getting_started/INSTALLATION.md) for detailed installation instructions.

### Basic Concepts

Before using the system, understand these key concepts:

- **Experts**: Specialized AI personas with domain expertise
- **Gates**: Safety checks that prevent unsafe actions
- **Constraints**: Limits on system parameters (budget, timeline, etc.)
- **Confidence**: Measure of system certainty about decisions
- **Triggers**: Human-in-the-loop checkpoints

---

## Core Concepts

### The Dual-Plane Architecture

The system uses a dual-plane architecture:

```
Control Plane (Reasoning) → Execution Plane (Action)
        ↓                          ↓
    Generates                  Executes
    and Plans                 Deterministically
        ↓                          ↓
  Signed Packets ────────────→ Actions
```

**Key Points**:
- Reasoning and execution are physically separated
- Only signed packets can trigger actions
- No reverse channel from execution to reasoning
- Prevents AI from directly executing actions

### Confidence Engine

The system computes confidence using:

```
Confidence = Goodness + Domain - Hazard
```

- **Goodness**: Positive factors (evidence quality, expert consensus)
- **Domain**: Alignment with domain requirements
- **Hazard**: Negative factors (security risks, compliance issues)

### Safety Gates

Gates prevent unsafe actions:

- **Regulatory Gates**: Ensure compliance (HIPAA, PCI DSS, SOC2)
- **Security Gates**: Verify security measures
- **Performance Gates**: Check performance requirements
- **Quality Gates**: Validate quality standards

### Phases

The system operates in 7 phases:

1. **EXPAND** - Generate hypotheses
2. **TYPE** - Classify problems
3. **ENUMERATE** - Enumerate options
4. **CONSTRAIN** - Apply constraints
5. **COLLAPSE** - Select best options
6. **BIND** - Bind to execution
7. **EXECUTE** - Execute actions

---

## Building Systems

### Building a Simple System

Build a simple web application:

```bash
curl -X POST http://localhost:8000/api/system/build \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Build a simple web application",
    "requirements": {
      "domain": "software",
      "complexity": "simple"
    }
  }'
```

**What Happens**:
1. System analyzes your requirements
2. Generates appropriate experts
3. Creates safety gates
4. Adds constraints
5. Provides recommendations

### Building a Complex System

Build a complex healthcare application:

```bash
curl -X POST http://localhost:8000/api/system/build \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Build a healthcare application",
    "requirements": {
      "domain": "software",
      "complexity": "complex",
      "budget": 30000,
      "timeline": 180,
      "regulatory_requirements": ["hipaa"],
      "security_requirements": true
    }
  }'
```

**Key Requirements**:
- Specify domain (software, infrastructure, data)
- Set complexity level (simple, medium, complex, very_complex)
- Include budget and timeline if applicable
- List regulatory requirements
- Enable security focus if needed

### Understanding the Response

```json
{
  "success": true,
  "data": {
    "system_id": "system_1",
    "experts": [...],
    "gates": [...],
    "constraints": [...],
    "recommendations": [...]
  },
  "message": "System built successfully"
}
```

**Review**:
- **Experts**: Check if experts match your needs
- **Gates**: Verify gates cover all requirements
- **Constraints**: Ensure constraints are appropriate
- **Recommendations**: Review and implement recommendations

### Validating Your System

After building, validate your system:

```bash
curl -X POST http://localhost:8000/api/system/validate \
  -H "Content-Type: application/json" \
  -d '{
    "system_state": {
      "total_cost": 28000,
      "timeline": 160,
      "hipaa_aligned": true
    }
  }'
```

**Check Results**:
- Overall validation status
- Constraint validation results
- Gate validation results
- Any issues or warnings

---

## Managing Experts

### Generating Experts

Generate a team of experts:

```bash
curl -X POST http://localhost:8000/api/experts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Need experts for a fintech platform",
    "parameters": {
      "domain": "software",
      "complexity": "very_complex",
      "budget": 20000,
      "regulatory_requirements": ["pci_dss"]
    }
  }'
```

### Viewing Experts

Get all experts:

```bash
curl http://localhost:8000/api/experts
```

Get a specific expert:

```bash
curl http://localhost:8000/api/experts/exp_1
```

### Understanding Expert Specializations

Common expert types:

| Expert | Specialization | When to Use |
|--------|---------------|-------------|
| Frontend Engineer | UI/UX development | Web/mobile applications |
| Backend Engineer | Server-side logic | APIs, databases, services |
| Security Engineer | Security measures | Security-critical systems |
| Compliance Specialist | Regulatory compliance | Regulated industries |
| DevOps Engineer | Deployment and operations | Production systems |

### Customizing Expert Teams

Specify team size and specializations:

```bash
curl -X POST http://localhost:8000/api/experts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Need a specialized team",
    "parameters": {
      "domain": "software",
      "team_size": 6,
      "specializations": ["security", "performance", "compliance"]
    }
  }'
```

---

## Working with Gates

### Creating Gates

Create safety gates:

```bash
curl -X POST http://localhost:8000/api/gates/create \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Create gates for a financial application",
    "parameters": {
      "domain": "software",
      "regulatory_requirements": ["pci_dss", "soc2"],
      "security_focus": true
    }
  }'
```

### Gate Types

| Gate Type | Purpose | Example |
|-----------|---------|---------|
| Regulatory | Ensure compliance | HIPAA, PCI DSS, SOC2 |
| Security | Verify security measures | Encryption, authentication |
| Performance | Check performance | Response time, throughput |
| Quality | Validate quality | Code quality, testing |
| Budget | Verify budget constraints | Cost limits |
| Timeline | Verify timeline | Delivery dates |

### Viewing Gates

Get all gates:

```bash
curl http://localhost:8000/api/gates
```

Filter by type:

```bash
curl http://localhost:8000/api/gates?type=regulatory
```

### Evaluating Gates

Evaluate a specific gate:

```bash
curl -X POST http://localhost:8000/api/gates/gate_1/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "system_state": {
      "encryption_enabled": true,
      "audit_logging": true
    }
  }'
```

**Check Results**:
- Gate status (passed/failed)
- Conditions evaluated
- Which conditions passed/failed

---

## Using Constraints

### Adding Constraints

Add constraints to your system:

```bash
curl -X POST http://localhost:8000/api/constraints/add \
  -H "Content-Type: application/json" \
  -d '{
    "type": "budget",
    "value": 50000,
    "priority": 9,
    "justification": "Maximum budget allocation"
  }'
```

### Constraint Types

| Type | Description | Example |
|------|-------------|---------|
| Budget | Financial limits | $50,000 maximum |
| Timeline | Time limits | 180 days maximum |
| Scope | Feature scope | Core features only |
| Quality | Quality standards | 95% test coverage |
| Performance | Performance requirements | <200ms response time |

### Viewing Constraints

Get all constraints:

```bash
curl http://localhost:8000/api/constraints
```

### Validating Constraints

Validate constraints:

```bash
curl -X POST http://localhost:8000/api/constraints/constraint_1/validate \
  -H "Content-Type: application/json" \
  -d '{
    "system_state": {
      "current_value": 45000
    }
  }'
```

---

## Analyzing Choices

### Analyzing a Technical Choice

Analyze a decision:

```bash
curl -X POST http://localhost:8000/api/choices/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Should I use React or Angular for my frontend?",
    "type": "technical",
    "context": {
      "budget": 25000,
      "timeline": 120,
      "team_size": 5
    }
  }'
```

### Understanding Analysis Results

The system provides:

- **Scores**: Numerical scores for each option
- **Pros**: Advantages of each option
- **Cons**: Disadvantages of each option
- **Recommendation**: Which option to choose and why

### Comparing Multiple Options

Compare several options:

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

## Chat Interface

### Sending Messages

Use the chat interface for natural language interaction:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Build a healthcare app with HIPAA compliance"
  }'
```

### Maintaining Context

Use session IDs to maintain conversation context:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What about security?",
    "context": {
      "session_id": "session_1"
    }
  }'
```

### Getting Chat History

Retrieve conversation history:

```bash
curl "http://localhost:8000/api/chat/history?session_id=session_1"
```

---

## Best Practices

### 1. Be Specific with Requirements

**Good**: "Build a complex e-commerce platform with 1M users, $50K budget, PCI DSS compliance"

**Better than**: "Build a website"

### 2. Include All Constraints

Always mention:
- Budget (if applicable)
- Timeline (if applicable)
- Security requirements
- Regulatory compliance
- Scale (users, traffic)

### 3. Review Triggers

Always check for triggers after complex operations:

```bash
curl http://localhost:8000/api/triggers
```

### 4. Validate Before Deployment

Always validate your system before deployment:

```bash
curl -X POST http://localhost:8000/api/system/validate \
  -H "Content-Type: application/json" \
  -d '{"system_state": {...}}'
```

### 5. Monitor Performance

Regularly check system performance:

```bash
curl http://localhost:8000/api/telemetry/metrics
```

### 6. Review Recommendations

Always review system recommendations:

```bash
curl http://localhost:8000/api/recommendations
```

---

## Common Workflows

### Workflow 1: Complete System Build

1. Build system
2. Check for triggers
3. Validate system
4. Get report

### Workflow 2: Expert Team Generation

1. Generate team
2. Review experts
3. Add constraints
4. Validate constraints

### Workflow 3: Choice Analysis

1. Analyze choice
2. Review recommendations
3. Create gates based on choice
4. Validate gates

---

## Troubleshooting

### System Won't Start

**Problem**: API server won't start

**Solution**:
```bash
# Check if port is in use
lsof -i :8000

# Kill process using port
kill -9 <PID>

# Try different port
python murphy_system_1.0_runtime.py --port 8053
```

### No Experts Generated

**Problem**: Empty experts list

**Solution**: Ensure valid domain and complexity parameters

### Gates Always Fail

**Problem**: Gates always fail

**Solution**: Check that system state values match gate conditions

### Low Confidence Scores

**Problem**: Confidence scores consistently low

**Solution**: Review hazard factors and improve goodness/domain scores

---

## Next Steps

- [API Reference](API_REFERENCE.md) - Complete API reference
- [Command Reference](COMMAND_REFERENCE.md) - Command-line interface
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions

---

**© 2025 Corey Post InonI LLC. All rights reserved.**  
**Licensed under BSL 1.1 (converts to Apache 2.0 after 4 years)**  
**Contact: corey.gfc@gmail.com**