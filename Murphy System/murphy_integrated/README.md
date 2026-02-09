# Murphy System - Runtime 1.0 (Primary)

**A comprehensive AI automation runtime with task execution, validation modules, and optional form/correction components.**

---

## 🚀 Quick Start

```bash
# 1. Start runtime 1.0 (installs requirements_murphy_1.0.txt)
./start_murphy_1.0.sh

# 2. Verify the runtime
curl http://localhost:6666/api/health
```

**That's it!** Runtime 1.0 is now running.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Installation](#installation)
5. [Usage](#usage)
6. [API Documentation](#api-documentation)
7. [Development](#development)
8. [Deployment](#deployment)
9. [Contributing](#contributing)
10. [License](#license)

---

## 🎯 Overview

Runtime 1.0 is the only prepared runtime in this repository. References to v2/v3 are planning documents only.

Runtime 1.0 combines:

- **Original Murphy Runtime** - Proven execution engine with G/D/H confidence scoring
- **Phase 1-5 Enhancements** - Form-driven interface, Murphy validation, correction capture, shadow agent training
- **Integration Layer** - Seamlessly connects new and old systems

### Integrated Enhancements

✅ **Form Intake Modules** - Form handlers included (not wired to runtime 1.0 APIs by default)  
✅ **Enhanced Murphy Validation** - 5D uncertainty analysis (UD/UA/UI/UR/UG)  
✅ **Correction Capture** - Learn from human corrections  
✅ **Shadow Agent Training** - Self-improving AI that learns from mistakes  
✅ **Human-in-the-Loop** - Smart checkpoints for critical decisions  
✅ **Additional API Endpoints** - RESTful API for integrated features  
✅ **Optional Web UI** - Static HTML interface (served separately)  
✅ **Backward Compatible** - Core original features preserved (verify for your deployment)  

---

For a concise status summary, see [RUNTIME_1.0_STATUS.md](RUNTIME_1.0_STATUS.md).

## ✨ Features

### Core Capabilities

#### 1. Task Execution (Runtime 1.0)
- Execute tasks via `/api/execute`
- Orchestrates work through the control plane and two-phase workflow
- Form intake modules are present but not exposed by default in runtime 1.0

#### 2. Murphy Validation System
- **Original G/D/H Formula** - Goodness, Domain, Hazard scoring
- **New 5D Uncertainty** - UD (Data), UA (Authority), UI (Information), UR (Resources), UG (Disagreement)
- **Murphy Gate** - Threshold-based approval/rejection
- **Confidence Reports** - Detailed validation results

#### 3. Correction Capture & Learning
- Correction and learning modules are available in code
- Runtime 1.0 does not expose dedicated correction endpoints by default

#### 4. Shadow Agent Training
- Training pipeline modules are present
- Requires integration work to run end-to-end in runtime 1.0

#### 5. Human-in-the-Loop (HITL)
- **Smart Checkpoints** - 6 checkpoint types for critical decisions
- **Intervention Requests** - Automatic escalation when needed
- **Approval Workflows** - Structured decision-making
- **Statistics** - Track intervention patterns

These modules are included but require configuration and wiring to specific workflows in runtime 1.0.

---

## 🏗️ Architecture

### System Components

```
murphy_integrated/
├── src/
│   ├── form_intake/              # Form processing
│   ├── confidence_engine/        # Validation
│   │   ├── unified_confidence_engine.py  # Integration class
│   │   ├── uncertainty_calculator.py     # 5D uncertainty
│   │   ├── murphy_gate.py                # Threshold validation
│   │   └── risk/                         # Risk assessment
│   ├── execution_engine/         # Task execution
│   │   └── integrated_form_executor.py   # Integration class
│   ├── learning_engine/          # Learning & corrections
│   │   ├── integrated_correction_system.py  # Integration class
│   │   ├── correction_capture.py            # Capture system
│   │   ├── pattern_extraction.py            # Pattern mining
│   │   └── shadow_agent.py                  # Self-improving AI
│   ├── supervisor_system/        # HITL monitoring
│   │   └── integrated_hitl_monitor.py    # Integration class
│   └── ... (original runtime modules)
├── murphy_system_1.0_runtime.py         # Runtime 1.0 API server
├── murphy_ui_integrated.html            # Optional static web UI
└── tests/                               # Test suite
```

---

## 📦 Installation

### Prerequisites
- Python 3.11 or higher
- pip (Python package manager)
- 4GB RAM minimum (8GB recommended)

### Step 1: Install Dependencies
```bash
pip install -r requirements_murphy_1.0.txt
```

### Step 2: Verify Installation (Optional)
```bash
python tests/test_basic_imports.py
```

Expected output:
```
✓ UnifiedConfidenceEngine imported successfully
✓ IntegratedCorrectionSystem imported successfully
✓ IntegratedFormExecutor imported successfully
✓ IntegratedHITLMonitor imported successfully
✓ Form intake modules imported successfully

Results: 5/5 tests passed
```

### Step 3: Start the Server
```bash
python murphy_system_1.0_runtime.py
```

Server starts on: **http://localhost:6666**

---

## 💻 Usage

### Optional Web UI

Serve the static UI with a simple HTTP server (not hosted by runtime 1.0):

```bash
python -m http.server 8090
```

Then open:

```
http://localhost:8090/murphy_ui_integrated.html
```

### API Usage

#### Execute a Task
```bash
curl -X POST http://localhost:6666/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Analyze Q4 sales data",
    "task_type": "analysis",
    "parameters": {"quarter": "Q4", "year": 2024}
  }'
```

#### Check System Status
```bash
curl http://localhost:6666/api/status
```

#### Run Business Automation
```bash
curl -X POST http://localhost:6666/api/automation/sales/generate_leads \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"target_industry": "SaaS"}}'
```

---

## 📚 API Documentation

See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for complete API reference.

### Available Endpoints

**Core Endpoints:**
- `POST /api/execute` - Execute a task
- `GET /api/status` - Get system status
- `GET /api/info` - Get system information
- `GET /api/health` - Health check

**Integration Endpoints:** (available when integration engine dependencies are installed)
- `POST /api/integrations/add` - Submit integration request
- `POST /api/integrations/{request_id}/approve` - Approve integration
- `POST /api/integrations/{request_id}/reject` - Reject integration
- `GET /api/integrations/{status}` - List integrations (`pending`, `committed`, `all`)

**Automation Endpoints:**
- `POST /api/automation/{engine_name}/{action}` - Run business automation action

---

## 🛠️ Development

### Running Tests
```bash
python -m pytest
```

---

## 🚀 Deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for deployment notes. Docker and Kubernetes examples live in legacy archives.

---

## 📄 License

Copyright © 2020 Inoni Limited Liability Company  
Creator: Corey Post  
License: Apache License 2.0

---

## 📞 Support

### Documentation
- [START_INTEGRATED_SYSTEM.md](START_INTEGRATED_SYSTEM.md) - Quick start guide
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md) - Complete API reference
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Deployment instructions
- [INTEGRATION_COMPLETE_SUMMARY.md](INTEGRATION_COMPLETE_SUMMARY.md) - Integration details

---

**Murphy System Integrated Runtime** - Intelligent, Self-Improving, Human-Centered AI

*Making AI agents smarter, one correction at a time.* 🚀
