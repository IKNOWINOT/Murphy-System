#!/usr/bin/env python3

# Read the backend
with open('murphy_backend_complete.py', 'r') as f:
    content = f.read()

# The endpoints code
endpoints_code = '''

# ==================== ENHANCED LIBRARIAN ENDPOINTS (Option C) ====================

@app.route('/api/librarian/enhanced', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def librarian_enhanced_ask():
    """Enhanced librarian endpoint with discovery workflow"""
    try:
        data = request.get_json()
        user_input = data.get('input', '')
        
        if not user_input:
            return jsonify({
                'success': False,
                'message': 'Input is required'
            }), 400
        
        result = enhanced_librarian_system.ask(user_input)
        
        return jsonify({
            'success': True,
            'data': result
        })
    
    except Exception as e:
        logger.error(f"Enhanced librarian error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/librarian/interpret', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def librarian_interpret_command():
    """Interpret a command in natural language"""
    try:
        data = request.get_json()
        command = data.get('command', '')
        
        if not command:
            return jsonify({
                'success': False,
                'message': 'Command is required'
            }), 400
        
        result = hybrid_command_system.interpret_command(command)
        
        return jsonify({
            'success': True,
            'data': result.__dict__ if hasattr(result, '__dict__') else result
        })
    
    except Exception as e:
        logger.error(f"Command interpretation error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/librarian/natural-to-command', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def librarian_natural_to_command():
    """Convert natural language to command"""
    try:
        data = request.get_json()
        natural = data.get('natural', '')
        
        if not natural:
            return jsonify({
                'success': False,
                'message': 'Natural language text is required'
            }), 400
        
        hybrid = hybrid_command_system.natural_to_command(natural)
        
        return jsonify({
            'success': True,
            'data': hybrid.__dict__ if hasattr(hybrid, '__dict__') else hybrid
        })
    
    except Exception as e:
        logger.error(f"Natural to command error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ==================== EXECUTIVE BOT ENDPOINTS (Option C) ====================

@app.route('/api/executive/bots', methods=['GET'])
def get_executive_bots():
    """Get all executive bots"""
    try:
        bots = executive_bot_manager.get_all_bots()
        
        return jsonify({
            'success': True,
            'bots': bots
        })
    
    except Exception as e:
        logger.error(f"Get executive bots error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/executive/execute', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def execute_executive_command():
    """Execute a command on an executive bot"""
    try:
        data = request.get_json()
        bot_role = data.get('bot', '')
        command = data.get('command', '')
        context = data.get('context', '')
        
        if not bot_role or not command:
            return jsonify({
                'success': False,
                'message': 'Bot role and command are required'
            }), 400
        
        result = executive_bot_manager.execute_command(bot_role, command, context)
        
        return jsonify({
            'success': True,
            'data': result
        })
    
    except Exception as e:
        logger.error(f"Execute executive command error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/executive/workflow/<workflow_name>', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def execute_executive_workflow(workflow_name):
    """Execute an executive workflow"""
    try:
        result = executive_bot_manager.coordinate_workflow(workflow_name)
        
        return jsonify({
            'success': True,
            'data': result
        })
    
    except Exception as e:
        logger.error(f"Execute executive workflow error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/executive/terminology/<bot_role>', methods=['GET'])
def get_bot_terminology(bot_role):
    """Get domain terminology for a bot"""
    try:
        terminology = executive_bot_manager.get_bot_terminology(bot_role)
        
        return jsonify({
            'success': True,
            'terminology': terminology
        })
    
    except Exception as e:
        logger.error(f"Get bot terminology error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ==================== HYBRID COMMAND ENDPOINTS (Option C) ====================

@app.route('/api/commands/parse', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def parse_hybrid_command():
    """Parse a hybrid command"""
    try:
        data = request.get_json()
        command = data.get('command', '')
        
        if not command:
            return jsonify({
                'success': False,
                'message': 'Command is required'
            }), 400
        
        hybrid = hybrid_command_system.parse_hybrid_command(command)
        
        return jsonify({
            'success': True,
            'data': hybrid.__dict__ if hasattr(hybrid, '__dict__') else hybrid
        })
    
    except Exception as e:
        logger.error(f"Parse hybrid command error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/commands/dropdown-data', methods=['GET'])
def get_command_dropdown_data():
    """Get data for command dropdown interface"""
    try:
        data = hybrid_command_system.get_command_dropdown_data()
        
        return jsonify({
            'success': True,
            'data': data
        })
    
    except Exception as e:
        logger.error(f"Get command dropdown data error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/commands/workflows', methods=['GET'])
def get_workflows():
    """Get all available workflows"""
    try:
        workflows = hybrid_command_system.get_available_workflows()
        
        return jsonify({
            'success': True,
            'workflows': workflows
        })
    
    except Exception as e:
        logger.error(f"Get workflows error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/commands/validate', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def validate_command():
    """Validate command syntax"""
    try:
        data = request.get_json()
        command = data.get('command', '')
        
        if not command:
            return jsonify({
                'success': False,
                'message': 'Command is required'
            }), 400
        
        validation = hybrid_command_system.validate_command_syntax(command)
        
        return jsonify({
            'success': True,
            'data': validation
        })
    
    except Exception as e:
        logger.error(f"Validate command error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
'''

# Add endpoints at the end of the file
if "/api/librarian/enhanced" not in content:
    content += endpoints_code
    print("✓ Added 12 API endpoints")
else:
    print("✓ Endpoints already exist")

# Write back
with open('murphy_backend_complete.py', 'w') as f:
    f.write(content)

print("✓ Backend file updated")