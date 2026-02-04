# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

#!/usr/bin/env python3
"""
Add Librarian endpoint to connect the existing LibrarianSystem with real LLM.
"""

# Read the file
with open('/workspace/murphy_backend_complete.py', 'r') as f:
    content = f.read()

# Add librarian import after llm_providers import
llm_import = "from llm_providers import LLMManager"
librarian_import = """from llm_providers import LLMManager
from librarian_system import LibrarianSystem"""

content = content.replace(llm_import, librarian_import)

# Initialize LibrarianSystem after LLM Manager initialization
llm_init = """try:
    # Load Groq API keys from file
    groq_keys = []
    try:
        with open('/workspace/groq_keys.txt', 'r') as f:
            groq_keys = [line.strip() for line in f if line.strip()]
        logger.info(f"Loaded {len(groq_keys)} Groq API keys")
    except FileNotFoundError:
        logger.warning("No Groq API keys found, using demo mode")
    
    # Initialize LLM Manager
    llm_manager = LLMManager(groq_api_keys=groq_keys)
    LLM_AVAILABLE = True
    if len(groq_keys) > 0:
        logger.info(f"LLM Manager initialized with {len(groq_keys)} real Groq API keys")
    else:
        logger.info("LLM Manager initialized (demo mode)")
except Exception as e:
    logger.error(f"Failed to initialize LLM Manager: {e}")
    LLM_AVAILABLE = False
    llm_manager = None"""

librarian_init = llm_init + """

# ============================================================================
# LIBRARIAN SYSTEM INTEGRATION
# ============================================================================

try:
    # Initialize Librarian System with real LLM
    librarian_system = LibrarianSystem(llm_client=llm_manager if LLM_AVAILABLE else None)
    LIBRARIAN_AVAILABLE = True
    logger.info("Librarian System initialized")
except Exception as e:
    logger.error(f"Failed to initialize Librarian System: {e}")
    LIBRARIAN_AVAILABLE = False
    librarian_system = None"""

content = content.replace(llm_init, librarian_init)

# Add Librarian API endpoint before LLM API endpoints
llm_endpoints_marker = "# LLM API ENDPOINTS"

librarian_endpoint = """

# ============================================================================
# LIBRARIAN API ENDPOINTS
# ============================================================================

@app.route('/api/librarian/ask', methods=['POST'])
def librarian_ask():
    &quot;&quot;&quot;Process any user input with intent classification and command mapping.&quot;&quot;&quot;
    try:
        if not LIBRARIAN_AVAILABLE or not librarian_system:
            return jsonify({
                'success': False,
                'error': 'Librarian system not available'
            }), 500
        
        data = request.get_json()
        user_input = data.get('input', '')
        
        if not user_input:
            return jsonify({
                'success': False,
                'error': 'No input provided'
            }), 400
        
        # Use the LibrarianSystem to process input
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            response = loop.run_until_complete(librarian_system.ask(user_input))
            
            return jsonify({
                'success': True,
                'intent': {
                    'category': response.intent.category.value,
                    'confidence': response.intent.confidence,
                    'keywords': response.intent.keywords,
                    'suggested_commands': response.intent.suggested_commands
                },
                'message': response.message,
                'commands': response.commands,
                'workflow': response.workflow,
                'follow_up_questions': response.follow_up_questions,
                'confidence_level': response.confidence_level.value
            })
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Librarian ask error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# LLM API ENDPOINTS"""

content = content.replace(llm_endpoints_marker, librarian_endpoint)

# Update status endpoint to include librarian
status_update = """'llm': LLM_AVAILABLE,
            'librarian': LIBRARIAN_AVAILABLE,"""
status_old = """'llm': LLM_AVAILABLE,"""
content = content.replace(status_old, status_update)

# Write back
with open('/workspace/murphy_backend_complete.py', 'w') as f:
    f.write(content)

print("Added Librarian system integration")
print("Added /api/librarian/ask endpoint")
print("Connected Librarian with real LLM")
print("Updated status endpoint")