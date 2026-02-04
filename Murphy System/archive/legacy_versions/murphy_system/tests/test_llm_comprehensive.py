"""
Comprehensive LLM Functionality Test Suite
Tests 500+ prompts across all confidence bands and domains
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unified_mfgc import UnifiedMFGC
import time
import json
from datetime import datetime

class LLMTestSuite:
    def __init__(self):
        self.system = UnifiedMFGC()
        self.results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'by_band': {
                'introductory': {'total': 0, 'passed': 0, 'failed': 0},
                'conversational': {'total': 0, 'passed': 0, 'failed': 0},
                'exploratory': {'total': 0, 'passed': 0, 'failed': 0}
            },
            'by_domain': {},
            'response_times': [],
            'confidence_scores': [],
            'failures': []
        }
        
    def run_test(self, prompt, expected_band=None, expected_domain=None, test_name=""):
        """Run a single test"""
        self.results['total'] += 1
        
        try:
            start_time = time.time()
            response = self.system.process_message(prompt)
            end_time = time.time()
            
            response_time = end_time - start_time
            self.results['response_times'].append(response_time)
            
            # Extract metrics
            confidence = response.get('confidence', 0)
            band = response.get('band', 'unknown')
            content = response.get('content', '')
            
            self.results['confidence_scores'].append(confidence)
            self.results['by_band'][band]['total'] += 1
            
            # Check for errors
            if 'error' in response or len(content) == 0:
                self.results['failed'] += 1
                self.results['by_band'][band]['failed'] += 1
                self.results['failures'].append({
                    'test': test_name,
                    'prompt': prompt[:100],
                    'reason': 'Empty or error response',
                    'response': response
                })
                return False
            
            # Check band routing if expected
            if expected_band and band != expected_band:
                self.results['failed'] += 1
                self.results['by_band'][band]['failed'] += 1
                self.results['failures'].append({
                    'test': test_name,
                    'prompt': prompt[:100],
                    'reason': f'Wrong band: expected {expected_band}, got {band}',
                    'response': response
                })
                return False
            
            # Success
            self.results['passed'] += 1
            self.results['by_band'][band]['passed'] += 1
            return True
            
        except Exception as e:
            self.results['errors'] += 1
            self.results['failures'].append({
                'test': test_name,
                'prompt': prompt[:100],
                'reason': f'Exception: {str(e)}',
                'response': None
            })
            return False
    
    def print_progress(self, current, total, category=""):
        """Print progress bar"""
        percent = (current / total) * 100
        bar_length = 50
        filled = int(bar_length * current / total)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\r{category:30s} [{bar}] {current}/{total} ({percent:.1f}%)", end='', flush=True)
    
    def print_results(self):
        """Print comprehensive results"""
        print("\n\n" + "="*80)
        print("LLM COMPREHENSIVE TEST RESULTS")
        print("="*80)
        
        print(f"\nTotal Tests: {self.results['total']}")
        print(f"Passed: {self.results['passed']} ({self.results['passed']/self.results['total']*100:.1f}%)")
        print(f"Failed: {self.results['failed']} ({self.results['failed']/self.results['total']*100:.1f}%)")
        print(f"Errors: {self.results['errors']} ({self.results['errors']/self.results['total']*100:.1f}%)")
        
        print("\n" + "-"*80)
        print("RESULTS BY CONFIDENCE BAND")
        print("-"*80)
        for band, stats in self.results['by_band'].items():
            if stats['total'] > 0:
                pass_rate = (stats['passed'] / stats['total']) * 100
                print(f"{band.upper():20s}: {stats['passed']}/{stats['total']} passed ({pass_rate:.1f}%)")
        
        print("\n" + "-"*80)
        print("PERFORMANCE METRICS")
        print("-"*80)
        if self.results['response_times']:
            avg_time = sum(self.results['response_times']) / len(self.results['response_times'])
            min_time = min(self.results['response_times'])
            max_time = max(self.results['response_times'])
            print(f"Average Response Time: {avg_time:.3f}s")
            print(f"Min Response Time: {min_time:.3f}s")
            print(f"Max Response Time: {max_time:.3f}s")
        
        if self.results['confidence_scores']:
            avg_conf = sum(self.results['confidence_scores']) / len(self.results['confidence_scores'])
            min_conf = min(self.results['confidence_scores'])
            max_conf = max(self.results['confidence_scores'])
            print(f"Average Confidence: {avg_conf:.3f}")
            print(f"Min Confidence: {min_conf:.3f}")
            print(f"Max Confidence: {max_conf:.3f}")
        
        if self.results['failures']:
            print("\n" + "-"*80)
            print(f"FIRST 10 FAILURES (of {len(self.results['failures'])})")
            print("-"*80)
            for i, failure in enumerate(self.results['failures'][:10]):
                print(f"\n{i+1}. {failure['test']}")
                print(f"   Prompt: {failure['prompt']}")
                print(f"   Reason: {failure['reason']}")
        
        print("\n" + "="*80)
        
        # Save detailed results
        with open('test_results_llm_comprehensive.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        print("\nDetailed results saved to: test_results_llm_comprehensive.json")


def main():
    """Run comprehensive LLM test suite"""
    suite = LLMTestSuite()
    
    print("="*80)
    print("COMPREHENSIVE LLM FUNCTIONALITY TEST SUITE")
    print("Testing 500+ prompts across all confidence bands")
    print("="*80)
    print()
    
    # ========================================================================
    # CATEGORY 1: GREETINGS & BASIC INTERACTIONS (50 tests)
    # ========================================================================
    greetings = [
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
        "greetings", "howdy", "yo", "sup", "what's up", "hiya", "heya",
        "hello there", "hi there", "hey there", "good day", "salutations",
        "how are you", "how's it going", "what's happening", "how do you do",
        "nice to meet you", "pleased to meet you", "hello friend",
        "hi bot", "hello ai", "hey system", "greetings system",
        "good to see you", "long time no see", "welcome back",
        "hi again", "hello again", "hey again", "back again",
        "morning", "afternoon", "evening", "night",
        "hola", "bonjour", "ciao", "namaste", "aloha",
        "hey buddy", "hi pal", "hello mate", "yo dude", "sup bro"
    ]
    
    print("\n[1/10] Testing Greetings & Basic Interactions...")
    for i, prompt in enumerate(greetings):
        suite.run_test(prompt, expected_band='introductory', test_name=f"Greeting {i+1}")
        suite.print_progress(i+1, len(greetings), "Greetings")
    
    # ========================================================================
    # CATEGORY 2: HELP & CAPABILITIES (50 tests)
    # ========================================================================
    help_queries = [
        "what can you do", "help", "what are your capabilities", "what do you do",
        "how can you help me", "what features do you have", "what can I ask you",
        "tell me about yourself", "what are you", "who are you", "describe yourself",
        "what's your purpose", "what are you designed for", "what's your function",
        "list your features", "show me what you can do", "what services do you offer",
        "how do you work", "explain your capabilities", "what tasks can you handle",
        "can you help me with", "what kind of questions can I ask",
        "what are your skills", "what do you specialize in", "what's your expertise",
        "give me an overview", "tell me your features", "what can you assist with",
        "how can I use you", "what should I ask you", "guide me",
        "what are your functions", "what can you process", "what do you support",
        "show capabilities", "list features", "describe features",
        "what's possible", "what can be done", "what options do I have",
        "help me understand", "explain what you do", "walk me through",
        "what are the options", "what can we do together", "how to use you",
        "getting started", "quick start", "tutorial", "guide"
    ]
    
    print("\n[2/10] Testing Help & Capabilities Queries...")
    for i, prompt in enumerate(help_queries):
        suite.run_test(prompt, expected_band='introductory', test_name=f"Help {i+1}")
        suite.print_progress(i+1, len(help_queries), "Help Queries")
    
    # ========================================================================
    # CATEGORY 3: SIMPLE QUESTIONS (100 tests)
    # ========================================================================
    simple_questions = [
        # General knowledge
        "what is Python", "what is JavaScript", "what is machine learning",
        "what is AI", "what is cloud computing", "what is blockchain",
        "what is quantum computing", "what is cybersecurity", "what is DevOps",
        "what is agile", "what is scrum", "what is REST API",
        
        # Definitions
        "define algorithm", "define database", "define API", "define framework",
        "define library", "define compiler", "define interpreter", "define IDE",
        "define version control", "define git", "define docker", "define kubernetes",
        
        # How-to questions
        "how to learn programming", "how to start coding", "how to build a website",
        "how to create an app", "how to use git", "how to deploy code",
        "how to write tests", "how to debug code", "how to optimize performance",
        "how to secure applications", "how to scale systems", "how to monitor services",
        
        # Comparisons
        "difference between Python and Java", "difference between SQL and NoSQL",
        "difference between frontend and backend", "difference between REST and GraphQL",
        "difference between git and github", "difference between docker and VM",
        "difference between AI and ML", "difference between compiler and interpreter",
        
        # Best practices
        "best practices for coding", "best practices for testing",
        "best practices for security", "best practices for deployment",
        "best practices for documentation", "best practices for code review",
        "best practices for git", "best practices for API design",
        
        # Recommendations
        "recommend a programming language", "recommend a framework",
        "recommend a database", "recommend a cloud provider",
        "recommend a text editor", "recommend a testing tool",
        "recommend a CI/CD tool", "recommend a monitoring tool",
        
        # Explanations
        "explain REST API", "explain microservices", "explain containers",
        "explain serverless", "explain CI/CD", "explain TDD",
        "explain OOP", "explain functional programming", "explain async programming",
        "explain caching", "explain load balancing", "explain authentication",
        
        # Quick facts
        "what year was Python created", "who created Linux", "what is the latest Python version",
        "what is the most popular programming language", "what is the fastest database",
        "what is the most secure cloud provider", "what is the best IDE",
        
        # Technology questions
        "what is React", "what is Angular", "what is Vue", "what is Node.js",
        "what is Django", "what is Flask", "what is Spring", "what is Laravel",
        "what is MongoDB", "what is PostgreSQL", "what is Redis", "what is Elasticsearch",
        "what is AWS", "what is Azure", "what is GCP", "what is Heroku"
    ]
    
    print("\n[3/10] Testing Simple Questions...")
    for i, prompt in enumerate(simple_questions):
        suite.run_test(prompt, expected_band='conversational', test_name=f"Simple Q {i+1}")
        suite.print_progress(i+1, len(simple_questions), "Simple Questions")
    
    # ========================================================================
    # CATEGORY 4: MODERATE COMPLEXITY TASKS (100 tests)
    # ========================================================================
    moderate_tasks = [
        # Software development
        "create a simple web server", "write a REST API endpoint",
        "design a database schema for users", "implement user authentication",
        "create a CRUD application", "build a todo list app",
        "design a blog system", "create a shopping cart",
        "implement file upload", "create a search feature",
        
        # Data analysis
        "analyze sales data", "create a data visualization",
        "calculate statistics from dataset", "find trends in data",
        "clean messy data", "merge multiple datasets",
        "create a dashboard", "generate a report",
        "perform sentiment analysis", "cluster customer data",
        
        # Problem solving
        "solve the fibonacci problem", "implement binary search",
        "create a sorting algorithm", "solve the knapsack problem",
        "implement a linked list", "create a binary tree",
        "solve the traveling salesman", "implement graph traversal",
        "create a hash table", "implement a queue",
        
        # System design
        "design a URL shortener", "design a chat application",
        "design a file storage system", "design a notification system",
        "design a caching layer", "design a rate limiter",
        "design a load balancer", "design a message queue",
        "design a search engine", "design a recommendation system",
        
        # Business analysis
        "analyze market trends", "create a business plan",
        "calculate ROI", "perform competitor analysis",
        "create a pricing strategy", "analyze customer segments",
        "forecast revenue", "optimize costs",
        "analyze user behavior", "create a growth strategy",
        
        # Research tasks
        "research machine learning algorithms", "research cloud architectures",
        "research security best practices", "research scalability patterns",
        "research database optimization", "research API design patterns",
        "research testing strategies", "research deployment methods",
        "research monitoring solutions", "research performance tuning",
        
        # Code review
        "review this code for bugs", "optimize this algorithm",
        "refactor this function", "improve code readability",
        "add error handling", "add logging",
        "add tests", "add documentation",
        "fix security issues", "improve performance",
        
        # Documentation
        "write API documentation", "create user guide",
        "write technical specification", "create architecture diagram",
        "write deployment guide", "create troubleshooting guide",
        "write release notes", "create README file",
        "write code comments", "create tutorial",
        
        # Planning
        "plan a software project", "create a development roadmap",
        "plan a migration strategy", "create a testing plan",
        "plan a deployment strategy", "create a backup plan",
        "plan a security audit", "create a monitoring plan",
        "plan a scaling strategy", "create a disaster recovery plan",
        
        # Integration
        "integrate payment gateway", "integrate authentication service",
        "integrate email service", "integrate SMS service",
        "integrate analytics", "integrate logging",
        "integrate monitoring", "integrate CI/CD",
        "integrate cloud storage", "integrate CDN"
    ]
    
    print("\n[4/10] Testing Moderate Complexity Tasks...")
    for i, prompt in enumerate(moderate_tasks):
        suite.run_test(prompt, expected_band='conversational', test_name=f"Moderate {i+1}")
        suite.print_progress(i+1, len(moderate_tasks), "Moderate Tasks")
    
    # ========================================================================
    # CATEGORY 5: COMPLEX EXPLORATORY TASKS (50 tests)
    # ========================================================================
    complex_tasks = [
        # Large system design
        "/swarmauto design a complete e-commerce platform with microservices",
        "/swarmauto build a distributed social media system",
        "/swarmauto create a real-time analytics platform",
        "/swarmauto design a multi-tenant SaaS application",
        "/swarmauto build a video streaming service",
        
        # Enterprise solutions
        "/swarmauto design an enterprise resource planning system",
        "/swarmauto create a customer relationship management platform",
        "/swarmauto build a supply chain management system",
        "/swarmauto design a human resources management system",
        "/swarmauto create a financial management platform",
        
        # Advanced architectures
        "/swarmauto design a serverless architecture for high-scale application",
        "/swarmauto create a event-driven microservices system",
        "/swarmauto build a CQRS and event sourcing architecture",
        "/swarmauto design a multi-region distributed system",
        "/swarmauto create a hybrid cloud architecture",
        
        # AI/ML systems
        "/swarmauto design a machine learning pipeline",
        "/swarmauto create a recommendation engine",
        "/swarmauto build a natural language processing system",
        "/swarmauto design a computer vision platform",
        "/swarmauto create a predictive analytics system",
        
        # Data platforms
        "/swarmauto design a big data processing platform",
        "/swarmauto create a data lake architecture",
        "/swarmauto build a real-time data streaming system",
        "/swarmauto design a data warehouse solution",
        "/swarmauto create a data governance framework",
        
        # Security systems
        "/swarmauto design a zero-trust security architecture",
        "/swarmauto create a threat detection system",
        "/swarmauto build an identity and access management platform",
        "/swarmauto design a security operations center",
        "/swarmauto create a compliance monitoring system",
        
        # IoT systems
        "/swarmauto design an IoT platform for smart cities",
        "/swarmauto create an industrial IoT system",
        "/swarmauto build a connected vehicle platform",
        "/swarmauto design a smart home ecosystem",
        "/swarmauto create a wearable device platform",
        
        # Blockchain systems
        "/swarmauto design a blockchain-based supply chain",
        "/swarmauto create a decentralized finance platform",
        "/swarmauto build a smart contract system",
        "/swarmauto design a cryptocurrency exchange",
        "/swarmauto create a NFT marketplace",
        
        # Gaming systems
        "/swarmauto design a multiplayer game server architecture",
        "/swarmauto create a game analytics platform",
        "/swarmauto build a matchmaking system",
        "/swarmauto design a game asset management system",
        "/swarmauto create a player progression system",
        
        # Healthcare systems
        "/swarmauto design an electronic health records system",
        "/swarmauto create a telemedicine platform",
        "/swarmauto build a medical imaging system",
        "/swarmauto design a patient monitoring system",
        "/swarmauto create a clinical decision support system"
    ]
    
    print("\n[5/10] Testing Complex Exploratory Tasks...")
    for i, prompt in enumerate(complex_tasks):
        suite.run_test(prompt, expected_band='exploratory', test_name=f"Complex {i+1}")
        suite.print_progress(i+1, len(complex_tasks), "Complex Tasks")
    
    # ========================================================================
    # CATEGORY 6: EDGE CASES & STRESS TESTS (50 tests)
    # ========================================================================
    edge_cases = [
        # Empty/minimal
        "", " ", "  ", "   ", "\n", "\t",
        
        # Single words
        "test", "help", "code", "design", "build", "create",
        
        # Very long prompts
        "I need you to " + "help me " * 100,
        "Please design " + "a system " * 100,
        
        # Special characters
        "!@#$%^&*()", "test!@#", "design???", "help!!!",
        "what is <html>", "explain [brackets]", "show {curly}",
        
        # Mixed languages
        "hola, what can you do", "bonjour, help me",
        "ciao, design system", "namaste, create app",
        
        # Ambiguous
        "it", "that", "this", "thing", "stuff",
        "do it", "make it", "fix it", "show it",
        
        # Contradictory
        "design but don't design", "help but don't help",
        "create nothing", "build without building",
        
        # Nonsensical
        "colorless green ideas sleep furiously",
        "the quick brown fox jumps over the lazy dog",
        "lorem ipsum dolor sit amet",
        
        # Multiple questions
        "what is Python and how do I learn it and what are best practices",
        "design a system and test it and deploy it and monitor it",
        
        # Incomplete
        "I want to", "Can you", "Please help me with",
        "I need", "Show me how to", "Explain"
    ]
    
    print("\n[6/10] Testing Edge Cases & Stress Tests...")
    for i, prompt in enumerate(edge_cases):
        suite.run_test(prompt, test_name=f"Edge {i+1}")
        suite.print_progress(i+1, len(edge_cases), "Edge Cases")
    
    # ========================================================================
    # CATEGORY 7: DOMAIN-SPECIFIC QUERIES (50 tests)
    # ========================================================================
    domain_queries = [
        # Software Engineering
        "explain microservices architecture", "what is continuous integration",
        "how to implement OAuth2", "explain design patterns",
        "what is test-driven development", "how to optimize database queries",
        
        # Data Science
        "explain neural networks", "what is gradient descent",
        "how to handle imbalanced data", "explain cross-validation",
        "what is feature engineering", "how to prevent overfitting",
        
        # DevOps
        "explain infrastructure as code", "what is container orchestration",
        "how to implement blue-green deployment", "explain service mesh",
        "what is observability", "how to implement chaos engineering",
        
        # Security
        "explain zero-trust architecture", "what is penetration testing",
        "how to implement encryption", "explain threat modeling",
        "what is security by design", "how to handle security incidents",
        
        # Cloud Computing
        "explain serverless computing", "what is cloud-native architecture",
        "how to implement multi-cloud strategy", "explain cloud cost optimization",
        "what is edge computing", "how to implement disaster recovery",
        
        # Business
        "explain agile methodology", "what is product-market fit",
        "how to calculate customer lifetime value", "explain lean startup",
        "what is growth hacking", "how to conduct market research",
        
        # Finance
        "explain compound interest", "what is risk management",
        "how to calculate ROI", "explain financial modeling",
        "what is portfolio optimization", "how to analyze cash flow",
        
        # Healthcare
        "explain HIPAA compliance", "what is electronic health records",
        "how to implement telemedicine", "explain clinical decision support"
    ]
    
    print("\n[7/10] Testing Domain-Specific Queries...")
    for i, prompt in enumerate(domain_queries):
        suite.run_test(prompt, test_name=f"Domain {i+1}")
        suite.print_progress(i+1, len(domain_queries), "Domain Queries")
    
    # ========================================================================
    # CATEGORY 8: CONVERSATIONAL CONTEXT (30 tests)
    # ========================================================================
    context_tests = [
        # Follow-up questions
        ("what is Python", "tell me more"),
        ("what is Python", "how do I learn it"),
        ("what is Python", "what are its advantages"),
        ("design a web app", "what technologies should I use"),
        ("design a web app", "how do I deploy it"),
        
        # Clarifications
        ("create an app", "what kind of app"),
        ("build a system", "what type of system"),
        ("design something", "can you be more specific"),
        
        # Corrections
        ("I meant Python not Java", "okay"),
        ("actually I need a mobile app", "got it"),
        
        # Continuations
        ("let's continue", "okay"),
        ("go on", "continue"),
        ("what's next", "proceed"),
        
        # References
        ("as I mentioned before", "yes"),
        ("like we discussed", "right"),
        ("from earlier", "okay")
    ]
    
    print("\n[8/10] Testing Conversational Context...")
    for i, (first, second) in enumerate(context_tests):
        suite.run_test(first, test_name=f"Context {i+1}a")
        suite.run_test(second, test_name=f"Context {i+1}b")
        suite.print_progress(i+1, len(context_tests), "Context Tests")
    
    # ========================================================================
    # CATEGORY 9: COMMAND VARIATIONS (20 tests)
    # ========================================================================
    command_variations = [
        "/swarmauto design web app",
        "/swarmmonitor check status",
        "swarmauto create system",
        "swarmmonitor show progress",
        "/swarmauto build platform",
        "/swarmmonitor display metrics",
        "can you /swarmauto design",
        "please /swarmmonitor check",
        "/swarmauto help me design",
        "/swarmmonitor show me status",
        "use /swarmauto to create",
        "run /swarmmonitor for status",
        "/SWARMAUTO design system",
        "/SWARMMONITOR check progress",
        "/SwarmAuto create app",
        "/SwarmMonitor show status",
        "/swarmauto", "/swarmmonitor",
        "swarmauto", "swarmmonitor"
    ]
    
    print("\n[9/10] Testing Command Variations...")
    for i, prompt in enumerate(command_variations):
        suite.run_test(prompt, test_name=f"Command {i+1}")
        suite.print_progress(i+1, len(command_variations), "Commands")
    
    # ========================================================================
    # CATEGORY 10: REALISTIC USER SCENARIOS (20 tests)
    # ========================================================================
    realistic_scenarios = [
        "I'm building a startup and need help with the tech stack",
        "My application is slow, how can I optimize it",
        "I need to migrate from monolith to microservices",
        "How do I implement user authentication securely",
        "I want to add real-time features to my app",
        "My database is getting too large, what should I do",
        "I need to scale my application to handle more users",
        "How do I implement a payment system",
        "I want to add machine learning to my product",
        "My team is growing, how do I organize the codebase",
        "I need to improve my application's security",
        "How do I implement a mobile app for my web service",
        "I want to add analytics to track user behavior",
        "My deployment process is manual, how do I automate it",
        "I need to implement a search feature",
        "How do I handle file uploads at scale",
        "I want to add notifications to my app",
        "My API is getting too many requests, what should I do",
        "I need to implement multi-tenancy",
        "How do I ensure my application is GDPR compliant"
    ]
    
    print("\n[10/10] Testing Realistic User Scenarios...")
    for i, prompt in enumerate(realistic_scenarios):
        suite.run_test(prompt, test_name=f"Scenario {i+1}")
        suite.print_progress(i+1, len(realistic_scenarios), "Scenarios")
    
    # Print final results
    suite.print_results()
    
    # Return success/failure
    success_rate = (suite.results['passed'] / suite.results['total']) * 100
    return success_rate >= 80  # 80% pass rate required


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)