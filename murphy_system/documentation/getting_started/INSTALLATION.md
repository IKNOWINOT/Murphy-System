# Installation Guide - Murphy System Runtime

**Complete installation instructions for all environments**

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation Methods](#installation-methods)
3. [Installing from Source](#installing-from-source)
4. [Installing from Package](#installing-from-package)
5. [Docker Installation](#docker-installation)
6. [Post-Installation](#post-installation)
7. [Verification](#verification)
8. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Requirements

- **Operating System**: Linux, macOS, or Windows 10+
- **Python Version**: 3.10 or higher
- **RAM**: 4GB minimum
- **Disk Space**: 500MB free space
- **CPU**: 2 cores minimum

### Recommended Requirements

- **Operating System**: Linux (Ubuntu 20.04+ recommended)
- **Python Version**: 3.10 or 3.12
- **RAM**: 8GB or more
- **Disk Space**: 2GB free space
- **CPU**: 4 cores or more

### Enterprise Requirements

- **Operating System**: Linux (Ubuntu 22.04+ recommended)
- **Python Version**: 3.10 or 3.12
- **RAM**: 32GB or more
- **Disk Space**: 5GB free space
- **CPU**: 16 cores or more

---

## Installation Methods

The Murphy System Runtime can be installed using three methods:

1. **From Source** - Clone repository and install (recommended for development)
2. **From Package** - Download and extract pre-built package (recommended for production)
3. **Docker** - Use Docker container (recommended for testing and isolation)

Choose the method that best fits your use case.

---

## Installing from Source

### Step 1: Prerequisites

Ensure you have the required tools:

```bash
# Check Python version
python --version

# Install pip if not already installed
python -m ensurepip --upgrade

# Install git (if cloning from repository)
sudo apt-get install git  # Linux
brew install git          # macOS
# Git on Windows: https://git-scm.com/download/win
```

### Step 2: Clone the Repository

```bash
# Clone the repository
git clone <repository-url>
cd murphy-system-runtime

# Or download and extract if not using git
wget <repository-url>/archive/main.zip
unzip main.zip
cd murphy-system-runtime-main
```

### Step 3: Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Upgrade pip
pip install --upgrade pip
```

### Step 4: Install Dependencies

```bash
# Install all required dependencies
pip install -r requirements_murphy_1.0.txt
```

If `requirements_murphy_1.0.txt` is not available, install dependencies manually:

```bash
# Core dependencies
pip install rich prompt-toolkit pyyaml networkx cryptography numpy

# Optional dependencies for advanced features
pip install torch transformers sentencepiece
```

### Step 5: Verify Installation

```bash
# Run health check
python -c "import src.system_integrator; print('Installation successful!')"
```

---

## Installing from Package

### Step 1: Download the Package

Download the latest package from the official repository:

```bash
# Download using wget
wget <download-url>/murphy_system_runtime.zip

# Or download using curl
curl -O <download-url>/murphy_system_runtime.zip
```

### Step 2: Extract the Package

```bash
# Extract the package
unzip murphy_system_runtime.zip
cd murphy_system_runtime
```

### Step 3: Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Upgrade pip
pip install --upgrade pip
```

### Step 4: Install Dependencies

```bash
# Install all required dependencies
pip install -r requirements_murphy_1.0.txt
```

### Step 5: Verify Installation

```bash
# Run health check
python -c "import src.system_integrator; print('Installation successful!')"
```

---

## Docker Installation

### Step 1: Install Docker

Install Docker on your system:

```bash
# Linux
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# macOS
brew install --cask docker

# Windows
# Download from https://www.docker.com/products/docker-desktop
```

### Step 2: Pull the Docker Image

```bash
# Pull the official image
docker pull murphy-system-runtime:v1.0.0
```

### Step 3: Run the Container

```bash
# Run the container
docker run -d -p 8000:8000 --name murphy-system murphy-system-runtime:v1.0.0
```

### Step 4: Verify Installation

```bash
# Check container status
docker ps

# Test the API
curl http://localhost:8000/api/health
```

### Step 5: Stop the Container

```bash
# Stop the container
docker stop murphy-system

# Remove the container
docker rm murphy-system
```

---

## Post-Installation

### Configuration

After installation, you may want to configure the system. Murphy System uses YAML
files in the `config/` directory for defaults, with environment variables always
taking precedence:

```bash
# Edit the main configuration file (LLM provider, thresholds, logging, etc.)
nano config/murphy.yaml

# Edit engine configuration (swarm size, gate parameters, orchestrator settings)
nano config/engines.yaml

# Annotated examples with documentation for every setting:
# config/murphy.yaml.example
# config/engines.yaml.example
```

### Environment Variables

Set environment variables as needed:

```bash
# Linux/macOS
export MURPHY_API_PORT=8000
export MURPHY_LOG_LEVEL=INFO
export MURPHY_CACHE_ENABLED=true

# Windows
set MURPHY_API_PORT=8000
set MURPHY_LOG_LEVEL=INFO
set MURPHY_CACHE_ENABLED=true
```

### Service Installation (Optional)

Install as a system service for automatic startup:

#### Linux (systemd)

```bash
# Create service file
sudo nano /etc/systemd/system/murphy-system.service
```

Add the following content:

```ini
[Unit]
Description=Murphy System Runtime API Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/murphy-system-runtime
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python murphy_system_1.0_runtime.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable murphy-system

# Start service
sudo systemctl start murphy-system

# Check status
sudo systemctl status murphy-system
```

---

## Verification

### Test 1: Health Check

```bash
# Start the API server
python murphy_system_1.0_runtime.py

# In another terminal, test health endpoint
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

### Test 2: System Build

```bash
# Test system building
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Build a simple web application"
  }'
```

### Test 3: Expert Generation

```bash
# Test expert generation
curl -X POST http://localhost:8000/api/experts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Need experts for a web app",
    "parameters": {
      "domain": "software"
    }
  }'
```

### Test 4: Gate Creation

```bash
# Test gate creation
curl -X POST http://localhost:8000/api/gates/create \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Create gates for a web app",
    "parameters": {
      "domain": "software"
    }
  }'
```

---

## Troubleshooting

### Issue: Python Version Incompatible

**Symptom:** Installation fails with Python version errors

**Solution:**
```bash
# Check Python version
python --version

# Install Python 3.10+ if needed
# Linux
sudo apt-get install python3.10

# macOS
brew install python@3.10

# Windows
# Download from https://www.python.org/downloads/
```

### Issue: Permission Denied

**Symptom:** Installation fails with permission errors

**Solution:**
```bash
# Use virtual environment (recommended)
python -m venv venv
source venv/bin/activate

# Or use user installation
pip install --user -r requirements_murphy_1.0.txt
```

### Issue: Port Already in Use

**Symptom:** API server won't start, port already in use

**Solution:**
```bash
# Find process using the port
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use a different port
python murphy_system_1.0_runtime.py --port 8053
```

### Issue: Dependencies Not Found

**Symptom:** Import errors for required packages

**Solution:**
```bash
# Upgrade pip
pip install --upgrade pip

# Reinstall dependencies
pip install --force-reinstall -r requirements_murphy_1.0.txt

# Or install manually
pip install rich prompt-toolkit pyyaml networkx cryptography numpy
```

### Issue: Docker Container Won't Start

**Symptom:** Docker container fails to start

**Solution:**
```bash
# Check Docker logs
docker logs murphy-system

# Check if port is available
netstat -tuln | grep 8000

# Try running without detaching to see errors
docker run -it -p 8000:8000 murphy-system-runtime:v1.0.0
```

### Issue: Slow Performance

**Symptom:** System responses are slow

**Solution:**
```bash
# Check system resources
htop

# Enable caching in config/murphy.yaml:
# cache:
#   enabled: true
#   ttl: 3600

# Or via environment variable (takes precedence over YAML):
export MURPHY_CACHE__ENABLED=true

# Increase memory allocation
export MURPHY_CACHE_SIZE=256
```

---

## Next Steps

After successful installation:

1. ✅ Read the [Quick Start Guide](QUICK_START.md)
2. ✅ Configure the system for your environment
3. ✅ Test with example workflows
4. ✅ Review the [API Documentation](../api/ENDPOINTS.md)
5. ✅ Deploy to production when ready

---

## Uninstallation

### Remove from Source

```bash
# Deactivate virtual environment
deactivate

# Remove virtual environment
rm -rf venv

# Remove source directory
rm -rf murphy-system-runtime
```

### Remove Docker Container

```bash
# Stop and remove container
docker stop murphy-system
docker rm murphy-system

# Remove image
docker rmi murphy-system-runtime:v1.0.0
```

### Remove System Service (Linux)

```bash
# Stop and disable service
sudo systemctl stop murphy-system
sudo systemctl disable murphy-system

# Remove service file
sudo rm /etc/systemd/system/murphy-system.service

# Reload systemd
sudo systemctl daemon-reload
```

---

## Support

For installation issues:

1. Check the [Troubleshooting Guide](../user_guides/TROUBLESHOOTING.md)
2. Review the [FAQ](../reference/FAQ.md)
3. Contact support: corey.gfc@gmail.com

---

## Summary

You should now have the Murphy System Runtime installed and verified. The system is ready to:

- Build autonomous systems
- Generate expert teams
- Create safety gates
- Analyze technical choices
- Validate system designs

**Next:** Read the [Quick Start Guide](QUICK_START.md) to get started!

---

**© 2025 Corey Post InonI LLC. All rights reserved.**  
**Licensed under BSL 1.1 (converts to Apache 2.0 after 4 years)**  
**Contact: corey.gfc@gmail.com**