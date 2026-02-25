"""
Script to add authentication decorators to all write endpoints in murphy_backend_complete.py
"""

# List of POST endpoints that need authentication (excluding auth endpoints)
post_endpoints_to_protect = [
    '/api/monitoring/analyze',
    '/api/artifacts/generate',
    '/api/artifacts/<artifact_id>/convert',
    '/api/shadow/observe',
    '/api/shadow/learn',
    '/api/shadow/proposals/<agent_id>/<proposal_id>/approve',
    '/api/shadow/proposals/<agent_id>/<proposal_id>/reject',
    '/api/shadow/analyze',
    '/api/cooperative/workflows',
    '/api/cooperative/workflows/<workflow_id>/execute',
    '/api/cooperative/handoffs',
    '/api/cooperative/handoffs/<handoff_id>/confirm',
    '/api/cooperative/messages',
    '/api/attention/form',
    '/api/attention/set-role',
    '/api/attention/reset',
]

# PUT endpoints to protect
put_endpoints_to_protect = [
    '/api/artifacts/<artifact_id>',
]

# DELETE endpoints to protect
delete_endpoints_to_protect = [
    '/api/artifacts/<artifact_id>',
]

def add_auth_decorators():
    """Add @require_auth decorator to all write endpoints"""
    
    with open('murphy_backend_complete.py', 'r') as f:
        content = f.read()
    
    # Add decorator to each POST endpoint
    for endpoint in post_endpoints_to_protect:
        old_pattern = f"@app.route('{endpoint}', methods=['POST'])"
        new_pattern = f"@app.route('{endpoint}', methods=['POST'])\n@require_auth(auth_system if AUTH_AVAILABLE else None)"
        content = content.replace(old_pattern, new_pattern)
    
    # Add decorator to each PUT endpoint
    for endpoint in put_endpoints_to_protect:
        old_pattern = f"@app.route('{endpoint}', methods=['PUT'])"
        new_pattern = f"@app.route('{endpoint}', methods=['PUT'])\n@require_auth(auth_system if AUTH_AVAILABLE else None)"
        content = content.replace(old_pattern, new_pattern)
    
    # Add decorator to each DELETE endpoint
    for endpoint in delete_endpoints_to_protect:
        old_pattern = f"@app.route('{endpoint}', methods=['DELETE'])"
        new_pattern = f"@app.route('{endpoint}', methods=['DELETE'])\n@require_auth(auth_system if AUTH_AVAILABLE else None)"
        content = content.replace(old_pattern, new_pattern)
    
    # Write back
    with open('murphy_backend_complete.py', 'w') as f:
        f.write(content)
    
    print(f"✓ Added @require_auth decorators to {len(post_endpoints_to_protect)} POST endpoints")
    print(f"✓ Added @require_auth decorators to {len(put_endpoints_to_protect)} PUT endpoints")
    print(f"✓ Added @require_auth decorators to {len(delete_endpoints_to_protect)} DELETE endpoints")

if __name__ == '__main__':
    add_auth_decorators()