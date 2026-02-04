# Murphy System 1.0 - System Overview

**Created:** February 4, 2026  
**Version:** 1.0.0  
**Status:** Complete, Requires Security Hardening

---

## Executive Summary

Murphy System 1.0 is a **Universal AI Automation System** capable of automating any business type, including its own operations. The system integrates advanced AI capabilities with enterprise-grade architecture to provide:

- **6 Automation Types:** Factory/IoT, Content Publishing, Data Processing, System Administration, Agent Reasoning, Business Operations
- **Self-Integration:** Automatically adds GitHub repositories, external APIs, and hardware devices with human-in-the-loop safety approval
- **Self-Improvement:** Learns from human corrections through correction capture and shadow agent training
- **Self-Operation:** Runs Inoni LLC (the company that makes Murphy) autonomously through 5 business automation engines

---

## Codebase Statistics

| Metric | Count |
|--------|-------|
| **Total Python Files** | 538 |
| **Total Directories** | 254 |
| **Codebase Size** | 13 MB |
| **Test Files** | 89 |
| **Specialized Bots** | 70+ |
| **API Endpoints** | 30+ |
| **Documentation (lines)** | 2,153+ |

---

## Directory Structure

```
murphy_integrated/
├── murphy_system_1.0_runtime.py       # Main entry point
├── murphy_complete_backend_extended.py # FastAPI REST API (Port 6666)
├── universal_control_plane.py         # Modular control plane
├── inoni_business_automation.py       # Business automation engines
├── two_phase_orchestrator.py          # Setup → Execute orchestration
├── src/                               # Core source code (31 subdirectories)
│   ├── execution_engine/             # Task execution & workflows
│   ├── learning_engine/              # Correction capture & shadow agents
│   ├── integration_engine/           # GitHub integration & SwissKiss
│   ├── form_intake/                  # Form-driven task submission
│   ├── confidence_engine/            # Murphy validation (G/D/H + 5D)
│   ├── supervisor_system/            # Human-in-the-loop monitoring
│   ├── security_plane/               # Auth, crypto, DLP, access control
│   ├── governance_framework/         # Control & oversight
│   ├── neuro_symbolic_models/        # Neural-symbolic reasoning
│   ├── module_compiler/              # Dynamic code generation
│   ├── compute_plane/                # Advanced computation
│   ├── adapter_framework/            # Integration adapters
│   ├── domain_expert_system.py       # Domain expertise injection
│   ├── swarm_proposal_generator.py   # Multi-agent coordination
│   ├── llm_integration.py            # LLM orchestration
│   ├── config.py                     # Centralized configuration
│   └── [25+ more modules]
├── bots/                             # 70+ specialized agents
│   ├── analysisbot/                  # Analysis capabilities
│   ├── engineering_bot/              # Engineering tasks
│   ├── librarian_bot/                # Knowledge management
│   ├── json_bot/                     # JSON processing
│   ├── optimization_bot/             # Optimization tasks
│   ├── swisskiss_loader/             # Repository integration
│   └── [64+ more bots]
├── tests/                            # Comprehensive test suite
│   ├── test_*.py                     # Unit tests (60+ files)
│   ├── integration/                  # Integration tests
│   ├── e2e/                          # End-to-end tests
│   └── system/                       # System tests
├── documentation/                    # Detailed documentation
│   ├── api/                          # API specifications
│   ├── architecture/                 # System design docs
│   ├── components/                   # Component guides
│   ├── deployment/                   # Deployment procedures
│   └── domain_system/                # Domain system docs
├── examples/                         # Usage examples
├── scripts/                          # Utility scripts
├── requirements_murphy_1.0.txt       # Complete dependencies
├── setup.py                          # Package configuration
└── [Terminal UIs, startup scripts]
```

---

## Key Technologies and Frameworks

### Core Stack

| Category | Technologies |
|----------|-------------|
| **Language** | Python 3.11+ |
| **Web Framework** | FastAPI, Uvicorn, Flask (legacy) |
| **Data Validation** | Pydantic 2.0+ |
| **Async** | asyncio, aiohttp, httpx |

### AI/ML Stack

| Category | Technologies |
|----------|-------------|
| **LLM Integration** | Groq (primary), Aristotle, Onboard AI |
| **ML Frameworks** | PyTorch 2.1+, scikit-learn 1.3+ |
| **Transformers** | Hugging Face Transformers 4.35+ |
| **NLP** | spaCy 3.7+, NLTK 3.8+ |

### Data & Storage

| Category | Technologies |
|----------|-------------|
| **Database** | SQLAlchemy 2.0+, PostgreSQL (psycopg2-binary) |
| **Cache/Queue** | Redis 5.0+, Celery 5.3+ |
| **Data Processing** | Pandas 2.1+, NumPy 1.24+, SciPy 1.11+ |
| **Migrations** | Alembic 1.12+ |

### Security & Infrastructure

| Category | Technologies |
|----------|-------------|
| **Cryptography** | cryptography 41.0+, PyJWT 2.8+, bcrypt 4.1+ |
| **Monitoring** | Prometheus Client 0.19+, Sentry SDK 1.38+ |
| **Containerization** | Docker 6.1+, Kubernetes 28.1+ |
| **Cloud** | boto3 (AWS), google-cloud-storage (GCP), azure-storage-blob |

### Testing & Quality

| Category | Technologies |
|----------|-------------|
| **Testing** | pytest 7.4+, pytest-asyncio, pytest-cov, pytest-mock |
| **Code Quality** | black 23.11+, flake8 6.1+, mypy 1.7+, pylint 3.0+ |
| **Documentation** | mkdocs 1.5+, mkdocs-material 9.4+ |

### Additional Libraries

- **HTTP/API:** requests, urllib3, beautifulsoup4
- **File Processing:** python-magic, Pillow, PyPDF2
- **Git Integration:** GitPython
- **Utilities:** python-dotenv, click, rich, tqdm
- **Serialization:** msgpack, protobuf, PyYAML, TOML
- **Payment:** Stripe 7.4+
- **Communication:** Twilio, SendGrid

---

## External Dependencies

### Required Services

| Service | Purpose | Configuration |
|---------|---------|---------------|
| **PostgreSQL** | Primary database | Connection via SQLAlchemy |
| **Redis** | Caching & message queue | Optional, defaults to memory |
| **Groq API** | Primary LLM provider | API key required |
| **Aristotle** | Alternative LLM | API key optional |

### Optional Services

| Service | Purpose | Usage |
|---------|---------|-------|
| **Prometheus** | Metrics collection | Monitoring dashboard |
| **Grafana** | Visualization | Metrics visualization |
| **Stripe** | Payment processing | Business automation |
| **Twilio** | SMS/Voice | Communication automation |
| **SendGrid** | Email | Marketing automation |
| **AWS/GCP/Azure** | Cloud storage | Artifact storage |

---

## Architecture Patterns

### Design Principles

1. **Modular Engine System** - 7 engines (Sensor, Actuator, Database, API, Content, Command, Agent) that load per-session
2. **Two-Phase Execution** - Phase 1 (Generative Setup) → Phase 2 (Production Execution)
3. **Session Isolation** - Different automation types don't interfere with each other
4. **Human-in-the-Loop** - Safety approval checkpoints throughout
5. **Form-Driven Interface** - JSON/YAML/Natural Language task submission
6. **Murphy Validation** - G/D/H formula + 5D uncertainty (UD/UA/UI/UR/UG)
7. **Correction Learning** - 4-method capture system (interactive, batch, API, inline)
8. **Shadow Agent Training** - Self-improving AI trained on corrections

### Key Architectural Components

#### 1. Universal Control Plane
- Handles any automation type through modular engines
- Dynamically loads engines based on task requirements
- Provides unified interface for all automation types

#### 2. Inoni Business Automation
- 5 autonomous engines: Sales, Marketing, R&D, Business Management, Production
- Enables Murphy to run its own business
- Fully integrated with core control plane

#### 3. Integration Engine (SwissKiss)
- Automatically ingests GitHub repositories
- Extracts capabilities and generates modules
- Implements HITL approval for safety
- Supports API and hardware integration

#### 4. Two-Phase Orchestrator
- **Phase 1 (Generative):** Analyze request, determine control type, select engines, discover constraints
- **Phase 2 (Production):** Execute with selected engines, deliver results, learn from execution

#### 5. Learning System
- Captures corrections through 4 methods
- Extracts patterns from correction data
- Trains shadow agent for improvement
- Improves accuracy from 80% to 95%+ over time

---

## Configuration Management

### Configuration Files

| File | Purpose |
|------|---------|
| `src/config.py` | Centralized Pydantic settings |
| `.env` | Environment variables (not in repo) |
| `requirements_murphy_1.0.txt` | Python dependencies |
| `setup.py` | Package metadata |

### Key Configuration Areas

1. **API Configuration** - Host, port, debug mode
2. **Database** - Connection strings, timeout, pooling
3. **LLM Integration** - API keys, timeouts, retry logic
4. **Safety Thresholds** - Confidence, Murphy index, gate satisfaction
5. **Caching** - Redis URL, TTL, enable/disable
6. **Rate Limiting** - Per-endpoint limits
7. **Logging** - Level, format, rotation
8. **Security** - Master keys, CORS, encryption

---

## Entry Points

### Primary Entry Points

| File | Purpose | Usage |
|------|---------|-------|
| `murphy_system_1.0_runtime.py` | Complete system runtime | `python murphy_system_1.0_runtime.py` |
| `murphy_complete_backend_extended.py` | Web server with API | Started by runtime |
| `start_murphy_1.0.sh` | Linux/Mac startup | `./start_murphy_1.0.sh` |
| `start_murphy_1.0.bat` | Windows startup | `start_murphy_1.0.bat` |

### Secondary Entry Points

| File | Purpose |
|------|---------|
| `universal_control_plane.py` | Control plane module |
| `inoni_business_automation.py` | Business automation module |
| `two_phase_orchestrator.py` | Orchestrator module |
| `test_integration_engine.py` | Integration testing |
| `create_murphy_1.0_package.py` | Package builder |

### Terminal UIs

| File | Purpose |
|------|---------|
| `murphy_ui_integrated.html` | Onboarding/Librarian setup UI |
| `terminal_integrated.html` | Integrated terminal UI |
| `terminal_architect.html` | Architect mode |
| `terminal_enhanced.html` | Enhanced features |
| `terminal_worker.html` | Worker mode |

---

## Current System Status

### Completed Components

✅ **Core Architecture**
- Universal Control Plane implemented
- Inoni Business Automation complete
- Integration Engine operational
- Two-Phase Orchestrator functional

✅ **Phase 1-5 Implementations**
- Form intake system (Phase 1)
- Murphy validation (Phase 2)
- Correction capture (Phase 3)
- Shadow agent training (Phase 4)
- Deployment infrastructure (Phase 5)

✅ **Original Murphy Runtime**
- 319 files preserved and integrated
- All bots operational
- SwissKiss loader working

✅ **Documentation**
- 50,000+ words across 10+ documents
- API documentation complete
- Architecture docs comprehensive

✅ **Test Structure**
- pytest framework implemented
- 89 test files created
- Unit, integration, e2e, system tests

### System Capabilities

| Capability | Status |
|-----------|--------|
| **Functional** | ✅ Yes, can execute tasks and integrations |
| **Production-Ready** | ⚠️ No, needs security hardening |
| **Deployed** | ❌ Not deployed |
| **Last Updated** | February 3, 2025 |

---

## Version Information

- **Murphy System Version:** 1.0.0
- **Package Version (mfgc-ai):** 0.1.0
- **Python Requirement:** 3.11+
- **License:** Apache License 2.0
- **Copyright:** © 2020 Inoni Limited Liability Company
- **Creator:** Corey Post
- **Contact:** corey.gfc@gmail.com
- **Repository:** https://github.com/inoni-llc/murphy

---

## Quick Reference

### Start Murphy
```bash
# Linux/Mac
cd murphy_integrated
./start_murphy_1.0.sh

# Windows
cd murphy_integrated
start_murphy_1.0.bat
```

### Access Points
- **API Documentation:** http://localhost:6666/docs
- **System Status:** http://localhost:6666/api/status
- **Health Check:** http://localhost:6666/api/health

### Key Commands
```bash
# Install dependencies
pip install -r requirements_murphy_1.0.txt

# Run tests
pytest tests/

# Build package
python create_murphy_1.0_package.py

# Check imports
python tests/test_basic_imports.py
```

---

## Next Steps

This system overview provides the foundation for:
1. **Phase 2:** Intent Analysis & Issue Identification
2. **Security Audit:** Authentication, secrets management, rate limiting
3. **Test Implementation:** Expand coverage to 80%+
4. **Production Hardening:** Error handling, logging, monitoring
5. **Code Quality:** Type hints, docstrings, comments

See `ARCHITECTURE_MAP.md` for detailed component relationships and `FILE_CLASSIFICATION.md` for complete file inventory.
