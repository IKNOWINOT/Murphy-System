"""
Interactive demo of the Deterministic-Gated Chatbot
Run this to chat with the bot in your terminal
"""

import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.chatbot import create_chatbot

# Load environment variables
load_dotenv()


def main():
    """Run interactive chat session"""
    
    # Check for API key
    if not os.getenv("GROQ_API_KEY"):
        print("=" * 60)
        print("ERROR: GROQ_API_KEY not found!")
        print("=" * 60)
        print("\nTo use this chatbot, you need a free Groq API key.")
        print("\nSteps:")
        print("1. Go to: https://console.groq.com")
        print("2. Sign up for a free account")
        print("3. Create an API key")
        print("4. Create a .env file with: GROQ_API_KEY=your_key_here")
        print("\nOr set it as environment variable:")
        print("export GROQ_API_KEY=your_key_here")
        print("=" * 60)
        return
    
    # Create chatbot
    print("\nInitializing chatbot...")
    chatbot = create_chatbot(
        min_confidence=0.80,
        strict_mode=True
    )
    
    # Run interactive session
    chatbot.interactive_session()


if __name__ == "__main__":
    main()