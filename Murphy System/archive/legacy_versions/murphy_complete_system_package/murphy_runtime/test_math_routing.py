# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Test math routing to Aristotle
"""

from llm_providers_enhanced import get_enhanced_llm_manager

print("=" * 80)
print("TEST: Math Task Routing to Aristotle")
print("=" * 80)

llm = get_enhanced_llm_manager()

test_cases = [
    ("Calculate ROI of AI investment", "Math task - should route to Aristotle"),
    ("Write marketing copy for a product", "General task - should route to Groq"),
    ("Solve the differential equation: dy/dx = 2x", "Math task - should route to Aristotle"),
    ("Generate a blog post about AI", "General task - should route to Groq"),
    ("What is the break-even point?", "Math task - should route to Aristotle"),
    ("Create a project timeline", "General task - should route to Groq"),
    ("Compute compound interest over 5 years", "Math task - should route to Aristotle"),
    ("Write a company mission statement", "General task - should route to Groq"),
]

print("\nTesting math detection and routing...")
print("-" * 80)

for prompt, expected in test_cases:
    result = llm.generate(prompt)
    
    provider = result['provider']
    math_detected = result['math_task']
    key_info = f"Key {result['key_index'] + 1}" if result['key_index'] else "N/A"
    
    # Check routing correctness
    if "Math task" in expected:
        correct = "✓" if provider == 'aristotle' else "✗"
    else:
        correct = "✓" if provider == 'groq' else "✗"
    
    print(f"\n{expected}")
    print(f"  Prompt: {prompt[:50]}...")
    print(f"  Provider: {provider:12s} | Key: {key_info:4s} | Math detected: {math_detected} | {correct}")

print("\n" + "-" * 80)
print(f"Usage Statistics:")
import json
print(json.dumps(llm.get_usage_stats(), indent=2))

print("\n" + "=" * 80)