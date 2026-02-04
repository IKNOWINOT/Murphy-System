"""
Quick System Test - 100 Representative Tests

Tests the unified system with realistic scenarios that complete quickly.
Uses fuzzy matching to verify semantic correctness.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unified_mfgc import UnifiedMFGC
import time

def fuzzy_match(text: str, keywords: list, min_matches: int = 1) -> bool:
    """Check if text contains relevant keywords"""
    text_lower = text.lower()
    matches = sum(1 for kw in keywords if kw.lower() in text_lower)
    return matches >= min_matches

def verify_response(response: str) -> bool:
    """Verify response is substantive"""
    return response and len(response) > 20 and 'error' not in response.lower()

def run_tests():
    system = UnifiedMFGC()
    passed = 0
    failed = 0
    start_time = time.time()
    
    print("\n" + "="*80)
    print("QUICK SYSTEM TEST - 100 TESTS")
    print("="*80)
    print("\nTesting ONE unified system across all confidence bands")
    print("Using fuzzy match verification (semantic relevance)\n")
    
    tests = [
        # Introductory Band (30 tests)
        ("hi", ["hello", "mfgc", "system"], "introductory"),
        ("hello", ["hello", "system"], "introductory"),
        ("hey", ["hello", "system"], "introductory"),
        ("good morning", ["hello", "morning"], "introductory"),
        ("what can you do", ["capabilit", "swarm"], "introductory"),
        ("help", ["help", "capabilit"], "introductory"),
        ("status", ["status", "system"], "introductory"),
        ("thanks", ["thank", "welcome"], "introductory"),
        ("greetings", ["hello", "system"], "introductory"),
        ("hello there", ["hello", "system"], "introductory"),
        ("what are your capabilities", ["capabilit", "feature"], "introductory"),
        ("how can you help", ["help", "capabilit"], "introductory"),
        ("are you working", ["work", "status"], "introductory"),
        ("thank you", ["thank", "welcome"], "introductory"),
        ("hiya", ["hello", "system"], "introductory"),
        ("what is this", ["system", "mfgc"], "introductory"),
        ("are you online", ["online", "status"], "introductory"),
        ("great", ["great", "good"], "introductory"),
        ("hey there", ["hello", "system"], "introductory"),
        ("hi there", ["hello", "system"], "introductory"),
        ("what do you do", ["capabilit", "system"], "introductory"),
        ("can you help me", ["help", "assist"], "introductory"),
        ("is this working", ["work", "status"], "introductory"),
        ("awesome", ["awesome", "great"], "introductory"),
        ("describe your capabilities", ["capabilit", "feature"], "introductory"),
        ("hello?", ["hello", "system"], "introductory"),
        ("perfect", ["perfect", "great"], "introductory"),
        ("okay", ["okay", "good"], "introductory"),
        ("nice", ["nice", "good"], "introductory"),
        ("cool", ["cool", "good"], "introductory"),
        
        # Conversational Band - Software (25 tests)
        ("design a website", ["web", "design", "frontend"], "conversational"),
        ("create a web app", ["web", "app", "design"], "conversational"),
        ("build an API", ["api", "backend", "endpoint"], "conversational"),
        ("design a database", ["database", "schema", "table"], "conversational"),
        ("create a mobile app", ["mobile", "app", "ios"], "conversational"),
        ("build a REST API", ["rest", "api", "endpoint"], "conversational"),
        ("design user tables", ["user", "table", "database"], "conversational"),
        ("create an iOS app", ["ios", "app", "mobile"], "conversational"),
        ("build a dashboard", ["dashboard", "web", "interface"], "conversational"),
        ("design a user interface", ["interface", "ui", "design"], "conversational"),
        ("create authentication API", ["auth", "api", "security"], "conversational"),
        ("build a CRM system", ["crm", "customer", "management"], "conversational"),
        ("design a landing page", ["landing", "page", "web"], "conversational"),
        ("create a database schema", ["schema", "database", "table"], "conversational"),
        ("build an Android app", ["android", "app", "mobile"], "conversational"),
        ("design a GraphQL API", ["graphql", "api", "query"], "conversational"),
        ("create product database", ["product", "database", "schema"], "conversational"),
        ("build a Flutter app", ["flutter", "mobile", "app"], "conversational"),
        ("design a responsive website", ["responsive", "web", "design"], "conversational"),
        ("create a data model", ["data", "model", "entity"], "conversational"),
        ("build a microservice", ["microservice", "api", "service"], "conversational"),
        ("design analytics database", ["analytics", "database", "data"], "conversational"),
        ("create a React Native app", ["react", "native", "mobile"], "conversational"),
        ("build a payment API", ["payment", "api", "transaction"], "conversational"),
        ("design NoSQL database", ["nosql", "database", "document"], "conversational"),
        
        # Conversational Band - Business (25 tests)
        ("create a business plan", ["business", "plan", "strategy"], "conversational"),
        ("analyze the market", ["market", "analysis", "research"], "conversational"),
        ("create a budget", ["budget", "financial", "plan"], "conversational"),
        ("optimize operations", ["optimize", "operation", "efficiency"], "conversational"),
        ("design a growth strategy", ["growth", "strategy", "scale"], "conversational"),
        ("research competitors", ["competitor", "research", "analysis"], "conversational"),
        ("design a revenue model", ["revenue", "model", "income"], "conversational"),
        ("improve processes", ["improve", "process", "efficiency"], "conversational"),
        ("create a competitive strategy", ["competitive", "strategy", "advantage"], "conversational"),
        ("analyze pricing models", ["pricing", "model", "analysis"], "conversational"),
        ("build a cost structure", ["cost", "structure", "expense"], "conversational"),
        ("streamline workflow", ["streamline", "workflow", "process"], "conversational"),
        ("develop a product strategy", ["product", "strategy", "roadmap"], "conversational"),
        ("study competitive landscape", ["competitive", "landscape", "study"], "conversational"),
        ("create a cash flow plan", ["cash", "flow", "plan"], "conversational"),
        ("improve quality", ["improve", "quality", "standard"], "conversational"),
        ("create an innovation strategy", ["innovation", "strategy", "new"], "conversational"),
        ("analyze customer needs", ["customer", "need", "analysis"], "conversational"),
        ("build a ROI model", ["roi", "return", "investment"], "conversational"),
        ("optimize scheduling", ["optimize", "schedule", "plan"], "conversational"),
        ("design an expansion strategy", ["expansion", "strategy", "grow"], "conversational"),
        ("analyze customer journey", ["customer", "journey", "analysis"], "conversational"),
        ("create a valuation model", ["valuation", "model", "worth"], "conversational"),
        ("increase capacity", ["increase", "capacity", "scale"], "conversational"),
        ("create a technology strategy", ["technology", "strategy", "digital"], "conversational"),
        
        # Conversational Band - Research (20 tests)
        ("analyze data", ["analyze", "data", "insight"], "conversational"),
        ("research patterns", ["research", "pattern", "data"], "conversational"),
        ("investigate correlations", ["investigate", "correlation", "relationship"], "conversational"),
        ("examine statistics", ["examine", "statistic", "data"], "conversational"),
        ("analyze metrics", ["analyze", "metric", "kpi"], "conversational"),
        ("examine effects", ["examine", "effect", "impact"], "conversational"),
        ("analyze behavior", ["analyze", "behavior", "pattern"], "conversational"),
        ("research preferences", ["research", "preference", "choice"], "conversational"),
        ("investigate anomalies", ["investigate", "anomaly", "outlier"], "conversational"),
        ("examine distributions", ["examine", "distribution", "spread"], "conversational"),
        ("analyze segments", ["analyze", "segment", "group"], "conversational"),
        ("research classifications", ["research", "classification", "category"], "conversational"),
        ("examine dependencies", ["examine", "dependency", "relationship"], "conversational"),
        ("examine predictions", ["examine", "prediction", "forecast"], "conversational"),
        ("analyze variance", ["analyze", "variance", "variation"], "conversational"),
        ("study deviations", ["study", "deviation", "difference"], "conversational"),
        ("research outliers", ["research", "outlier", "anomaly"], "conversational"),
        ("investigate errors", ["investigate", "error", "mistake"], "conversational"),
        ("examine accuracy", ["examine", "accuracy", "precision"], "conversational"),
        ("analyze reliability", ["analyze", "reliability", "consistent"], "conversational"),
    ]
    
    for i, (message, keywords, expected_band) in enumerate(tests, 1):
        try:
            result = system.process_message(message)
            
            # Verify response quality
            if not verify_response(result.get('response', '')):
                print(f"❌ Test {i}: {message[:40]}")
                failed += 1
                continue
            
            # Verify fuzzy match
            if not fuzzy_match(result['response'], keywords):
                print(f"❌ Test {i}: {message[:40]}")
                failed += 1
                continue
            
            # Verify band (if specified)
            if expected_band and result.get('band') != expected_band:
                print(f"❌ Test {i}: {message[:40]} (wrong band: {result.get('band')})")
                failed += 1
                continue
            
            print(f"✅ Test {i}: {message[:40]}")
            passed += 1
            
        except Exception as e:
            print(f"❌ Test {i}: {message[:40]} (error: {str(e)[:30]})")
            failed += 1
    
    duration = time.time() - start_time
    total = passed + failed
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print(f"Pass Rate: {pass_rate:.1f}%")
    print(f"Duration: {duration:.1f}s")
    print(f"Tests/sec: {total/duration:.1f}")
    
    if pass_rate >= 95:
        print("\n🎉 EXCELLENT - System performing at high quality")
    elif pass_rate >= 90:
        print("\n✅ GOOD - System performing well")
    elif pass_rate >= 80:
        print("\n⚠️  ACCEPTABLE - Minor issues")
    else:
        print("\n❌ NEEDS WORK - Significant issues")
    
    print("\n" + "="*80)
    
    return passed, failed

if __name__ == "__main__":
    passed, failed = run_tests()
    sys.exit(0 if (passed / (passed + failed)) >= 0.90 else 1)