#!/usr/bin/env python3
import os
import sys

# Get all Python files
py_files = []
for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.py'):
            py_files.append(os.path.join(root, f))

# Get all HTML files
html_files = []
for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.html'):
            html_files.append(os.path.join(root, f))

print("PYTHON FILES:")
for f in sorted(py_files):
    print(f"  {f}")

print("\nHTML FILES:")
for f in sorted(html_files):
    print(f"  {f}")

sys.exit(0)