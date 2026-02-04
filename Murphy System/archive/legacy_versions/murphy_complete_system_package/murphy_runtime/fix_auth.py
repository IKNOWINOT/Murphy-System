# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

#!/usr/bin/env python3
"""
Fix auth decorator issues by adding pass-through decorators
"""

with open('murphy_backend_complete.py', 'r') as f:
    content = f.read()

# Add pass-through decorators after the import section
insert_point = content.find('# Initialize Flask app')
if insert_point == -1:
    insert_point = content.find('app = Flask(')

if insert_point != -1:
    pass_through_decorators = '''
# ============================================================================
# PASS-THROUGH DECORATORS (for when auth is not available)
# ============================================================================

def pass_through_decorator(*args, **kwargs):
    """Decorator that passes through when auth is not available"""
    def decorator(func):
        return func
    return decorator

# Use pass-through decorators when auth is not available
if not AUTH_AVAILABLE:
    require_auth = pass_through_decorator
    validate_input = pass_through_decorator
    rate_limit = pass_through_decorator

'''

    content = content[:insert_point] + pass_through_decorators + content[insert_point:]
    
    with open('murphy_backend_complete.py', 'w') as f:
        f.write(content)
    
    print("✓ Added pass-through decorators")
else:
    print("✗ Could not find insertion point")