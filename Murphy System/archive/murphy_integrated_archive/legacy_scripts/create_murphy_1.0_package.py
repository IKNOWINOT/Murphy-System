"""
Murphy System 1.0 - Package Creator

This script creates a complete, production-ready package of Murphy System 1.0.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: Apache License 2.0
"""

import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime
import json

def create_package():
    """Create Murphy System 1.0 package"""
    
    print("\n" + "="*80)
    print("MURPHY SYSTEM 1.0 - PACKAGE CREATOR")
    print("="*80 + "\n")
    
    # Package name
    package_name = f"murphy_system_1.0_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    package_dir = Path(package_name)
    
    # Create package directory
    print(f"Creating package directory: {package_name}")
    package_dir.mkdir(exist_ok=True)
    
    # Files to include
    files_to_copy = [
        # Core runtime
        "murphy_system_1.0_runtime.py",
        "requirements_murphy_1.0.txt",
        "start_murphy_1.0.sh",
        "start_murphy_1.0.bat",
        
        # Documentation
        "README_MURPHY_1.0.md",
        "MURPHY_1.0_QUICK_START.md",
        "MURPHY_SYSTEM_1.0_SPECIFICATION.md",
        "INTEGRATION_ENGINE_COMPLETE.md",
        "COMPLETE_INTEGRATION_ANALYSIS.md",
        "MURPHY_SELF_INTEGRATION_CAPABILITIES.md",
        
        # Key components
        "universal_control_plane.py",
        "inoni_business_automation.py",
        "two_phase_orchestrator.py",
        "murphy_final_runtime.py",
        
        # Test files
        "test_integration_engine.py",
    ]
    
    # Directories to copy
    dirs_to_copy = [
        "src",
        "bots",
        "tests",
        "config",
        "examples",
    ]
    
    print("\nCopying files...")
    copied_files = 0
    
    # Copy individual files
    for file in files_to_copy:
        src = Path(file)
        if src.exists():
            dst = package_dir / file
            shutil.copy2(src, dst)
            copied_files += 1
            print(f"  ✓ {file}")
        else:
            print(f"  ⚠ {file} (not found)")
    
    # Copy directories
    print("\nCopying directories...")
    copied_dirs = 0
    
    for dir_name in dirs_to_copy:
        src_dir = Path(dir_name)
        if src_dir.exists():
            dst_dir = package_dir / dir_name
            shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
            copied_dirs += 1
            
            # Count files in directory
            file_count = sum(1 for _ in dst_dir.rglob('*') if _.is_file())
            print(f"  ✓ {dir_name}/ ({file_count} files)")
        else:
            print(f"  ⚠ {dir_name}/ (not found)")
    
    # Create package metadata
    print("\nCreating package metadata...")
    metadata = {
        "name": "Murphy System",
        "version": "1.0.0",
        "description": "Universal AI Automation System",
        "owner": "Inoni Limited Liability Company",
        "creator": "Corey Post",
        "license": "Apache License 2.0",
        "created_at": datetime.now().isoformat(),
        "components": {
            "original_runtime": "319 Python files, 67 directories",
            "phase_implementations": "Phase 1-5 (forms, validation, correction, learning)",
            "control_plane": "7 modular engines, 6 control types",
            "business_automation": "5 engines (sales, marketing, R&D, business, production)",
            "integration_engine": "6 components (HITL, safety testing, capability extraction)",
            "orchestrator": "2-phase execution (setup → execute)"
        },
        "capabilities": [
            "Universal Automation (factory, content, data, system, agent, business)",
            "Self-Integration (GitHub, APIs, hardware)",
            "Self-Improvement (correction learning, shadow agent)",
            "Self-Operation (Inoni business automation)",
            "Safety & Governance (HITL, Murphy validation)",
            "Scalability (Kubernetes-ready)",
            "Monitoring (Prometheus + Grafana)"
        ],
        "files": {
            "copied_files": copied_files,
            "copied_directories": copied_dirs
        }
    }
    
    metadata_file = package_dir / "PACKAGE_METADATA.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"  ✓ PACKAGE_METADATA.json")
    
    # Create .env template
    print("\nCreating .env template...")
    env_template = """# Murphy System 1.0 - Environment Configuration
# Copyright © 2020 Inoni Limited Liability Company

# Core Configuration
MURPHY_VERSION=1.0.0
MURPHY_ENV=production
MURPHY_PORT=6666

# Database (optional)
# DATABASE_URL=postgresql://user:pass@localhost:5432/murphy
# REDIS_URL=redis://localhost:6379

# API Keys (add your keys)
# GROQ_API_KEY=your_groq_key
# OPENAI_API_KEY=your_openai_key

# Integration Keys (add as needed)
# GITHUB_TOKEN=your_github_token
# STRIPE_API_KEY=your_stripe_key
# PAYPAL_CLIENT_ID=your_paypal_id
# PAYPAL_CLIENT_SECRET=your_paypal_secret

# Security (generate secure keys)
# JWT_SECRET=your_jwt_secret
# ENCRYPTION_KEY=your_encryption_key

# Monitoring (optional)
# PROMETHEUS_PORT=9090
# GRAFANA_PORT=3000
"""
    
    env_file = package_dir / ".env.template"
    with open(env_file, 'w') as f:
        f.write(env_template)
    print(f"  ✓ .env.template")
    
    # Create installation instructions
    print("\nCreating installation instructions...")
    install_instructions = """# Murphy System 1.0 - Installation Instructions

## Quick Install

### Linux/Mac
```bash
# 1. Copy .env.template to .env and configure
cp .env.template .env
nano .env  # Add your API keys

# 2. Make startup script executable
chmod +x start_murphy_1.0.sh

# 3. Start Murphy
./start_murphy_1.0.sh
```

### Windows
```cmd
REM 1. Copy .env.template to .env and configure
copy .env.template .env
notepad .env  REM Add your API keys

REM 2. Start Murphy
start_murphy_1.0.bat
```

## Access Murphy

- API Documentation: http://localhost:6666/docs
- Health Check: http://localhost:6666/api/health
- System Status: http://localhost:6666/api/status
- System Info: http://localhost:6666/api/info

## Next Steps

1. Read MURPHY_1.0_QUICK_START.md
2. Try example use cases
3. Add your first integration
4. Run business automation

## Support

- Documentation: See README_MURPHY_1.0.md
- Issues: GitHub Issues
- Email: support@ninjatech.ai
"""
    
    install_file = package_dir / "INSTALL.md"
    with open(install_file, 'w') as f:
        f.write(install_instructions)
    print(f"  ✓ INSTALL.md")
    
    # Create zip archive
    print("\nCreating zip archive...")
    zip_name = f"{package_name}.zip"
    
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(package_dir.parent)
                zipf.write(file_path, arcname)
    
    # Get zip size
    zip_size = Path(zip_name).stat().st_size / (1024 * 1024)  # MB
    
    print(f"  ✓ {zip_name} ({zip_size:.2f} MB)")
    
    # Summary
    print("\n" + "="*80)
    print("PACKAGE CREATION COMPLETE")
    print("="*80)
    print(f"\n📦 Package: {zip_name}")
    print(f"📊 Size: {zip_size:.2f} MB")
    print(f"📁 Files: {copied_files} individual files")
    print(f"📂 Directories: {copied_dirs} directories")
    print(f"\n✅ Murphy System 1.0 is ready for distribution!")
    print(f"\n📖 Next steps:")
    print(f"   1. Extract {zip_name}")
    print(f"   2. Read INSTALL.md")
    print(f"   3. Configure .env")
    print(f"   4. Run start_murphy_1.0.sh (or .bat)")
    print(f"\n🚀 Welcome to Murphy System 1.0!\n")
    
    return zip_name, zip_size


if __name__ == "__main__":
    try:
        zip_name, zip_size = create_package()
    except Exception as e:
        print(f"\n❌ Error creating package: {e}")
        import traceback
        traceback.print_exc()