"""
Test LLM Integration
Priority 4: Real LLM Integration
"""

import asyncio
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_groq_client():
    """Test Groq client"""
    print("\n" + "="*50)
    print("Test 1: Groq Client")
    print("="*50)
    
    try:
        from groq_client import GroqClient
        
        # Note: Using placeholder keys - will fail without real keys
        client = GroqClient(
            api_keys=['gsk_test_key_placeholder'],
            model='mixtral-8x7b-32768'
        )
        
        print("✓ Groq client initialized")
        print(f"  Model: {client.model}")
        print(f"  Temperature: {client.temperature}")
        print(f"  API keys: {len(client.api_keys)}")
        
        return True
    
    except Exception as e:
        print(f"✗ Groq client test failed: {str(e)}")
        return False


async def test_aristotle_client():
    """Test Aristotle client"""
    print("\n" + "="*50)
    print("Test 2: Aristotle Client")
    print("="*50)
    
    try:
        from aristotle_client import AristotleClient
        
        client = AristotleClient(
            api_key='test_key_placeholder',
            model='claude-3-haiku-20240307'
        )
        
        print("✓ Aristotle client initialized")
        print(f"  Model: {client.model}")
        print(f"  Temperature: {client.temperature}")
        
        return True
    
    except Exception as e:
        print(f"✗ Aristotle client test failed: {str(e)}")
        return False


async def test_response_validator():
    """Test response validator"""
    print("\n" + "="*50)
    print("Test 3: Response Validator")
    print("="*50)
    
    try:
        from response_validator import validator, ValidationResult
        
        # Test valid response
        valid_content = "This is a valid response. It has proper structure and meaningful content."
        result, details = validator.validate(valid_content)
        
        if result == ValidationResult.VALID:
            print("✓ Valid response detected correctly")
        else:
            print(f"✗ Valid response incorrectly classified as {result}")
            return False
        
        # Test invalid response
        invalid_content = "Too short"
        result, details = validator.validate(invalid_content)
        
        if result == ValidationResult.INVALID:
            print("✓ Invalid response detected correctly")
        else:
            print(f"✗ Invalid response incorrectly classified as {result}")
            return False
        
        # Test warning response
        warning_content = "This response is long enough but has no proper structure or punctuation"
        result, details = validator.validate(warning_content)
        
        if result == ValidationResult.WARNING:
            print("✓ Warning response detected correctly")
        else:
            print(f"✗ Warning response incorrectly classified as {result}")
            return False
        
        print("✓ All validator tests passed")
        return True
    
    except Exception as e:
        print(f"✗ Response validator test failed: {str(e)}")
        return False


async def test_llm_manager():
    """Test LLM manager"""
    print("\n" + "="*50)
    print("Test 4: LLM Manager")
    print("="*50)
    
    try:
        from llm_integration_manager import llm_manager, LLMProvider
        
        print("✓ LLM manager initialized")
        
        # Check providers
        providers = list(llm_manager.providers.keys())
        print(f"  Available providers: {[p.value for p in providers]}")
        
        # Check rate limiters
        rate_limiters = list(llm_manager.rate_limiters.keys())
        print(f"  Rate limiters: {[p.value for p in rate_limiters]}")
        
        # Check cache
        print(f"  Cache TTL: {llm_manager.cache.ttl}s")
        
        # Get stats
        stats = llm_manager.get_stats()
        print(f"  Total calls: {stats['total_calls']}")
        print(f"  Cache hits: {stats['cache_hits']}")
        print(f"  Cache misses: {stats['cache_misses']}")
        
        return True
    
    except Exception as e:
        print(f"✗ LLM manager test failed: {str(e)}")
        return False


async def test_cache():
    """Test cache functionality"""
    print("\n" + "="*50)
    print("Test 5: Cache Functionality")
    print("="*50)
    
    try:
        from llm_integration_manager import ResponseCache, LLMResponse, LLMProvider
        from datetime import datetime
        
        cache = ResponseCache(ttl=60)
        
        # Test cache miss
        result = await cache.get("test prompt", "test model")
        if result is None:
            print("✓ Cache miss works correctly")
        else:
            print("✗ Cache miss failed")
            return False
        
        # Create test response
        from llm_integration_manager import LLMResponseQuality
        test_response = LLMResponse(
            content="Test content",
            provider=LLMProvider.GROQ,
            model="test-model",
            tokens_used=100,
            confidence=0.9,
            quality=LLMResponseQuality.GOOD,
            cached=False,
            generation_time=1.0,
            timestamp=datetime.now()
        )
        
        # Test cache set
        await cache.set("test prompt", "test model", test_response)
        print("✓ Cache set works correctly")
        
        # Test cache hit
        result = await cache.get("test prompt", "test model")
        if result and result.cached:
            print("✓ Cache hit works correctly")
        else:
            print("✗ Cache hit failed")
            return False
        
        # Test cache clear
        await cache.clear()
        result = await cache.get("test prompt", "test model")
        if result is None:
            print("✓ Cache clear works correctly")
        else:
            print("✗ Cache clear failed")
            return False
        
        print("✓ All cache tests passed")
        return True
    
    except Exception as e:
        print(f"✗ Cache test failed: {str(e)}")
        return False


async def test_rate_limiter():
    """Test rate limiter"""
    print("\n" + "="*50)
    print("Test 6: Rate Limiter")
    print("="*50)
    
    try:
        from llm_integration_manager import RateLimiter
        
        limiter = RateLimiter(max_calls=5, time_window=10)
        
        # Test normal operation
        for i in range(5):
            acquired = await limiter.acquire()
            if not acquired:
                print(f"✗ Failed to acquire slot {i+1}")
                return False
        
        print("✓ Acquired 5 slots successfully")
        
        # Test rate limit
        acquired = await limiter.acquire()
        if not acquired:
            print("✓ Rate limit enforced correctly")
        else:
            print("✗ Rate limit not enforced")
            return False
        
        # Test wait_for_slot
        # This would take too long, so we skip it
        print("✓ Rate limiter tests passed")
        return True
    
    except Exception as e:
        print(f"✗ Rate limiter test failed: {str(e)}")
        return False


async def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("LLM INTEGRATION TEST SUITE")
    print("="*60)
    
    tests = [
        ("Groq Client", test_groq_client),
        ("Aristotle Client", test_aristotle_client),
        ("Response Validator", test_response_validator),
        ("LLM Manager", test_llm_manager),
        ("Cache Functionality", test_cache),
        ("Rate Limiter", test_rate_limiter)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ Test {test_name} crashed: {str(e)}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)