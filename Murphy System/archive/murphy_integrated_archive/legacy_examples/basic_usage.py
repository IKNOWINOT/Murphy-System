"""
Basic usage examples for the Deterministic-Gated Chatbot
"""

import os
from dotenv import load_dotenv
from src.chatbot import create_chatbot

# Load environment variables
load_dotenv()


def example_1_factual_lookup():
    """Example: Factual lookup with verification"""
    print("\n" + "=" * 60)
    print("Example 1: Factual Lookup")
    print("=" * 60)
    
    chatbot = create_chatbot()
    
    questions = [
        "What is the latest version of ISO 26262?",
        "Tell me about ISO 9001",
        "What is Python?"
    ]
    
    for question in questions:
        print(f"\nQ: {question}")
        response = chatbot.process_query(question)
        print(f"State: {response['state']}")
        print(f"Answer: {response['message']}")
        print(f"Verified: {response['verified']}")
        print("-" * 60)


def example_2_calculation():
    """Example: Deterministic calculation"""
    print("\n" + "=" * 60)
    print("Example 2: Calculations")
    print("=" * 60)
    
    chatbot = create_chatbot()
    
    questions = [
        "Calculate 25 * 4 + 10",
        "What is (100 - 25) / 5?",
    ]
    
    for question in questions:
        print(f"\nQ: {question}")
        response = chatbot.process_query(question)
        print(f"State: {response['state']}")
        print(f"Answer: {response['message']}")
        print("-" * 60)


def example_3_confidence_threshold():
    """Example: Confidence threshold in action"""
    print("\n" + "=" * 60)
    print("Example 3: Confidence Threshold")
    print("=" * 60)
    
    # Strict mode with high confidence requirement
    chatbot_strict = create_chatbot(min_confidence=0.90, strict_mode=True)
    
    # Relaxed mode with lower confidence requirement
    chatbot_relaxed = create_chatbot(min_confidence=0.60, strict_mode=False)
    
    question = "What is the latest version of ISO 26262?"
    
    print(f"\nQ: {question}")
    print("\nStrict Mode (min_confidence=0.90):")
    response_strict = chatbot_strict.process_query(question)
    print(f"State: {response_strict['state']}")
    print(f"Confidence: {response_strict['confidence']:.2f}")
    
    print("\nRelaxed Mode (min_confidence=0.60):")
    response_relaxed = chatbot_relaxed.process_query(question)
    print(f"State: {response_relaxed['state']}")
    print(f"Confidence: {response_relaxed['confidence']:.2f}")


def example_4_murphy_defense():
    """Example: Murphy's Law defense in action"""
    print("\n" + "=" * 60)
    print("Example 4: Murphy Defense")
    print("=" * 60)
    
    chatbot = create_chatbot(strict_mode=True)
    
    # This should trigger CLARIFY due to ambiguity
    ambiguous_question = "What is the best standard?"
    
    print(f"\nQ: {ambiguous_question}")
    response = chatbot.process_query(ambiguous_question)
    print(f"State: {response['state']}")
    print(f"Reasoning: {response['reasoning']}")
    print(f"Answer: {response['message']}")


def example_5_simple_chat():
    """Example: Simple chat interface"""
    print("\n" + "=" * 60)
    print("Example 5: Simple Chat")
    print("=" * 60)
    
    chatbot = create_chatbot()
    
    questions = [
        "What is ISO 26262?",
        "When was it last revised?",
        "What domain does it cover?"
    ]
    
    for question in questions:
        print(f"\nYou: {question}")
        answer = chatbot.chat(question)
        print(f"Bot: {answer}")


if __name__ == "__main__":
    # Check for API key
    if not os.getenv("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY not found!")
        print("Get a free API key from: https://console.groq.com")
        print("Then set it in .env file or as environment variable")
        exit(1)
    
    # Run examples
    example_1_factual_lookup()
    example_2_calculation()
    example_3_confidence_threshold()
    example_4_murphy_defense()
    example_5_simple_chat()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)