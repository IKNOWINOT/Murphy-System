"""
Test forced offline mode by simulating API failure
"""

import sys
sys.path.insert(0, '/workspace')

from src.llm_integration_layer import LLMIntegrationLayer, LLMProvider, DomainType


def test_forced_offline_mode():
    """Test that local LLM is used when API fails"""
    
    print("=" * 80)
    print("FORCED OFFLINE MODE TEST")
    print("=" * 80)
    print()
    
    # Create integration layer with local fallback enabled
    print("Creating LLM Integration Layer with local fallback...")
    llm = LLMIntegrationLayer(use_local_fallback=True)
    print()
    
    # Simulate API failure by breaking the _call_aristotle method
    print("Simulating API failure...")
    original_call_aristotle = llm._call_aristotle
    
    def broken_aristotle(request):
        raise Exception("Simulated API failure")
    
    llm._call_aristotle = broken_aristotle
    print("✅ API failure simulated")
    print()
    
    # Test request - should fall back to local LLM
    print("Testing request with failed API...")
    print("Expected: Should use local fallback")
    print()
    
    response = llm.route_request(
        prompt="Calculate 2+2",
        provider=LLMProvider.ARISTOTLE,
        domain=DomainType.MATHEMATICAL
    )
    
    print(f"Response: {response.response}")
    print(f"Confidence: {response.confidence}")
    print(f"Provider: {response.provider.value}")
    print(f"Metadata: {response.metadata}")
    print()
    
    # Check if offline mode was used
    offline_mode = response.metadata.get('offline_mode', False)
    processing_type = response.metadata.get('processing_type', '')
    
    print("Analysis:")
    print(f"  Offline Mode: {offline_mode}")
    print(f"  Processing Type: {processing_type}")
    print(f"  Model: {response.metadata.get('model', 'N/A')}")
    print()
    
    # Restore original method
    llm._call_aristotle = original_call_aristotle
    
    # Verify it matches mock format
    print("Verification:")
    expected_pattern = "Aristotle deterministic analysis"
    matches = expected_pattern in response.response
    print(f"  Matches mock pattern: {matches}")
    print()
    
    if offline_mode and matches:
        print("✅ SUCCESS: Offline mode working correctly")
        print("   - Local LLM was used")
        print("   - Output matches mock format")
        return True
    else:
        print("❌ FAILURE: Offline mode not working correctly")
        print(f"   - Offline mode: {offline_mode}")
        print(f"   - Matches mock: {matches}")
        return False


if __name__ == "__main__":
    success = test_forced_offline_mode()
    
    print()
    print("=" * 80)
    
    if success:
        print("✅ OFFLINE MODE TEST PASSED")
        print("   System correctly falls back to local LLM when API fails")
    else:
        print("❌ OFFLINE MODE TEST FAILED")
        print("   System did not fall back to local LLM correctly")
    
    print("=" * 80)
    
    sys.exit(0 if success else 1)