"""
Demo Script for Enhanced LLM Provider
Tests key rotation, math routing, and parallel execution
"""

import asyncio
import json
from datetime import datetime
from llm_providers_enhanced import get_enhanced_llm_manager


def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


async def demo_1_key_rotation():
    """
    Demo 1: Verify key rotation is working
    Makes multiple calls and tracks which key is used
    """
    print_section("DEMO 1: Key Rotation Verification")
    
    llm = get_enhanced_llm_manager()
    
    print(f"Status: {llm.get_status()}")
    print(f"\nMaking 20 consecutive calls to verify rotation...")
    print("-" * 80)
    
    results = []
    for i in range(20):
        prompt = f"Test call {i+1}. What is 2+2?"
        result = llm.generate(prompt)
        
        key_info = f"Key {result['key_index'] + 1}" if result['key_index'] else "Aristotle"
        success = "✓" if result['success'] else "✗"
        
        print(f"Call {i+1:2d}: {key_info:12s} | Provider: {result['provider']:12s} | {success}")
        
        results.append({
            'call': i+1,
            'key_index': result['key_index'],
            'provider': result['provider'],
            'success': result['success']
        })
    
    # Analyze rotation
    print("\n" + "-" * 80)
    print("Rotation Analysis:")
    key_counts = {}
    for r in results:
        if r['key_index'] is not None:
            key = r['key_index']
            key_counts[key] = key_counts.get(key, 0) + 1
    
    print(f"  Keys used: {len(key_counts)}")
    print(f"  Distribution: {dict(sorted(key_counts.items()))}")
    
    # Check if rotation completed
    if len(key_counts) >= min(16, 20):
        print(f"  ✓ Rotation working - used {len(key_counts)} different keys")
    else:
        print(f"  ✗ Rotation may not be working - only used {len(key_counts)} keys")
    
    # Show final stats
    print(f"\nUsage Statistics:")
    print(json.dumps(llm.get_usage_stats(), indent=2))


async def demo_2_math_routing():
    """
    Demo 2: Verify math tasks route to Aristotle
    Tests different prompts to see routing
    """
    print_section("DEMO 2: Math Task Routing")
    
    llm = get_enhanced_llm_manager()
    
    # Test prompts
    test_prompts = [
        ("Calculate ROI of AI investment", "Math task"),
        ("Write marketing copy for product", "General task"),
        ("Solve the differential equation: dy/dx = 2x", "Math task"),
        ("Generate a blog post about AI", "General task"),
        ("What is the break-even point for this business?", "Math task"),
        ("Create a project timeline", "General task"),
        ("Compute compound interest over 5 years", "Math task"),
        ("Write a company mission statement", "General task"),
    ]
    
    print("Testing routing with different prompt types...")
    print("-" * 80)
    
    for prompt, expected_type in test_prompts:
        result = llm.generate(prompt)
        
        provider = result['provider']
        math_task = result['math_task']
        key_info = f"Key {result['key_index'] + 1}" if result['key_index'] else "N/A"
        
        # Check if routing is correct
        expected_provider = 'aristotle' if expected_type == "Math task" else 'groq'
        correct = "✓" if provider == expected_provider else "✗"
        
        print(f"\n{expected_type:12s}")
        print(f"  Prompt: {prompt[:50]}...")
        print(f"  Routed to: {provider:12s} (Key: {key_info}) | Math detected: {math_task} | {correct}")
    
    print("\n" + "-" * 80)
    print(f"Usage Statistics:")
    print(json.dumps(llm.get_usage_stats(), indent=2))


async def demo_3_parallel_execution():
    """
    Demo 3: Test parallel execution with multiple keys
    Simulates what the Enhanced Runtime would do
    """
    print_section("DEMO 3: Parallel Execution (Simulating Enhanced Runtime)")
    
    llm = get_enhanced_llm_manager()
    
    # Simulate 9 agents working in parallel (like book chapters)
    tasks = [
        ("Write introduction to AI automation", "Introduction"),
        ("Explain AI fundamentals", "Chapter 1"),
        ("Describe practical applications", "Chapter 2"),
        ("Discuss implementation strategies", "Chapter 3"),
        ("Cover ROI and cost analysis", "Chapter 4"),
        ("Address common challenges", "Chapter 5"),
        ("Explore future trends", "Chapter 6"),
        ("Create conclusion", "Conclusion"),
        ("Generate marketing copy", "Marketing"),
    ]
    
    print(f"Launching {len(tasks)} parallel agents...")
    print("-" * 80)
    
    # Create async tasks
    async def run_task(prompt, task_name):
        result = llm.generate(prompt)
        key_info = f"Key {result['key_index'] + 1}" if result['key_index'] else "Aristotle"
        return {
            'task': task_name,
            'prompt': prompt,
            'provider': result['provider'],
            'key_index': result['key_index'],
            'success': result['success'],
            'key_used': key_info
        }
    
    # Execute in parallel
    start_time = datetime.now()
    results = await asyncio.gather(*[run_task(p, n) for p, n in tasks])
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Display results
    print(f"\nParallel Execution Results (completed in {duration:.2f}s):")
    print("-" * 80)
    
    # Group by key
    key_distribution = {}
    for r in results:
        key = r['key_index']
        if key is not None:
            if key not in key_distribution:
                key_distribution[key] = []
            key_distribution[key].append(r['task'])
    
    # Show distribution
    print(f"\nLoad Distribution:")
    for key, tasks in sorted(key_distribution.items()):
        print(f"  Key {key + 1:2d}: {', '.join(tasks)}")
    
    # Show individual results
    print(f"\nIndividual Results:")
    for i, r in enumerate(results, 1):
        success = "✓" if r['success'] else "✗"
        print(f"  {i:2d}. {r['task']:20s} | {r['provider']:12s} | Key {r['key_index']+1 if r['key_index'] else 'N/A':3s} | {success}")
    
    print("\n" + "-" * 80)
    print(f"Usage Statistics:")
    stats = llm.get_usage_stats()
    print(json.dumps(stats, indent=2))


async def demo_4_book_generation():
    """
    Demo 4: Generate a complete book using maximum parallelization
    """
    print_section("DEMO 4: Book Generation with Maximum Parallelization")
    
    llm = get_enhanced_llm_manager()
    
    book_topic = "AI Automation for Small Business"
    num_chapters = 9
    
    print(f"Generating book: '{book_topic}'")
    print(f"Chapters: {num_chapters}")
    print("Using maximum parallelization with rotating keys...")
    print("-" * 80)
    
    # Define chapters
    chapters = [
        ("Introduction to AI Automation", "Overview of AI automation for small businesses, benefits, and getting started"),
        ("Understanding AI Fundamentals", "Core concepts, terminology, and types of AI automation"),
        ("Identifying Automation Opportunities", "How to find the best automation opportunities in your business"),
        ("Getting Started with AI", "First steps, tools selection, and initial implementation"),
        ("Customer Service Automation", "Chatbots, automated responses, and customer support systems"),
        ("Marketing and Sales Automation", "Email campaigns, social media, lead generation automation"),
        ("Operations and Workflow Automation", "Streamlining internal processes and operations"),
        ("Data and Analytics", "Using AI for data analysis, insights, and decision making"),
        ("Future of AI in Business", "Emerging trends and preparing for the future"),
    ]
    
    # Generate chapters in parallel
    start_time = datetime.now()
    
    async def write_chapter(title, description):
        prompt = f"Write a chapter titled '{title}' about: {description}\n\nInclude examples, case studies, and practical advice."
        result = llm.generate(prompt)
        
        return {
            'chapter': title,
            'description': description,
            'provider': result['provider'],
            'key_index': result['key_index'],
            'success': result['success'],
            'word_count': len(result['response'].split()) if result['response'] else 0
        }
    
    chapter_results = await asyncio.gather(*[write_chapter(t, d) for t, d in chapters])
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Display results
    print(f"\nBook Generation Results (completed in {duration:.2f}s):")
    print("-" * 80)
    
    total_words = 0
    for i, ch in enumerate(chapter_results, 1):
        success = "✓" if ch['success'] else "✗"
        key = ch['key_index'] + 1 if ch['key_index'] else "N/A"
        words = ch['word_count']
        total_words += words
        
        print(f"  Chapter {i:2d}: {ch['chapter'][:40]:40s}")
        print(f"    Key: {key:3s} | Words: {words:4d} | {success}")
    
    print("\n" + "-" * 80)
    print(f"Book Statistics:")
    print(f"  Total chapters: {len(chapter_results)}")
    print(f"  Total words: {total_words}")
    print(f"  Generation time: {duration:.2f} seconds")
    print(f"  Average time per chapter: {duration/len(chapter_results):.2f} seconds")
    print(f"  Words per second: {total_words/duration:.1f}")
    
    print("\n" + "-" * 80)
    print(f"Usage Statistics:")
    stats = llm.get_usage_stats()
    print(json.dumps(stats, indent=2))


async def main():
    """Run all demos"""
    print_section("MURPHY SYSTEM ENHANCED LLM PROVIDER DEMO")
    print("This demo showcases:")
    print("  1. Key rotation (round-robin)")
    print("  2. Math task routing to Aristotle")
    print("  3. Parallel execution with load balancing")
    print("  4. Book generation with maximum parallelization")
    print()
    
    try:
        # Run demos
        await demo_1_key_rotation()
        await demo_2_math_routing()
        await demo_3_parallel_execution()
        await demo_4_book_generation()
        
        print_section("DEMO COMPLETE")
        print("All demos finished successfully!")
        print("\nThe Enhanced LLM Provider is ready for integration with the Runtime Orchestrator.")
        
    except Exception as e:
        print(f"\n\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())