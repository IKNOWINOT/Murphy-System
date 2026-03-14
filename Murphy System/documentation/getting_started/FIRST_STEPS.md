# First Steps - Getting Started with Murphy System Runtime

**Your first steps after installation**

---

## Welcome!

Congratulations on installing the Murphy System Runtime! This guide will walk you through your first steps with the system, helping you get familiar with its capabilities and features.

---

## What You'll Learn

In this guide, you'll learn how to:

1. ✅ Start the system for the first time
2. ✅ Understand the system architecture
3. ✅ Build your first system
4. ✅ Generate your first expert team
5. ✅ Create your first safety gates
6. ✅ Analyze your first technical choice
7. ✅ Validate your first system design

---

## Step 1: Start the System

### Start the API Server

Open your terminal and navigate to the installation directory:

```bash
cd /path/to/murphy-system-runtime
```

Start the API server:

```bash
python murphy_system_1.0_runtime.py
```

You should see output like:

```
Starting Murphy System Runtime API Server...
Server running on http://localhost:8000
Press Ctrl+C to stop
```

### Verify the System is Running

Open a new terminal and test the health endpoint:

```bash
curl http://localhost:8000/api/health
```

You should see a response like:

```json
{
  "status": "healthy",
  "system_id": "murphy_system_20260117_100000",
  "timestamp": "2026-01-17T10:00:00"
}
```

🎉 **Congratulations! Your system is running!**

---

## Step 2: Understand the Architecture

### The Dual-Plane Architecture

The Murphy System Runtime uses a unique dual-plane architecture:

```
┌─────────────────────────────────────┐
│      CONTROL PLANE (Cloud)          │
│  - Reasoning and planning           │
│  - Expert generation                │
│  - Gate creation                    │
│  - Packet compilation               │
└─────────────────────────────────────┘
              │ Signed Packets Only
              ↓
┌─────────────────────────────────────┐
│     EXECUTION PLANE (Edge)          │
│  - Deterministic execution          │
│  - No generative inference          │
│  - Safety enforcement               │
└─────────────────────────────────────┘
```

### Key Concepts

1. **Control Plane**: Handles all reasoning and planning
2. **Execution Plane**: Executes actions using deterministic FSM only
3. **One-Way Communication**: Control Plane → Execution Plane only
4. **Signed Packets**: All execution packets are cryptographically signed
5. **Safety Gates**: 10+ gate types prevent unsafe actions

### Confidence Engine

The system computes confidence using:

```
Confidence(t) = w_g·G(x) + w_d·D(x) - κ·H(x)

Where:
- G(x) = Goodness score (positive factors)
- D(x) = Domain alignment score
- H(x) = Hazard score (negative factors)
```

This ensures the system only executes actions when confident.

---

## Step 3: Build Your First System

Let's build a simple web application together!

### Send a Build Request

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Build a simple web application for tracking workouts"
  }'
```

### What Happens Behind the Scenes

The system automatically:

1. **Analyzes Your Request** - Understands you want a workout tracking app
2. **Generates Experts** - Creates a team of experts (Frontend, Backend, Database)
3. **Creates Safety Gates** - Adds gates for security, performance, and user experience
4. **Adds Constraints** - Sets reasonable budget and timeline constraints
5. **Provides Recommendations** - Suggests technologies and architecture
6. **Validates Design** - Ensures the design meets safety and quality standards

### Review the Response

The response will include:

```json
{
  "request_id": "req_1",
  "success": true,
  "data": {
    "experts": [
      {
        "id": "exp_1",
        "name": "Frontend Engineer",
        "specialization": "React/TypeScript"
      },
      {
        "id": "exp_2",
        "name": "Backend Engineer",
        "specialization": "Python/FastAPI"
      },
      {
        "id": "exp_3",
        "name": "Database Expert",
        "specialization": "PostgreSQL"
      }
    ],
    "gates": [
      {
        "id": "gate_1",
        "name": "Security Gate",
        "type": "security"
      },
      {
        "id": "gate_2",
        "name": "Performance Gate",
        "type": "performance"
      }
    ],
    "recommendations": [
      "Use React for frontend",
      "Use FastAPI for backend",
      "Use PostgreSQL for database",
      "Implement JWT authentication",
      "Add rate limiting"
    ]
  },
  "message": "System built successfully",
  "warnings": [],
  "triggers": []
}
```

🎉 **You've built your first system!**

---

## Step 4: Generate Your First Expert Team

Let's create a specialized expert team for a more complex project.

### Generate Experts

```bash
curl -X POST http://localhost:8000/api/experts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Need experts for a healthcare application",
    "parameters": {
      "domain": "software",
      "complexity": "complex",
      "budget": 30000,
      "regulatory_requirements": ["hipaa"]
    }
  }'
```

### Review the Generated Experts

The system will generate specialized healthcare experts:

```json
{
  "data": {
    "experts": [
      {
        "id": "exp_1",
        "name": "Healthcare Frontend Specialist",
        "specialization": "React/Healthcare UI",
        "expertise_level": "senior",
        "regulatory_knowledge": ["HIPAA", "GDPR"]
      },
      {
        "id": "exp_2",
        "name": "Healthcare Backend Engineer",
        "specialization": "Python/FastAPI/Healthcare",
        "expertise_level": "senior",
        "regulatory_knowledge": ["HIPAA", "HL7", "FHIR"]
      },
      {
        "id": "exp_3",
        "name": "Healthcare Data Security Expert",
        "specialization": "Encryption/Audit Logging",
        "expertise_level": "senior",
        "regulatory_knowledge": ["HIPAA", "PCI DSS"]
      },
      {
        "id": "exp_4",
        "name": "Healthcare Compliance Specialist",
        "specialization": "Regulatory Compliance",
        "expertise_level": "expert",
        "regulatory_knowledge": ["HIPAA", "GDPR", "HITECH"]
      }
    ]
  }
}
```

### Key Observations

- Each expert has specialized knowledge for healthcare
- All experts include regulatory knowledge (HIPAA, GDPR)
- Expertise levels are appropriate for the complexity
- The team covers all aspects of healthcare application development

🎉 **You've generated your first expert team!**

---

## Step 5: Create Your First Safety Gates

Now let's create comprehensive safety gates for a financial system.

### Create Gates

```bash
curl -X POST http://localhost:8000/api/gates/create \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Create gates for a financial application",
    "parameters": {
      "domain": "software",
      "regulatory_requirements": ["pci_dss", "soc2"],
      "security_focus": true,
      "performance_requirements": ["response_time", "throughput"]
    }
  }'
```

### Review the Generated Gates

The system will create comprehensive gates:

```json
{
  "data": {
    "gates": [
      {
        "id": "gate_1",
        "name": "PCI DSS Compliance Gate",
        "type": "regulatory",
        "conditions": [
          "Encryption at rest enabled",
          "Encryption in transit enabled",
          "Secure key management",
          "Regular security audits"
        ],
        "severity": "critical"
      },
      {
        "id": "gate_2",
        "name": "SOC2 Compliance Gate",
        "type": "regulatory",
        "conditions": [
          "Access controls implemented",
          "Audit logging enabled",
          "Change management process",
          "Incident response plan"
        ],
        "severity": "critical"
      },
      {
        "id": "gate_3",
        "name": "Security Gate",
        "type": "security",
        "conditions": [
          "Vulnerability scanning completed",
          "Penetration testing passed",
          "Secure coding practices",
          "Dependency scanning"
        ],
        "severity": "high"
      },
      {
        "id": "gate_4",
        "name": "Performance Gate",
        "type": "performance",
        "conditions": [
          "Response time < 200ms",
          "Throughput > 1000 RPS",
          "99.9% uptime",
          "Scalability verified"
        ],
        "severity": "medium"
      }
    ]
  }
}
```

### Key Observations

- Gates cover regulatory, security, and performance aspects
- Severity levels are appropriate for each gate type
- Conditions are specific and measurable
- All gates are automatically enforced

🎉 **You've created your first safety gates!**

---

## Step 6: Analyze Your First Technical Choice

Let's analyze a common technical decision.

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
      "requirements": ["fast_prototyping", "large_ecosystem", "easy_hiring"]
    }
  }'
```

### Review the Analysis

The system will provide a comprehensive analysis:

```json
{
  "data": {
    "question": "Should I use React or Angular for my frontend?",
    "analysis": {
      "react": {
        "score": 8.5,
        "pros": [
          "Large ecosystem and community",
          "Fast development cycle",
          "Easy to hire developers",
          "Flexible component architecture"
        ],
        "cons": [
          "Requires additional libraries for routing/state",
          "Learning curve for JSX",
          "Toolchain complexity"
        ],
        "suitability": "high"
      },
      "angular": {
        "score": 7.0,
        "pros": [
          "Complete framework out of the box",
          "Built-in routing and state management",
          "Strong TypeScript support",
          "Enterprise-friendly"
        ],
        "cons": [
          "Steeper learning curve",
          "Less flexible",
          "Slower development cycle",
          "Smaller community"
        ],
        "suitability": "medium"
      }
    },
    "recommendation": {
      "choice": "React",
      "confidence": 0.85,
      "reasoning": "React better matches your requirements for fast prototyping, large ecosystem, and easy hiring within your budget and timeline constraints."
    }
  }
}
```

### Key Observations

- System scores each option based on your context
- Provides pros and cons for each option
- Makes a clear recommendation with confidence score
- Explains the reasoning behind the recommendation

🎉 **You've analyzed your first technical choice!**

---

## Step 7: Validate Your First System Design

Now let's validate a system design against all constraints and gates.

### Validate the System

```bash
curl -X POST http://localhost:8000/api/system/validate \
  -H "Content-Type: application/json" \
  -d '{
    "system_state": {
      "total_cost": 28000,
      "timeline": 110,
      "hipaa_aligned": true,
      "security_audit_passed": true,
      "performance_met": true
    }
  }'
```

### Review the Validation Results

The system will validate against all constraints and gates:

```json
{
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
            "limit": 30000,
            "message": "Within budget"
          },
          {
            "constraint": "Timeline",
            "status": "passed",
            "value": 110,
            "limit": 120,
            "message": "Within timeline"
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
              "Encryption in transit enabled",
              "Audit logging enabled"
            ]
          },
          {
            "gate": "Security Gate",
            "status": "passed",
            "conditions_met": [
              "Vulnerability scanning completed",
              "Security audit passed"
            ]
          }
        ]
      },
      "recommendations": [
        "System is ready for deployment",
        "All safety gates passed",
        "All constraints satisfied"
      ]
    }
  }
}
```

### Key Observations

- System validates against all constraints
- System validates against all gates
- Provides detailed results for each validation
- Makes clear recommendations

🎉 **You've validated your first system design!**

---

## What's Next?

Now that you've completed your first steps, you're ready to:

### 1. Explore More Features

- Try building more complex systems
- Experiment with different expert teams
- Create comprehensive gate sets
- Analyze more technical choices

### 2. Read More Documentation

- [User Guide](../user_guides/USER_GUIDE.md) - Complete user guide
- [API Documentation](../api/ENDPOINTS.md) - Full API reference
- [Architecture Guide](../architecture/ARCHITECTURE_OVERVIEW.md) - Detailed architecture

### 3. Try Example Workflows

- Complete system build workflow
- Expert team generation workflow
- Choice analysis workflow
- System validation workflow

### 4. Configure for Production

- [Deployment Guide](../deployment/DEPLOYMENT_GUIDE.md) - Production deployment
- [Configuration](../deployment/CONFIGURATION.md) - System configuration
- [Scaling](../deployment/SCALING.md) - Scaling strategies

### 5. Explore Enterprise Features

- [Enterprise Overview](../enterprise/ENTERPRISE_OVERVIEW.md) - Enterprise capabilities
- [Scaling Guide](../enterprise/SCALING_GUIDE.md) - Enterprise scaling
- [Performance](../enterprise/PERFORMANCE.md) - Performance characteristics

---

## Common Questions

### Q: How do I stop the API server?

Press `Ctrl+C` in the terminal where the server is running.

### Q: How do I change the port?

```bash
python murphy_system_1.0_runtime.py --port 8053
```

### Q: What if I see errors?

Check the [Troubleshooting Guide](../user_guides/TROUBLESHOOTING.md) for common issues and solutions.

### Q: How do I get help?

- Check the documentation
- Review the FAQ
- Contact support: corey.gfc@gmail.com

---

## Tips for Success

1. **Start Simple** - Begin with simple systems and gradually increase complexity
2. **Be Specific** - Provide clear, specific requirements for better results
3. **Validate Often** - Validate your system designs regularly
4. **Review Recommendations** - Always review system recommendations
5. **Check Triggers** - Check for triggers after complex operations

---

## Congratulations! 🎉

You've completed your first steps with the Murphy System Runtime! You now know how to:

- ✅ Start and verify the system
- ✅ Understand the dual-plane architecture
- ✅ Build complete systems
- ✅ Generate expert teams
- ✅ Create safety gates
- ✅ Analyze technical choices
- ✅ Validate system designs

You're ready to explore more advanced features and build complex autonomous systems!

---

**© 2025 Corey Post InonI LLC. All rights reserved.**  
**Licensed under BSL 1.1 (converts to Apache 2.0 after 4 years)**  
**Contact: corey.gfc@gmail.com**