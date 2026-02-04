# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - LLM-Enhanced Backend
Priority 4: Real LLM Integration
Phase 1: Backend Integration
"""

from flask import Flask, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import asyncio
import logging
from datetime import datetime
import os
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'murphy-system-llm-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Import LLM components
try:
    from llm_integration_manager import llm_manager, LLMProvider
    from groq_client import GroqClient
    from aristotle_client import AristotleClient
    from response_validator import validator, ValidationResult
    LLM_AVAILABLE = True
    logger.info("✓ LLM components loaded successfully")
except ImportError as e:
    logger.error(f"✗ Failed to load LLM components: {e}")
    LLM_AVAILABLE = False

# System state
system_state = {
    'initialized': False,
    'states': {},
    'agents': {},
    'gates': {},
    'llm_stats': {
        'total_calls': 0,
        'successful_calls': 0,
        'failed_calls': 0,
        'cache_hits': 0,
        'cache_misses': 0,
        'providers_used': {}
    }
}


# ===== LLM API Endpoints =====

@app.route('/api/llm/generate', methods=['POST'])
def llm_generate():
    """
    Generate text using LLM
    
    Request body:
    {
        "prompt": "text to generate",
        "provider": "groq" | "aristotle" | null,
        "model": "model name" | null,
        "temperature": 0.7,
        "max_tokens": 2048,
        "use_cache": true
    }
    """
    if not LLM_AVAILABLE:
        return jsonify({
            'error': 'LLM components not available',
            'message': 'Please check server logs for details'
        }), 500
    
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        # Parse parameters
        provider = data.get('provider')
        if provider:
            provider = LLMProvider(provider.lower())
        
        model = data.get('model')
        temperature = data.get('temperature')
        max_tokens = data.get('max_tokens', 2048)
        use_cache = data.get('use_cache', True)
        
        # Make async call
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            response = loop.run_until_complete(
                llm_manager.call_llm(
                    prompt=prompt,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    use_cache=use_cache
                )
            )
            
            # Update stats
            system_state['llm_stats']['total_calls'] += 1
            system_state['llm_stats']['successful_calls'] += 1
            
            provider_name = response.provider.value
            system_state['llm_stats']['providers_used'][provider_name] = \
                system_state['llm_stats']['providers_used'].get(provider_name, 0) + 1
            
            if response.cached:
                system_state['llm_stats']['cache_hits'] += 1
            else:
                system_state['llm_stats']['cache_misses'] += 1
            
            # Return response
            return jsonify({
                'success': True,
                'content': response.content,
                'provider': response.provider.value,
                'model': response.model,
                'tokens_used': response.tokens_used,
                'confidence': response.confidence,
                'quality': response.quality.value,
                'cached': response.cached,
                'generation_time': response.generation_time,
                'timestamp': response.timestamp.isoformat()
            })
        
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"LLM generation error: {str(e)}")
        system_state['llm_stats']['failed_calls'] += 1
        
        return jsonify({
            'error': 'Generation failed',
            'message': str(e)
        }), 500


@app.route('/api/llm/verify', methods=['POST'])
def llm_verify():
    """
    Verify content using Aristotle
    
    Request body:
    {
        "content": "content to verify",
        "criteria": "verification criteria"
    }
    """
    if not LLM_AVAILABLE:
        return jsonify({
            'error': 'LLM components not available'
        }), 500
    
    try:
        data = request.get_json()
        content = data.get('content', '')
        criteria = data.get('criteria', '')
        
        if not content or not criteria:
            return jsonify({
                'error': 'Content and criteria are required'
            }), 400
        
        # Get Aristotle client
        aristotle = llm_manager.providers.get(LLMProvider.ARISTOTLE)
        
        if not aristotle:
            return jsonify({
                'error': 'Aristotle provider not available'
            }), 500
        
        # Make async call
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            is_valid, confidence, explanation = loop.run_until_complete(
                aristotle.verify(content, criteria)
            )
            
            return jsonify({
                'success': True,
                'is_valid': is_valid,
                'confidence': confidence,
                'explanation': explanation,
                'verified_at': datetime.now().isoformat()
            })
        
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"LLM verification error: {str(e)}")
        
        return jsonify({
            'error': 'Verification failed',
            'message': str(e)
        }), 500


@app.route('/api/llm/stats', methods=['GET'])
def llm_stats():
    """Get LLM usage statistics"""
    if not LLM_AVAILABLE:
        return jsonify({'error': 'LLM components not available'}), 500
    
    # Get manager stats
    manager_stats = llm_manager.get_stats()
    
    return jsonify({
        'success': True,
        'manager_stats': manager_stats,
        'system_stats': system_state['llm_stats'],
        'cache_stats': {
            'size': len(llm_manager.cache.cache),
            'ttl': llm_manager.cache.ttl
        },
        'providers': {
            provider.value: llm_manager.providers.get(provider) is not None
            for provider in LLMProvider
        }
    })


@app.route('/api/llm/clear-cache', methods=['POST'])
def llm_clear_cache():
    """Clear LLM response cache"""
    if not LLM_AVAILABLE:
        return jsonify({'error': 'LLM components not available'}), 500
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(llm_manager.clear_cache())
        finally:
            loop.close()
        
        return jsonify({
            'success': True,
            'message': 'Cache cleared successfully',
            'cleared_at': datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Cache clear error: {str(e)}")
        
        return jsonify({
            'error': 'Failed to clear cache',
            'message': str(e)
        }), 500


# ===== Enhanced Command Endpoints =====

@app.route('/api/command/help', methods=['POST'])
def command_help():
    """
    Get intelligent help using LLM
    
    Request body:
    {
        "topic": "topic to get help on" | null
    }
    """
    if not LLM_AVAILABLE:
        # Fallback to static help
        return jsonify({
            'success': True,
            'content': get_static_help(),
            'llm_generated': False
        })
    
    try:
        data = request.get_json()
        topic = data.get('topic', '')
        
        prompt = f"Provide helpful information about Murphy System commands{' for: ' + topic if topic else ' in general'}. Include examples and best practices."
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            response = loop.run_until_complete(
                llm_manager.call_llm(prompt=prompt, max_tokens=1024)
            )
            
            return jsonify({
                'success': True,
                'content': response.content,
                'llm_generated': True,
                'provider': response.provider.value,
                'confidence': response.confidence
            })
        
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Help generation error: {str(e)}")
        # Fallback to static help
        return jsonify({
            'success': True,
            'content': get_static_help(),
            'llm_generated': False,
            'error': str(e)
        })


@app.route('/api/command/suggest', methods=['POST'])
def command_suggest():
    """
    Get intelligent command suggestions using LLM
    
    Request body:
    {
        "context": "current context",
        "recent_commands": ["command1", "command2"],
        "goal": "user goal" | null
    }
    """
    if not LLM_AVAILABLE:
        return jsonify({
            'success': True,
            'suggestions': []
        })
    
    try:
        data = request.get_json()
        context = data.get('context', '')
        recent_commands = data.get('recent_commands', [])
        goal = data.get('goal', '')
        
        prompt = f"""Suggest Murphy System commands based on the following:

Context: {context}
Recent commands: {', '.join(recent_commands)}
Goal: {goal if goal else 'General system operation'}

Provide 3-5 relevant commands with brief explanations of what they do."""
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            response = loop.run_until_complete(
                llm_manager.call_llm(prompt=prompt, max_tokens=512)
            )
            
            # Parse suggestions (simple implementation)
            suggestions = parse_suggestions(response.content)
            
            return jsonify({
                'success': True,
                'suggestions': suggestions,
                'provider': response.provider.value,
                'confidence': response.confidence
            })
        
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Suggestion generation error: {str(e)}")
        
        return jsonify({
            'success': True,
            'suggestions': [],
            'error': str(e)
        })


# ===== Helper Functions =====

def get_static_help():
    """Get static help text"""
    return """
Murphy System v2.0 - Command Help

Core Commands:
  /help [topic]           - Show help information
  /status                 - Show system status
  /initialize             - Initialize the system
  /clear                  - Clear terminal

State Commands:
  /state list             - List all states
  /state evolve <id>      - Evolve a state
  /state regenerate <id>  - Regenerate a state
  /state rollback <id>    - Rollback a state

Organization Commands:
  /org agents             - List all agents
  /org chart              - Show organization chart

LLM Commands (Priority 4):
  /llm status             - Show LLM status
  /llm generate <prompt>  - Generate text with LLM
  /llm verify <content>   - Verify with Aristotle

Enhancement Commands (Priority 3):
  /alias [list|create|delete] - Manage aliases
  /history [clear]       - View command history
  /script [list|run|create|delete] - Manage scripts
  /schedule [list|add|remove] - Schedule commands

Use Tab for autocomplete, Arrow keys for history.
"""


def parse_suggestions(content: str) -> list:
    """Parse suggestions from LLM response"""
    suggestions = []
    
    # Simple parsing - look for numbered items or bullets
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check for numbered items or bullets
        if line[0].isdigit() and '. ' in line:
            # Format: "1. command - description"
            parts = line.split('. ', 1)
            if len(parts) == 2:
                suggestions.append({
                    'command': parts[1].split(' -')[0].strip(),
                    'description': parts[1].split(' -')[1].strip() if ' -' in parts[1] else ''
                })
        elif line.startswith('- ') or line.startswith('• '):
            # Format: "- command - description"
            parts = line[2:].split(' -', 1)
            if len(parts) == 2:
                suggestions.append({
                    'command': parts[0].strip(),
                    'description': parts[1].strip()
                })
    
    return suggestions[:5]  # Limit to 5 suggestions


# ===== WebSocket Events =====

@socketio.on('llm_generate')
def handle_llm_generate(data):
    """Handle LLM generation via WebSocket"""
    logger.info(f"LLM generate request: {data.get('prompt', '')[:50]}...")
    
    try:
        prompt = data.get('prompt', '')
        provider = data.get('provider')
        model = data.get('model')
        temperature = data.get('temperature')
        max_tokens = data.get('max_tokens', 2048)
        use_cache = data.get('use_cache', True)
        
        if provider:
            provider = LLMProvider(provider.lower())
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            response = loop.run_until_complete(
                llm_manager.call_llm(
                    prompt=prompt,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    use_cache=use_cache
                )
            )
            
            emit('llm_response', {
                'success': True,
                'content': response.content,
                'provider': response.provider.value,
                'tokens_used': response.tokens_used,
                'confidence': response.confidence,
                'cached': response.cached
            })
        
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"WebSocket LLM error: {str(e)}")
        emit('llm_response', {
            'success': False,
            'error': str(e)
        })


# ===== Server Info =====

if __name__ == '__main__':
    print("=" * 60)
    print("MURPHY SYSTEM - LLM-ENHANCED BACKEND")
    print("=" * 60)
    print(f"LLM Available: {LLM_AVAILABLE}")
    print(f"Port: 3000")
    print("=" * 60)
    
    socketio.run(app, host='0.0.0.0', port=3000, debug=False, allow_unsafe_werkzeug=True)