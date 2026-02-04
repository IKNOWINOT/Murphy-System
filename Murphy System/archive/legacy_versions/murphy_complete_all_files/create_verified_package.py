#!/usr/bin/env python3
"""
Murphy System - Automated Package Creation with Verification
This script ensures ALL required files are present before creating the package.
"""

import os
import zipfile
from datetime import datetime

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def check_file(filepath, expected_size=None):
    """Check if file exists and optionally verify size"""
    if os.path.exists(filepath):
        actual_size = os.path.getsize(filepath)
        if expected_size and abs(actual_size - expected_size) > 100:  # Allow 100 byte variance
            return 'warning', actual_size
        return 'ok', actual_size
    return 'missing', 0

def print_status(status, message):
    """Print colored status message"""
    if status == 'ok':
        print(f"{GREEN}✓{RESET} {message}")
    elif status == 'warning':
        print(f"{YELLOW}⚠{RESET} {message}")
    elif status == 'error':
        print(f"{RED}✗{RESET} {message}")
    else:
        print(f"{BLUE}•{RESET} {message}")

# Define all required files with expected sizes
CORE_MODULES = {
    'agent_communication_system.py': 16715,
    'agent_handoff_manager.py': 6634,
    'artifact_download_system.py': 9897,
    'artifact_generation_system.py': 25508,
    'artifact_manager.py': 14326,
    'autonomous_business_dev_implementation.py': 28991,
    'business_integrations.py': 20834,
    'command_system.py': 14109,
    'cooperative_swarm_system.py': 10605,
    'database_integration.py': 13498,
    'dynamic_projection_gates.py': 18297,
    'enhanced_gate_integration.py': 19716,
    'generative_gate_system.py': 29709,
    'learning_engine.py': 14543,
    'librarian_command_integration.py': 14302,
    'librarian_system.py': 25923,
    'llm_providers_enhanced.py': 19051,
    'monitoring_system.py': 8526,
    'multi_agent_book_generator.py': 24253,
    'payment_verification_system.py': 10661,
    'production_setup.py': 14853,
    'register_all_commands.py': 25863,
    'runtime_orchestrator_enhanced.py': 24926,
    'scheduled_automation_system.py': 16627,
    'shadow_agent_system.py': 20273,
    'swarm_knowledge_pipeline.py': 23364,
    'workflow_orchestrator.py': 17874,
    'murphy_complete_integrated.py': 82491,
}

CRITICAL_DEPENDENCIES = {
    'groq_client.py': 4933,  # CRITICAL!
    'insurance_risk_gates.py': None,
    'intelligent_system_generator.py': None,
}

UI_FILES = {
    'murphy_ui_final.html': 33115,  # MUST BE THIS SIZE
}

INSTALLATION_SCRIPTS = {
    'install.bat': None,
    'start_murphy.bat': None,
    'stop_murphy.bat': None,
    'install.sh': None,
    'start_murphy.sh': None,
    'stop_murphy.sh': None,
}

CONFIG_FILES = {
    'requirements.txt': None,  # Will check for aiohttp
    'groq_keys.txt': None,
    'aristotle_key.txt': None,
    'README.md': None,
}

def main():
    print("="*70)
    print("MURPHY SYSTEM - AUTOMATED PACKAGE CREATION")
    print("="*70)
    print()
    
    # Step 1: Check workspace files
    print(f"{BLUE}STEP 1: Checking Workspace Files{RESET}")
    print("-"*70)
    
    all_files_ok = True
    missing_files = []
    warning_files = []
    
    # Check core modules
    print(f"\n{BLUE}Core Modules (28 required):{RESET}")
    for filename, expected_size in CORE_MODULES.items():
        status, actual_size = check_file(filename, expected_size)
        if status == 'ok':
            print_status('ok', f"{filename:50} {actual_size:>10,} bytes")
        elif status == 'warning':
            print_status('warning', f"{filename:50} {actual_size:>10,} bytes (expected ~{expected_size:,})")
            warning_files.append(filename)
        else:
            print_status('error', f"{filename:50} MISSING!")
            missing_files.append(filename)
            all_files_ok = False
    
    # Check critical dependencies
    print(f"\n{BLUE}Critical Dependencies (3 required):{RESET}")
    for filename, expected_size in CRITICAL_DEPENDENCIES.items():
        status, actual_size = check_file(filename, expected_size)
        if status == 'ok':
            print_status('ok', f"{filename:50} {actual_size:>10,} bytes")
        elif status == 'warning':
            print_status('warning', f"{filename:50} {actual_size:>10,} bytes")
            warning_files.append(filename)
        else:
            print_status('error', f"{filename:50} MISSING!")
            missing_files.append(filename)
            all_files_ok = False
    
    # Check UI files
    print(f"\n{BLUE}UI Files:{RESET}")
    for filename, expected_size in UI_FILES.items():
        status, actual_size = check_file(filename, expected_size)
        if status == 'ok':
            print_status('ok', f"{filename:50} {actual_size:>10,} bytes ✓✓✓")
        elif status == 'warning':
            print_status('error', f"{filename:50} {actual_size:>10,} bytes (WRONG SIZE!)")
            all_files_ok = False
        else:
            print_status('error', f"{filename:50} MISSING!")
            missing_files.append(filename)
            all_files_ok = False
    
    # Check installation scripts
    print(f"\n{BLUE}Installation Scripts:{RESET}")
    for filename in INSTALLATION_SCRIPTS.keys():
        status, actual_size = check_file(filename)
        if status == 'ok':
            print_status('ok', f"{filename:50} {actual_size:>10,} bytes")
        else:
            print_status('error', f"{filename:50} MISSING!")
            missing_files.append(filename)
            all_files_ok = False
    
    # Check config files
    print(f"\n{BLUE}Configuration Files:{RESET}")
    for filename in CONFIG_FILES.keys():
        status, actual_size = check_file(filename)
        if status == 'ok':
            print_status('ok', f"{filename:50} {actual_size:>10,} bytes")
            
            # Special check for requirements.txt
            if filename == 'requirements.txt':
                with open(filename, 'r') as f:
                    content = f.read()
                if 'aiohttp' in content:
                    print_status('ok', f"  → aiohttp dependency present")
                else:
                    print_status('error', f"  → aiohttp dependency MISSING!")
                    all_files_ok = False
        else:
            print_status('error', f"{filename:50} MISSING!")
            missing_files.append(filename)
            all_files_ok = False
    
    # Check server configuration
    print(f"\n{BLUE}Server Configuration:{RESET}")
    if os.path.exists('murphy_complete_integrated.py'):
        with open('murphy_complete_integrated.py', 'r') as f:
            content = f.read()
        if 'murphy_ui_final.html' in content and 'send_from_directory' in content:
            # Check it's not serving the wrong file
            if "send_from_directory('.', 'murphy_ui_complete.html')" in content:
                print_status('error', "Server configured to serve murphy_ui_complete.html (WRONG!)")
                all_files_ok = False
            else:
                print_status('ok', "Server configured to serve murphy_ui_final.html")
        else:
            print_status('error', "Server configuration unclear")
            all_files_ok = False
    
    # Summary
    print()
    print("="*70)
    if all_files_ok:
        print(f"{GREEN}✓✓✓ ALL REQUIRED FILES PRESENT AND VERIFIED ✓✓✓{RESET}")
    else:
        print(f"{RED}✗✗✗ VERIFICATION FAILED ✗✗✗{RESET}")
        if missing_files:
            print(f"\n{RED}Missing files ({len(missing_files)}):{RESET}")
            for f in missing_files:
                print(f"  - {f}")
        if warning_files:
            print(f"\n{YELLOW}Warning files ({len(warning_files)}):{RESET}")
            for f in warning_files:
                print(f"  - {f}")
        print(f"\n{RED}CANNOT CREATE PACKAGE - FIX ISSUES FIRST{RESET}")
        return False
    print("="*70)
    
    # Step 2: Create package
    if not all_files_ok:
        return False
    
    print(f"\n{BLUE}STEP 2: Creating Package{RESET}")
    print("-"*70)
    
    # Create package directory
    package_dir = 'murphy_system_fixed'
    if not os.path.exists(package_dir):
        os.makedirs(package_dir)
        print_status('ok', f"Created package directory: {package_dir}")
    
    # Copy all files
    all_files = {}
    all_files.update(CORE_MODULES)
    all_files.update(CRITICAL_DEPENDENCIES)
    all_files.update(UI_FILES)
    all_files.update(INSTALLATION_SCRIPTS)
    all_files.update(CONFIG_FILES)
    
    copied_count = 0
    for filename in all_files.keys():
        if os.path.exists(filename):
            import shutil
            shutil.copy2(filename, os.path.join(package_dir, filename))
            copied_count += 1
    
    print_status('ok', f"Copied {copied_count} files to {package_dir}")
    
    # Copy documentation (optional)
    doc_files = []
    for file in os.listdir('.'):
        if file.endswith('.md') and file != 'README.md':
            import shutil
            shutil.copy2(file, os.path.join(package_dir, file))
            doc_files.append(file)
    
    if doc_files:
        print_status('ok', f"Copied {len(doc_files)} documentation files")
    
    # Create ZIP
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    zip_filename = f'murphy_system_v2.1_VERIFIED_{timestamp}.zip'
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        file_count = 0
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.join('murphy_system', file)
                zipf.write(file_path, arcname)
                file_count += 1
    
    zip_size = os.path.getsize(zip_filename)
    print_status('ok', f"Created package: {zip_filename}")
    print_status('ok', f"Package size: {zip_size:,} bytes ({zip_size/1024:.2f} KB)")
    print_status('ok', f"Total files: {file_count}")
    
    # Step 3: Verify package
    print(f"\n{BLUE}STEP 3: Verifying Package Contents{RESET}")
    print("-"*70)
    
    with zipfile.ZipFile(zip_filename, 'r') as zipf:
        zip_files = zipf.namelist()
        
        # Verify critical files
        critical_checks = {
            'murphy_system/groq_client.py': 'Groq client module',
            'murphy_system/murphy_ui_final.html': 'Fixed UI file',
            'murphy_system/murphy_complete_integrated.py': 'Main server',
            'murphy_system/requirements.txt': 'Dependencies',
        }
        
        all_verified = True
        for file, desc in critical_checks.items():
            if file in zip_files:
                info = zipf.getinfo(file)
                print_status('ok', f"{desc:40} {info.file_size:>10,} bytes")
            else:
                print_status('error', f"{desc:40} MISSING!")
                all_verified = False
        
        # Check requirements.txt has aiohttp
        req_content = zipf.read('murphy_system/requirements.txt').decode('utf-8')
        if 'aiohttp' in req_content:
            print_status('ok', "requirements.txt includes aiohttp")
        else:
            print_status('error', "requirements.txt missing aiohttp!")
            all_verified = False
        
        # Check UI file size
        ui_info = zipf.getinfo('murphy_system/murphy_ui_final.html')
        if ui_info.file_size == 33115:
            print_status('ok', f"UI file size correct: {ui_info.file_size:,} bytes")
        else:
            print_status('error', f"UI file size wrong: {ui_info.file_size:,} bytes (expected 33,115)")
            all_verified = False
    
    print()
    print("="*70)
    if all_verified:
        print(f"{GREEN}✓✓✓ PACKAGE VERIFIED AND READY ✓✓✓{RESET}")
        print()
        print(f"Package: {zip_filename}")
        print(f"Size: {zip_size:,} bytes ({zip_size/1024:.2f} KB)")
        print(f"Files: {file_count}")
        print()
        print("Next steps:")
        print("1. Extract package")
        print("2. Run: pip install -r requirements.txt")
        print("3. Start server")
        print("4. Test natural language: 'hi how ya doing?'")
    else:
        print(f"{RED}✗✗✗ PACKAGE VERIFICATION FAILED ✗✗✗{RESET}")
        return False
    print("="*70)
    
    return True

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)