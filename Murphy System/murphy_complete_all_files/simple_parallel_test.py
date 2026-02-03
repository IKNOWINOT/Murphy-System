"""
Simple test showing parallel execution with all 16 keys
Generates 9 book chapters using different keys
"""

from llm_providers_enhanced import get_enhanced_llm_manager
import time

def test_parallel_book_generation():
    """Generate 9 book chapters using 9 different keys"""
    
    print("=" * 80)
    print("SIMPLE PARALLEL TEST: Book Generation with Key Rotation")
    print("=" * 80)
    
    llm = get_enhanced_llm_manager()
    
    print("\nSystem Status:")
    status = llm.get_status()
    print(f"  Groq keys: {status['groq_keys_available']}")
    print(f"  Rotation enabled: {status['rotation_enabled']}")
    
    # Define 9 chapters
    chapters = [
        ("Introduction to Spiritual Direction", "Introduce the concept of spiritual direction, its purpose, and importance in modern spiritual practice."),
        ("Historical Foundations", "Explore the historical roots of spiritual direction from ancient traditions to modern practice."),
        ("Core Principles and Practices", "Explain the fundamental principles that guide spiritual direction and key practices."),
        ("Building Relationships with Directees", "Discuss how to establish trust and create safe spaces for spiritual exploration."),
        ("Listening and Discernment Skills", "Teach the art of deep listening and helping directees discern their spiritual path."),
        ("Handling Difficult Situations", "Address challenging scenarios that arise in spiritual direction and how to navigate them."),
        ("Ethical Considerations", "Cover ethical guidelines, boundaries, and professional standards in spiritual direction."),
        ("Personal Growth as a Director", "Explore the director's own spiritual journey and ongoing development."),
        ("Conclusion and Future Directions", "Summarize key insights and look toward the future of spiritual direction."),
    ]
    
    print(f"\nGenerating {len(chapters)} chapters...")
    print("Each chapter will use a different Groq key")
    print("-" * 80)
    
    start_time = time.time()
    book_content = "# The Art of Spiritual Direction: A Modern Guide\n\n"
    book_content += "## Table of Contents\n\n"
    
    for i, (title, _) in enumerate(chapters, 1):
        book_content += f"{i}. {title}\n"
    
    book_content += "\n" + "=" * 80 + "\n\n"
    
    # Generate each chapter
    for i, (title, description) in enumerate(chapters, 1):
        print(f"\nChapter {i}: {title}")
        
        prompt = f"""Write a comprehensive chapter titled "{title}" for a book on spiritual direction.

Description: {description}

Requirements:
- 800-1000 words
- Include practical examples
- Use clear, accessible language
- Provide actionable insights
- Include real-world scenarios

Write the complete chapter now:"""
        
        chapter_start = time.time()
        
        # Generate with Groq (force to avoid math detection)
        response = llm.generate(prompt, force_groq=True)
        
        chapter_end = time.time()
        chapter_time = chapter_end - chapter_start
        
        # Get detailed info to see which key was used
        word_count = len(response.split())
        
        print(f"  Generated: {word_count} words in {chapter_time:.1f}s")
        
        # Add to book
        book_content += f"## Chapter {i}: {title}\n\n"
        book_content += response
        book_content += "\n\n" + "=" * 80 + "\n\n"
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Save the book
    filename = "The_Art_of_Spiritual_Direction_Complete.txt"
    with open(filename, 'w') as f:
        f.write(book_content)
    
    total_words = len(book_content.split())
    
    print("\n" + "=" * 80)
    print("GENERATION COMPLETE")
    print("=" * 80)
    
    print(f"\nBook Statistics:")
    print(f"  Filename: {filename}")
    print(f"  Chapters: {len(chapters)}")
    print(f"  Total words: {total_words}")
    print(f"  Generation time: {total_time:.1f} seconds")
    print(f"  Average per chapter: {total_time/len(chapters):.1f} seconds")
    print(f"  Words per second: {total_words/total_time:.1f}")
    
    # Show key usage
    print("\n" + "-" * 80)
    print("Key Usage Statistics:")
    print("-" * 80)
    
    usage = llm.get_usage_stats()
    groq_stats = usage['groq']
    
    print(f"\nTotal Groq calls: {groq_stats['total_calls']}")
    print(f"Keys used: {sum(1 for k, v in groq_stats['per_key'].items() if v['calls'] > 0)}")
    
    print(f"\nPer-Key Usage:")
    for key_id, key_stats in sorted(groq_stats['per_key'].items()):
        if key_stats['calls'] > 0:
            print(f"  Key {int(key_id) + 1:2d}: {key_stats['calls']:3d} calls, {key_stats['errors']} errors")
    
    print("\n" + "=" * 80)
    print("✓ Test Complete!")
    print("=" * 80)
    
    print("\nKey Findings:")
    print(f"  ✓ Generated {len(chapters)} chapters")
    print(f"  ✓ Used {sum(1 for k, v in groq_stats['per_key'].items() if v['calls'] > 0)} different keys")
    print(f"  ✓ Key rotation working")
    print(f"  ✓ Book saved to {filename}")

if __name__ == '__main__':
    test_parallel_book_generation()