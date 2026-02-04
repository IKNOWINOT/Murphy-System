# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Groq API Client
"""

import os
import logging
import aiohttp
from typing import List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class GroqClient:
    """Client for Groq API"""
    
    def __init__(
        self,
        api_keys: List[str],
        model: str = 'mixtral-8x7b-32768',
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.9,
        frequency_penalty: float = 0.0
    ):
        """
        Initialize Groq client
        
        Args:
            api_keys: List of Groq API keys (for round-robin)
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            top_p: Nucleus sampling parameter
            frequency_penalty: Frequency penalty
        """
        self.api_keys = api_keys
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.frequency_penalty = frequency_penalty
        self.current_key_index = 0
        self.base_url = "https://api.groq.com/openai/v1"
        
        logger.info(f"Initialized Groq client with {len(api_keys)} API keys")
        logger.info(f"Model: {model}, Temperature: {temperature}")
    
    def _get_next_api_key(self) -> str:
        """Get next API key using round-robin"""
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key
    
    def _format_messages(self, prompt: str) -> List[dict]:
        """Format prompt as messages"""
        return [
            {
                "role": "system",
                "content": "You are Murphy, an intelligent AI assistant for the Murphy System business automation platform. Provide clear, concise, and helpful responses."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None
    ) -> Tuple[str, int]:
        """
        Generate text using Groq API
        
        Args:
            prompt: The prompt text
            model: Model name (overrides default)
            temperature: Temperature (overrides default)
            max_tokens: Max tokens (overrides default)
            top_p: Top P (overrides default)
            frequency_penalty: Frequency penalty (overrides default)
        
        Returns:
            Tuple of (generated_text, tokens_used)
        """
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self._get_next_api_key()}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model or self.model,
            "messages": self._format_messages(prompt),
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "top_p": top_p if top_p is not None else self.top_p,
            "frequency_penalty": frequency_penalty if frequency_penalty is not None else self.frequency_penalty
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Groq API error {response.status}: {error_text}")
                    
                    data = await response.json()
                    
                    # Extract response
                    content = data['choices'][0]['message']['content']
                    tokens_used = data['usage']['total_tokens']
                    
                    logger.debug(f"Groq response: {len(content)} chars, {tokens_used} tokens")
                    
                    return content, tokens_used
        
        except aiohttp.ClientError as e:
            logger.error(f"Groq client error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Groq API error: {str(e)}")
            raise
    
    async def generate_stream(self, prompt: str, **kwargs):
        """
        Generate text with streaming (not yet implemented)
        
        Args:
            prompt: The prompt text
            **kwargs: Additional parameters
        
        Yields:
            Chunks of generated text
        """
        # TODO: Implement streaming
        raise NotImplementedError("Streaming not yet implemented")