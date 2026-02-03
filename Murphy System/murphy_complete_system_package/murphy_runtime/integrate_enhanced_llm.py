# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Integration script to add Enhanced LLM Provider to Murphy system
"""

import sys
import re

def integrate_enhanced_llm():
    """Replace old LLM provider with enhanced version"""
    
    # Read the current murphy file
    with open('murphy_complete_integrated.py', 'r') as f:
        content = f.read()
    
    # Replace the import
    old_import = "from llm_providers import LLMManager"
    new_import = "from llm_providers_enhanced import get_enhanced_llm_manager as get_llm_manager"
    
    content = content.replace(old_import, new_import)
    
    # Replace LLMManager initialization
    old_init = """    # Load Groq API keys
    groq_keys = []
    if os.path.exists('groq_keys.txt'):
        with open('groq_keys.txt', 'r') as f:
            groq_keys = [line.strip() for line in f if line.strip()]
    
    llm_manager = LLMManager(groq_api_keys=groq_keys)"""
    
    new_init = """    # Initialize Enhanced LLM Manager with rotation
    llm_manager = get_llm_manager(
        groq_keys_file='all_groq_keys.txt',
        aristotle_key_file='aristotle_key.txt'
    )"""
    
    content = content.replace(old_init, new_init)
    
    # Add new endpoints for LLM management
    new_endpoints = """

# ============================================================================
# ENHANCED LLM MANAGEMENT ENDPOINTS
# ============================================================================

@app.route('/api/llm/status', methods=['GET'])
def get_llm_status():
    &quot;&quot;&quot;Get detailed LLM provider status&quot;&quot;&quot;
    if not llm_manager:
        return jsonify({'error': 'LLM manager not available'}), 503
    
    try:
        return jsonify({
            'success': True,
            'status': llm_manager.get_status()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/llm/usage', methods=['GET'])
def get_llm_usage():
    &quot;&quot;&quot;Get LLM usage statistics&quot;&quot;&quot;
    if not llm_manager:
        return jsonify({'error': 'LLM manager not available'}), 503
    
    try:
        return jsonify({
            'success': True,
            'usage': llm_manager.get_usage_stats()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/llm/test-rotation', methods=['GET'])
def test_llm_rotation():
    &quot;&quot;&quot;Test key rotation by making multiple calls&quot;&quot;&quot;
    if not llm_manager:
        return jsonify({'error': 'LLM manager not available'}), 503
    
    try:
        num_calls = 10
        results = []
        
        for i in range(num_calls):
            result = llm_manager.generate(f"Test call {i+1}: What is 2+2?")
            results.append({
                'call': i+1,
                'provider': result['provider'],
                'key_index': result['key_index'],
                'success': result['success']
            })
        
        # Analyze distribution
        key_counts = {}
        for r in results:
            if r['key_index'] is not None:
                key_counts[r['key_index']] = key_counts.get(r['key_index'], 0) + 1
        
        return jsonify({
            'success': True,
            'calls': num_calls,
            'results': results,
            'key_distribution': key_counts,
            'unique_keys_used': len(key_counts)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/llm/test-math', methods=['POST'])
def test_llm_math():
    &quot;&quot;&quot;Test math routing to Aristotle&quot;&quot;&quot;
    if not llm_manager:
        return jsonify({'error': 'LLM manager not available'}), 503
    
    try:
        data = request.json
        prompt = data.get('prompt', 'Calculate 2+2')
        
        result = llm_manager.generate(prompt)
        
        return jsonify({
            'success': True,
            'prompt': prompt,
            'provider': result['provider'],
            'math_detected': result['math_task'],
            'response': result.get('response', '')[:500],  # First 500 chars
            'key_index': result['key_index']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
"""
    
    # Find where to insert (before if __name__)
    main_pos = content.find("if __name__ == '__main__':")
    if main_pos != -1:
        content = content[:main_pos] + new_endpoints + "\n" + content[main_pos:]
    else:
        # Append at end
        content += new_endpoints
    
    # Write back
    with open('murphy_complete_integrated.py', 'w') as f:
        f.write(content)
    
    print("✓ Enhanced LLM Provider integrated into Murphy system")
    print("\nChanges made:")
    print("  - Replaced llm_providers import with llm_providers_enhanced")
    print("  - Updated LLM manager initialization to use all 16 keys")
    print("  - Added Aristotle integration")
    print("\nNew endpoints added:")
    print("  GET  /api/llm/status - Get detailed LLM status")
    print("  GET  /api/llm/usage - Get usage statistics")
    print("  GET  /api/llm/test-rotation - Test key rotation")
    print("  POST /api/llm/test-math - Test math routing")

if __name__ == '__main__':
    integrate_enhanced_llm()