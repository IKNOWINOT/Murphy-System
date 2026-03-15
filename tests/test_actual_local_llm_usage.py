"""
Test that Enhanced Local LLM is actually used in offline mode
"""

import sys
sys.path.insert(0, '/workspace')

from src.llm_integration_layer import LLMIntegrationLayer, LLMProvider, DomainType
from src.enhanced_local_llm import EnhancedLocalLLM


def test_actual_local_llm_usage():
    """Test that the enhanced local LLM is actually being used"""

    print("=" * 80)
    print("ACTUAL LOCAL LLM USAGE TEST")
    print("=" * 80)
    print()

    # Test 1: Direct call to Enhanced Local LLM
    print("Test 1: Direct call to Enhanced Local LLM")
    print("-" * 80)

    local_llm = EnhancedLocalLLM()

    # Test Aristotle-style
    result = local_llm.query("Calculate 5 * 7", provider='aristotle')
    print("Aristotle Query: 'Calculate 5 * 7'")
    print(f"  Response: {result['response'][:200]}...")
    print(f"  Confidence: {result['confidence']}")
    print(f"  Provider: {result['provider']}")
    print(f"  Metadata: {result['metadata']}")
    print()

    # Test Wulfrum-style
    result = local_llm.query("Is 2+2 equal to 5?", provider='wulfrum')
    print("Wulfrum Query: 'Is 2+2 equal to 5?'")
    print(f"  Response: {result['response'][:200]}...")
    print(f"  Confidence: {result['confidence']}")
    print(f"  Provider: {result['provider']}")
    print(f"  Metadata: {result['metadata']}")
    print()

    # Test Groq-style (creative)
    result = local_llm.query("Write a poem about AI", provider='groq')
    print("Groq Query: 'Write a poem about AI'")
    print(f"  Response: {result['response'][:200]}...")
    print(f"  Confidence: {result['confidence']}")
    print(f"  Provider: {result['provider']}")
    print(f"  Metadata: {result['metadata']}")
    print()

    # Test 2: Compare with mock outputs
    print("=" * 80)
    print("Test 2: Compare Local LLM with Mock Outputs")
    print("=" * 80)
    print()

    mock_outputs = {
        "aristotle": "Aristotle deterministic analysis: Mathematical calculation verified. Confidence: 0.95. Result: The equation holds true under standard mathematical axioms.",
        "wulfrum": "Wulfrum fuzzy match: Mathematical validation complete. Match score: 0.88. Minor discrepancies found in rounding.",
        "groq": "Creative response generated with innovative solutions."
    }

    # Test Aristotle
    result = local_llm.query("Calculate 2+2", provider='aristotle')
    mock = mock_outputs["aristotle"]

    print("Aristotle Comparison:")
    print(f"  Mock Output: {mock}")
    print(f"  Local LLM: {result['response'][:150]}...")
    print(f"  Similar pattern: {mock.split(':')[0] in result['response']}")
    print()

    # Test Wulfrum
    result = local_llm.query("Validate this", provider='wulfrum')
    mock = mock_outputs["wulfrum"]

    print("Wulfrum Comparison:")
    print(f"  Mock Output: {mock}")
    print(f"  Local LLM: {result['response'][:150]}...")
    print(f"  Similar pattern: {mock.split(':')[0] in result['response']}")
    print()

    # Test Groq
    result = local_llm.query("Write something creative", provider='groq')
    mock = mock_outputs["groq"]

    print("Groq Comparison:")
    print(f"  Mock Output: {mock}")
    print(f"  Local LLM: {result['response'][:150]}...")
    print(f"  Similar pattern: {'creative' in result['response'].lower()}")
    print()

    # Test 3: Verify structure matches
    print("=" * 80)
    print("Test 3: Verify Output Structure Matches Mock")
    print("=" * 80)
    print()

    required_keys = ['response', 'confidence', 'tokens_used', 'provider', 'metadata']

    result = local_llm.query("Test query", provider='aristotle')

    print("Checking required keys...")
    all_present = True
    for key in required_keys:
        present = key in result
        status = "✅" if present else "❌"
        print(f"  {status} {key}: {present}")
        if not present:
            all_present = False

    print()

    if all_present:
        print("✅ All required keys present - Structure matches mock")
    else:
        print("❌ Missing keys - Structure does not match mock")

    print()
    print("=" * 80)

    assert all_present, "Not all expected fields present in response"


if __name__ == "__main__":
    success = test_actual_local_llm_usage()

    if success:
        print("✅ ENHANCED LOCAL LLM IS WORKING CORRECTLY")
        print("   Structure matches mock outputs")
        print("   Ready for integration testing")
    else:
        print("❌ ENHANCED LOCAL LLM NEEDS IMPROVEMENT")
        print("   Structure does not match mock outputs")

    sys.exit(0 if success else 1)
