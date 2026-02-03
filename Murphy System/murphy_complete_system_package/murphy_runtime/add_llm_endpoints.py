# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

#!/usr/bin/env python3
"""
Add LLM API endpoints to murphy_backend_complete.py.
"""

# Read the file
with open('/workspace/murphy_backend_complete.py', 'r') as f:
    lines = f.readlines()

# Find the SERVER STARTUP section
insert_index = None
for i, line in enumerate(lines):
    if "# SERVER STARTUP" in line:
        insert_index = i
        break

if insert_index is None:
    print("Could not find SERVER STARTUP section")
    exit(1)

# Insert LLM endpoints before SERVER STARTUP
llm_endpoints = """
# ============================================================================
# LLM API ENDPOINTS
# ============================================================================

@app.route('/api/llm/generate', methods=['POST'])
def llm_generate():
    &quot;&quot;&quot;Generate LLM response.&quot;&quot;&quot;
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({
                'success': False,
                'error': 'No prompt provided'
            }), 400
        
        if not LLM_AVAILABLE or not llm_manager:
            return jsonify({
                'success': False,
                'error': 'LLM system not available'
            }), 500
        
        result = llm_manager.generate(prompt)
        
        return jsonify({
            'success': result['success'],
            'response': result['response'],
            'provider': result['provider'],
            'demo_mode': result['demo_mode']
        })
    
    except Exception as e:
        logger.error(f"LLM generate error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/llm/status', methods=['GET'])
def llm_status():
    &quot;&quot;&quot;Get LLM system status.&quot;&quot;&quot;
    try:
        if not LLM_AVAILABLE or not llm_manager:
            return jsonify({
                'success': False,
                'available': False,
                'providers': []
            })
        
        status = llm_manager.get_status()
        
        return jsonify({
            'success': True,
            'available': True,
            'total_providers': status['total_providers'],
            'available_providers': status['available_providers'],
            'providers': status['providers']
        })
    
    except Exception as e:
        logger.error(f"LLM status error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


"""

lines.insert(insert_index, llm_endpoints)

# Write back
with open('/workspace/murphy_backend_complete.py', 'w') as f:
    f.writelines(lines)

print(f"✓ LLM endpoints added at line {insert_index}")