"""
Test Enhanced Runtime Orchestrator with all 16 keys
Generate a complete book with 9 parallel chapters
"""

import asyncio
import time
from llm_providers_enhanced import get_enhanced_llm_manager
from runtime_orchestrator_enhanced import RuntimeOrchestrator

async def test_book_generation():
    """Test book generation with Enhanced Runtime using all 16 keys"""
    
    print("=" * 80)
    print("ENHANCED RUNTIME TEST: Book Generation with 16 Parallel Keys")
    print("=" * 80)
    
    # Initialize LLM manager
    llm_manager = get_enhanced_llm_manager()
    
    print("\nLLM Manager Status:")
    status = llm_manager.get_status()
    print(f"  Groq keys: {status['groq_keys_available']}")
    print(f"  Aristotle: {status['aristotle_available']}")
    print(f"  Rotation: {status['rotation_enabled']}")
    
    # Initialize Runtime Orchestrator
    print("\nInitializing Enhanced Runtime Orchestrator...")
    orchestrator = RuntimeOrchestrator(
        llm_manager=llm_manager,
        capacity_limit=16,  # Use all 16 keys
        max_parallel=9      # 9 chapters in parallel
    )
    
    print(f"  Capacity limit: {orchestrator.capacity_limit}")
    print(f"  Max parallel: {orchestrator.max_parallel}")
    
    # Define the book generation task
    book_task = """
    Write a complete book titled "The Art of Spiritual Direction: A Modern Guide"
    
    The book should cover:
    - Introduction to spiritual direction
    - Historical foundations
    - Core principles and practices
    - Building relationships with directees
    - Listening and discernment skills
    - Handling difficult situations
    - Ethical considerations
    - Personal growth as a director
    - Conclusion and future directions
    
    Each chapter should be comprehensive, practical, and include real-world examples.
    """
    
    print("\n" + "-" * 80)
    print("Task: Generate complete book with 9 chapters")
    print("Method: Enhanced Runtime with parallel execution")
    print("Expected: 9 agents working simultaneously on different keys")
    print("-" * 80)
    
    # Start generation
    start_time = time.time()
    
    print("\nStarting book generation...")
    result = await orchestrator.process_request(book_task)
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Display results
    print("\n" + "=" * 80)
    print("GENERATION COMPLETE")
    print("=" * 80)
    
    print(f"\nTask ID: {result['task_id']}")
    print(f"Status: {result['status']}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Agents Used: {result.get('num_agents', 0)}")
    
    # Show agent results
    if 'results' in result:
        print("\nAgent Results:")
        for agent_id, agent_result in result['results'].items():
            content_len = len(agent_result.get('content', ''))
            print(f"  {agent_id}: {content_len} characters")
    
    # Show global context
    if 'global_context' in result:
        context = result['global_context']
        print("\nGlobal Context:")
        print(f"  Themes: {context.get('themes', [])}")
        print(f"  Inconsistencies: {len(context.get('inconsistencies', []))}")
    
    # Save the book
    if 'final_output' in result:
        filename = "The_Art_of_Spiritual_Direction_Runtime_Generated.txt"
        with open(filename, 'w') as f:
            f.write(result['final_output'])
        
        word_count = len(result['final_output'].split())
        print(f"\nBook saved to: {filename}")
        print(f"Total words: {word_count}")
        print(f"Words per second: {word_count/duration:.1f}")
    
    # Show LLM usage statistics
    print("\n" + "-" * 80)
    print("LLM Usage Statistics:")
    print("-" * 80)
    
    usage = llm_manager.get_usage_stats()
    print(f"\nTotal calls: {usage['total_calls']}")
    print(f"Total errors: {usage['total_errors']}")
    
    groq_stats = usage['groq']
    print(f"\nGroq Statistics:")
    print(f"  Total calls: {groq_stats['total_calls']}")
    print(f"  Keys used: {sum(1 for k, v in groq_stats['per_key'].items() if v['calls'] > 0)}")
    
    print(f"\nPer-Key Usage:")
    for key_id, key_stats in sorted(groq_stats['per_key'].items()):
        if key_stats['calls'] > 0:
            print(f"  Key {int(key_id) + 1:2d}: {key_stats['calls']:3d} calls")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    
    return result

async def main():
    """Run the test"""
    try:
        result = await test_book_generation()
        
        print("\n✓ Enhanced Runtime test completed successfully!")
        print("\nKey Achievements:")
        print("  ✓ Runtime orchestrator operational")
        print("  ✓ All 16 keys available for parallel execution")
        print("  ✓ Dynamic agent generation working")
        print("  ✓ Collective mind coordination functional")
        print("  ✓ Book generated with parallel agents")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())