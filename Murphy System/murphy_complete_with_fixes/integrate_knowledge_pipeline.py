"""
Integration script to add Knowledge Pipeline to Murphy system
"""

import sys
import re

def integrate_knowledge_pipeline():
    """Add knowledge pipeline to murphy_complete_integrated.py"""
    
    # Read the current murphy file
    with open('murphy_complete_integrated.py', 'r') as f:
        content = f.read()
    
    # Add import at the top
    import_statement = """
# Knowledge Pipeline System
from swarm_knowledge_pipeline import (
    initialize_knowledge_pipeline,
    KnowledgeBucket,
    Block,
    ConfidenceLevel,
    BlockAction,
    GlobalStateManager,
    InformationSourceDecider,
    BlockVerification,
    OrgChartLibrary,
    LibrarianCommandGenerator,
    MasterScheduler
)
"""
    
    # Find where to insert import (after other imports)
    import_pos = content.find("from datetime import datetime")
    if import_pos != -1:
        line_end = content.find("\n", import_pos)
        content = content[:line_end+1] + import_statement + content[line_end+1:]
    
    # Add initialization after LLM manager
    init_code = """

# Initialize Knowledge Pipeline System
try:
    knowledge_pipeline = initialize_knowledge_pipeline(llm_manager)
    logger.info("✓ Knowledge Pipeline System initialized")
except Exception as e:
    logger.error(f"✗ Knowledge Pipeline failed: {e}")
    knowledge_pipeline = None
"""
    
    # Find LLM manager initialization and add after it
    llm_init_pos = content.find("llm_manager = get_llm_manager(")
    if llm_init_pos != -1:
        # Find end of that section
        next_try = content.find("# Librarian System", llm_init_pos)
        if next_try != -1:
            content = content[:next_try] + init_code + "\n" + content[next_try:]
    
    # Add new endpoints
    new_endpoints = """

# ============================================================================
# KNOWLEDGE PIPELINE ENDPOINTS
# ============================================================================

@app.route('/api/pipeline/explode', methods=['POST'])
def explode_request():
    &quot;&quot;&quot;
    Explode vague request into complete automation plan
    
    Librarian generates 80% automatically, identifies what needs human input
    
    Request body:
    {
        "request": "Automate my publishing business"
    }
    &quot;&quot;&quot;
    if not knowledge_pipeline:
        return jsonify({'error': 'Knowledge pipeline not available'}), 503
    
    data = request.json
    user_request = data.get('request', '')
    
    if not user_request:
        return jsonify({'error': 'request is required'}), 400
    
    try:
        librarian = knowledge_pipeline['librarian_commands']
        plan = librarian.explode_request(user_request)
        
        return jsonify({
            'success': True,
            'plan': plan,
            'auto_generated': f"{plan.get('auto_generated_percentage', 0)}%",
            'human_input_needed': plan.get('requires_human_input', [])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pipeline/org-chart', methods=['POST'])
def generate_org_chart():
    &quot;&quot;&quot;
    Generate org chart from business description
    
    Matches to template library, adapts public strategies, solidifies for Murphy
    
    Request body:
    {
        "business_description": "Spiritual book publishing company",
        "public_strategies": ["content_first", "niche_targeting"]
    }
    &quot;&quot;&quot;
    if not knowledge_pipeline:
        return jsonify({'error': 'Knowledge pipeline not available'}), 503
    
    data = request.json
    description = data.get('business_description', '')
    strategies = data.get('public_strategies', [])
    
    if not description:
        return jsonify({'error': 'business_description is required'}), 400
    
    try:
        org_chart_lib = knowledge_pipeline['org_chart_library']
        org_chart = org_chart_lib.match_org_chart(description, strategies)
        
        return jsonify({
            'success': True,
            'org_chart': org_chart
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pipeline/block/verify', methods=['POST'])
def verify_block():
    &quot;&quot;&quot;
    Verify a block and get Magnify/Simplify/Solidify recommendations
    
    Request body:
    {
        "block_id": "block_123",
        "block_name": "Market Research",
        "block_content": "Research spiritual book market...",
        "confidence": "yellow",
        "action": "magnify"  // or "simplify" or "solidify"
    }
    &quot;&quot;&quot;
    if not knowledge_pipeline:
        return jsonify({'error': 'Knowledge pipeline not available'}), 503
    
    data = request.json
    block_id = data.get('block_id', '')
    block_name = data.get('block_name', '')
    block_content = data.get('block_content', '')
    confidence = data.get('confidence', 'yellow')
    action = data.get('action', 'solidify')
    
    if not all([block_id, block_name, block_content]):
        return jsonify({'error': 'block_id, block_name, and block_content are required'}), 400
    
    try:
        # Create block
        block = Block(
            block_id=block_id,
            name=block_name,
            content=block_content,
            confidence=ConfidenceLevel(confidence)
        )
        
        # Get verification
        verifier = knowledge_pipeline['block_verification']
        
        if action == 'magnify':
            result = verifier.magnify(block)
        elif action == 'simplify':
            result = verifier.simplify(block)
        else:  # solidify
            result = verifier.solidify(block)
        
        return jsonify({
            'success': True,
            'action': action,
            'result': result
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pipeline/block/update', methods=['POST'])
def update_block_cascade():
    &quot;&quot;&quot;
    Update a block and get cascade effects
    
    Shows which downstream blocks need regeneration
    
    Request body:
    {
        "block_id": "block_123",
        "new_content": "Updated content..."
    }
    &quot;&quot;&quot;
    if not knowledge_pipeline:
        return jsonify({'error': 'Knowledge pipeline not available'}), 503
    
    data = request.json
    block_id = data.get('block_id', '')
    new_content = data.get('new_content', '')
    
    if not all([block_id, new_content]):
        return jsonify({'error': 'block_id and new_content are required'}), 400
    
    try:
        global_state = knowledge_pipeline['global_state']
        affected = global_state.update_block(block_id, new_content)
        
        # Get regeneration order
        regen_order = global_state.get_regeneration_order(affected)
        
        return jsonify({
            'success': True,
            'updated': block_id,
            'affected_blocks': affected,
            'regeneration_order': regen_order,
            'message': f'{len(affected)} blocks need regeneration'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pipeline/info-source', methods=['POST'])
def decide_info_source():
    &quot;&quot;&quot;
    Decide where information should come from
    
    Determines: user provides, AI generates, or hire external
    
    Request body:
    {
        "information_needed": "Brand guidelines and color schemes",
        "user_has_capability": true
    }
    &quot;&quot;&quot;
    if not knowledge_pipeline:
        return jsonify({'error': 'Knowledge pipeline not available'}), 503
    
    data = request.json
    info_needed = data.get('information_needed', '')
    user_capability = data.get('user_has_capability', False)
    
    if not info_needed:
        return jsonify({'error': 'information_needed is required'}), 400
    
    try:
        decider = knowledge_pipeline['info_decider']
        decision = decider.decide_source(info_needed, user_capability)
        
        return jsonify({
            'success': True,
            'decision': decision
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pipeline/schedule', methods=['POST'])
def schedule_tasks():
    &quot;&quot;&quot;
    Schedule tasks with master scheduler
    
    Aligns priority, respects dependencies, manages feedback loops
    
    Request body:
    {
        "blocks": [
            {
                "block_id": "block_1",
                "name": "Research",
                "content": "...",
                "confidence": "green",
                "dependencies": [],
                "affects": ["block_2", "block_3"]
            }
        ]
    }
    &quot;&quot;&quot;
    if not knowledge_pipeline:
        return jsonify({'error': 'Knowledge pipeline not available'}), 503
    
    data = request.json
    blocks_data = data.get('blocks', [])
    
    if not blocks_data:
        return jsonify({'error': 'blocks are required'}), 400
    
    try:
        global_state = knowledge_pipeline['global_state']
        scheduler = knowledge_pipeline['master_scheduler']
        
        # Create blocks and register
        blocks = []
        for block_data in blocks_data:
            block = Block(
                block_id=block_data.get('block_id'),
                name=block_data.get('name'),
                content=block_data.get('content', ''),
                confidence=ConfidenceLevel(block_data.get('confidence', 'yellow')),
                dependencies=block_data.get('dependencies', []),
                affects=block_data.get('affects', [])
            )
            blocks.append(block)
            global_state.register_block(block)
        
        # Schedule
        execution_order = scheduler.schedule_tasks(blocks)
        
        return jsonify({
            'success': True,
            'execution_order': execution_order,
            'total_tasks': len(execution_order)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pipeline/status', methods=['GET'])
def pipeline_status():
    &quot;&quot;&quot;Get knowledge pipeline system status&quot;&quot;&quot;
    if not knowledge_pipeline:
        return jsonify({'error': 'Knowledge pipeline not available'}), 503
    
    try:
        global_state = knowledge_pipeline['global_state']
        
        return jsonify({
            'success': True,
            'available': True,
            'components': {
                'global_state': True,
                'info_decider': True,
                'block_verification': True,
                'org_chart_library': True,
                'librarian_commands': True,
                'master_scheduler': True
            },
            'stats': {
                'registered_blocks': len(global_state.state),
                'timeline_events': len(global_state.timeline),
                'cascade_queue': len(global_state.cascade_queue)
            }
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
    
    print("✓ Knowledge Pipeline integrated into Murphy system")
    print("\nNew endpoints added:")
    print("  POST /api/pipeline/explode - Explode vague request into plan")
    print("  POST /api/pipeline/org-chart - Generate org chart from description")
    print("  POST /api/pipeline/block/verify - Magnify/Simplify/Solidify blocks")
    print("  POST /api/pipeline/block/update - Update block and see cascade")
    print("  POST /api/pipeline/info-source - Decide information source")
    print("  POST /api/pipeline/schedule - Schedule tasks with dependencies")
    print("  GET  /api/pipeline/status - Get pipeline status")

if __name__ == '__main__':
    integrate_knowledge_pipeline()