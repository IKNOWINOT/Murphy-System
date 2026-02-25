"""
LLM Providers for Murphy System
Provides real LLM integration with graceful fallback to demo mode.
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class LLMProvider:
    """Base class for LLM providers."""
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.available = False
    
    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """Generate response from LLM."""
        raise NotImplementedError
    
    def is_available(self) -> bool:
        """Check if provider is available."""
        return self.available


class DemoLLMProvider(LLMProvider):
    """Demo LLM provider that returns simulated responses."""
    
    def __init__(self):
        super().__init__("Demo LLM")
        self.available = True
        
        # Predefined responses for common queries
        self.responses = {
            "overview": """
The Murphy System is a comprehensive business automation platform with:
- 5 AI agents (Executive, Engineering, Financial, Legal, Operations)
- 7 system states showing current workflow progression
- 6 interactive panels for system management
- Real-time monitoring and shadow agent learning
- Artifact generation capabilities

Current Status: All systems operational
Database: Connected with 13 tables
Monitoring: 100% health score
            """.strip(),
            
            "guidance": """
I'm here to help you navigate the Murphy System. Here are some suggestions:

1. Start with /initialize to set up the system
2. Use /status to check system health
3. Try /state list to see available states
4. Explore the 6 interactive panels in the sidebar
5. Use /librarian ask <query> to ask questions
            """.strip()
        }
    
    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """Generate demo response based on prompt keywords."""
        prompt_lower = prompt.lower()
        
        # Check for keywords and return appropriate response
        if "overview" in prompt_lower or "status" in prompt_lower or "system" in prompt_lower:
            return self.responses["overview"]
        elif "guide" in prompt_lower or "help" in prompt_lower or "suggestion" in prompt_lower:
            return self.responses["guidance"]
        else:
            # Generic intelligent response
            return f"I understand you're asking about: {prompt}\n\nThis is the demo mode. To use real LLM capabilities, please configure API keys for Groq or Aristotle."
    
    def is_available(self) -> bool:
        return True


class GroqLLMProvider(LLMProvider):
    """Real Groq LLM provider."""
    
    def __init__(self, api_keys: list):
        super().__init__("Groq")
        self.api_keys = api_keys
        self.available = len(api_keys) > 0
        
        if self.available:
            logger.info(f"Groq provider initialized with {len(api_keys)} API keys")
        else:
            logger.warning("Groq provider initialized with no API keys - will use demo mode")
    
    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """Generate response using Groq API."""
        if not self.available:
            return None
        
        # Import GroqClient dynamically to avoid errors if not available
        try:
            from groq_client import GroqClient
            import asyncio
            
            client = GroqClient(
                api_keys=self.api_keys,
                model="llama-3.3-70b-versatile",  # Current Groq model
                temperature=0.7,
                max_tokens=1024
            )
            
            # Run the async method synchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(client.generate(prompt))
                # GroqClient returns [response, token_count], extract just the response
                if isinstance(result, (list, tuple)) and len(result) > 0:
                    return result[0]
                return result
            finally:
                loop.close()
            
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            return None
    
    def is_available(self) -> bool:
        return self.available


class LLMManager:
    """Manages multiple LLM providers with fallback."""
    
    def __init__(self, groq_api_keys: list = None):
        """Initialize LLM manager with providers."""
        self.providers = []
        
        # Try to initialize real providers first
        if groq_api_keys and len(groq_api_keys) > 0:
            groq_provider = GroqLLMProvider(groq_api_keys)
            self.providers.append(groq_provider)
        
        # Always add demo provider as fallback
        demo_provider = DemoLLMProvider()
        self.providers.append(demo_provider)
        
        logger.info(f"LLM Manager initialized with {len(self.providers)} providers")
    
    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Generate response using available providers.
        
        Returns:
            Dict with keys: success, response, provider, demo_mode
        """
        for provider in self.providers:
            if provider.is_available():
                try:
                    response = provider.generate(prompt, **kwargs)
                    if response:
                        is_demo = isinstance(provider, DemoLLMProvider)
                        return {
                            "success": True,
                            "response": response,
                            "provider": provider.provider_name,
                            "demo_mode": is_demo
                        }
                except Exception as e:
                    logger.error(f"Provider {provider.provider_name} error: {e}")
                    continue
        
        return {
            "success": False,
            "response": None,
            "provider": None,
            "demo_mode": True
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all providers."""
        return {
            "total_providers": len(self.providers),
            "available_providers": sum(1 for p in self.providers if p.is_available()),
            "providers": [
                {
                    "name": p.provider_name,
                    "available": p.is_available()
                }
                for p in self.providers
            ]
        }