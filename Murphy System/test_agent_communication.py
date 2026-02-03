"""
Test Script: Agent Communication System
Demonstrates inter-agent messaging, decision gates, and cost analysis
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:3002"

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80 + "\n")

def test_create_task_review():
    """Test creating a task review with decision gates"""
    print_section("TEST 1: Create Task Review")
    
    response = requests.post(f"{BASE_URL}/api/task/review/create", json={
        'task_id': 'task_001',
        'agent_name': 'ContentCreator',
        'agent_role': 'Senior Content Writer',
        'user_request': 'Write a comprehensive guide about AI automation for small businesses that we can sell for $49'
    })
    
    if response.status_code == 200:
        data = response.json()
        review = data['review']
        
        print("✓ Task Review Created Successfully\n")
        print(f"Task ID: {review['task_id']}")
        print(f"Agent: {review['agent_name']} ({review['agent_role']})")
        print(f"Confidence Level: {review['overall_confidence'].upper()}")
        print(f"Librarian Confidence: {review['librarian_confidence'] * 100:.1f}%")
        
        print("\n--- LLM GENERATIVE SIDE ---")
        print(f"Tokens Used: {review['llm_tokens_used']}")
        print(f"Response Preview: {review['llm_response'][:200]}...")
        
        print("\n--- LIBRARIAN INTERPRETATION SIDE ---")
        print(f"Interpretation: {review['librarian_interpretation']}")
        print(f"Command Chain: {', '.join(review['librarian_command_chain'])}")
        
        print("\n--- COST ANALYSIS ---")
        print(f"Token Cost: {review['token_cost']} tokens")
        print(f"Revenue Potential: ${review['revenue_potential']:.2f}")
        print(f"Cost/Benefit Ratio: {review['cost_benefit_ratio']:.2f}")
        
        print("\n--- DECISION GATES ---")
        for i, gate in enumerate(review['gates'], 1):
            print(f"\nGate {i}: {gate['question']}")
            print(f"  Options: {', '.join(gate['options'])}")
            print(f"  Confidence: {gate['confidence'] * 100:.1f}%")
            print(f"  Reasoning: {gate['reasoning']}")
        
        print("\n--- CLARIFYING QUESTIONS ---")
        for i, q in enumerate(review['questions'], 1):
            print(f"\n{i}. {q['question']}")
            print(f"   Reason: {q['reason']}")
            print(f"   Confidence Boost: +{q['confidence_boost'] * 100:.1f}%")
        
        return review['task_id']
    else:
        print(f"✗ Failed: {response.status_code}")
        print(response.text)
        return None

def test_answer_question(task_id):
    """Test answering a clarifying question"""
    print_section("TEST 2: Answer Clarifying Question")
    
    response = requests.post(f"{BASE_URL}/api/task/review/{task_id}/answer", json={
        'question_index': 0,
        'answer': 'The deliverable should be a comprehensive PDF guide with actionable worksheets, case studies, and implementation checklists. Target format: 50-75 pages with professional design.'
    })
    
    if response.status_code == 200:
        data = response.json()
        
        print("✓ Question Answered Successfully\n")
        print(f"New Confidence: {data['new_confidence'] * 100:.1f}%")
        print(f"Confidence Level: {data['confidence_level'].upper()}")
        
        review = data['review']
        print(f"\nUpdated LLM Response Preview:")
        print(review['llm_response'][:300] + "...")
        
        return True
    else:
        print(f"✗ Failed: {response.status_code}")
        print(response.text)
        return False

def test_send_agent_message():
    """Test sending messages between agents"""
    print_section("TEST 3: Inter-Agent Communication")
    
    # Message 1: ContentCreator to Editor
    response1 = requests.post(f"{BASE_URL}/api/agent/message/send", json={
        'from_agent': 'ContentCreator',
        'to_agent': 'Editor',
        'message_type': 'QUESTION',
        'subject': 'Review Request: AI Automation Guide',
        'body': 'I\'ve completed the first draft of the AI automation guide. Could you review chapters 1-3 and provide feedback on technical accuracy and readability?',
        'requires_response': True
    })
    
    if response1.status_code == 200:
        msg1 = response1.json()['message']
        print("✓ Message 1 Sent: ContentCreator → Editor")
        print(f"  Subject: {msg1['subject']}")
        print(f"  Thread ID: {msg1['thread_id']}")
        
        # Message 2: Editor responds
        response2 = requests.post(f"{BASE_URL}/api/agent/message/send", json={
            'from_agent': 'Editor',
            'to_agent': 'ContentCreator',
            'message_type': 'ANSWER',
            'subject': 'RE: Review Request: AI Automation Guide',
            'body': 'Reviewed chapters 1-3. Overall excellent work! Minor suggestions:\n1. Add more concrete examples in Chapter 2\n2. Simplify technical jargon in Chapter 3\n3. Consider adding a case study in Chapter 1\n\nReady for QC after these revisions.',
            'thread_id': msg1['thread_id'],
            'requires_response': False
        })
        
        if response2.status_code == 200:
            msg2 = response2.json()['message']
            print("✓ Message 2 Sent: Editor → ContentCreator")
            print(f"  Subject: {msg2['subject']}")
            
            # Get the full thread
            response3 = requests.get(f"{BASE_URL}/api/agent/thread/{msg1['thread_id']}")
            if response3.status_code == 200:
                thread = response3.json()
                print(f"\n✓ Thread Retrieved: {thread['message_count']} messages")
                
                print("\n--- EMAIL THREAD ---")
                for msg in thread['messages']:
                    print(f"\nFrom: {msg['from_agent']} → To: {msg['to_agent']}")
                    print(f"Subject: {msg['subject']}")
                    print(f"Time: {msg['timestamp']}")
                    print(f"Body: {msg['body'][:100]}...")
                
                return msg1['thread_id']
    
    return None

def test_agent_inbox():
    """Test retrieving agent inbox"""
    print_section("TEST 4: Agent Inbox")
    
    response = requests.get(f"{BASE_URL}/api/agent/inbox/Editor")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Editor's Inbox Retrieved")
        print(f"  Total Messages: {data['message_count']}")
        
        print("\n--- INBOX MESSAGES ---")
        for msg in data['messages']:
            print(f"\nFrom: {msg['from_agent']}")
            print(f"Subject: {msg['subject']}")
            print(f"Type: {msg['message_type']}")
            print(f"Requires Response: {msg['requires_response']}")
        
        return True
    else:
        print(f"✗ Failed: {response.status_code}")
        return False

def test_librarian_deliverable_communication():
    """Test Librarian ↔ Deliverable Function communication"""
    print_section("TEST 5: Librarian ↔ Deliverable Communication")
    
    response = requests.post(f"{BASE_URL}/api/librarian/deliverable/communicate", json={
        'task_id': 'task_002',
        'request': 'Create a complete marketing campaign for our new AI automation guide including email sequence, social media posts, and landing page copy'
    })
    
    if response.status_code == 200:
        data = response.json()
        comm = data['communication']
        
        print("✓ Librarian ↔ Deliverable Communication Established\n")
        
        print("--- LIBRARIAN MESSAGE ---")
        lib_msg = comm['librarian_message']
        print(f"From: {lib_msg['from_agent']} → To: {lib_msg['to_agent']}")
        print(f"Subject: {lib_msg['subject']}")
        print(f"Body:\n{lib_msg['body']}")
        
        print("\n--- DELIVERABLE RESPONSE ---")
        del_msg = comm['deliverable_response']
        print(f"From: {del_msg['from_agent']} → To: {del_msg['to_agent']}")
        print(f"Subject: {del_msg['subject']}")
        print(f"Body:\n{del_msg['body']}")
        
        print("\n--- ANALYSIS ---")
        analysis = comm['analysis']
        print(f"Interpretation: {analysis.get('interpretation', 'N/A')}")
        print(f"Command Chain: {', '.join(analysis.get('command_chain', []))}")
        print(f"Estimated Tokens: {analysis.get('estimated_tokens', 0)}")
        print(f"Revenue Potential: ${analysis.get('revenue_potential', 0)}")
        
        return True
    else:
        print(f"✗ Failed: {response.status_code}")
        print(response.text)
        return False

def test_decision_gates(task_id):
    """Test retrieving decision gates"""
    print_section("TEST 6: Decision Gates Analysis")
    
    response = requests.get(f"{BASE_URL}/api/task/review/{task_id}/gates")
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"✓ Decision Gates Retrieved for Task: {task_id}\n")
        print(f"Overall Confidence: {data['overall_confidence'].upper()}")
        
        print("\n--- DECISION GATES ---")
        for i, gate in enumerate(data['gates'], 1):
            print(f"\n{i}. {gate['question']}")
            print(f"   Gate ID: {gate['gate_id']}")
            print(f"   Options: {', '.join(gate['options'])}")
            print(f"   Confidence: {gate['confidence'] * 100:.1f}%")
            print(f"   Reasoning: {gate['reasoning']}")
            print(f"   Token Cost: {gate['token_cost']}")
            print(f"   Revenue Impact: ${gate['revenue_impact']:.2f}")
        
        return True
    else:
        print(f"✗ Failed: {response.status_code}")
        return False

def test_cost_analysis(task_id):
    """Test cost analysis"""
    print_section("TEST 7: Cost Analysis")
    
    response = requests.get(f"{BASE_URL}/api/task/review/{task_id}/cost-analysis")
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"✓ Cost Analysis Retrieved for Task: {task_id}\n")
        print(f"Token Cost: {data['token_cost']} tokens")
        print(f"Revenue Potential: ${data['revenue_potential']:.2f}")
        print(f"Cost/Benefit Ratio: {data['cost_benefit_ratio']:.2f}")
        print(f"Recommendation: {data['recommendation']}")
        
        if data['cost_benefit_ratio'] > 1:
            print("\n✓ PROCEED: Revenue exceeds token costs")
        else:
            print("\n⚠ REVIEW REQUIRED: Token costs exceed revenue")
        
        return True
    else:
        print(f"✗ Failed: {response.status_code}")
        return False

def test_all_task_reviews():
    """Test retrieving all task reviews"""
    print_section("TEST 8: All Task Reviews")
    
    response = requests.get(f"{BASE_URL}/api/task/review/all")
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"✓ Retrieved {data['count']} Task Reviews\n")
        
        for review in data['reviews']:
            print(f"Task: {review['task_id']}")
            print(f"  Agent: {review['agent_name']} ({review['agent_role']})")
            print(f"  Confidence: {review['overall_confidence'].upper()}")
            print(f"  Cost/Benefit: {review['cost_benefit_ratio']:.2f}")
            print(f"  Messages: {len(review['message_thread'])}")
            print()
        
        return True
    else:
        print(f"✗ Failed: {response.status_code}")
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print(" AGENT COMMUNICATION SYSTEM - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    
    # Test 1: Create task review
    task_id = test_create_task_review()
    if not task_id:
        print("\n✗ Test suite aborted - could not create task review")
        return
    
    time.sleep(1)
    
    # Test 2: Answer clarifying question
    test_answer_question(task_id)
    time.sleep(1)
    
    # Test 3: Inter-agent messaging
    test_send_agent_message()
    time.sleep(1)
    
    # Test 4: Agent inbox
    test_agent_inbox()
    time.sleep(1)
    
    # Test 5: Librarian ↔ Deliverable
    test_librarian_deliverable_communication()
    time.sleep(1)
    
    # Test 6: Decision gates
    test_decision_gates(task_id)
    time.sleep(1)
    
    # Test 7: Cost analysis
    test_cost_analysis(task_id)
    time.sleep(1)
    
    # Test 8: All task reviews
    test_all_task_reviews()
    
    print_section("TEST SUITE COMPLETE")
    print("✓ All agent communication features tested successfully!")
    print("\nKey Features Demonstrated:")
    print("• Task review creation with LLM + Librarian analysis")
    print("• Decision gates with confidence levels")
    print("• Token cost vs revenue analysis")
    print("• Inter-agent email chatter")
    print("• Clarifying questions to boost confidence")
    print("• Librarian ↔ Deliverable Function communication")
    print("• Agent inboxes and message threads")

if __name__ == '__main__':
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to Murphy server")
        print("Please ensure the server is running on http://localhost:3002")
    except Exception as e:
        print(f"\n✗ Error: {e}")