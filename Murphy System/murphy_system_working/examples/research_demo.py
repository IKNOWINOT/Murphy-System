"""
Research & Generation Demo
Shows the chatbot's ability to research, distill, and generate
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.research_engine import ResearchEngine, CodeGenerator, ReportGenerator


def demo_research():
    """Demo: Multi-source research"""
    print("\n" + "=" * 70)
    print("DEMO 1: MULTI-SOURCE RESEARCH")
    print("=" * 70)
    
    research_engine = ResearchEngine()
    
    topics = ["ISO 26262", "ISO 9001", "IEC 61508"]
    
    for topic in topics:
        print(f"\n📚 Researching: {topic}")
        result = research_engine.research_topic(topic, depth="standard")
        
        print(f"  ✓ Sources: {result.synthesis['num_sources']}")
        print(f"  ✓ Confidence: {result.confidence:.2f}")
        print(f"  ✓ Verified: {result.synthesis['verified']}")
        
        if result.synthesis['key_facts']:
            fact = result.synthesis['key_facts'][0]
            print(f"  ✓ Key info: {fact['facts'].get('title', 'N/A')}")


def demo_code_generation():
    """Demo: Code generation from research"""
    print("\n" + "=" * 70)
    print("DEMO 2: CODE GENERATION")
    print("=" * 70)
    
    code_gen = CodeGenerator()
    
    tasks = [
        ("Create a safe calculator", "python"),
        ("Build an API client", "python"),
        ("Process JSON data", "python"),
    ]
    
    for task, lang in tasks:
        print(f"\n💻 Task: {task}")
        result = code_gen.generate_code(task, language=lang, research_first=False)
        
        print(f"  ✓ Language: {result['language']}")
        print(f"  ✓ Verified: {result['verified']}")
        print(f"  ✓ Explanation: {result['explanation']}")
        print(f"  ✓ Code length: {len(result['code'])} chars")


def demo_report_generation():
    """Demo: Report generation from research"""
    print("\n" + "=" * 70)
    print("DEMO 3: REPORT GENERATION")
    print("=" * 70)
    
    report_gen = ReportGenerator()
    
    print(f"\n📄 Generating report on: ISO 26262")
    report = report_gen.generate_report(
        topic="ISO 26262",
        format="markdown",
        depth="standard"
    )
    
    print(f"  ✓ Format: {report['format']}")
    print(f"  ✓ Confidence: {report['confidence']:.2f}")
    print(f"  ✓ Verified: {report['verified']}")
    print(f"  ✓ Sources: {len(report['sources'])}")
    
    print(f"\n📋 Report Content:")
    print("-" * 70)
    print(report['content'])


def demo_integrated_workflow():
    """Demo: Complete research → distill → generate workflow"""
    print("\n" + "=" * 70)
    print("DEMO 4: INTEGRATED WORKFLOW")
    print("=" * 70)
    
    print("\n🔬 Workflow: Research → Distill → Generate")
    print("-" * 70)
    
    # Step 1: Research
    print("\n[Step 1] Research topic...")
    research_engine = ResearchEngine()
    research = research_engine.research_topic("ISO 26262", depth="standard")
    print(f"  ✓ Found {research.synthesis['num_sources']} sources")
    
    # Step 2: Distill
    print("\n[Step 2] Distill information...")
    key_facts = research.synthesis['key_facts']
    print(f"  ✓ Distilled {len(key_facts)} key facts")
    
    # Step 3: Generate report
    print("\n[Step 3] Generate report...")
    report_gen = ReportGenerator()
    report = report_gen.generate_report("ISO 26262", format="text", depth="standard")
    print(f"  ✓ Generated {len(report['content'])} char report")
    
    # Step 4: Generate code
    print("\n[Step 4] Generate related code...")
    code_gen = CodeGenerator()
    code = code_gen.generate_code(
        "Create a standards compliance checker",
        language="python",
        research_first=False
    )
    print(f"  ✓ Generated {len(code['code'])} char code")
    
    print("\n✅ Complete workflow executed!")
    print("   Research → Distill → Generate (Report + Code)")


def main():
    """Run all demos"""
    print("=" * 70)
    print("🤖 RESEARCH & GENERATION CAPABILITIES DEMO")
    print("=" * 70)
    print("\nThis demonstrates the chatbot's ability to:")
    print("  1. Research topics from multiple sources")
    print("  2. Distill information")
    print("  3. Generate code based on research")
    print("  4. Generate reports from research")
    print("\nAll using VERIFIED sources only - Murphy-resistant!")
    
    demo_research()
    demo_code_generation()
    demo_report_generation()
    demo_integrated_workflow()
    
    print("\n" + "=" * 70)
    print("✅ ALL DEMOS COMPLETE")
    print("=" * 70)
    print("\n🎯 Key Capabilities Demonstrated:")
    print("  ✓ Multi-source research (Wikipedia, Standards DB, Wikidata)")
    print("  ✓ Information distillation (synthesis from multiple sources)")
    print("  ✓ Code generation (from verified templates)")
    print("  ✓ Report generation (markdown, HTML, text)")
    print("  ✓ Integrated workflows (research → distill → generate)")
    print("  ✓ All Murphy-resistant (verified sources only)")
    print("=" * 70)


if __name__ == "__main__":
    main()