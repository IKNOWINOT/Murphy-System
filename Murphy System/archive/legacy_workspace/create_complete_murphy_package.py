"""
Create Complete Murphy System Installation Package
Includes all original runtime files + new Phase 1-5 implementations
"""

import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

def create_complete_package():
    """Create complete Murphy system package with all components"""
    
    print("Creating Complete Murphy System Installation Package...")
    print("=" * 60)
    
    # Create package directory
    package_dir = Path("murphy_complete_system_package")
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir()
    
    # 1. Copy ALL original Murphy runtime files
    print("\n1. Copying original Murphy runtime system...")
    original_dir = Path("murphy_complete_all_files")
    runtime_dir = package_dir / "murphy_runtime"
    runtime_dir.mkdir()
    
    if original_dir.exists():
        # Copy all Python files
        py_files = list(original_dir.glob("*.py"))
        print(f"   Found {len(py_files)} Python files")
        for py_file in py_files:
            shutil.copy2(py_file, runtime_dir / py_file.name)
        
        # Copy all HTML files
        html_files = list(original_dir.glob("*.html"))
        print(f"   Found {len(html_files)} HTML files")
        for html_file in html_files:
            shutil.copy2(html_file, runtime_dir / html_file.name)
        
        # Copy all markdown documentation
        md_files = list(original_dir.glob("*.md"))
        print(f"   Found {len(md_files)} documentation files")
        for md_file in md_files:
            shutil.copy2(md_file, runtime_dir / md_file.name)
    
    # 2. Copy new Phase 1-5 implementations
    print("\n2. Copying Phase 1-5 implementations...")
    impl_source = Path("murphy_implementation")
    impl_dest = package_dir / "murphy_implementation"
    
    if impl_source.exists():
        shutil.copytree(impl_source, impl_dest, dirs_exist_ok=True)
        print("   ✓ Phase 1-5 implementations copied")
    
    # 3. Create main requirements.txt combining all dependencies
    print("\n3. Creating combined requirements.txt...")
    requirements = """# Murphy System - Complete Requirements
# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

# Core Dependencies
flask==3.0.0
flask-socketio==5.3.5
flask-cors==4.0.0
python-socketio==5.10.0
python-engineio==4.8.0

# FastAPI (for new Phase 1-5 APIs)
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.3

# Database
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
redis==5.0.1

# LLM Integration
groq==0.4.2
openai==1.10.0
anthropic==0.8.1

# HTTP and Async
aiohttp==3.9.1
httpx==0.26.0
requests==2.31.0

# Data Processing
pandas==2.1.4
numpy==1.26.3

# Machine Learning (for Shadow Agent)
scikit-learn==1.4.0

# Utilities
python-dotenv==1.0.0
pyyaml==6.0.1
"""
    
    with open(package_dir / "requirements.txt", "w") as f:
        f.write(requirements)
    print("   ✓ requirements.txt created")
    
    # 4. Create installation script
    print("\n4. Creating installation script...")
    install_script = """#!/bin/bash
# Murphy System Installation Script
# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

echo "=========================================="
echo "Murphy System Installation"
echo "Copyright © 2020 Inoni Limited Liability Company"
echo "Created by: Corey Post"
echo "=========================================="

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "To start the Murphy Runtime System:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run: python murphy_runtime/murphy_complete_integrated.py"
echo ""
echo "To use Phase 1-5 implementations:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run: python -m murphy_implementation.main"
echo ""
"""
    
    with open(package_dir / "install.sh", "w") as f:
        f.write(install_script)
    os.chmod(package_dir / "install.sh", 0o755)
    print("   ✓ install.sh created")
    
    # Windows installation script
    install_bat = """@echo off
REM Murphy System Installation Script
REM Copyright (C) 2020 Inoni Limited Liability Company. All rights reserved.
REM Created by: Corey Post

echo ==========================================
echo Murphy System Installation
echo Copyright (C) 2020 Inoni Limited Liability Company
echo Created by: Corey Post
echo ==========================================

REM Check Python version
python --version

REM Create virtual environment
echo.
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\\Scripts\\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo.
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo ==========================================
echo Installation Complete!
echo ==========================================
echo.
echo To start the Murphy Runtime System:
echo   1. Activate virtual environment: venv\\Scripts\\activate.bat
echo   2. Run: python murphy_runtime\\murphy_complete_integrated.py
echo.
echo To use Phase 1-5 implementations:
echo   1. Activate virtual environment: venv\\Scripts\\activate.bat
echo   2. Run: python -m murphy_implementation.main
echo.
pause
"""
    
    with open(package_dir / "install.bat", "w") as f:
        f.write(install_bat)
    print("   ✓ install.bat created")
    
    # 5. Create comprehensive README
    print("\n5. Creating README...")
    readme = """# Murphy System - Complete Installation Package

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
venv\\Scripts\\activate.bat

# Start Murphy Runtime System
python murphy_runtime\\murphy_complete_integrated.py
```

## Usage

### Starting the Original Murphy Runtime

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\\Scripts\\activate.bat  # Windows

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
"""
    
    with open(package_dir / "README.md", "w") as f:
        f.write(readme)
    print("   ✓ README.md created")
    
    # 6. Copy all documentation and LICENSE
    print("\n6. Copying documentation and LICENSE...")
    docs_to_copy = [
        "FINAL_SYSTEM_DOCUMENTATION.md",
        "PROJECT_COMPLETION_SUMMARY.md",
        "PHASE_4_COMPLETION_SUMMARY.md",
        "PHASE_5_COMPLETION_SUMMARY.md",
        "LICENSE",
    ]
    
    for doc in docs_to_copy:
        if Path(doc).exists():
            shutil.copy2(doc, package_dir / doc)
            print(f"   ✓ {doc} copied")
    
    # 7. Update copyright in all files
    print("\n7. Updating copyright information...")
    copyright_notice = """# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post
"""
    
    # Add copyright to main Python files
    for py_file in (package_dir / "murphy_runtime").glob("*.py"):
        try:
            with open(py_file, 'r') as f:
                content = f.read()
            
            # Add copyright at the top if not already present
            if "Inoni Limited Liability Company" not in content:
                with open(py_file, 'w') as f:
                    f.write(copyright_notice + "\n" + content)
        except Exception as e:
            print(f"   Warning: Could not update {py_file.name}: {e}")
    
    print("   ✓ Copyright information updated")
    
    # 8. Create ZIP package
    print("\n8. Creating ZIP package...")
    zip_filename = "murphy_complete_system_v1.0.0.zip"
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(package_dir.parent)
                zipf.write(file_path, arcname)
    
    # Get package size
    package_size = os.path.getsize(zip_filename) / (1024 * 1024)  # MB
    
    print(f"   ✓ Package created: {zip_filename}")
    print(f"   ✓ Package size: {package_size:.2f} MB")
    
    # 9. Create package manifest
    print("\n9. Creating package manifest...")
    
    # Count files
    runtime_files = len(list((package_dir / "murphy_runtime").glob("*.py")))
    impl_files = len(list((package_dir / "murphy_implementation").rglob("*.py")))
    doc_files = len(list(package_dir.glob("*.md")))
    
    manifest = f"""# Murphy System Package Manifest

**Package:** murphy_complete_system_v1.0.0.zip
**Size:** {package_size:.2f} MB
**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Copyright © 2020 Inoni Limited Liability Company. All rights reserved.**
**Created by: Corey Post**

## Contents

### Murphy Runtime System
- Python files: {runtime_files}
- Location: murphy_runtime/
- Main file: murphy_complete_integrated.py

### Phase 1-5 Implementations
- Python files: {impl_files}
- Location: murphy_implementation/
- Main file: murphy_implementation/main.py

### Documentation
- Documentation files: {doc_files}
- Complete API reference
- User guides
- Deployment guides
- Operations runbooks

### Installation Scripts
- install.sh (Linux/Mac)
- install.bat (Windows)
- requirements.txt

## Installation

```bash
# Extract package
unzip murphy_complete_system_v1.0.0.zip
cd murphy_complete_system_package

# Run installation
./install.sh  # Linux/Mac
# or
install.bat   # Windows
```

## Quick Start

```bash
# Activate environment
source venv/bin/activate

# Start Murphy Runtime
python murphy_runtime/murphy_complete_integrated.py

# Access at http://localhost:3002
```

## Version Information

- Murphy Runtime: Original System
- Phase 1-5: v1.0.0
- Package: v1.0.0
- Python: 3.11+

## License

Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
Created by: Corey Post
"""
    
    with open(package_dir / "MANIFEST.md", "w") as f:
        f.write(manifest)
    print("   ✓ MANIFEST.md created")
    
    # Summary
    print("\n" + "=" * 60)
    print("PACKAGE CREATION COMPLETE!")
    print("=" * 60)
    print(f"\nPackage: {zip_filename}")
    print(f"Size: {package_size:.2f} MB")
    print(f"\nContents:")
    print(f"  - Murphy Runtime files: {runtime_files}")
    print(f"  - Phase 1-5 implementation files: {impl_files}")
    print(f"  - Documentation files: {doc_files}")
    print(f"\nCopyright © 2020 Inoni Limited Liability Company")
    print(f"Created by: Corey Post")
    print("\nReady for distribution!")

if __name__ == "__main__":
    create_complete_package()