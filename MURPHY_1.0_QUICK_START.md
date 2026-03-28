# Murphy System 1.0 - Quick Start Guide

**Version:** 1.0.0  
**Date:** February 3, 2025  
**Owner:** Inoni Limited Liability Company  
**Creator:** Corey Post  
**License:** BSL 1.1 (converts to Apache 2.0 after 4 years)

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Install Python 3.10+
```bash
# Check Python version
python3 --version  # Should be 3.10 or higher
```

### Step 2: Start Murphy
```bash
# Linux/Mac
bash setup_and_start.sh

# Windows
setup_and_start.bat
```

> **No API key required.** `setup_and_start.sh` auto-generates your `.env`
> with the onboard LLM (`MURPHY_LLM_PROVIDER=local`), installs all
> dependencies, and launches the server.

### Step 3: Access Murphy
- **API Documentation:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/health
- **System Status:** http://localhost:8000/api/status
- **System Info:** http://localhost:8000/api/info

---

## 📖 What is Murphy System 1.0?

Murphy is a **Universal AI Automation System** that can:
- ✅ Automate **any business type** (factory, content, data, system, agent, business)
- ✅ **Self-integrate** (GitHub repositories, APIs, hardware)
- ✅ **Self-improve** (learns from corrections)
- ✅ **Self-operate** (runs Inoni LLC operations with autonomous execution and human-in-the-loop safety gates)
- ✅ Maintain **safety** (human-in-the-loop approval)

---

## 🎯 Core Capabilities

### 1. Universal Automation
```python
# Execute any task
POST /api/execute
{
    "task_description": "Automate HVAC system in factory",
    "task_type": "automation"
}
```

**Supported Automation Types:**
- **Factory/IoT:** Sensors, actuators, HVAC, robotics
- **Content:** Blog posts, social media, documentation
- **Data:** Databases, analytics, processing
- **System:** Commands, DevOps, infrastructure
- **Agent:** Swarms, complex tasks, reasoning
- **Business:** Sales, marketing, finance, support

### 2. Self-Integration
```python
# Add GitHub repository integration
POST /api/integrations/add
{
    "source": "https://github.com/stripe/stripe-python",
    "category": "payment-processing"
}

# Murphy will:
# 1. Clone and analyze repository
# 2. Extract capabilities
# 3. Generate module/agent
# 4. Test for safety
# 5. Ask for approval (HITL)
# 6. Load if approved
```

### 3. Self-Improvement
```python
# Submit correction
POST /api/corrections/submit
{
    "task_id": "abc123",
    "correction_type": "output_error",
    "correction": "The correct output should be..."
}

# Murphy will:
# 1. Capture correction
# 2. Extract patterns
# 3. Train shadow agent
# 4. Improve future performance
```

### 4. Self-Operation (Inoni Business Automation)
```python
# Run business automation
POST /api/automation/sales/generate_leads
{
    "parameters": {
        "target_industry": "SaaS",
        "company_size": "10-50"
    }
}

# Available engines:
# - sales: Lead generation, qualification, outreach
# - marketing: Content creation, social media, SEO
# - rd: Bug detection, code fixes, deployment (Murphy fixes Murphy!)
# - business: Finance, support, project management
# - production: Releases, QA, deployment, monitoring
```

---

## 📊 API Endpoints

### Core Endpoints
```
POST   /api/execute                    # Execute task
GET    /api/status                     # System status
GET    /api/info                       # System information
GET    /api/health                     # Health check
```

### Integration Endpoints
```
POST   /api/integrations/add           # Add integration
POST   /api/integrations/{id}/approve  # Approve integration
POST   /api/integrations/{id}/reject   # Reject integration
GET    /api/integrations/{status}      # List integrations
```

### Business Automation Endpoints
```
POST   /api/automation/{engine}/{action}  # Run automation
```

### System Endpoints
```
GET    /api/modules                    # List modules
```

### No-Code Workflow Builder Endpoints
```
POST   /api/workflow-terminal/sessions              # Create Librarian session
POST   /api/workflow-terminal/sessions/{id}/message  # Send message to Librarian
GET    /api/workflow-terminal/sessions/{id}          # Get session details
GET    /api/workflow-terminal/sessions/{id}/compile  # Compile workflow
GET    /api/workflow-terminal/sessions/{id}/agents/{aid} # Agent drill-down
```

### Onboarding & Org Chart Endpoints
```
POST   /api/onboarding-flow/org/initialize          # Initialize org chart
GET    /api/onboarding-flow/org/chart               # View org chart
POST   /api/onboarding-flow/start                   # Start onboarding
GET    /api/onboarding-flow/sessions/{id}/questions  # Get questions
POST   /api/onboarding-flow/sessions/{id}/answer     # Answer question
POST   /api/onboarding-flow/sessions/{id}/shadow-agent # Assign shadow agent
POST   /api/onboarding-flow/sessions/{id}/transition # Transition to builder
```

### IP Classification & Credential Endpoints
```
POST   /api/ip/assets                               # Register IP asset
GET    /api/ip/summary                              # IP summary
GET    /api/ip/trade-secrets                        # List trade secrets
POST   /api/credentials/profiles                    # Create credential profile
GET    /api/credentials/metrics                     # Optimal automation metrics
GET    /api/agent-dashboard/snapshot                # Agent dashboard
```

---

## 🔧 Configuration

### Environment Variables (.env file)
```bash
# Core Configuration (auto-generated by setup_and_start.sh)
MURPHY_VERSION=1.0.0
MURPHY_ENV=development
MURPHY_PORT=8000

# LLM — defaults to onboard LLM (no key required)
# Add an external key below for enhanced quality (optional)
# MURPHY_LLM_PROVIDER=deepinfra
# DEEPINFRA_API_KEY=your_deepinfra_key
# OPENAI_API_KEY=your_openai_key

# Integration Keys
GITHUB_TOKEN=your_github_token
STRIPE_API_KEY=your_stripe_key
PAYPAL_CLIENT_ID=your_paypal_id
PAYPAL_CLIENT_SECRET=your_paypal_secret

# Security
JWT_SECRET=your_jwt_secret
ENCRYPTION_KEY=your_encryption_key
```

---

## 🎯 Example Use Cases

### Use Case 1: Automate Factory HVAC
```bash
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Monitor temperature sensors and adjust HVAC to maintain 72°F",
    "task_type": "automation"
  }'
```

### Use Case 2: Add Stripe Integration
```bash
curl -X POST http://localhost:8000/api/integrations/add \
  -H "Content-Type: application/json" \
  -d '{
    "source": "https://github.com/stripe/stripe-python",
    "category": "payment-processing"
  }'

# Murphy will analyze and ask for approval
# Then approve with:
curl -X POST http://localhost:8000/api/integrations/{request_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approved_by": "admin"}'
```

### Use Case 3: Generate Sales Leads
```bash
curl -X POST http://localhost:8000/api/automation/sales/generate_leads \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "target_industry": "SaaS",
      "company_size": "10-50",
      "location": "USA"
    }
  }'
```

### Use Case 4: Create Blog Post
```bash
curl -X POST http://localhost:8000/api/automation/marketing/create_content \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "content_type": "blog_post",
      "topic": "AI Automation Benefits",
      "length": "1500 words"
    }
  }'
```

### Use Case 5: No-Code Workflow Builder (NEW)
```bash
# 1. Create a Librarian session
curl -X POST http://localhost:8000/api/workflow-terminal/sessions

# 2. Describe what you want to automate
curl -X POST http://localhost:8000/api/workflow-terminal/sessions/{session_id}/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Monitor API endpoints and send Slack alerts on failures"}'

# 3. Finalize the workflow
curl -X POST http://localhost:8000/api/workflow-terminal/sessions/{session_id}/message \
  -H "Content-Type: application/json" \
  -d '{"message": "finalize"}'
```

### Use Case 6: Complete Onboarding → Builder Flow (NEW)
```bash
# 1. Initialize org chart
curl -X POST http://localhost:8000/api/onboarding-flow/org/initialize

# 2. Start onboarding for a new employee
curl -X POST http://localhost:8000/api/onboarding-flow/start \
  -H "Content-Type: application/json" \
  -d '{"name": "Alex Smith", "email": "alex@company.com"}'

# 3. Assign shadow agent (becomes Employee IP; position_id is optional)
curl -X POST http://localhost:8000/api/onboarding-flow/sessions/{id}/shadow-agent \
  -H "Content-Type: application/json" -d '{}'

# 4. Transition to no-code builder
curl -X POST http://localhost:8000/api/onboarding-flow/sessions/{id}/transition
```

---

## 🛡️ Safety Features

### Human-in-the-Loop (HITL)
- **Every integration requires approval**
- **LLM-powered risk analysis**
- **Clear recommendations**
- **No automatic commits**

### Murphy Validation
- **G/D/H Formula:** Goodness, Domain, Hazard scoring
- **5D Uncertainty:** UD, UA, UI, UR, UG calculations
- **Murphy Gate:** Threshold-based validation
- **Safety Score:** 0.0-1.0 scoring

### Governance
- **Authority-based scheduling**
- **Permission levels** (LOW, MEDIUM, HIGH, CRITICAL)
- **Audit trails**
- **Compliance ready** (GDPR, SOC 2, HIPAA, PCI DSS)

---

## 📈 Monitoring

### System Status
```bash
curl http://localhost:8000/api/status
```

**Returns:**
```json
{
  "version": "1.0.0",
  "status": "running",
  "uptime_seconds": 3600,
  "components": {
    "control_plane": "active",
    "inoni_automation": "active",
    "integration_engine": "active"
  },
  "statistics": {
    "sessions": 10,
    "pending_integrations": 2,
    "committed_integrations": 15
  }
}
```

### Health Check
```bash
curl http://localhost:8000/api/health
```

---

## 🐛 Troubleshooting

### Issue: Port already in use
```bash
# Change port in .env
MURPHY_PORT=7777

# Or set environment variable
export MURPHY_PORT=7777
./start_murphy_1.0.sh
```

### Issue: Dependencies not installing
```bash
# Upgrade pip
pip install --upgrade pip

# Install dependencies manually
pip install -r requirements_murphy_1.0.txt
```

### Issue: Python version too old
```bash
# Install Python 3.10+
# Ubuntu/Debian
sudo apt install python3.10

# Mac
brew install python@3.10

# Windows
# Download from python.org
```

---

## 📚 Documentation

### Complete Documentation
- **MURPHY_SYSTEM_1.0_SPECIFICATION.md** - Complete system specification
- **INTEGRATION_ENGINE_COMPLETE.md** - Integration engine documentation
- **API Documentation** - http://localhost:8000/docs (when running)

### Architecture Documents
- **COMPLETE_INTEGRATION_ANALYSIS.md** - Integration system analysis
- **MURPHY_SELF_INTEGRATION_CAPABILITIES.md** - Self-integration capabilities

---

## 🎉 What's Next?

### Immediate Actions
1. ✅ Start Murphy System
2. ✅ Check system status
3. ✅ Try example use cases
4. ✅ Add your first integration
5. ✅ Run business automation

### Advanced Usage
1. Configure environment variables
2. Set up database (PostgreSQL)
3. Set up cache (Redis)
4. Configure monitoring (Prometheus + Grafana)
5. Deploy to production (Docker/Kubernetes)

---

## 💡 Tips

### Tip 1: Use API Documentation
Visit http://localhost:8000/docs for interactive API documentation with examples.

### Tip 2: Start Simple
Begin with simple tasks and gradually increase complexity.

### Tip 3: Monitor System
Regularly check http://localhost:8000/api/status to monitor system health.

### Tip 4: Review Integrations
Always review integration approval requests carefully before approving.

### Tip 5: Learn from Corrections
Submit corrections when Murphy makes mistakes - it will learn and improve.

---

## 🆘 Support

### Community Support
- GitHub Issues
- Documentation
- Examples

### Enterprise Support
- 24/7 Support
- Custom Development
- Training & Consulting

---

## 📄 License

**BSL 1.1** (Business Source License 1.1)

Copyright © 2020 Inoni Limited Liability Company  
Creator: Corey Post

---

## 🎯 Success!

You're now running Murphy System 1.0! 🎉

**Next Steps:**
1. Try the example use cases above
2. Add your first integration
3. Run business automation
4. Explore the API documentation

**Questions?** Check the complete documentation in MURPHY_SYSTEM_1.0_SPECIFICATION.md

---

**Welcome to the future of AI automation!** 🚀