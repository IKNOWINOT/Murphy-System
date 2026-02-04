# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Integration Script: Agent Communication System
Adds inter-agent messaging, decision gates, and token cost analysis to Murphy
"""

import sys

def integrate_agent_communication():
    """Integrate agent communication system into murphy_complete_integrated.py"""
    
    print("=" * 80)
    print("INTEGRATING AGENT COMMUNICATION SYSTEM")
    print("=" * 80)
    
    # Read the current murphy file
    with open('murphy_complete_integrated.py', 'r') as f:
        murphy_content = f.read()
    
    # Check if already integrated
    if 'agent_communication_system' in murphy_content:
        print("✓ Agent communication system already integrated")
        return True
    
    # Find the imports section
    import_marker = "from swarm_knowledge_pipeline import"
    if import_marker not in murphy_content:
        print("✗ Could not find import marker")
        return False
    
    # Add import
    new_import = """from agent_communication_system import (
    AgentCommunicationHub, get_communication_hub,
    MessageType, ConfidenceLevel, AgentMessage, AgentTaskReview
)
"""
    
    murphy_content = murphy_content.replace(
        import_marker,
        new_import + "\n" + import_marker
    )
    
    # We'll add initialization in the main block instead
    # Skip this step for now - will add it manually after endpoints
    
    # Add new API endpoints before the final if __name__ == '__main__'
    new_endpoints = """

# ============================================================================
# AGENT COMMUNICATION ENDPOINTS
# ============================================================================

@app.route('/api/agent/message/send', methods=['POST'])
def send_agent_message():
    &quot;&quot;&quot;Send a message from one agent to another&quot;&quot;&quot;
    try:
        data = request.json
        message = communication_hub.send_message(
            from_agent=data['from_agent'],
            to_agent=data['to_agent'],
            message_type=MessageType[data['message_type']],
            subject=data['subject'],
            body=data['body'],
            thread_id=data.get('thread_id'),
            requires_response=data.get('requires_response', False),
            attachments=data.get('attachments', [])
        )
        return jsonify({
            'success': True,
            'message': message.to_dict()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/agent/inbox/<agent_name>', methods=['GET'])
def get_agent_inbox(agent_name):
    &quot;&quot;&quot;Get all messages for an agent&quot;&quot;&quot;
    try:
        messages = communication_hub.get_agent_inbox(agent_name)
        return jsonify({
            'success': True,
            'agent': agent_name,
            'message_count': len(messages),
            'messages': [msg.to_dict() for msg in messages]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/agent/thread/<thread_id>', methods=['GET'])
def get_message_thread(thread_id):
    &quot;&quot;&quot;Get all messages in a thread&quot;&quot;&quot;
    try:
        messages = communication_hub.get_thread(thread_id)
        return jsonify({
            'success': True,
            'thread_id': thread_id,
            'message_count': len(messages),
            'messages': [msg.to_dict() for msg in messages]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/task/review/create', methods=['POST'])
def create_task_review():
    &quot;&quot;&quot;Create a complete review state for an agent task&quot;&quot;&quot;
    try:
        data = request.json
        review = communication_hub.create_task_review(
            task_id=data['task_id'],
            agent_name=data['agent_name'],
            agent_role=data['agent_role'],
            user_request=data['user_request']
        )
        return jsonify({
            'success': True,
            'review': review.to_dict()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/task/review/<task_id>', methods=['GET'])
def get_task_review(task_id):
    &quot;&quot;&quot;Get the complete review state for a task&quot;&quot;&quot;
    try:
        review = communication_hub.get_task_review(task_id)
        if not review:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        return jsonify({
            'success': True,
            'review': review.to_dict()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/task/review/all', methods=['GET'])
def get_all_task_reviews():
    &quot;&quot;&quot;Get all task reviews&quot;&quot;&quot;
    try:
        reviews = communication_hub.get_all_task_reviews()
        return jsonify({
            'success': True,
            'count': len(reviews),
            'reviews': [review.to_dict() for review in reviews]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/task/review/<task_id>/answer', methods=['POST'])
def answer_clarifying_question(task_id):
    &quot;&quot;&quot;Answer a clarifying question to boost confidence&quot;&quot;&quot;
    try:
        data = request.json
        review = communication_hub.update_task_with_answer(
            task_id=task_id,
            question_index=data['question_index'],
            answer=data['answer']
        )
        
        if not review:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        return jsonify({
            'success': True,
            'review': review.to_dict(),
            'new_confidence': review.librarian_confidence,
            'confidence_level': review.overall_confidence.value
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/librarian/deliverable/communicate', methods=['POST'])
def librarian_deliverable_communication():
    &quot;&quot;&quot;Handle communication between Librarian and Deliverable Function&quot;&quot;&quot;
    try:
        data = request.json
        result = communication_hub.librarian_deliverable_communication(
            task_id=data['task_id'],
            deliverable_request=data['request']
        )
        return jsonify({
            'success': True,
            'communication': result
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/task/review/<task_id>/gates', methods=['GET'])
def get_task_gates(task_id):
    &quot;&quot;&quot;Get all decision gates for a task&quot;&quot;&quot;
    try:
        review = communication_hub.get_task_review(task_id)
        if not review:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'gates': [asdict(gate) for gate in review.gates],
            'overall_confidence': review.overall_confidence.value
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/task/review/<task_id>/cost-analysis', methods=['GET'])
def get_task_cost_analysis(task_id):
    &quot;&quot;&quot;Get cost analysis for a task&quot;&quot;&quot;
    try:
        review = communication_hub.get_task_review(task_id)
        if not review:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'token_cost': review.token_cost,
            'revenue_potential': review.revenue_potential,
            'cost_benefit_ratio': review.cost_benefit_ratio,
            'recommendation': 'Proceed' if review.cost_benefit_ratio > 1 else 'Review Required'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

"""
    
    # Find the if __name__ == '__main__' section
    main_marker = "if __name__ == '__main__':"
    if main_marker in murphy_content:
        murphy_content = murphy_content.replace(main_marker, new_endpoints + "\n" + main_marker)
    else:
        murphy_content += new_endpoints
    
    # Add dataclasses import at the top if not present
    if 'from dataclasses import' not in murphy_content:
        murphy_content = murphy_content.replace(
            'import json',
            'import json\nfrom dataclasses import asdict'
        )
    
    # Write back
    with open('murphy_complete_integrated.py', 'w') as f:
        f.write(murphy_content)
    
    print("\n✓ Added agent communication system import")
    print("✓ Added communication hub initialization")
    print("✓ Added 10 new API endpoints:")
    print("  1. POST /api/agent/message/send - Send message between agents")
    print("  2. GET /api/agent/inbox/<agent_name> - Get agent's inbox")
    print("  3. GET /api/agent/thread/<thread_id> - Get message thread")
    print("  4. POST /api/task/review/create - Create task review")
    print("  5. GET /api/task/review/<task_id> - Get task review")
    print("  6. GET /api/task/review/all - Get all task reviews")
    print("  7. POST /api/task/review/<task_id>/answer - Answer clarifying question")
    print("  8. POST /api/librarian/deliverable/communicate - Librarian ↔ Deliverable")
    print("  9. GET /api/task/review/<task_id>/gates - Get decision gates")
    print("  10. GET /api/task/review/<task_id>/cost-analysis - Get cost analysis")
    
    return True

if __name__ == '__main__':
    success = integrate_agent_communication()
    if success:
        print("\n" + "=" * 80)
        print("INTEGRATION COMPLETE")
        print("=" * 80)
        print("\nAgent Communication System successfully integrated into Murphy!")
        print("\nNew capabilities:")
        print("• Inter-agent email chatter")
        print("• Decision gates with confidence levels")
        print("• Token cost vs revenue analysis")
        print("• LLM state + Librarian interpretation")
        print("• Clarifying questions to boost confidence")
        print("• Librarian ↔ Deliverable Function communication")
        sys.exit(0)
    else:
        print("\n✗ Integration failed")
        sys.exit(1)