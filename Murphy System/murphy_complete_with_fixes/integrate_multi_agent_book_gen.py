"""
Integration script to add multi-agent book generation to Murphy system
"""

import sys
import re

def integrate_multi_agent_system():
    """Add multi-agent book generation endpoints to Murphy"""
    
    # Read the current murphy file
    with open('murphy_complete_integrated.py', 'r') as f:
        content = f.read()
    
    # Add import at the top
    import_statement = """
# Multi-Agent Book Generation System
from multi_agent_book_generator import (
    generate_book_multi_agent,
    WritingStyle,
    MultiAgentBookGenerator
)
"""
    
    # Find where to insert import (after other imports)
    import_pos = content.find("from datetime import datetime")
    if import_pos != -1:
        # Find end of that line
        line_end = content.find("\n", import_pos)
        content = content[:line_end+1] + import_statement + content[line_end+1:]
    
    # Add new endpoints before the final if __name__ == '__main__'
    new_endpoints = """

# ============================================================================
# MULTI-AGENT BOOK GENERATION ENDPOINTS
# ============================================================================

@app.route('/api/book/generate-multi-agent', methods=['POST'])
def generate_book_multi_agent_endpoint():
    &quot;&quot;&quot;
    Generate a book using multi-agent parallel processing
    
    Request body:
    {
        "topic": "AI Automation for Small Business",
        "title": "The Complete Guide to AI Automation",
        "num_chapters": 9,
        "writing_style": "conversational"  // optional, defaults to "auto"
    }
    &quot;&quot;&quot;
    if not llm_manager:
        return jsonify({'error': 'LLM not available'}), 503
    
    data = request.json
    topic = data.get('topic', '')
    title = data.get('title', '')
    num_chapters = data.get('num_chapters', 9)
    writing_style = data.get('writing_style', 'auto')
    
    if not topic or not title:
        return jsonify({'error': 'topic and title are required'}), 400
    
    try:
        # Run async function in sync context
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            generate_book_multi_agent(llm_manager, topic, title, num_chapters)
        )
        
        loop.close()
        
        # Save the book
        filename = title.replace(' ', '_') + '.txt'
        with open(filename, 'w') as f:
            f.write(result['content'])
        
        return jsonify({
            'success': True,
            'book': result,
            'filename': filename,
            'message': f'Book generated with {num_chapters} chapters using multi-agent system'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/book/writing-styles', methods=['GET'])
def get_writing_styles():
    &quot;&quot;&quot;Get available writing styles&quot;&quot;&quot;
    styles = [style.value for style in WritingStyle]
    return jsonify({
        'styles': styles,
        'default': 'auto',
        'description': {
            'academic': 'Formal, research-based, citations',
            'conversational': 'Friendly, engaging, accessible',
            'technical': 'Precise, detailed, expert-level',
            'storytelling': 'Narrative-driven, examples, stories',
            'practical': 'Action-oriented, how-to, hands-on',
            'inspirational': 'Motivational, uplifting, aspirational',
            'humorous': 'Light, entertaining, witty',
            'auto': 'LLM decides best style for topic'
        }
    })

@app.route('/api/book/multi-agent/status', methods=['GET'])
def multi_agent_status():
    &quot;&quot;&quot;Get status of multi-agent book generation system&quot;&quot;&quot;
    return jsonify({
        'available': True,
        'features': [
            'Parallel chapter writing (up to 9 simultaneous)',
            'Collective mind coordination',
            'Three-stage processing (Magnify/Simplify/Solidify)',
            'Multiple writing styles',
            'Agent profile customization',
            'Context consistency checking',
            'Cross-chapter reference tracking'
        ],
        'max_parallel_chapters': 9,
        'processing_stages': ['magnify', 'simplify', 'solidify']
    })
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
    
    print("✓ Multi-agent book generation integrated into Murphy system")
    print("\nNew endpoints added:")
    print("  POST /api/book/generate-multi-agent")
    print("  GET  /api/book/writing-styles")
    print("  GET  /api/book/multi-agent/status")

if __name__ == '__main__':
    integrate_multi_agent_system()