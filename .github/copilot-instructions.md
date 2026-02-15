# Murphy System - GitHub Copilot Instructions

## Project Overview

Murphy System is a **universal AI automation system** designed to automate any business type, including its own operations. It's a production-ready platform that combines generative AI capabilities with robust execution engines for comprehensive business automation.

### Core Purpose
- Universal automation platform for factory/IoT, content, data, systems, agents, and business processes
- Self-integrating: Can automatically add GitHub repositories and APIs as new capabilities
- Self-improving: Learns from corrections and trains a shadow agent
- Self-operating: Autonomously runs Inoni LLC (the company that created Murphy)

### Key Capabilities
1. **Two-Phase Execution**: Generative setup phase → Production execution phase
2. **Universal Control Plane**: Modular engines for different automation types
3. **Integration Engine**: Automated GitHub repository ingestion with Human-in-the-Loop (HITL) approval
4. **Learning System**: Captures corrections and improves over time (85-95% accuracy improvement)
5. **Business Automation**: Complete engines for sales, marketing, R&D, business management, and production

## Technology Stack

### Core Technologies
- **Language**: Python 3.11+
- **Web Framework**: FastAPI (API server at port 6666)
- **AI/ML**: Transformers, PyTorch, Groq, OpenAI, Anthropic, Google AI
- **Data**: NumPy, NetworkX
- **Security**: Cryptography library for execution packet protection
- **UI**: Rich terminal, Prompt Toolkit, HTML/JS frontends
- **Testing**: pytest, pytest-cov
- **Configuration**: YAML, .env files

### Project Structure
```
Murphy System/
├── murphy_integrated/          # Main production system (Murphy 1.0)
│   ├── src/                    # Core 319 Python files
│   ├── bots/                   # Bot implementations
│   ├── scripts/                # Utility scripts
│   ├── tests/                  # Test suite
│   ├── requirements.txt        # Python dependencies
│   └── murphy_final_runtime.py # Complete runtime
├── murphy_v3/                  # Next-generation architecture
├── docs/                       # Documentation
├── archive/                    # Legacy versions and backups
└── tests/                      # Root-level tests
```

## Code Style and Standards

### Python Code Style
- **Python Version**: Use Python 3.11+ features
- **Type Hints**: Use type annotations wherever possible
- **Docstrings**: Use clear docstrings for all public functions and classes
- **Naming Conventions**:
  - Classes: `PascalCase` (e.g., `MurphyValidator`, `ExecutionEngine`)
  - Functions/methods: `snake_case` (e.g., `execute_task`, `validate_input`)
  - Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_PORT`, `MAX_RETRIES`)
  - Private methods: Prefix with `_` (e.g., `_internal_helper`)

### Code Organization
- Keep modules focused and single-purpose
- Use clear separation of concerns (engines, validators, learning systems, etc.)
- Follow the existing modular engine pattern for new automation types
- Maintain backward compatibility with existing APIs

### Import Style
```python
# Standard library imports first
import os
import sys
from typing import Dict, List, Optional

# Third-party imports
import numpy as np
from fastapi import FastAPI

# Local imports
from src.core.config import Config
from src.engines.base import BaseEngine
```

## Architecture Principles

### Murphy System Core Concepts

1. **Murphy Validation (G/D/H Formula)**
   - Goodness (G): How well does it work?
   - Domain (D): Relevance to the task
   - Hazard (H): Risk assessment
   - 5D Uncertainty: UD (data), UA (algorithm), UI (interpretation), UR (representation), UG (generalization)
   - All new features should maintain safety scores of 0.85+

2. **Two-Phase Execution**
   - Phase 1 (Setup): Generative, form intake, analysis, engine selection, session creation
   - Phase 2 (Execute): Production, load session, execute with selected engines, deliver results, learn

3. **Modular Engine Design**
   - Each engine (Sensor, Actuator, Database, API, Content, Command, Agent, Compute, Reasoning) is independent
   - Engines implement a common interface for loading and execution
   - New engines should follow the `BaseEngine` pattern

4. **Human-in-the-Loop (HITL)**
   - All integrations require human approval
   - LLM-powered risk analysis with clear recommendations
   - Never auto-commit or auto-merge without approval

5. **Security First**
   - Execution packets are cryptographically signed
   - Secrets are never committed to code (use .env files)
   - All inputs are validated before execution
   - License and risk scanning for all integrations

## Building and Testing

### Setup
```bash
# Navigate to the main system
cd "Murphy System/murphy_integrated"

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment (copy and edit)
cp .env.example .env
# Add at least one API key (Groq recommended)
```

### Running the System
```bash
# Start Murphy 1.0
./start_murphy_1.0.sh  # Linux/Mac
# OR
start_murphy_1.0.bat   # Windows

# Access API documentation
# http://localhost:6666/docs
# http://localhost:6666/api/status
```

### Testing
```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/integration/

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/test_security_packet_protection.py
```

### Linting (if available)
```bash
# Check code style
ruff check .

# Auto-fix issues
ruff check --fix .
```

## Common Development Tasks

### Adding a New Engine
1. Create new engine class inheriting from `BaseEngine` in `src/engines/`
2. Implement required methods: `load()`, `execute()`, `validate()`
3. Register engine in the Universal Control Plane
4. Add tests in `tests/`
5. Update documentation

### Adding an Integration
1. Integration requests go through `/api/integrations/add` endpoint
2. System automatically analyzes the GitHub repository
3. Generates module YAML with capabilities
4. Performs license and risk scanning
5. Requests HITL approval
6. Loads module only after approval

### Capturing Corrections
1. Corrections are submitted via `/api/corrections/submit`
2. System extracts patterns from the correction
3. Shadow agent is trained on the correction data
4. Future tasks benefit from learned patterns

## Security and Safety Guidelines

### Critical Security Rules
- **Never commit secrets**: Use environment variables and .env files
- **Validate all inputs**: Use Murphy Validation for all external inputs
- **Cryptographic signing**: All execution packets must be signed
- **License compliance**: Only use approved licenses (MIT, BSD, Apache, ISC, Unlicense, CC0)
- **HITL for integrations**: Never bypass human approval for new integrations
- **Sandboxing**: Execute untrusted code in isolated environments

### Safety Scores
- Minimum safety score: 0.85 (85%)
- Integration risk assessment: Required for all external repositories
- Hazard detection: Automatic scanning for security risks
- Fail-safe: System should degrade gracefully, never crash

## API Conventions

### RESTful Endpoints
- Use FastAPI for all API endpoints
- Return proper HTTP status codes (200, 201, 400, 404, 500, etc.)
- Include clear error messages in responses
- Use Pydantic models for request/response validation
- Document all endpoints with OpenAPI/Swagger

### Response Format
```python
{
    "success": true,
    "data": {...},
    "message": "Operation completed successfully",
    "metadata": {
        "timestamp": "2025-02-15T18:50:00Z",
        "version": "1.0.0"
    }
}
```

## Documentation Standards

- Keep README.md up to date with major changes
- Document new engines in their respective files
- Update API documentation for endpoint changes
- Add inline comments for complex logic
- Create examples for new features in `examples/`
- Maintain CHANGELOG for version tracking

## Performance Targets

- **API Throughput**: 1,000+ requests/second
- **Task Execution**: 100+ tasks/second
- **Integration Time**: <5 minutes per repository
- **API Latency**: <100ms p95
- **Uptime Target**: 99.9%
- **Error Rate**: <1%

## Dependencies Management

- Pin major versions in requirements.txt for stability
- Test before upgrading major dependencies
- Use virtual environments for all development
- Document any new dependencies added
- Check security advisories before adding dependencies

## Contributing Guidelines

### Before Making Changes
1. Understand the two-phase architecture
2. Review Murphy Validation principles
3. Check existing engine implementations for patterns
4. Ensure changes don't break the modular design

### Making Changes
1. Create focused, minimal changes
2. Follow existing code style and patterns
3. Add tests for new functionality
4. Update relevant documentation
5. Ensure safety scores remain above 0.85
6. Run full test suite before committing

### Pull Request Guidelines
1. Provide clear description of changes
2. Reference any related issues
3. Include test results
4. Document any breaking changes
5. Update CHANGELOG if significant

## Special Considerations

### Murphy Meta-Case
Murphy improves itself through the R&D engine, which can detect and fix bugs automatically. When working on Murphy's core systems:
- Changes affect Murphy's ability to self-improve
- Test thoroughly before deployment
- Maintain backward compatibility
- Document changes comprehensively

### Inoni LLC Self-Operation
Murphy autonomously operates Inoni LLC. Changes to business automation engines affect:
- Sales: Lead generation and qualification
- Marketing: Content creation and social media
- R&D: Bug detection and fixes
- Business: Finance and project management
- Production: Releases and monitoring

### Integration with LLMs
Murphy integrates with multiple LLM providers:
- Groq (recommended, free tier available)
- OpenAI (GPT-3.5, GPT-4)
- Anthropic (Claude)
- Google AI (Gemini)

Configure API keys in .env file. Always handle API failures gracefully.

## File Locations

### Key Files
- **Main Runtime**: `murphy_integrated/murphy_final_runtime.py`
- **System Specification**: `murphy_integrated/MURPHY_SYSTEM_1.0_SPECIFICATION.md`
- **Quick Start Guide**: `MURPHY_1.0_QUICK_START.md`
- **Integration Engine**: `murphy_integrated/INTEGRATION_ENGINE_COMPLETE.md`
- **Configuration**: `murphy_integrated/.env.example`
- **Requirements**: `murphy_integrated/requirements.txt`

### Important Directories
- `murphy_integrated/src/`: Core system (319 Python files)
- `murphy_integrated/bots/`: Bot implementations
- `murphy_integrated/tests/`: Test suite
- `murphy_integrated/scripts/`: Utility scripts
- `docs/`: System documentation

## Common Issues and Solutions

### Issue: API won't start
- Check .env file has at least one API key (Groq recommended)
- Verify port 6666 is not in use
- Check Python version is 3.11+
- Ensure all dependencies are installed

### Issue: Integration fails
- Verify GitHub URL is accessible
- Check license compatibility (must be MIT, BSD, Apache, ISC, Unlicense, or CC0)
- Ensure repository has a README
- Check network connectivity

### Issue: Tests failing
- Run from correct directory (`murphy_integrated/`)
- Activate virtual environment
- Install test dependencies: `pip install pytest pytest-cov`
- Check for missing environment variables

## Additional Resources

- **Visual Setup Guide**: `VISUAL_SETUP_GUIDE_WITH_SCREENSHOTS.md`
- **Complete Documentation**: `GETTING_STARTED.md`
- **API Documentation**: http://localhost:6666/docs (when running)
- **Architecture Details**: `murphy_integrated/MURPHY_SYSTEM_1.0_SPECIFICATION.md`

---

**Remember**: Murphy is designed to be universal, modular, and safe. All changes should maintain these core principles while extending capabilities.
