"""
Enhanced LLM Providers for Murphy System
Features:
- Revolving key rotation (round-robin)
- Math detection and routing to Aristotle
- Usage tracking per key
- Failover handling
- Rate limit management
"""

import os
import logging
import re
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
import threading

# Fix for "Cannot run the event loop while another loop is running"
# This allows nested event loops in Flask/SocketIO environments
try:
    import nest_asyncio
    nest_asyncio.apply()
    logger = logging.getLogger(__name__)
    logger.info("✓ nest_asyncio applied - nested event loops enabled")
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("⚠ nest_asyncio not installed - may have event loop issues")
    logger.warning("  Install with: pip install nest-asyncio")


class EnhancedGroqLLMProvider:
    """Enhanced Groq LLM provider with key rotation"""
    
    MATH_KEYWORDS = [
        'calculate', 'solve', 'equation', 'formula', 'compute',
        'algebra', 'calculus', 'geometry', 'trigonometry',
        'statistics', 'probability', 'derivative', 'integral',
        'matrix', 'vector', 'percentage', 'roi', 'profit margin',
        'cost-benefit', 'break-even', 'amortization', 'compound interest',
        'optimization', 'linear programming', 'regression', 'correlation',
        'standard deviation', 'variance', 'mean', 'median', 'mode'
    ]
    
    def __init__(self, groq_api_keys: List[str], aristotle_api_key: str = None):
        """
        Initialize enhanced LLM provider with rotation support
        
        Args:
            groq_api_keys: List of Groq API keys
            aristotle_api_key: Aristotle API key for math tasks
        """
        self.groq_keys = groq_api_keys
        self.aristotle_key = aristotle_api_key
        
        # Key rotation tracking
        self.current_groq_index = 0
        self.groq_lock = threading.Lock()
        
        # Usage statistics
        self.usage_stats = {
            'groq': {i: {'calls': 0, 'errors': 0, 'last_used': None} for i in range(len(groq_api_keys))},
            'aristotle': {'calls': 0, 'errors': 0, 'last_used': None}
        }
        
        # Rate limit tracking (simple per-key limit)
        self.rate_limits = {i: {'calls': 0, 'window_start': None} for i in range(len(groq_api_keys))}
        self.rate_limit_window = 60  # seconds
        self.rate_limit_max = 30  # calls per window per key
        
        logger.info(f"Enhanced LLM Provider initialized:")
        logger.info(f"  - Groq keys: {len(groq_api_keys)}")
        logger.info(f"  - Aristotle: {'Available' if aristotle_api_key else 'Not configured'}")
    
    def detect_math_task(self, prompt: str) -> bool:
        """
        Detect if task is mathematical and should go to Aristotle
        
        Args:
            prompt: The task prompt
            
        Returns:
            True if math task detected
        """
        prompt_lower = prompt.lower()
        
        # Check for math keywords (with word boundaries to avoid false positives)
        for keyword in self.MATH_KEYWORDS:
            # Use word boundaries to avoid matching "ratio" in "spiritual direction"
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, prompt_lower):
                logger.info(f"Math task detected via keyword: '{keyword}'")
                return True
        
        # Check for mathematical expressions
        if re.search(r'\d+\s*[\+\-\*\/\%]\s*\d+', prompt):
            logger.info("Math task detected via expression")
            return True
        
        # Check for mathematical symbols
        if re.search(r'[∂∫∑∏√∞≈≠≤≥]', prompt):
            logger.info("Math task detected via symbols")
            return True
        
        return False
    
    def get_next_groq_key(self) -> tuple:
        """
        Get next Groq key using round-robin rotation
        
        Returns:
            Tuple of (key, key_index)
        """
        with self.groq_lock:
            key_index = self.current_groq_index
            key = self.groq_keys[key_index]
            
            # Move to next key (round-robin)
            self.current_groq_index = (self.current_groq_index + 1) % len(self.groq_keys)
            
            logger.info(f"Groq key rotation: Using key {key_index + 1}/{len(self.groq_keys)}")
            return key, key_index
    
    def check_rate_limit(self, key_index: int) -> bool:
        """
        Check if key has hit rate limit
        
        Args:
            key_index: Index of the key to check
            
        Returns:
            True if under rate limit, False if rate limited
        """
        now = datetime.now()
        key_stats = self.rate_limits[key_index]
        
        # Reset window if expired
        if key_stats['window_start'] is None or \
           (now - key_stats['window_start']).total_seconds() > self.rate_limit_window:
            key_stats['calls'] = 0
            key_stats['window_start'] = now
            return True
        
        # Check if under limit
        if key_stats['calls'] >= self.rate_limit_max:
            logger.warning(f"Key {key_index} hit rate limit")
            return False
        
        return True
    
    def generate_with_groq(self, prompt: str, key_index: int = None) -> Optional[str]:
        """
        Generate response using Groq API
        
        Args:
            prompt: The prompt to send
            key_index: Specific key to use (optional, auto-rotates if None)
            
        Returns:
            Response string or None if failed
        """
        # Get key (rotate or use specific)
        if key_index is None:
            api_key, key_index = self.get_next_groq_key()
        else:
            api_key = self.groq_keys[key_index]
        
        # Check rate limit
        if not self.check_rate_limit(key_index):
            # Try next key
            logger.info(f"Key {key_index} rate limited, trying next key")
            api_key, key_index = self.get_next_groq_key()
        
        # Update usage stats
        self.usage_stats['groq'][key_index]['calls'] += 1
        self.usage_stats['groq'][key_index]['last_used'] = datetime.now().isoformat()
        self.rate_limits[key_index]['calls'] += 1
        
        try:
            from groq_client import GroqClient
            
            client = GroqClient(
                api_keys=[api_key],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=2048
            )
            
            # Run async method synchronously with proper loop handling
            try:
                # Try to get existing event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Loop is already running (Flask/SocketIO context)
                    # nest_asyncio allows nested calls
                    result = loop.run_until_complete(client.generate(prompt))
                else:
                    # Loop exists but not running
                    result = loop.run_until_complete(client.generate(prompt))
            except RuntimeError:
                # No event loop exists, create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(client.generate(prompt))
                finally:
                    loop.close()
            
            # GroqClient returns [response, token_count]
            if isinstance(result, (list, tuple)) and len(result) > 0:
                response = result[0]
                logger.info(f"Groq key {key_index} response: {len(response)} chars")
                return response
            return result
                
        except Exception as e:
            logger.error(f"Groq API error (key {key_index}): {e}")
            self.usage_stats['groq'][key_index]['errors'] += 1
            
            # Try next key as failover
            if key_index < len(self.groq_keys) - 1:
                logger.info(f"Trying next key as failover")
                return self.generate_with_groq(prompt, key_index + 1)
            
            return None
    
    def generate_with_aristotle(self, prompt: str) -> Optional[str]:
        """
        Generate response using Aristotle (math LLM)
        
        Args:
            prompt: The prompt to send
            
        Returns:
            Response string or None if failed
        """
        if not self.aristotle_key:
            logger.warning("Aristotle key not configured, falling back to Groq")
            return self.generate_with_groq(prompt)
        
        # Update usage stats
        self.usage_stats['aristotle']['calls'] += 1
        self.usage_stats['aristotle']['last_used'] = datetime.now().isoformat()
        
        try:
            # Import Aristotle client (placeholder - implement based on Aristotle API)
            # For now, this is a stub - you'll need to implement based on Aristotle's actual API
            logger.info(f"Using Aristotle for math task")
            
            # Placeholder for Aristotle API call
            # You'll need to implement this based on Aristotle's actual API documentation
            response = f"[Aristotle Math Response for: {prompt[:50]}...]"
            
            logger.info(f"Aristotle response: {len(response)} chars")
            return response
            
        except Exception as e:
            logger.error(f"Aristotle API error: {e}")
            self.usage_stats['aristotle']['errors'] += 1
            
            # Fallback to Groq
            logger.info("Falling back to Groq")
            return self.generate_with_groq(prompt)
    
    def generate(self, prompt: str, force_aristotle: bool = False, force_groq: bool = False) -> str:
        """
        Generate response with automatic routing
        
        Args:
            prompt: The prompt to send
            force_aristotle: Force use of Aristotle
            force_groq: Force use of Groq
            
        Returns:
            Response string (for compatibility with Runtime)
        """
        try:
            # Detect math task if not forced
            math_task = self.detect_math_task(prompt) if not force_groq else False
            
            # Route to appropriate provider
            if force_aristotle or (math_task and not force_groq):
                logger.info("Routing to Aristotle (math task)")
                response = self.generate_with_aristotle(prompt)
                
                if response:
                    return response
            else:
                logger.info("Routing to Groq (general task)")
                response = self.generate_with_groq(prompt)
                
                if response:
                    return response
            
            # If we got here, generation failed
            return "Error: Generation failed"
            
        except Exception as e:
            logger.error(f"Generation error: {e}")
            return f"Error: {str(e)}"
    
    def generate_detailed(self, prompt: str, force_aristotle: bool = False, force_groq: bool = False) -> Dict[str, Any]:
        """
        Generate response with detailed metadata
        
        Args:
            prompt: The prompt to send
            force_aristotle: Force use of Aristotle
            force_groq: Force use of Groq
            
        Returns:
            Dict with keys: success, response, provider, key_index, math_task
        """
        try:
            # Detect math task if not forced
            math_task = self.detect_math_task(prompt) if not force_groq else False
            
            # Route to appropriate provider
            if force_aristotle or (math_task and not force_groq):
                logger.info("Routing to Aristotle (math task)")
                response = self.generate_with_aristotle(prompt)
                
                if response:
                    return {
                        'success': True,
                        'response': response,
                        'provider': 'aristotle',
                        'key_index': None,
                        'math_task': True
                    }
            else:
                logger.info("Routing to Groq (general task)")
                response = self.generate_with_groq(prompt)
                
                if response:
                    return {
                        'success': True,
                        'response': response,
                        'provider': 'groq',
                        'key_index': self.current_groq_index - 1,  # Just used
                        'math_task': False
                    }
            
            # If we got here, generation failed
            return {
                'success': False,
                'response': None,
                'provider': None,
                'key_index': None,
                'math_task': math_task,
                'error': 'All providers failed'
            }
            
        except Exception as e:
            logger.error(f"Generation error: {e}")
            return {
                'success': False,
                'response': None,
                'provider': None,
                'key_index': None,
                'math_task': False,
                'error': str(e)
            }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics for all keys"""
        total_groq_calls = sum(stats['calls'] for stats in self.usage_stats['groq'].values())
        total_groq_errors = sum(stats['errors'] for stats in self.usage_stats['groq'].values())
        
        return {
            'total_calls': total_groq_calls + self.usage_stats['aristotle']['calls'],
            'total_errors': total_groq_errors + self.usage_stats['aristotle']['errors'],
            'groq': {
                'total_keys': len(self.groq_keys),
                'total_calls': total_groq_calls,
                'total_errors': total_groq_errors,
                'current_rotation': self.current_groq_index,
                'per_key': self.usage_stats['groq']
            },
            'aristotle': self.usage_stats['aristotle'],
            'rate_limits': {
                'window_seconds': self.rate_limit_window,
                'max_calls_per_window': self.rate_limit_max
            }
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get provider status"""
        return {
            'groq_keys_available': len(self.groq_keys),
            'aristotle_available': self.aristotle_key is not None,
            'rotation_enabled': True,
            'math_detection_enabled': True,
            'rate_limiting_enabled': True,
            'current_groq_key': self.current_groq_index + 1,
            'usage_stats': self.get_usage_stats()
        }


class EnhancedLLMManager:
    """
    Enhanced LLM Manager with rotation and routing
    """
    
    def __init__(self, groq_keys_file: str = 'all_groq_keys.txt', 
                 aristotle_key_file: str = 'aristotle_key.txt'):
        """
        Initialize enhanced LLM manager
        
        Args:
            groq_keys_file: Path to file containing Groq API keys (one per line)
            aristotle_key_file: Path to file containing Aristotle API key
        """
        # Load Groq keys
        self.groq_keys = []
        if os.path.exists(groq_keys_file):
            with open(groq_keys_file, 'r') as f:
                self.groq_keys = [line.strip() for line in f if line.strip()]
            logger.info(f"Loaded {len(self.groq_keys)} Groq keys from {groq_keys_file}")
        else:
            logger.warning(f"Groq keys file not found: {groq_keys_file}")
        
        # Load Aristotle key
        self.aristotle_key = None
        if os.path.exists(aristotle_key_file):
            with open(aristotle_key_file, 'r') as f:
                self.aristotle_key = f.read().strip()
            logger.info(f"Loaded Aristotle key from {aristotle_key_file}")
        else:
            logger.warning(f"Aristotle key file not found: {aristotle_key_file}")
        
        # Initialize enhanced provider
        if self.groq_keys:
            self.provider = EnhancedGroqLLMProvider(self.groq_keys, self.aristotle_key)
            self.available = True
        else:
            self.provider = None
            self.available = False
            logger.error("No Groq keys available - LLM manager not operational")
    
    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate response with automatic routing and rotation
        
        Args:
            prompt: The prompt to send
            **kwargs: Additional parameters (force_aristotle, force_groq)
            
        Returns:
            Response string
        """
        if not self.available or not self.provider:
            return "Error: LLM manager not available"
        
        force_aristotle = kwargs.get('force_aristotle', False)
        force_groq = kwargs.get('force_groq', False)
        
        return self.provider.generate(prompt, force_aristotle, force_groq)
    
    def generate_detailed(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Generate response with detailed metadata
        
        Args:
            prompt: The prompt to send
            **kwargs: Additional parameters (force_aristotle, force_groq)
            
        Returns:
            Dict with generation results
        """
        if not self.available or not self.provider:
            return {
                'success': False,
                'response': None,
                'error': 'LLM manager not available'
            }
        
        force_aristotle = kwargs.get('force_aristotle', False)
        force_groq = kwargs.get('force_groq', False)
        
        return self.provider.generate_detailed(prompt, force_aristotle, force_groq)
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        if self.provider:
            return self.provider.get_usage_stats()
        return {}
    
    def get_status(self) -> Dict[str, Any]:
        """Get manager status"""
        if self.provider:
            return self.provider.get_status()
        return {'available': False, 'error': 'Provider not initialized'}


# Convenience function for backward compatibility
def get_enhanced_llm_manager(groq_keys_file: str = 'all_groq_keys.txt',
                              aristotle_key_file: str = 'aristotle_key.txt') -> EnhancedLLMManager:
    """
    Get or create enhanced LLM manager instance
    
    Args:
        groq_keys_file: Path to Groq keys file
        aristotle_key_file: Path to Aristotle key file
        
    Returns:
        EnhancedLLMManager instance
    """
    return EnhancedLLMManager(groq_keys_file, aristotle_key_file)