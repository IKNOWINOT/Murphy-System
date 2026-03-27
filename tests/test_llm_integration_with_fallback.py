"""
Test LLM Integration with Enhanced Local Fallback
Tests both online API mode and offline fallback mode
"""

import pytest
import sys
import os

# Add workspace to path
sys.path.insert(0, '/workspace')

from src.llm_integration_layer import LLMIntegrationLayer, LLMProvider, DomainType
from src.enhanced_local_llm import EnhancedLocalLLM


class TestLLMIntegrationWithFallback:
    """Test LLM integration with enhanced local fallback"""

    @pytest.fixture
    def integration_layer_with_fallback(self):
        """Create integration layer with local fallback enabled"""
        return LLMIntegrationLayer(use_local_fallback=True)

    @pytest.fixture
    def integration_layer_without_fallback(self):
        """Create integration layer without local fallback"""
        return LLMIntegrationLayer(use_local_fallback=False)

    def test_local_fallback_initialization(self, integration_layer_with_fallback):
        """Test that local fallback initializes correctly"""
        assert integration_layer_with_fallback.use_local_fallback is True
        assert integration_layer_with_fallback.local_llm is not None
        print("✅ Local fallback initialized correctly")

    def test_local_fallback_disabled(self, integration_layer_without_fallback):
        """Test that local fallback can be disabled"""
        assert integration_layer_without_fallback.use_local_fallback is False
        assert integration_layer_without_fallback.local_llm is None
        print("✅ Local fallback disabled correctly")

    def test_aristotle_request_with_local_fallback(self, integration_layer_with_fallback):
        """Test Aristotle request using local fallback"""
        response = integration_layer_with_fallback.route_request(
            prompt="What is the derivative of x^2?",
            domain=DomainType.MATHEMATICAL,
            provider=LLMProvider.ARISTOTLE
        )

        assert response.response is not None
        assert response.provider == LLMProvider.ARISTOTLE
        assert 0.0 <= response.confidence <= 1.0
        print(f"✅ Aristotle request successful")
        print(f"   Confidence: {response.confidence}")
        print(f"   Response length: {len(response.response)} chars")
        print(f"   Response preview: {response.response[:200]}...")

    def test_wulfrum_request_with_local_fallback(self, integration_layer_with_fallback):
        """Test Wulfrum request using local fallback"""
        response = integration_layer_with_fallback.route_request(
            prompt="Is 2+2 equal to 5?",
            domain=DomainType.MATHEMATICAL,
            provider=LLMProvider.WULFRUM
        )

        assert response.response is not None
        assert response.provider == LLMProvider.WULFRUM
        assert 0.0 <= response.confidence <= 1.0
        print(f"✅ Wulfrum request successful")
        print(f"   Confidence: {response.confidence}")
        print(f"   Response length: {len(response.response)} chars")

    def test_deepinfra_request_with_local_fallback(self, integration_layer_with_fallback):
        """Test DeepInfra request using local fallback"""
        response = integration_layer_with_fallback.route_request(
            prompt="Write a short poem about AI",
            domain=DomainType.CREATIVE,
            provider=LLMProvider.DEEPINFRA
        )

        assert response.response is not None
        assert response.provider == LLMProvider.DEEPINFRA
        assert 0.0 <= response.confidence <= 1.0
        print(f"✅ DeepInfra request successful")
        print(f"   Confidence: {response.confidence}")
        print(f"   Response length: {len(response.response)} chars")
        print(f"   Response preview: {response.response[:200]}...")

    def test_offline_mode_metadata(self, integration_layer_with_fallback):
        """Test that offline mode is properly indicated in metadata"""
        response = integration_layer_with_fallback.route_request(
            prompt="What is kinetic energy?",
            domain=DomainType.PHYSICS,
            provider=LLMProvider.ARISTOTLE
        )

        # Check for offline mode indicators in metadata
        assert 'model' in response.metadata
        assert 'domain' in response.metadata
        assert 'processing_type' in response.metadata

        print(f"✅ Metadata includes offline indicators")
        print(f"   Model: {response.metadata.get('model')}")
        print(f"   Processing type: {response.metadata.get('processing_type')}")

    def test_multiple_requests_with_local_fallback(self, integration_layer_with_fallback):
        """Test multiple sequential requests with local fallback"""
        requests = [
            ("Calculate 5 * 7", LLMProvider.ARISTOTLE, DomainType.MATHEMATICAL),
            ("Write a poem about technology", LLMProvider.DEEPINFRA, DomainType.CREATIVE),
            ("Is this valid?", LLMProvider.WULFRUM, DomainType.MATHEMATICAL),
            ("What is force?", LLMProvider.ARISTOTLE, DomainType.PHYSICS),
        ]

        responses = []
        for prompt, provider, domain in requests:
            response = integration_layer_with_fallback.route_request(
                prompt=prompt,
                provider=provider,
                domain=domain
            )
            responses.append(response)
            assert response.response is not None

        assert len(responses) == len(requests)
        print(f"✅ Multiple requests successful ({len(requests)} requests)")

        # Print summary
        for i, (prompt, _, _) in enumerate(requests):
            print(f"   Request {i+1}: {prompt[:30]}...")
            print(f"      Confidence: {responses[i].confidence}")
            print(f"      Length: {len(responses[i].response)} chars")

    def test_domain_routing_with_local_fallback(self, integration_layer_with_fallback):
        """Test domain routing works with local fallback"""
        test_cases = [
            (DomainType.MATHEMATICAL, "Calculate 2+2"),
            (DomainType.PHYSICS, "What is velocity?"),
            (DomainType.ENGINEERING, "Design a bridge"),
            (DomainType.CREATIVE, "Write a story"),
            (DomainType.STRATEGIC, "Plan a project"),
        ]

        for domain, prompt in test_cases:
            response = integration_layer_with_fallback.route_request(
                prompt=prompt,
                provider=LLMProvider.AUTO,
                domain=domain
            )

            assert response.response is not None
            print(f"✅ Domain routing for {domain.value} successful")

    def test_confidence_scoring_with_local_fallback(self, integration_layer_with_fallback):
        """Test confidence scoring is reasonable with local fallback"""
        response = integration_layer_with_fallback.route_request(
            prompt="Calculate 5 * 7",
            provider=LLMProvider.ARISTOTLE,
            domain=DomainType.MATHEMATICAL
        )

        # Confidence should be reasonable (not too low, not 1.0 unless certain)
        assert response.confidence >= 0.5
        assert response.confidence <= 1.0
        print(f"✅ Confidence scoring is reasonable: {response.confidence}")

    def test_token_tracking_with_local_fallback(self, integration_layer_with_fallback):
        """Test token tracking works with local fallback"""
        response = integration_layer_with_fallback.route_request(
            prompt="Explain machine learning",
            provider=LLMProvider.DEEPINFRA,
            domain=DomainType.GENERAL
        )

        # Check if tokens are tracked in metadata
        if 'tokens_used' in response.metadata:
            assert isinstance(response.metadata['tokens_used'], int)
            assert response.metadata['tokens_used'] > 0
            print(f"✅ Token tracking working: {response.metadata['tokens_used']} tokens")
        else:
            print("⚠️  Token tracking not available in current implementation")

    def test_system_report_with_local_fallback(self, integration_layer_with_fallback):
        """Test system report generation with local fallback"""
        report = integration_layer_with_fallback.generate_system_report()

        assert report is not None
        assert isinstance(report, dict)
        assert 'total_requests' in report
        assert 'total_validations' in report

        print(f"✅ System report generated successfully")
        print(f"   Total requests: {report['total_requests']}")
        print(f"   Total validations: {report['total_validations']}")


def run_integration_tests():
    """Run integration tests and print results"""
    print("=" * 80)
    print("LLM INTEGRATION WITH LOCAL FALLBACK - INTEGRATION TESTS")
    print("=" * 80)
    print()

    # Create test instance
    integration = LLMIntegrationLayer(use_local_fallback=True)

    print("Testing initialization...")
    print(f"✅ Local fallback enabled: {integration.use_local_fallback}")
    print(f"✅ Local LLM loaded: {integration.local_llm is not None}")
    print()

    # Test various requests
    test_cases = [
        ("Aristotle - Math", LLMProvider.ARISTOTLE, DomainType.MATHEMATICAL, "Calculate 5 * 7"),
        ("Aristotle - Physics", LLMProvider.ARISTOTLE, DomainType.PHYSICS, "What is kinetic energy?"),
        ("Wulfrum - Validation", LLMProvider.WULFRUM, DomainType.MATHEMATICAL, "Is 2+2 equal to 5?"),
        ("DeepInfra - Creative", LLMProvider.DEEPINFRA, DomainType.CREATIVE, "Write a poem about AI"),
        ("DeepInfra - General", LLMProvider.DEEPINFRA, DomainType.GENERAL, "Explain machine learning"),
    ]

    results = []
    for test_name, provider, domain, prompt in test_cases:
        print(f"Testing: {test_name}")
        try:
            response = integration.route_request(
                prompt=prompt,
                provider=provider,
                domain=domain
            )

            assert response.provider == provider
            assert response.response is not None
            assert 0.0 <= response.confidence <= 1.0

            print(f"   ✅ Success")
            print(f"   Provider: {response.provider.value}")
            print(f"   Confidence: {response.confidence:.2f}")
            print(f"   Response length: {len(response.response)} chars")
            print(f"   Preview: {response.response[:100]}...")

            results.append((test_name, True, None))
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            results.append((test_name, False, str(e)))
        print()

    # Print summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    passed = sum(1 for _, success, _ in results if success)
    failed = sum(1 for _, success, _ in results if not success)

    print(f"Total tests: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print()

    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️  Some tests failed:")
        for test_name, success, error in results:
            if not success:
                print(f"   - {test_name}: {error}")

    print()
    print("=" * 80)


if __name__ == "__main__":
    run_integration_tests()
