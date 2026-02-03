"""
Enhanced Chatbot Demo
Shows all advanced capabilities integrated into chat interface
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.enhanced_chatbot import create_enhanced_chatbot


def demo_enhanced_chat():
    """Demo: Enhanced chat with automatic capability detection"""
    
    print("=" * 70)
    print("🤖 ENHANCED CHATBOT DEMO")
    print("=" * 70)
    print("\nCreating enhanced chatbot...")
    
    chatbot = create_enhanced_chatbot(
        use_local_model=False,
        min_confidence=0.60
    )
    
    print("\n✓ Chatbot ready!\n")
    print("=" * 70)
    print("CONVERSATIONAL INTERFACE")
    print("=" * 70)
    
    # Test conversations
    conversations = [
        # Research
        ("Research ISO 26262", "📚 Research"),
        
        # Code generation
        ("Generate code in Python for an API client", "💻 Code Gen"),
        
        # Advanced research - Control Theory
        ("Explain PID control theory", "🔬 Control Theory"),
        
        # Advanced research - Probability
        ("Tell me about Bayes theorem", "🔬 Probability"),
        
        # Advanced research - Quantum
        ("Explain quantum superposition", "🔬 Quantum"),
        
        # Advanced research - Statistics
        ("Explain linear regression", "🔬 Statistics"),
        
        # Multi-language code
        ("Generate code in JavaScript for data processing", "💻 Multi-Lang"),
        
        # Report generation
        ("Generate report on ISO 9001 in markdown", "📄 Report"),
    ]
    
    for i, (query, category) in enumerate(conversations, 1):
        print(f"\n[{category} - Turn {i}]")
        print(f"You: {query}")
        print("-" * 70)
        
        response = chatbot.chat(query)
        
        # Truncate long responses for demo
        if len(response) > 500:
            print(f"Bot: {response[:500]}...")
            print(f"     (truncated - {len(response)} total chars)")
        else:
            print(f"Bot: {response}")
        
        print()
    
    print("=" * 70)
    print("✅ ENHANCED CHAT DEMO COMPLETE")
    print("=" * 70)


def demo_capabilities_summary():
    """Show summary of all capabilities"""
    
    print("\n" + "=" * 70)
    print("📊 CAPABILITIES SUMMARY")
    print("=" * 70)
    
    capabilities = {
        "Research": [
            "Multi-source research (Wikipedia, Standards DB, Wikidata)",
            "Information distillation and synthesis",
            "Confidence scoring",
            "Source attribution"
        ],
        "Code Generation": [
            "10 programming languages supported",
            "Python, JavaScript, Java, C++, C#, Go, Rust, TypeScript, Ruby, PHP",
            "Verified templates and patterns",
            "Automatic test generation",
            "Documentation generation"
        ],
        "Advanced Research": [
            "Control Theory (PID, feedback, stability, state space)",
            "Probability Theory (Bayes, distributions, Markov chains)",
            "Quantum Mechanics (Schrödinger, superposition, entanglement)",
            "Statistics (regression, hypothesis testing, ANOVA)",
            "Domain-specific equations and concepts",
            "Applications and related topics"
        ],
        "Report Generation": [
            "6 formats: Markdown, HTML, LaTeX, JSON, Text, PDF",
            "Customizable depth (quick, standard, deep)",
            "Include/exclude equations and code",
            "Source attribution",
            "Confidence scores"
        ],
        "Chat Integration": [
            "Automatic capability detection",
            "Natural language interface",
            "Multi-turn conversations",
            "Context awareness",
            "Murphy-resistant throughout"
        ]
    }
    
    for category, features in capabilities.items():
        print(f"\n{category}:")
        for feature in features:
            print(f"  ✓ {feature}")
    
    print("\n" + "=" * 70)


def demo_advanced_research():
    """Demo: Advanced research in specific domains"""
    
    print("\n" + "=" * 70)
    print("🔬 ADVANCED RESEARCH DEMO")
    print("=" * 70)
    
    from src.advanced_research import AdvancedResearchEngine
    
    engine = AdvancedResearchEngine()
    
    topics = [
        ("PID controller", "control"),
        ("Bayes theorem", "probability"),
        ("Quantum entanglement", "quantum"),
        ("Linear regression", "statistics")
    ]
    
    for topic, domain in topics:
        print(f"\n📚 Researching: {topic} (Domain: {domain})")
        result = engine.research(topic, domain)
        
        print(f"  ✓ Domain: {result.domain}")
        print(f"  ✓ Confidence: {result.confidence:.2f}")
        print(f"  ✓ Concepts: {len(result.mathematical_concepts)}")
        print(f"  ✓ Equations: {len(result.key_equations)}")
        print(f"  ✓ Applications: {len(result.applications)}")
        
        if result.mathematical_concepts:
            print(f"  ✓ Key concept: {result.mathematical_concepts[0]}")
        if result.key_equations:
            print(f"  ✓ Key equation: {result.key_equations[0]}")


def demo_multi_language():
    """Demo: Multi-language code generation"""
    
    print("\n" + "=" * 70)
    print("💻 MULTI-LANGUAGE CODE GENERATION DEMO")
    print("=" * 70)
    
    from src.multi_language_codegen import MultiLanguageCodeGenerator
    
    codegen = MultiLanguageCodeGenerator()
    
    task = "Create an API client"
    languages = ["python", "javascript", "java", "go", "rust"]
    
    for lang in languages:
        print(f"\n🔧 Generating {lang.upper()} code...")
        result = codegen.generate(task, lang, research_first=False)
        
        print(f"  ✓ Language: {result['language']}")
        print(f"  ✓ Verified: {result['verified']}")
        print(f"  ✓ Code length: {len(result['code'])} chars")
        print(f"  ✓ Has tests: {len(result['tests']) > 0}")
        print(f"  ✓ Has docs: {len(result['documentation']) > 0}")


def main():
    """Run all demos"""
    
    print("=" * 70)
    print("🚀 ENHANCED CHATBOT - COMPLETE DEMO")
    print("=" * 70)
    print("\nThis demo shows:")
    print("  1. Enhanced conversational interface")
    print("  2. Advanced research capabilities")
    print("  3. Multi-language code generation")
    print("  4. All integrated into natural chat")
    
    demo_enhanced_chat()
    demo_capabilities_summary()
    demo_advanced_research()
    demo_multi_language()
    
    print("\n" + "=" * 70)
    print("✅ ALL ENHANCED DEMOS COMPLETE")
    print("=" * 70)
    print("\n🎯 What You Can Do:")
    print("  • Research any topic with multi-source verification")
    print("  • Generate code in 10 programming languages")
    print("  • Get advanced research in control theory, probability, quantum, statistics")
    print("  • Generate reports in 6 formats")
    print("  • All through natural conversation")
    print("  • All Murphy-resistant with verified sources")
    print("=" * 70)


if __name__ == "__main__":
    main()