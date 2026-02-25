# Murphy System 1.0 - Quick Start Guide

**Version:** 1.0.0  
**Date:** February 3, 2025  
**Owner:** Inoni Limited Liability Company  
**Creator:** Corey Post  
**License:** Apache License 2.0

* * *

## 🚀 Quick Start (5 Minutes)

### Step 1: Install Python 3.11+

```bash
# Check Python version
python3 --version  # Should be 3.11 or higher
```

### Step 2: Start Murphy

```bash
# Linux/Mac
chmod +x start_murphy_1.0.sh
./start_murphy_1.0.sh

# Windows
start_murphy_1.0.bat
```

### Step 3: Access Murphy

-   **API Documentation:** [http://localhost:6666/docs](http://localhost:6666/docs)
-   **Health Check:** [http://localhost:6666/api/health](http://localhost:6666/api/health)
-   **System Status:** [http://localhost:6666/api/status](http://localhost:6666/api/status)
-   **System Info:** [http://localhost:6666/api/info](http://localhost:6666/api/info)

* * *

## 📖 What is Murphy System 1.0?

Murphy is a **Universal AI Automation System** that can:

-   ✅ Automate **any business type** (factory, content, data, system, agent, business)
-   ✅ **Self-integrate** (GitHub repositories, APIs, hardware)
-   ✅ **Self-improve** (learns from corrections)
-   ✅ **Self-operate** (runs Inoni LLC autonomously)
-   ✅ Maintain **safety** (human-in-the-loop approval)

* * *

## 🎯 Core Capabilities

### 1\. Universal Automation

```python
# Execute any task
POST /api/execute
{
    "task_description": "Automate HVAC system in factory",
    "task_type": "automation"
}
```

**Supported Automation Types:**

-   **Factory/IoT:** Sensors, actuators, HVAC, robotics
-   **Content:** Blog posts, social media, documentation
-   **Data:** Databases, analytics, processing
-   **System:** Commands, DevOps, infrastructure
-   **Agent:** Swarms, complex tasks, reasoning
-   **Business:** Sales, marketing, finance, support

### 2\. Self-Integration

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

### 3\. Self-Improvement

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

### 4\. Self-Operation (Inoni Business Automation)

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

* * *

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

* * *

## 🔧 Configuration

### Environment Variables (.env file)

```bash
# Core Configuration
MURPHY_VERSION=1.0.0
MURPHY_ENV=production
MURPHY_PORT=6666

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/murphy
REDIS_URL=redis://localhost:6379

# API Keys
GROQ_API_KEY=your_groq_key
OPENAI_API_KEY=your_openai_key

# Integration Keys
GITHUB_TOKEN=your_github_token
STRIPE_API_KEY=your_stripe_key
PAYPAL_CLIENT_ID=your_paypal_id
PAYPAL_CLIENT_SECRET=your_paypal_secret

# Security
JWT_SECRET=your_jwt_secret
ENCRYPTION_KEY=your_encryption_key
```

* * *

## 🎯 Example Use Cases

### Use Case 1: Automate Factory HVAC

```bash
curl -X POST http://localhost:6666/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Monitor temperature sensors and adjust HVAC to maintain 72°F",
    "task_type": "automation"
  }'
```

### Use Case 2: Add Stripe Integration

```bash
curl -X POST http://localhost:6666/api/integrations/add \
  -H "Content-Type: application/json" \
  -d '{
    "source": "https://github.com/stripe/stripe-python",
    "category": "payment-processing"
  }'

# Murphy will analyze and ask for approval
# Then approve with:
curl -X POST http://localhost:6666/api/integrations/{request_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approved_by": "admin"}'
```

### Use Case 3: Generate Sales Leads

```bash
curl -X POST http://localhost:6666/api/automation/sales/generate_leads \
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
curl -X POST http://localhost:6666/api/automation/marketing/create_content \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "content_type": "blog_post",
      "topic": "AI Automation Benefits",
      "length": "1500 words"
    }
  }'
```

* * *

## 🛡️ Safety Features

### Human-in-the-Loop (HITL)

-   **Every integration requires approval**
-   **LLM-powered risk analysis**
-   **Clear recommendations**
-   **No automatic commits**

### Murphy Validation

-   **G/D/H Formula:** Goodness, Domain, Hazard scoring
-   **5D Uncertainty:** UD, UA, UI, UR, UG calculations
-   **Murphy Gate:** Threshold-based validation
-   **Safety Score:** 0.0-1.0 scoring

### Governance

-   **Authority-based scheduling**
-   **Permission levels** (LOW, MEDIUM, HIGH, CRITICAL)
-   **Audit trails**
-   **Compliance ready** (GDPR, SOC 2, HIPAA, PCI DSS)

* * *

## 📈 Monitoring

### System Status

```bash
curl http://localhost:6666/api/status
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
curl http://localhost:6666/api/health
```

* * *

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
# Install Python 3.11+
# Ubuntu/Debian
sudo apt install python3.11

# Mac
brew install python@3.11

# Windows
# Download from python.org
```

* * *

## 📚 Documentation

### Complete Documentation

-   **MURPHY\_SYSTEM\_1.0\_SPECIFICATION.md** - Complete system specification
-   **INTEGRATION\_ENGINE\_COMPLETE.md** - Integration engine documentation
-   **API Documentation** - [http://localhost:6666/docs](http://localhost:6666/docs) (when running)

### Architecture Documents

-   **COMPLETE\_INTEGRATION\_ANALYSIS.md** - Integration system analysis
-   **MURPHY\_SELF\_INTEGRATION\_CAPABILITIES.md** - Self-integration capabilities

* * *

## 🎉 What's Next?

### Immediate Actions

1.  ✅ Start Murphy System
2.  ✅ Check system status
3.  ✅ Try example use cases
4.  ✅ Add your first integration
5.  ✅ Run business automation

### Advanced Usage

1.  Configure environment variables
2.  Set up database (PostgreSQL)
3.  Set up cache (Redis)
4.  Configure monitoring (Prometheus + Grafana)
5.  Deploy to production (Docker/Kubernetes)

* * *

## 💡 Tips

### Tip 1: Use API Documentation

Visit [http://localhost:6666/docs](http://localhost:6666/docs) for interactive API documentation with examples.

### Tip 2: Start Simple

Begin with simple tasks and gradually increase complexity.

### Tip 3: Monitor System

Regularly check [http://localhost:6666/api/status](http://localhost:6666/api/status) to monitor system health.

### Tip 4: Review Integrations

Always review integration approval requests carefully before approving.

### Tip 5: Learn from Corrections

Submit corrections when Murphy makes mistakes - it will learn and improve.

* * *

## 🆘 Support

### Community Support

-   GitHub Issues
-   Documentation
-   Examples

### Enterprise Support

-   24/7 Support
-   Custom Development
-   Training & Consulting

* * *

## 📄 License

**Apache License 2.0**

Copyright © 2020 Inoni Limited Liability Company  
Creator: Corey Post

* * *

## 🎯 Success!

You're now running Murphy System 1.0! 🎉

**Next Steps:**

1.  Try the example use cases above
2.  Add your first integration
3.  Run business automation
4.  Explore the API documentation

**Questions?** Check the complete documentation in MURPHY\_SYSTEM\_1.0\_SPECIFICATION.md

* * *

**Welcome to the future of AI automation!** 🚀