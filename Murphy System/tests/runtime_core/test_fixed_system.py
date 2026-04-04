"""
Comprehensive tests for fixed MFGC v1.1 system
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest

try:
    from chatbot_v1_1_fixed import ChatbotV1_1Fixed
except ImportError:
    pytest.skip("chatbot_v1_1_fixed module not available", allow_module_level=True)
from safe_llm_wrapper import SafeLLMWrapper, MFGCIntegratedLLM
import re


def test_safety_gates():
    """Test that safety gates catch problematic outputs"""
    print("\n=== TEST: Safety Gates ===")

    wrapper = SafeLLMWrapper(None)

    # Test 1: Hallucination markers
    hallucinated = "Visit [location] Coffeehouse at [address]"
    assert not wrapper._check_hallucination_markers(hallucinated), "Should catch hallucination markers"
    print("✓ Catches hallucination markers")

    # Test 2: Unbounded lists
    unbounded = "\n".join([f"{i}. Item" for i in range(1, 21)])
    assert not wrapper._check_unbounded_lists(unbounded), "Should catch unbounded lists"
    print("✓ Catches unbounded lists")

    # Test 3: Coherence
    repetitive = "hello " * 100
    assert not wrapper._check_coherence(repetitive), "Should catch repetitive text"
    print("✓ Catches incoherent text")

    # Test 4: Clean text passes
    clean = "This is a clear, concise response to your question."
    assert wrapper._check_hallucination_markers(clean), "Clean text should pass"
    assert wrapper._check_unbounded_lists(clean), "Clean text should pass"
    assert wrapper._check_coherence(clean), "Clean text should pass"
    print("✓ Clean text passes all gates")


def test_response_markers():
    """Test that responses have proper markers"""
    print("\n=== TEST: Response Markers ===")

    chatbot = ChatbotV1_1Fixed(use_llm=False)

    # Test simple greeting
    response = chatbot.process_message("hello", {})
    assert response['marker'] in ['V', 'G', 'B', 'R'], f"Invalid marker: {response['marker']}"
    assert 'metadata' in response, "Response should have metadata"
    assert 'confidence' in response['metadata'], "Metadata should have confidence"
    print(f"✓ Greeting has marker: {response['marker']}")

    # Test question
    response = chatbot.process_message("What can you do?", {})
    assert response['marker'] in ['V', 'G', 'B', 'R'], f"Invalid marker: {response['marker']}"
    print(f"✓ Question has marker: {response['marker']}")

    # Test complex task
    response = chatbot.process_message("Design a distributed system", {})
    assert response['marker'] in ['V', 'G', 'B', 'R'], f"Invalid marker: {response['marker']}"
    print(f"✓ Complex task has marker: {response['marker']}")


def test_complexity_routing():
    """Test that complexity routing works correctly"""
    print("\n=== TEST: Complexity Routing ===")

    chatbot = ChatbotV1_1Fixed(use_llm=False)

    # Low complexity
    response = chatbot.process_message("hello", {})
    routing = response['metadata'].get('routing', 'unknown')
    complexity = response['metadata'].get('complexity', 'unknown')
    print(f"✓ 'hello' → routing={routing}, complexity={complexity}")

    # Medium complexity
    response = chatbot.process_message("What is Bayes theorem?", {})
    routing = response['metadata'].get('routing', 'unknown')
    complexity = response['metadata'].get('complexity', 'unknown')
    print(f"✓ 'What is Bayes theorem?' → routing={routing}, complexity={complexity}")

    # High complexity
    response = chatbot.process_message("Design a distributed real-time data processing system with fault tolerance", {})
    routing = response['metadata'].get('routing', 'unknown')
    complexity = response['metadata'].get('complexity', 'unknown')
    print(f"✓ Complex design task → routing={routing}, complexity={complexity}")
    assert complexity == 'high', "Complex task should be high complexity"


def test_bounded_responses():
    """Test that responses are properly bounded"""
    print("\n=== TEST: Bounded Responses ===")

    chatbot = ChatbotV1_1Fixed(use_llm=False)

    test_messages = [
        "hello",
        "What can you do?",
        "Tell me about yourself",
        "What is LLM?",
        "Design a system"
    ]

    for msg in test_messages:
        response = chatbot.process_message(msg, {})
        length = len(response['content'])
        assert length < 2000, f"Response too long: {length} chars for '{msg}'"
        print(f"✓ '{msg}' → {length} chars (bounded)")


def test_no_hallucination_patterns():
    """Test that responses don't contain hallucination patterns"""
    print("\n=== TEST: No Hallucination Patterns ===")

    chatbot = ChatbotV1_1Fixed(use_llm=False)

    hallucination_patterns = [
        r'\[location\]',
        r'\[name\]',
        r'\[address\]',
        r'\[placeholder\]',
    ]

    test_messages = [
        "hello",
        "What can you do?",
        "Tell me about cafes",
        "What is your name?"
    ]

    for msg in test_messages:
        response = chatbot.process_message(msg, {})
        content = response['content']

        for pattern in hallucination_patterns:
            matches = re.findall(pattern, content)
            assert len(matches) == 0, f"Found hallucination pattern '{pattern}' in response to '{msg}'"

        print(f"✓ '{msg}' → No hallucination patterns")


def test_metadata_completeness():
    """Test that metadata is complete"""
    print("\n=== TEST: Metadata Completeness ===")

    chatbot = ChatbotV1_1Fixed(use_llm=False)

    response = chatbot.process_message("hello", {})

    required_fields = ['marker', 'content', 'metadata', 'marker_class']
    for field in required_fields:
        assert field in response, f"Missing required field: {field}"

    print(f"✓ Response has all required fields: {required_fields}")

    metadata = response['metadata']
    metadata_fields = ['routing', 'complexity', 'confidence']
    for field in metadata_fields:
        assert field in metadata, f"Missing metadata field: {field}"

    print(f"✓ Metadata has all required fields: {metadata_fields}")


def test_confidence_tracking():
    """Test that confidence is properly tracked"""
    print("\n=== TEST: Confidence Tracking ===")

    chatbot = ChatbotV1_1Fixed(use_llm=False)

    test_cases = [
        ("hello", "Simple greeting should have high confidence"),
        ("What can you do?", "Capability question should have high confidence"),
        ("What is quantum mechanics?", "Complex topic may have lower confidence")
    ]

    for msg, description in test_cases:
        response = chatbot.process_message(msg, {})
        confidence = response['metadata'].get('confidence', 0)
        assert 0 <= confidence <= 1, f"Confidence out of range: {confidence}"
        print(f"✓ '{msg}' → confidence={confidence:.2f} ({description})")


def test_murphy_risk_computation():
    """Test that Murphy risk is computed for LLM responses"""
    print("\n=== TEST: Murphy Risk Computation ===")

    # Test with safe wrapper directly
    wrapper = SafeLLMWrapper(None)

    # Simulate different risk levels
    test_texts = [
        ("Clean response", "This is a clear and concise answer."),
        ("Hallucinated", "Visit [location] at [address] for [service]"),
        ("Unbounded", "\n".join([f"{i}. Item" for i in range(1, 21)])),
        ("Repetitive", "hello " * 100)
    ]

    for name, text in test_texts:
        result = wrapper.safe_generate(text, {}, max_tokens=100)
        murphy_risk = result.get('murphy_risk', 0)
        print(f"✓ {name} → Murphy risk={murphy_risk:.2f}, marker={result['marker']}")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("RUNNING COMPREHENSIVE FIXED SYSTEM TESTS")
    print("="*60)

    tests = [
        test_safety_gates,
        test_response_markers,
        test_complexity_routing,
        test_bounded_responses,
        test_no_hallucination_patterns,
        test_metadata_completeness,
        test_confidence_tracking,
        test_murphy_risk_computation
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
