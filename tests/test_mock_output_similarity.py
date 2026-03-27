"""
Test that Enhanced Local LLM produces outputs similar to mock templates
Test both API mode and onboard (local) mode
"""

import sys
sys.path.insert(0, '/workspace')

from src.llm_integration_layer import LLMIntegrationLayer, LLMProvider, DomainType


def test_mock_similarity():
    """Test that local LLM outputs are similar to mock outputs"""

    print("=" * 80)
    print("MOCK OUTPUT SIMILARITY TEST - API MODE vs ONBOARD MODE")
    print("=" * 80)
    print()

    # Create integration layer WITHOUT local fallback (API mode only)
    print("Testing API Mode (no local fallback)...")
    api_llm = LLMIntegrationLayer(use_local_fallback=False)
    print()

    # Create integration layer WITH local fallback (will use local in our test)
    print("Testing Onboard Mode (local fallback)...")
    onboard_llm = LLMIntegrationLayer(use_local_fallback=True)
    print()

    # Test cases
    test_cases = [
        {
            "name": "Aristotle - Math",
            "provider": LLMProvider.ARISTOTLE,
            "domain": DomainType.MATHEMATICAL,
            "prompt": "Calculate 2+2",
            "expected_mock_pattern": "Aristotle deterministic analysis"
        },
        {
            "name": "Aristotle - Physics",
            "provider": LLMProvider.ARISTOTLE,
            "domain": DomainType.PHYSICS,
            "prompt": "What is velocity?",
            "expected_mock_pattern": "Aristotle deterministic analysis"
        },
        {
            "name": "Wulfrum - Validation",
            "provider": LLMProvider.WULFRUM,
            "domain": DomainType.MATHEMATICAL,
            "prompt": "Is this correct?",
            "expected_mock_pattern": "Wulfrum fuzzy match"
        },
        {
            "name": "Groq - Creative",
            "provider": LLMProvider.DEEPINFRA,
            "domain": DomainType.CREATIVE,
            "prompt": "Write something creative",
            "expected_mock_pattern": "Creative response"
        },
        {
            "name": "Groq - General",
            "provider": LLMProvider.DEEPINFRA,
            "domain": DomainType.GENERAL,
            "prompt": "General question",
            "expected_mock_pattern": "General response"
        }
    ]

    results = []

    for test in test_cases:
        print(f"Test: {test['name']}")
        print(f"  Prompt: {test['prompt']}")
        print(f"  Expected pattern: {test['expected_mock_pattern']}")
        print()

        # Test API mode
        print("  API Mode:")
        try:
            api_response = api_llm.route_request(
                prompt=test['prompt'],
                provider=test['provider'],
                domain=test['domain']
            )
            api_matches = test['expected_mock_pattern'].lower() in api_response.response.lower()
            print(f"    Response: {api_response.response[:100]}...")
            print(f"    Matches mock pattern: {api_matches}")
            print(f"    Confidence: {api_response.confidence}")
            print(f"    Provider: {api_response.provider.value}")
        except Exception as e:
            api_matches = False
            print(f"    ERROR: {e}")

        print()

        # Test Onboard mode
        print("  Onboard Mode:")
        try:
            onboard_response = onboard_llm.route_request(
                prompt=test['prompt'],
                provider=test['provider'],
                domain=test['domain']
            )
            onboard_matches = test['expected_mock_pattern'].lower() in onboard_response.response.lower()
            print(f"    Response: {onboard_response.response[:100]}...")
            print(f"    Matches mock pattern: {onboard_matches}")
            print(f"    Confidence: {onboard_response.confidence}")
            print(f"    Provider: {onboard_response.provider.value}")
            print(f"    Offline mode: {onboard_response.metadata.get('offline_mode', False)}")
        except Exception as e:
            onboard_matches = False
            print(f"    ERROR: {e}")

        print()

        results.append({
            "test": test['name'],
            "api_matches": api_matches,
            "onboard_matches": onboard_matches,
            "api_response": api_response.response if api_matches else None,
            "onboard_response": onboard_response.response if onboard_matches else None
        })

        print("-" * 80)
        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    api_total = len(results)
    api_passed = sum(1 for r in results if r['api_matches'])
    onboard_total = len(results)
    onboard_passed = sum(1 for r in results if r['onboard_matches'])

    print(f"API Mode:")
    print(f"  Total: {api_total}")
    print(f"  Passed: {api_passed}")
    print(f"  Failed: {api_total - api_passed}")
    print(f"  Success Rate: {api_passed/api_total*100:.1f}%")
    print()

    print(f"Onboard Mode:")
    print(f"  Total: {onboard_total}")
    print(f"  Passed: {onboard_passed}")
    print(f"  Failed: {onboard_total - onboard_passed}")
    print(f"  Success Rate: {onboard_passed/onboard_total*100:.1f}%")
    print()

    # Detailed failures
    if api_passed < api_total:
        print("API Mode Failures:")
        for r in results:
            if not r['api_matches']:
                print(f"  - {r['test']}")
        print()

    if onboard_passed < onboard_total:
        print("Onboard Mode Failures:")
        for r in results:
            if not r['onboard_matches']:
                print(f"  - {r['test']}")
        print()

    print("=" * 80)

    assert api_passed == api_total and onboard_passed == onboard_total, (
        f"API: {api_passed}/{api_total}, Onboard: {onboard_passed}/{onboard_total}"
    )


if __name__ == "__main__":
    success = test_mock_similarity()

    if success:
        print("✅ ALL TESTS PASSED - Both modes produce mock-similar outputs")
    else:
        print("⚠️  SOME TESTS FAILED - Need to improve output similarity")

    sys.exit(0 if success else 1)
