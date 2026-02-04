# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Simplified LLM Provider using official Groq SDK (no aiohttp needed)
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class SimpleLLMManager:
    """Simple LLM Manager using official Groq SDK"""
    
    def __init__(self, groq_keys_file: str = 'groq_keys.txt', aristotle_key_file: str = 'aristotle_key.txt'):
        """Initialize with API keys from files"""
        self.groq_keys = []
        self.current_key_index = 0
        
        # Load Groq keys
        if os.path.exists(groq_keys_file):
            with open(groq_keys_file, 'r') as f:
                self.groq_keys = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            logger.info(f"Loaded {len(self.groq_keys)} Groq keys")
        
        # Load Aristotle key (optional)
        self.aristotle_key = None
        if os.path.exists(aristotle_key_file):
            with open(aristotle_key_file, 'r') as f:
                self.aristotle_key = f.read().strip()
    
    def get_next_key(self) -> str:
        """Get next Groq API key (round-robin)"""
        if not self.groq_keys:
            raise ValueError("No Groq API keys available")
        
        key = self.groq_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.groq_keys)
        return key
    
    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate response using Groq API
        
        Args:
            prompt: The prompt to send
            **kwargs: Additional arguments (ignored for compatibility)
        
        Returns:
            Generated text response
        """
        try:
            from groq import Groq
            
            # Get API key
            api_key = self.get_next_key()
            
            # Create client
            client = Groq(api_key=api_key)
            
            # Generate response
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are Murphy, a helpful AI assistant for business automation."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2048
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            return f"Error: {str(e)}"
    
    def generate_detailed(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate with detailed metadata"""
        response = self.generate(prompt, **kwargs)
        
        return {
            'response': response,
            'model': 'llama-3.3-70b-versatile',
            'provider': 'groq',
            'timestamp': datetime.now().isoformat()
        }