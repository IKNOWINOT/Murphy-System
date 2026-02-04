# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Quick test to verify key rotation is working
"""

from llm_providers_enhanced import get_enhanced_llm_manager

print("=" * 80)
print("QUICK TEST: Key Rotation Verification")
print("=" * 80)

llm = get_enhanced_llm_manager()

print(f"\nStatus: {llm.get_status()}")

print(f"\nMaking 20 calls to test rotation...")
print("-" * 80)

results = []
for i in range(20):
    prompt = f"Test {i+1}: Write a brief summary about AI automation."
    result = llm.generate(prompt)
    
    key_info = f"Key {result['key_index'] + 1}" if result['key_index'] else "Aristotle"
    provider = result['provider']
    success = "✓" if result['success'] else "✗"
    
    print(f"Call {i+1:2d}: {key_info:12s} | {provider:12s} | {success}")
    
    results.append({
        'call': i+1,
        'key': result['key_index'],
        'provider': provider,
        'success': result['success']
    })

print("\n" + "-" * 80)
print("Analysis:")
key_counts = {}
for r in results:
    if r['key'] is not None:
        key_counts[r['key']] = key_counts.get(r['key'], 0) + 1

print(f"  Keys used: {len(key_counts)}")
print(f"  Distribution: {dict(sorted(key_counts.items()))}")

if len(key_counts) >= 16:
    print(f"\n✓ SUCCESS: Rotation working - used all {len(key_counts)} keys!")
else:
    print(f"\n⚠ PARTIAL: Used {len(key_counts)} keys (may need more calls to see full rotation)")

print(f"\nUsage Stats:")
import json
print(json.dumps(llm.get_usage_stats(), indent=2))

print("\n" + "=" * 80)