# Murphy System - Complete Installation Package

**Copyright © 2020 Inoni Limited Liability Company. All rights reserved.**  
**Created by: Corey Post**

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

## Overview

This package contains the complete Murphy System including:
- **Original Murphy Runtime System** (131 Python files)
- **Phase 1-5 Implementations** (New autonomous agent capabilities)
- **Complete Documentation** (20,000+ words)
- **Deployment Infrastructure** (Docker, Kubernetes, CI/CD)

## What's Included

### Murphy Runtime System (`murphy_runtime/`)
The original Murphy automation operating system with:
- Complete Flask-based server
- Agent communication system
- Generative gate system
- Swarm knowledge pipeline
- LLM integration (Groq, OpenAI, Anthropic)
- Web UI interface
- 131 Python modules

### Phase 1-5 Implementations (`murphy_implementation/`)
New capabilities including:
- **Phase 1:** Form intake and execution framework
- **Phase 2:** Enhanced Murphy validation with uncertainty calculation
- **Phase 3:** Correction capture and learning system
- **Phase 4:** Shadow agent training and continuous improvement
- **Phase 5:** Production deployment infrastructure

### Documentation
- Complete API documentation
- User guides and tutorials
- Deployment guides
- Operations runbooks
- System architecture documentation

## Installation

### Quick Start (Linux/Mac)

```bash
# Make installation script executable
chmod +x install.sh

# Run installation
./install.sh

# Activate virtual environment
source venv/bin/activate

# Start Murphy Runtime System
python murphy_runtime/murphy_complete_integrated.py
```

### Quick Start (Windows)

```cmd
# Run installation
install.bat

# Activate virtual environment
venv\Scripts\activate.bat

# Start Murphy Runtime System
python murphy_runtime\murphy_complete_integrated.py
```

## Usage

### Starting the Original Murphy Runtime

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate.bat  # Windows

# Start server
python murphy_runtime/murphy_complete_integrated.py

# Access UI at http://localhost:3002
```

### Using Phase 1-5 Implementations

```bash
# Activate virtual environment
source venv/bin/activate

# Start new API server
python -m murphy_implementation.main

# Access API at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## System Requirements

- Python 3.11 or higher
- 8GB RAM minimum (16GB recommended)
- 10GB disk space
- Internet connection for LLM APIs

## Configuration

### Environment Variables

Create a `.env` file with:

```bash
# LLM API Keys
GROQ_API_KEY=your_groq_key
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# Database (optional)
DATABASE_URL=postgresql://user:pass@localhost:5432/murphy

# Redis (optional)
REDIS_URL=redis://localhost:6379/0
```

## Documentation

Complete documentation is available in:
- `murphy_implementation/deployment/API_DOCUMENTATION.md`
- `murphy_implementation/deployment/USER_GUIDE.md`
- `murphy_implementation/deployment/DEPLOYMENT_GUIDE.md`
- `murphy_implementation/deployment/RUNBOOK.md`
- `FINAL_SYSTEM_DOCUMENTATION.md`

## Architecture

The Murphy System consists of:

1. **Original Runtime System** - Flask-based automation OS
2. **Phase 1-5 Implementations** - New autonomous capabilities
3. **Deployment Infrastructure** - Production-ready deployment
4. **Monitoring Stack** - Prometheus + Grafana
5. **Documentation Suite** - Complete guides and references

## Support

For issues or questions:
- Review documentation in `/murphy_implementation/deployment/`
- Check `FINAL_SYSTEM_DOCUMENTATION.md` for complete overview
- Review phase completion summaries for detailed information

## License

Copyright © 2020 Inoni Limited Liability Company. All rights reserved.

Licensed under the Apache License, Version 2.0. See LICENSE file for details.

Created by: Corey Post

## Version

- Murphy Runtime System: Original
- Phase 1-5 Implementations: v1.0.0
- Package Version: 1.0.0
- Last Updated: 2024-01-15
