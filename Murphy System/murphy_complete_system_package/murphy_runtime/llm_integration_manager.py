# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - LLM Integration Manager
Priority 4: Real LLM Integration
Phase 1: LLM Integration Infrastructure
"""

import os
import time
import json
import hashlib
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Available LLM providers"""
    GROQ = "groq"
    ARISTOTLE = "aristotle"
    ONBOARD = "onboard"


class LLMResponseQuality(Enum):
    """Response quality levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    INVALID = "invalid"


@dataclass
class LLMResponse:
    """LLM response data structure"""
    content: str
    provider: LLMProvider
    model: str
    tokens_used: int
    confidence: float
    quality: LLMResponseQuality
    cached: bool
    generation_time: float
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'content': self.content,
            'provider': self.provider.value,
            'model': self.model,
            'tokens_used': self.tokens_used,
            'confidence': self.confidence,
            'quality': self.quality.value,
            'cached': self.cached,
            'generation_time': self.generation_time,
            'timestamp': self.timestamp.isoformat()
        }


class RateLimiter:
    """Rate limiter for API calls"""
    
    def __init__(self, max_calls: int = 60, time_window: int = 60):
        """
        Initialize rate limiter
        
        Args:
            max_calls: Maximum number of calls allowed
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """
        Acquire permission to make a call
        
        Returns:
            True if call is allowed, False otherwise
        """
        async with self.lock:
            now = time.time()
            # Remove calls outside the time window
            self.calls = [call_time for call_time in self.calls 
                         if now - call_time < self.time_window]
            
            if len(self.calls) < self.max_calls:
                self.calls.append(now)
                return True
            
            # Calculate wait time
            oldest_call = self.calls[0]
            wait_time = self.time_window - (now - oldest_call)
            logger.warning(f"Rate limit reached. Wait {wait_time:.2f} seconds")
            return False
    
    async def wait_for_slot(self, timeout: int = 30) -> bool:
        """
        Wait for an available slot
        
        Args:
            timeout: Maximum time to wait in seconds
        
        Returns:
            True if slot acquired, False if timeout
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if await self.acquire():
                return True
            await asyncio.sleep(1)
        return False


class ResponseCache:
    """Cache for LLM responses"""
    
    def __init__(self, ttl: int = 3600):
        """
        Initialize cache
        
        Args:
            ttl: Time to live for cache entries in seconds
        """
        self.cache: Dict[str, Tuple[LLMResponse, datetime]] = {}
        self.ttl = ttl
        self.lock = asyncio.Lock()
    
    def _generate_key(self, prompt: str, model: str, **kwargs) -> str:
        """Generate cache key"""
        key_data = {
            'prompt': prompt,
            'model': model,
            **kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    async def get(self, prompt: str, model: str, **kwargs) -> Optional[LLMResponse]:
        """
        Get cached response
        
        Args:
            prompt: The prompt
            model: The model name
            **kwargs: Additional parameters
        
        Returns:
            Cached response or None
        """
        async with self.lock:
            key = self._generate_key(prompt, model, **kwargs)
            
            if key not in self.cache:
                return None
            
            response, cached_at = self.cache[key]
            
            # Check if expired
            if datetime.now() - cached_at > timedelta(seconds=self.ttl):
                del self.cache[key]
                return None
            
            logger.info(f"Cache hit for key: {key[:16]}...")
            response.cached = True
            return response
    
    async def set(self, prompt: str, model: str, response: LLMResponse, **kwargs):
        """
        Cache a response
        
        Args:
            prompt: The prompt
            model: The model name
            response: The response to cache
            **kwargs: Additional parameters
        """
        async with self.lock:
            key = self._generate_key(prompt, model, **kwargs)
            self.cache[key] = (response, datetime.now())
            logger.info(f"Cached response for key: {key[:16]}...")
    
    async def clear(self):
        """Clear all cache entries"""
        async with self.lock:
            self.cache.clear()
            logger.info("Cache cleared")
    
    async def cleanup_expired(self):
        """Remove expired cache entries"""
        async with self.lock:
            now = datetime.now()
            expired_keys = [
                key for key, (_, cached_at) in self.cache.items()
                if now - cached_at > timedelta(seconds=self.ttl)
            ]
            
            for key in expired_keys:
                del self.cache[key]
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")


class LLMClientManager:
    """Manager for LLM API clients"""
    
    def __init__(self):
        """Initialize LLM client manager"""
        self.providers: Dict[LLMProvider, Any] = {}
        self.rate_limiters: Dict[LLMProvider, RateLimiter] = {}
        self.cache = ResponseCache()
        self.call_stats: Dict[str, int] = {
            'total_calls': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'provider_calls': {provider.value: 0 for provider in LLMProvider},
            'errors': 0,
            'retries': 0
        }
        
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize LLM providers"""
        # Groq API
        groq_keys = [
            'gsk_VKqX3lfpHlXpQz5JZpXpQz5JZpXpQz5JZpXpQz5JZpXpQz5J',
            'gsk_VKqX3lfpHlXpQz5JZpXpQz5JZpXpQz5JZpXpQz5JZpXpQz5J',
            # Add remaining 7 keys...
        ]
        
        # Filter out placeholder keys
        groq_keys = [key for key in groq_keys if not key.startswith('gsk_VKqX3lfp')]
        
        if groq_keys:
            from groq_client import GroqClient
            self.providers[LLMProvider.GROQ] = GroqClient(
                api_keys=groq_keys,
                model='mixtral-8x7b-32768',
                temperature=0.7
            )
            self.rate_limiters[LLMProvider.GROQ] = RateLimiter(
                max_calls=60, time_window=60
            )
            logger.info(f"Initialized Groq with {len(groq_keys)} API keys")
        
        # Aristotle API
        aristotle_key = 'arstl_D7uKG0m-c3fs_4pRRBZ9wxnYGDVVLgTCLIKkH0UD2vQ'
        
        if aristotle_key:
            from aristotle_client import AristotleClient
            self.providers[LLMProvider.ARISTOTLE] = AristotleClient(
                api_key=aristotle_key,
                model='claude-3-haiku-20240307',
                temperature=0.1
            )
            self.rate_limiters[LLMProvider.ARISTOTLE] = RateLimiter(
                max_calls=50, time_window=60
            )
            logger.info("Initialized Aristotle API")
        
        # Onboard LLM (fallback)
        self.providers[LLMProvider.ONBOARD] = None  # Will be initialized on demand
        logger.info("Initialized Onboard LLM (fallback)")
    
    async def call_llm(
        self,
        prompt: str,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 2048,
        use_cache: bool = True,
        retries: int = 3,
        **kwargs
    ) -> LLMResponse:
        """
        Call LLM with automatic retry and fallback
        
        Args:
            prompt: The prompt to send
            provider: Preferred provider (None for automatic selection)
            model: Model name (None for provider default)
            temperature: Temperature (None for provider default)
            max_tokens: Maximum tokens
            use_cache: Whether to use cache
            retries: Number of retry attempts
            **kwargs: Additional parameters
        
        Returns:
            LLMResponse object
        """
        self.call_stats['total_calls'] += 1
        
        # Try cache first
        if use_cache:
            cached = await self.cache.get(prompt, model or 'default', **kwargs)
            if cached:
                self.call_stats['cache_hits'] += 1
                return cached
            else:
                self.call_stats['cache_misses'] += 1
        
        # Determine provider preference order
        provider_order = self._get_provider_order(provider)
        
        # Try each provider in order
        last_error = None
        for attempt in range(retries):
            for current_provider in provider_order:
                try:
                    # Check rate limit
                    rate_limiter = self.rate_limiters.get(current_provider)
                    if rate_limiter:
                        if not await rate_limiter.wait_for_slot():
                            logger.warning(f"Rate limit reached for {current_provider.value}")
                            continue
                    
                    # Get client
                    client = self.providers.get(current_provider)
                    if not client:
                        continue
                    
                    # Make API call
                    start_time = time.time()
                    content, tokens_used = await client.generate(
                        prompt=prompt,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs
                    )
                    generation_time = time.time() - start_time
                    
                    # Validate response
                    if not self._validate_response(content):
                        raise ValueError("Invalid response from LLM")
                    
                    # Create response object
                    response = LLMResponse(
                        content=content,
                        provider=current_provider,
                        model=model or client.model,
                        tokens_used=tokens_used,
                        confidence=self._calculate_confidence(content),
                        quality=self._assess_quality(content),
                        cached=False,
                        generation_time=generation_time,
                        timestamp=datetime.now()
                    )
                    
                    # Cache response
                    if use_cache:
                        await self.cache.set(prompt, model or 'default', response, **kwargs)
                    
                    # Update stats
                    self.call_stats['provider_calls'][current_provider.value] += 1
                    
                    logger.info(f"LLM call successful: {current_provider.value}, "
                               f"tokens={tokens_used}, time={generation_time:.2f}s")
                    
                    return response
                
                except Exception as e:
                    last_error = e
                    self.call_stats['errors'] += 1
                    logger.error(f"LLM call failed: {current_provider.value}, "
                               f"attempt {attempt + 1}/{retries}, error: {str(e)}")
                    
                    # Retry with exponential backoff
                    if attempt < retries - 1:
                        backoff_time = (2 ** attempt) * 1.0
                        await asyncio.sleep(backoff_time)
                        self.call_stats['retries'] += 1
                    else:
                        logger.error(f"All retry attempts failed for {current_provider.value}")
        
        # All providers failed
        logger.error(f"All LLM providers failed. Last error: {str(last_error)}")
        raise RuntimeError(f"Failed to get LLM response: {str(last_error)}")
    
    def _get_provider_order(self, preferred: Optional[LLMProvider]) -> List[LLMProvider]:
        """Get provider preference order"""
        if preferred:
            return [preferred] + [p for p in LLMProvider if p != preferred]
        return [LLMProvider.GROQ, LLMProvider.ARISTOTLE, LLMProvider.ONBOARD]
    
    def _validate_response(self, content: str) -> bool:
        """Validate LLM response"""
        if not content or len(content.strip()) < 10:
            return False
        return True
    
    def _calculate_confidence(self, content: str) -> float:
        """Calculate confidence score for response"""
        # Simple heuristic based on content length and structure
        confidence = 0.5
        
        # Length factor
        if len(content) > 100:
            confidence += 0.2
        if len(content) > 500:
            confidence += 0.1
        
        # Structure factor (has paragraphs, lists, etc.)
        if '\n' in content:
            confidence += 0.1
        if any(marker in content for marker in ['•', '-', '1.', '2.', '3.']):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _assess_quality(self, content: str) -> LLMResponseQuality:
        """Assess response quality"""
        confidence = self._calculate_confidence(content)
        
        if confidence >= 0.9:
            return LLMResponseQuality.EXCELLENT
        elif confidence >= 0.7:
            return LLMResponseQuality.GOOD
        elif confidence >= 0.5:
            return LLMResponseQuality.ACCEPTABLE
        elif confidence >= 0.3:
            return LLMResponseQuality.POOR
        else:
            return LLMResponseQuality.INVALID
    
    def get_stats(self) -> Dict:
        """Get call statistics"""
        return self.call_stats.copy()
    
    async def clear_cache(self):
        """Clear response cache"""
        await self.cache.clear()
    
    async def cleanup_cache(self):
        """Clean up expired cache entries"""
        await self.cache.cleanup_expired()


# Global instance
llm_manager = LLMClientManager()


async def test_llm_integration():
    """Test LLM integration"""
    print("Testing LLM Integration...")
    
    # Test basic call
    try:
        response = await llm_manager.call_llm(
            prompt="What is the Murphy System?",
            use_cache=False
        )
        print(f"\n✓ Test 1 passed: Basic LLM call")
        print(f"  Provider: {response.provider.value}")
        print(f"  Tokens: {response.tokens_used}")
        print(f"  Confidence: {response.confidence:.2f}")
        print(f"  Time: {response.generation_time:.2f}s")
    except Exception as e:
        print(f"\n✗ Test 1 failed: {str(e)}")
    
    # Test cache
    try:
        response1 = await llm_manager.call_llm(
            prompt="Test cache",
            use_cache=True
        )
        response2 = await llm_manager.call_llm(
            prompt="Test cache",
            use_cache=True
        )
        
        if response2.cached:
            print(f"\n✓ Test 2 passed: Cache working")
        else:
            print(f"\n✗ Test 2 failed: Cache not working")
    except Exception as e:
        print(f"\n✗ Test 2 failed: {str(e)}")
    
    # Print stats
    stats = llm_manager.get_stats()
    print(f"\n{'='*50}")
    print("LLM Call Statistics:")
    print(f"{'='*50}")
    print(f"Total calls: {stats['total_calls']}")
    print(f"Cache hits: {stats['cache_hits']}")
    print(f"Cache misses: {stats['cache_misses']}")
    print(f"Cache hit rate: {stats['cache_hits'] / stats['total_calls'] * 100:.1f}%")
    print(f"Errors: {stats['errors']}")
    print(f"Retries: {stats['retries']}")
    print(f"Provider calls: {stats['provider_calls']}")


if __name__ == "__main__":
    asyncio.run(test_llm_integration())