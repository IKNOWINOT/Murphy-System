# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Integration Script for Enhanced Murphy Systems

This script integrates:
1. Enhanced Librarian System
2. Executive Bot System
3. Hybrid Command System

Run this to update the backend with new systems
"""

import sys

# Read current backend
try:
    with open('/workspace/murphy_backend_complete.py', 'r') as f:
        backend_content = f.read()
    print("Backend file loaded successfully")
except FileNotFoundError:
    print("Backend file not found. Creating new integration code...")
    backend_content = ""

# Import statements to add
new_imports = """
# Enhanced Systems Integration
from enhanced_librarian_system import EnhancedLibrarianSystem, DiscoveryPhase
from executive_bot_system import ExecutiveBotManager, BotRole
from hybrid_command_system import HybridCommandSystem
"""

# Check if imports already exist
if "from enhanced_librarian_system" not in backend_content:
    # Find the last import statement and add after it
    lines = backend_content.split('\n')
    import_idx = -1
    
    for i, line in enumerate(lines):
        if line.startswith('from ') or line.startswith('import '):
            import_idx = i
    
    if import_idx >= 0:
        lines.insert(import_idx + 1, new_imports)
        backend_content = '\n'.join(lines)
        print("Added new imports")
    else:
        print("No imports found, appending to beginning")
        backend_content = new_imports + '\n' + backend_content
else:
    print("Imports already exist")

# Initialization code to add
initialization_code = """

# Initialize Enhanced Systems
enhanced_librarian_system = None
executive_bot_manager = None
hybrid_command_system = None

if LIBRARIAN_AVAILABLE and llm_manager:
    enhanced_librarian_system = EnhancedLibrarianSystem(llm_client=llm_manager)
    executive_bot_manager = ExecutiveBotManager(llm_client=llm_manager)
    hybrid_command_system = HybridCommandSystem(
        librarian_system=enhanced_librarian_system,
        executive_bots=executive_bot_manager
    )
    logger.info("Enhanced systems initialized with LLM support")
else:
    enhanced_librarian_system = EnhancedLibrarianSystem()
    executive_bot_manager = ExecutiveBotManager()
    hybrid_command_system = HybridCommandSystem()
    logger.info("Enhanced systems initialized without LLM support")
"""

# Find where to add initialization (after librarian initialization)
if "enhanced_librarian_system" not in backend_content:
    # Find librarian initialization block
    if "librarian_system = LibrarianSystem" in backend_content:
        # Add after librarian initialization
        backend_content = backend_content.replace(
            "    logger.info(&quot;Librarian System initialized&quot;)",
            "    logger.info(&quot;Librarian System initialized&quot;)" + initialization_code
        )
        print("Added enhanced systems initialization")
    else:
        print("Librarian initialization not found, cannot add enhanced systems initialization")
else:
    print("Enhanced systems initialization already exists")

# New API endpoints to add
new_endpoints = """

# ==================== ENHANCED LIBRARIAN ENDPOINTS ====================

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
            'data': result.__dict__
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
            'data': hybrid.__dict__
        })
    
    except Exception as e:
        logger.error(f"Natural to command error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ==================== EXECUTIVE BOT ENDPOINTS ====================

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


# ==================== HYBRID COMMAND ENDPOINTS ====================

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
            'data': hybrid.__dict__
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
"""

# Add new endpoints if they don't exist
if "/api/librarian/enhanced" not in backend_content:
    backend_content += new_endpoints
    print("Added new API endpoints")
else:
    print("New endpoints already exist")

# Write updated content
try:
    with open('/workspace/murphy_backend_complete.py', 'w') as f:
        f.write(backend_content)
    print("Backend updated successfully")
except Exception as e:
    print(f"Error writing backend: {e}")
    sys.exit(1)

print("\nIntegration complete!")
print("Please restart the backend server to use the new systems.")