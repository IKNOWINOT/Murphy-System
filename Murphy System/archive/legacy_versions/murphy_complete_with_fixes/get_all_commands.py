#!/usr/bin/env python3
"""
Extract all commands and map them to endpoints
"""

import re

# Read the murphy_complete_integrated.py file
with open('murphy_complete_integrated.py', 'r') as f:
    content = f.read()

# Extract all routes
routes = re.findall(r"@app\.route\('([^']+)'[^)]*\)", content)

print("="*80)
print(f"TOTAL ENDPOINTS: {len(routes)}")
print("="*80)
print()

# Categorize by prefix
categories = {}
for route in routes:
    if route == '/':
        continue
    parts = route.split('/')
    if len(parts) >= 3:
        category = parts[2]  # /api/CATEGORY/...
        if category not in categories:
            categories[category] = []
        categories[category].append(route)

for category, endpoints in sorted(categories.items()):
    print(f"\n{category.upper()} ({len(endpoints)} endpoints):")
    for endpoint in sorted(endpoints):
        print(f"  {endpoint}")

print(f"\n\nTOTAL CATEGORIES: {len(categories)}")
print(f"TOTAL ENDPOINTS: {len(routes)}")