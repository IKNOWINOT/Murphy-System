# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Integration script to add Enhanced Runtime Orchestrator to Murphy system
"""

import sys
import re

def integrate_enhanced_runtime():
    """Add Enhanced Runtime Orchestrator to Murphy"""
    
    # Read the current murphy file
    with open('murphy_complete_integrated.py', 'r') as f:
        content = f.read()
    
    # Add import at the top
    import_statement = """
# Enhanced Runtime Orchestrator with Dynamic Agent Generation
from runtime_orchestrator_enhanced import (
    get_orchestrator,
    reset_orchestrator,
    RuntimeOrchestrator,
    DynamicAgentGenerator,
    CollectiveMind,
    ParallelExecutor,
    GeneratedAgent
)
"""
    
    # Find where to insert import (after other imports)
    import_pos = content.find("from datetime import datetime")
    if import_pos != -1:
        # Find end of that line
        line_end = content.find("\n", import_pos)
        content = content[:line_end+1] + import_statement + content[line_end+1:]
    
    # Initialize the enhanced orchestrator in the main initialization section
    # Find where llm_manager is initialized
    init_pattern = r'llm_manager\s*=\s*LLMManager\(\)'
    init_match = re.search(init_pattern, content)
    
    if init_match:
        init_end = init_match.end()
        init_code = """

# Initialize Enhanced Runtime Orchestrator
enhanced_orchestrator = get_orchestrator(llm_manager)
"""
        content = content[:init_end] + init_code + content[init_end:]
    
    # Add new endpoints before the final if __name__ == '__main__'
    new_endpoints = """

# ============================================================================
# ENHANCED RUNTIME ORCHESTRATOR ENDPOINTS
# ============================================================================

@app.route('/api/runtime/process', methods=['POST'])
def process_request_runtime():
    &quot;&quot;&quot;
    Process any request using enhanced runtime orchestrator with dynamic agent generation
    
    This works for ANY task type:
    - Books, articles, content
    - Software development
    - Research projects
    - Marketing campaigns
    - Business operations
    - Data analysis
    - etc.
    
    Request body:
    {
        "task": "Write a complete book about AI automation for small businesses",
        "capacity_limit": 9,  // optional, default 9
        "max_parallel": 9     // optional, default 9
    }
    
    The runtime will:
    1. Analyze the task
    2. Determine optimal number of agents
    3. Generate specialized agents dynamically
    4. Execute in parallel with collective mind
    5. Ensure consistency across all outputs
    6. Synthesize final coherent result
    &quot;&quot;&quot;
    if not llm_manager:
        return jsonify({'error': 'LLM not available'}), 503
    
    data = request.json
    task = data.get('task', '')
    capacity_limit = data.get('capacity_limit', 9)
    max_parallel = data.get('max_parallel', 9)
    
    if not task:
        return jsonify({'error': 'task is required'}), 400
    
    try:
        # Update capacity if specified
        if capacity_limit != 9:
            enhanced_orchestrator.set_capacity_limit(capacity_limit)
        if max_parallel != 9:
            enhanced_orchestrator.set_max_parallel(max_parallel)
        
        # Run async function in sync context
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            enhanced_orchestrator.process_request(task)
        )
        
        loop.close()
        
        # Save output to file
        task_id = result.get('task_id')
        filename = f"runtime_task_{task_id}.txt"
        with open(filename, 'w') as f:
            f.write(result.get('final_output', ''))
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'result': result,
            'filename': filename,
            'message': f'Task completed with {result.get(&quot;num_agents&quot;, 0)} agents'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/runtime/task/<task_id>', methods=['GET'])
def get_runtime_task_status(task_id):
    &quot;&quot;&quot;Get status of a specific runtime task&quot;&quot;&quot;
    try:
        status = enhanced_orchestrator.get_task_status(task_id)
        if status:
            return jsonify({'success': True, 'task': status})
        else:
            return jsonify({'error': 'Task not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/runtime/tasks', methods=['GET'])
def get_all_runtime_tasks():
    &quot;&quot;&quot;Get all runtime task history&quot;&quot;&quot;
    try:
        tasks = enhanced_orchestrator.get_all_tasks()
        return jsonify({'success': True, 'tasks': tasks})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/runtime/capacity', methods=['POST'])
def set_runtime_capacity():
    &quot;&quot;&quot;
    Update runtime capacity limits
    
    Use for rate limiting or adjusting to available resources
    
    Request body:
    {
        "capacity_limit": 9,  // Max agents to generate
        "max_parallel": 9     // Max simultaneous executions
    }
    &quot;&quot;&quot;
    try:
        data = request.json
        capacity_limit = data.get('capacity_limit')
        max_parallel = data.get('max_parallel')
        
        if capacity_limit:
            enhanced_orchestrator.set_capacity_limit(capacity_limit)
        if max_parallel:
            enhanced_orchestrator.set_max_parallel(max_parallel)
        
        return jsonify({
            'success': True,
            'message': 'Capacity limits updated',
            'capacity_limit': enhanced_orchestrator.capacity_limit,
            'max_parallel': enhanced_orchestrator.max_parallel
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/runtime/status', methods=['GET'])
def get_runtime_status():
    &quot;&quot;&quot;Get enhanced runtime orchestrator status&quot;&quot;&quot;
    try:
        return jsonify({
            'available': True,
            'type': 'enhanced_runtime_orchestrator',
            'features': [
                'Dynamic agent generation from any request',
                'Automatic task breakdown and parallelization',
                'Collective mind coordination',
                'Capacity and rate limit aware scaling',
                'Works for ANY task type',
                'Context consistency checking',
                'Cross-agent knowledge sharing'
            ],
            'capacity_limit': enhanced_orchestrator.capacity_limit,
            'max_parallel': enhanced_orchestrator.max_parallel,
            'active_tasks': len(enhanced_orchestrator.active_tasks),
            'total_tasks_completed': len(enhanced_orchestrator.task_history)
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
    
    print("✓ Enhanced Runtime Orchestrator integrated into Murphy system")
    print("\nNew endpoints added:")
    print("  POST /api/runtime/process")
    print("  GET  /api/runtime/task/<task_id>")
    print("  GET  /api/runtime/tasks")
    print("  POST /api/runtime/capacity")
    print("  GET  /api/runtime/status")

if __name__ == '__main__':
    integrate_enhanced_runtime()