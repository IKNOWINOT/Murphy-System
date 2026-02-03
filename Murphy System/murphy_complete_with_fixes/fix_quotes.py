#!/usr/bin/env python3
"""
Fix all HTML entity quotes in the backend file.
"""

# Read the file
with open('/workspace/murphy_backend_complete.py', 'r') as f:
    content = f.read()

# Replace HTML entities with proper quotes
content = content.replace('&quot;', '"')
content = content.replace('&apos;', "'")

# Write back
with open('/workspace/murphy_backend_complete.py', 'w') as f:
    f.write(content)

print("Fixed all HTML entity quotes")