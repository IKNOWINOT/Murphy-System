# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Cooperative Swarm System API Endpoints
To be imported into the main backend file
"""

from flask import Flask, request, jsonify
import asyncio


def register_cooperative_endpoints(app, cooperative_swarm, handoff_manager, workflow_orchestrator):
    """Register all cooperative swarm API endpoints"""
    
    @app.route('/api/cooperative/workflows/define', methods=['POST'])
    def define_workflow():
        """Define a new workflow"""
        try:
            data = request.get_json()
            
            workflow = workflow_orchestrator.define_workflow(
                name=data.get('name', 'Untitled Workflow'),
                description=data.get('description', ''),
                steps=data.get('steps', []),
                execution_mode=data.get('execution_mode', 'sequential'),
                **data.get('metadata', {})
            )
            
            return jsonify({
                'success': True,
                'workflow_id': workflow.workflow_id,
                'name': workflow.name,
                'steps_count': len(workflow.steps)
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cooperative/workflows/execute', methods=['POST'])
    def execute_workflow():
        """Execute a workflow"""
        try:
            data = request.get_json()
            
            workflow = workflow_orchestrator.define_workflow(
                name=data.get('name', 'Untitled Workflow'),
                description=data.get('description', ''),
                steps=data.get('steps', []),
                execution_mode=data.get('execution_mode', 'sequential')
            )
            
            execution = asyncio.run(workflow_orchestrator.execute_workflow(
                workflow,
                initial_input=data.get('input', {})
            ))
            
            return jsonify({
                'success': True,
                'execution_id': execution.execution_id,
                'workflow_id': execution.workflow_definition.workflow_id,
                'status': execution.status.value,
                'step_results': execution.step_results
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cooperative/workflows/<execution_id>/status', methods=['GET'])
    def get_workflow_status(execution_id):
        """Get workflow execution status"""
        try:
            execution = workflow_orchestrator.get_execution_status(execution_id)
            
            if not execution:
                return jsonify({'error': 'Execution not found'}), 404
            
            return jsonify({
                'success': True,
                'execution_id': execution.execution_id,
                'status': execution.status.value,
                'current_step': execution.current_step_index,
                'step_results': execution.step_results,
                'errors': execution.errors,
                'started_at': execution.started_at.isoformat() if execution.started_at else None,
                'completed_at': execution.completed_at.isoformat() if execution.completed_at else None
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cooperative/tasks/create', methods=['POST'])
    def create_cooperative_task():
        """Create a new cooperative task"""
        try:
            data = request.get_json()
            
            task = cooperative_swarm.create_task(
                description=data.get('description', ''),
                task_type=data.get('task_type', 'generic'),
                required_capabilities=data.get('required_capabilities', []),
                input_data=data.get('input_data', {}),
                parent_task_id=data.get('parent_task_id')
            )
            
            return jsonify({
                'success': True,
                'task_id': task.id,
                'status': task.status.value,
                'description': task.description
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cooperative/tasks/<task_id>/delegate', methods=['POST'])
    def delegate_task(task_id):
        """Delegate a task to another agent"""
        try:
            data = request.get_json()
            
            handoff = cooperative_swarm.delegate_task(
                task_id=task_id,
                from_agent=data.get('from_agent'),
                to_agent=data.get('to_agent'),
                context=data.get('context', {})
            )
            
            return jsonify({
                'success': True,
                'handoff_id': handoff.id,
                'from_agent': handoff.from_agent,
                'to_agent': handoff.to_agent,
                'task_id': handoff.task_id,
                'handoff_type': handoff.handoff_type.value
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cooperative/handoffs', methods=['GET'])
    def get_handoffs():
        """Get handoff history"""
        try:
            agent = request.args.get('agent')
            limit = int(request.args.get('limit', 100))
            
            handoffs = cooperative_swarm.handoffs
            if agent:
                handoffs = [h for h in handoffs 
                           if h.from_agent == agent or h.to_agent == agent]
            
            return jsonify({
                'success': True,
                'handoffs': [
                    {
                        'id': h.id,
                        'from_agent': h.from_agent,
                        'to_agent': h.to_agent,
                        'task_id': h.task_id,
                        'handoff_type': h.handoff_type.value,
                        'timestamp': h.timestamp.isoformat(),
                        'acknowledged': h.acknowledged
                    }
                    for h in handoffs[-limit:]
                ]
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cooperative/messages', methods=['POST'])
    def send_agent_message():
        """Send a message from one agent to another"""
        try:
            data = request.get_json()
            
            message = cooperative_swarm.send_message(
                from_agent=data.get('from_agent'),
                to_agent=data.get('to_agent'),
                message_type=data.get('message_type', 'info'),
                content=data.get('content', {})
            )
            
            return jsonify({
                'success': True,
                'message_id': message.id,
                'from_agent': message.from_agent,
                'to_agent': message.to_agent,
                'message_type': message.message_type
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cooperative/messages/<agent_id>', methods=['GET'])
    def get_agent_messages(agent_id):
        """Get messages for an agent"""
        try:
            unread_only = request.args.get('unread_only', 'false').lower() == 'true'
            
            messages = cooperative_swarm.get_agent_messages(agent_id, unread_only)
            
            return jsonify({
                'success': True,
                'messages': [
                    {
                        'id': m.id,
                        'from_agent': m.from_agent,
                        'to_agent': m.to_agent,
                        'message_type': m.message_type,
                        'content': m.content,
                        'timestamp': m.timestamp.isoformat(),
                        'read': m.read
                    }
                    for m in messages
                ]
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500