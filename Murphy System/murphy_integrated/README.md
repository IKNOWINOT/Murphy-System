# Murphy System - Integrated Version 2.0

**A comprehensive AI agent system with form-driven task execution, Murphy validation, correction capture, and self-improving shadow agents.**

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Verify installation
python tests/test_basic_imports.py

# 3. Start the server
python murphy_complete_backend_extended.py

# 4. Open the UI
# Navigate to: http://localhost:8000/murphy_ui_integrated.html
```

**That's it!** The system is now running with all integrated features.

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

Murphy System v2.0 is the integrated version that combines:

- **Original Murphy Runtime** (272 files) - Proven execution engine with G/D/H confidence scoring
- **Phase 1-5 Enhancements** (67 files) - Form-driven interface, Murphy validation, correction capture, shadow agent training
- **Integration Layer** (4 bridge classes) - Seamlessly connects new and old systems

### What's New in v2.0

✅ **Form-Driven Interface** - Submit tasks via intuitive forms  
✅ **Enhanced Murphy Validation** - 5D uncertainty analysis (UD/UA/UI/UR/UG)  
✅ **Correction Capture** - Learn from human corrections  
✅ **Shadow Agent Training** - Self-improving AI that learns from mistakes  
✅ **Human-in-the-Loop** - Smart checkpoints for critical decisions  
✅ **15+ New API Endpoints** - RESTful API for all features  
✅ **Modern Web UI** - Beautiful, responsive interface  
✅ **100% Backward Compatible** - All original features preserved  

---

## ✨ Features

### Core Capabilities

#### 1. Form-Driven Task Execution
- Submit tasks via forms (JSON, YAML, or natural language)
- Automatic task decomposition
- Dependency management
- Async execution with progress tracking

#### 2. Murphy Validation System
- **Original G/D/H Formula** - Goodness, Domain, Hazard scoring
- **New 5D Uncertainty** - UD (Data), UA (Authority), UI (Information), UR (Resources), UG (Disagreement)
- **Murphy Gate** - Threshold-based approval/rejection
- **Confidence Reports** - Detailed validation results

#### 3. Correction Capture & Learning
- **4 Capture Methods** - Interactive, batch, API, inline
- **Pattern Extraction** - Automatic learning from corrections
- **Feedback System** - Collect and analyze human feedback
- **Validation** - Conflict detection and quality scoring

#### 4. Shadow Agent Training
- **Training Pipeline** - Automated data preparation and model training
- **Continuous Learning** - Learns from every correction
- **A/B Testing** - Compare shadow agent vs Murphy Gate
- **Gradual Rollout** - Safe production deployment

#### 5. Human-in-the-Loop (HITL)
- **Smart Checkpoints** - 6 checkpoint types for critical decisions
- **Intervention Requests** - Automatic escalation when needed
- **Approval Workflows** - Structured decision-making
- **Statistics** - Track intervention patterns

---

## 🏗️ Architecture

### System Components

```
murphy_integrated/
├── src/
│   ├── form_intake/              # Form processing (6 files)
│   ├── confidence_engine/        # Validation (+23 files)
│   │   ├── unified_confidence_engine.py  # Integration class
│   │   ├── uncertainty_calculator.py     # 5D uncertainty
│   │   ├── murphy_gate.py                # Threshold validation
│   │   └── risk/                         # Risk assessment
│   ├── execution_engine/         # Task execution (+8 files)
│   │   └── integrated_form_executor.py   # Integration class
│   ├── learning_engine/          # Learning & corrections (+22 files)
│   │   ├── integrated_correction_system.py  # Integration class
│   │   ├── correction_capture.py            # Capture system
│   │   ├── pattern_extraction.py            # Pattern mining
│   │   └── shadow_agent.py                  # Self-improving AI
│   ├── supervisor_system/        # HITL monitoring (+8 files)
│   │   └── integrated_hitl_monitor.py    # Integration class
│   └── ... (original 272 files)
├── murphy_complete_backend_extended.py  # Integrated backend
├── murphy_ui_integrated.html            # Onboarding/Librarian setup UI
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
pip install -r requirements.txt
```

### Step 2: Verify Installation
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
python murphy_complete_backend_extended.py
```

Server starts on: **http://localhost:8000**

---

## 💻 Usage

### Web UI

Open your browser and navigate to:
```
http://localhost:8000/murphy_ui_integrated.html
```

The UI has 4 tabs:

1. **📝 Form Submission** - Execute tasks with Murphy validation
2. **✓ Validation** - Validate tasks without executing
3. **🔧 Corrections** - Submit corrections to help Murphy learn
4. **📊 Monitoring** - View system statistics and performance

### API Usage

#### Execute a Task
```bash
curl -X POST http://localhost:8000/api/forms/task-execution \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "analysis",
    "description": "Analyze Q4 sales data",
    "parameters": {"quarter": "Q4", "year": 2024}
  }'
```

#### Validate a Task
```bash
curl -X POST http://localhost:8000/api/forms/validation \
  -H "Content-Type: application/json" \
  -d '{
    "task_data": {
      "task_type": "general",
      "description": "Process customer data"
    }
  }'
```

#### Submit a Correction
```bash
curl -X POST http://localhost:8000/api/forms/correction \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task_12345",
    "correction_type": "output_error",
    "original_output": "Wrong result",
    "corrected_output": "Correct result",
    "explanation": "Fixed calculation error"
  }'
```

---

## 📚 API Documentation

See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for complete API reference.

### Available Endpoints

**Form Endpoints:**
- `POST /api/forms/plan-upload` - Upload plan
- `POST /api/forms/plan-generation` - Generate plan
- `POST /api/forms/task-execution` - Execute task
- `POST /api/forms/validation` - Validate task
- `POST /api/forms/correction` - Submit correction
- `GET /api/forms/submission/<id>` - Get submission status

**Correction Endpoints:**
- `GET /api/corrections/patterns` - Get patterns
- `GET /api/corrections/statistics` - Get statistics
- `GET /api/corrections/training-data` - Get training data

**HITL Endpoints:**
- `GET /api/hitl/interventions/pending` - Get pending interventions
- `POST /api/hitl/interventions/<id>/respond` - Respond to intervention
- `GET /api/hitl/statistics` - Get HITL statistics

**System Endpoints:**
- `GET /api/system/info` - Get system information

---

## 🛠️ Development

### Running Tests
```bash
# Import tests
python tests/test_basic_imports.py

# Integration tests (requires pytest)
pip install pytest pytest-asyncio
pytest tests/test_integration.py -v
```

---

## 🚀 Deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed deployment instructions.

### Quick Deploy with Docker

```bash
# Build image
docker build -t murphy-system:latest .

# Run container
docker run -d -p 8000:8000 murphy-system:latest
```

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

**Murphy System v2.0** - Intelligent, Self-Improving, Human-Centered AI

*Making AI agents smarter, one correction at a time.* 🚀
