# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

#!/usr/bin/env python3
"""
Diagnostic script to check Murphy installation
"""

import sys
import os

print("="*70)
print("MURPHY INSTALLATION DIAGNOSTIC")
print("="*70)
print()

# Check 1: Python version
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print()

# Check 2: Current directory
print(f"Current directory: {os.getcwd()}")
print()

# Check 3: Check if requirements.txt exists
if os.path.exists('requirements.txt'):
    print("✓ requirements.txt found")
    with open('requirements.txt', 'r') as f:
        content = f.read()
    if 'aiohttp' in content:
        print("✓ requirements.txt contains aiohttp")
    else:
        print("✗ requirements.txt MISSING aiohttp!")
else:
    print("✗ requirements.txt NOT FOUND!")
    print("  Are you in the murphy_system directory?")
print()

# Check 4: Try importing aiohttp
print("Checking installed packages:")
try:
    import aiohttp
    print(f"✓ aiohttp installed: version {aiohttp.__version__}")
except ImportError as e:
    print(f"✗ aiohttp NOT installed: {e}")
    print()
    print("FIX: Run this command:")
    print("  pip install aiohttp==3.9.1")
    print()

# Check 5: Try importing nest_asyncio
try:
    import nest_asyncio
    print(f"✓ nest_asyncio installed")
except ImportError:
    print(f"✗ nest_asyncio NOT installed")
    print("FIX: Run this command:")
    print("  pip install nest-asyncio==1.5.8")
    print()

# Check 6: Try importing groq
try:
    import groq
    print(f"✓ groq installed")
except ImportError:
    print(f"✗ groq NOT installed")
    print("FIX: Run this command:")
    print("  pip install groq==0.4.1")
    print()

# Check 7: Check if groq_client.py exists
if os.path.exists('groq_client.py'):
    size = os.path.getsize('groq_client.py')
    print(f"✓ groq_client.py found ({size:,} bytes)")
    if size == 4933:
        print("  ✓ Correct size (4,933 bytes)")
    else:
        print(f"  ⚠ Size mismatch (expected 4,933 bytes)")
else:
    print("✗ groq_client.py NOT FOUND!")
    print("  You may be in the wrong directory")
print()

# Check 8: Check if murphy_complete_integrated.py exists
if os.path.exists('murphy_complete_integrated.py'):
    print("✓ murphy_complete_integrated.py found")
else:
    print("✗ murphy_complete_integrated.py NOT FOUND!")
    print("  You are NOT in the murphy_system directory!")
print()

# Summary
print("="*70)
print("SUMMARY")
print("="*70)

missing = []
if not os.path.exists('requirements.txt'):
    missing.append("requirements.txt")
if not os.path.exists('groq_client.py'):
    missing.append("groq_client.py")
if not os.path.exists('murphy_complete_integrated.py'):
    missing.append("murphy_complete_integrated.py")

try:
    import aiohttp
except ImportError:
    missing.append("aiohttp (not installed)")

try:
    import nest_asyncio
except ImportError:
    missing.append("nest_asyncio (not installed)")

if missing:
    print(f"✗ Missing {len(missing)} items:")
    for item in missing:
        print(f"  - {item}")
    print()
    print("ACTION REQUIRED:")
    if "aiohttp (not installed)" in missing:
        print("  1. Run: pip install -r requirements.txt")
    if any(f in missing for f in ["requirements.txt", "groq_client.py", "murphy_complete_integrated.py"]):
        print("  2. Make sure you're in the murphy_system directory")
        print("     Run: cd murphy_system")
else:
    print("✓✓✓ ALL CHECKS PASSED ✓✓✓")
    print()
    print("Your installation is correct!")
    print("You can start the server with: start_murphy.bat")

print("="*70)