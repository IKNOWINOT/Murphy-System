"""
Local LLM Fallback System
Provides intelligent responses without internet connection
Uses pattern matching and templates for offline operation
Integrates with Ollama for local model inference when available
"""

import logging

logger = logging.getLogger(__name__)
import random
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    import json as _json
    import urllib.request
    _HAS_URLLIB = True
except ImportError:
    _HAS_URLLIB = False


def _check_ollama_available(base_url: str = "http://localhost:11434") -> bool:
    """Check if an Ollama instance is reachable."""
    if not _HAS_URLLIB:
        return False
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception as exc:
        logger.debug("Suppressed exception: %s", exc)
        return False


def _query_ollama(
    prompt: str,
    model: str = "llama3",
    base_url: str = "http://localhost:11434",
    max_tokens: int = 500,
) -> Optional[str]:
    """Query a local Ollama model. Returns the response text or None on failure."""
    if not _HAS_URLLIB:
        return None
    try:
        payload = _json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
            return data.get("response", "")
    except Exception as exc:
        logger.debug("Suppressed exception: %s", exc)
        return None


# Preferred Ollama models in priority order
_OLLAMA_MODELS = ["llama3", "mistral", "phi3", "phi"]


class LocalLLMFallback:
    """
    Lightweight fallback LLM for offline operation
    Uses intelligent pattern matching and response templates.
    When Ollama is available locally, routes queries to a real local model.
    """

    def __init__(self):
        self.knowledge_base = self._build_knowledge_base()
        self.patterns = self._build_patterns()
        self._ollama_available: Optional[bool] = None
        self._ollama_model: Optional[str] = None

    def _build_knowledge_base(self) -> Dict[str, str]:
        """Build a knowledge base of common topics"""
        return {
            "neural_networks": """Neural networks are computational models inspired by biological neurons. They consist of interconnected layers of nodes (neurons) that process information through weighted connections. Each neuron receives inputs, applies an activation function, and passes the output to the next layer. Through training with data, the network adjusts these weights to learn patterns and make predictions. Common types include feedforward networks, convolutional neural networks (CNNs) for images, and recurrent neural networks (RNNs) for sequences.""",

            "machine_learning": """Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without explicit programming. It uses algorithms to identify patterns in data and make predictions or decisions. The three main types are: supervised learning (learning from labeled data), unsupervised learning (finding patterns in unlabeled data), and reinforcement learning (learning through trial and error with rewards).""",

            "python": """Python is a high-level, interpreted programming language known for its simplicity and readability. It supports multiple programming paradigms including procedural, object-oriented, and functional programming. Python is widely used in web development, data science, machine learning, automation, and scientific computing. Its extensive standard library and rich ecosystem of third-party packages make it versatile for various applications.""",

            "web_development": """Web development involves creating websites and web applications. It typically consists of frontend development (HTML, CSS, JavaScript for user interfaces), backend development (server-side logic, databases, APIs), and full-stack development (both frontend and backend). Modern web development uses frameworks like React, Vue, Angular for frontend, and Node.js, Django, Flask for backend. Key concepts include responsive design, RESTful APIs, authentication, and database management.""",

            "databases": """Databases are organized collections of structured data. Relational databases (SQL) like PostgreSQL and MySQL use tables with defined schemas and relationships. NoSQL databases like MongoDB and Redis offer flexible schemas for unstructured data. Key concepts include CRUD operations (Create, Read, Update, Delete), indexing for performance, transactions for data integrity, and normalization for efficient storage.""",

            "algorithms": """Algorithms are step-by-step procedures for solving problems or performing computations. Common algorithm types include sorting (quicksort, mergesort), searching (binary search, depth-first search), dynamic programming (solving complex problems by breaking them into subproblems), and greedy algorithms (making locally optimal choices). Algorithm efficiency is measured using Big O notation, which describes time and space complexity.""",

            "api": """APIs (Application Programming Interfaces) are interfaces that allow different software systems to communicate. REST APIs use HTTP methods (GET, POST, PUT, DELETE) to perform operations on resources. GraphQL APIs provide flexible querying of data. APIs typically return data in JSON or XML format. Key concepts include endpoints, authentication (API keys, OAuth), rate limiting, and versioning.""",

            "cloud_computing": """Cloud computing delivers computing services over the internet, including servers, storage, databases, networking, and software. Major providers include AWS, Azure, and Google Cloud. Cloud services are categorized as IaaS (Infrastructure as a Service), PaaS (Platform as a Service), and SaaS (Software as a Service). Benefits include scalability, cost-efficiency, and reduced infrastructure management.""",

            "security": """Cybersecurity protects systems, networks, and data from digital attacks. Key practices include encryption (protecting data in transit and at rest), authentication (verifying user identity), authorization (controlling access), input validation (preventing injection attacks), and regular security updates. Common threats include SQL injection, cross-site scripting (XSS), and denial-of-service (DoS) attacks.""",

            "git": """Git is a distributed version control system for tracking changes in source code. Key concepts include repositories (project storage), commits (snapshots of changes), branches (parallel development lines), and merging (combining changes). Common workflows involve cloning repositories, creating feature branches, committing changes, and pushing to remote repositories like GitHub or GitLab.""",

            "murphy": """Murphy System is an AI-powered automation assistant that helps teams automate operations, onboard new users, manage integrations, and run end-to-end workflows. Key commands include: 'start interview' for guided onboarding, 'help' for command list, 'show modules' for system modules, 'status' for system health, 'execute <task>' to run workflows, 'set key <provider> <key>' to configure API keys, and 'api keys' for integration setup links.""",

            "murphy_setup": """To set up Murphy System: 1) Run the startup script (start_murphy_1.0.sh). 2) Set your Groq API key using 'set key groq gsk_yourKeyHere' in the terminal. 3) Type 'start interview' for guided onboarding. 4) Use 'status' to verify connectivity. 5) Use 'execute <task>' to start automating. For API keys, type 'api keys' to see all available integrations.""",

            "murphy_troubleshooting": """Common Murphy troubleshooting: If LLM is not working, check 'llm status' and ensure your API key is set with 'set key groq <key>'. If the backend is unreachable, try 'reconnect' or 'set api <url>'. If you're stuck, type 'help' for available commands. For API key issues, use 'set key <provider> <key>' to set keys inline without restarting.""",
        }

    def _build_patterns(self) -> List[Tuple[str, str]]:
        """Build regex patterns for matching queries"""
        return [
            (r"what (is|are) (.+)", "definition"),
            (r"how (does|do|to) (.+)", "explanation"),
            (r"explain (.+)", "explanation"),
            (r"(tell me about|describe) (.+)", "description"),
            (r"(difference between|compare) (.+)", "comparison"),
            (r"(why|when|where) (.+)", "reasoning"),
            (r"(create|build|make|design) (.+)", "creation"),
            (r"(best|good|recommend) (.+)", "recommendation"),
        ]

    @property
    def ollama_available(self) -> bool:
        """Check (and cache) whether Ollama is reachable."""
        if self._ollama_available is None:
            self._ollama_available = _check_ollama_available()
            if self._ollama_available:
                # Detect which model is available
                for model in _OLLAMA_MODELS:
                    result = _query_ollama("hi", model=model, max_tokens=5)
                    if result is not None:
                        self._ollama_model = model
                        break
                else:
                    self._ollama_available = False
        return self._ollama_available

    def generate(self, prompt: str, max_tokens: int = 500) -> str:
        """
        Generate a response based on the prompt.
        Tries Ollama first, then falls back to pattern matching.
        """
        # Try Ollama if available
        if self.ollama_available and self._ollama_model:
            result = _query_ollama(prompt, model=self._ollama_model, max_tokens=max_tokens)
            if result:
                return result

        return self._generate_offline(prompt, max_tokens)

    def _generate_offline(self, prompt: str, max_tokens: int = 500) -> str:
        """Generate a response using the built-in pattern matcher."""
        prompt_lower = prompt.lower()

        # Check knowledge base for direct matches
        for topic, content in self.knowledge_base.items():
            if topic.replace("_", " ") in prompt_lower:
                return self._format_response(content, max_tokens)

        # Pattern-based responses
        for pattern, response_type in self.patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                return self._generate_by_type(response_type, prompt, max_tokens)

        # Default intelligent response
        return self._generate_default_response(prompt, max_tokens)

    def _format_response(self, content: str, max_tokens: int) -> str:
        """Format response to fit within token limit"""
        words = content.split()
        # Rough estimate: 1 token ≈ 0.75 words
        max_words = int(max_tokens * 0.75)

        if len(words) <= max_words:
            return content

        # Truncate and add ellipsis
        truncated = " ".join(words[:max_words])
        return truncated + "..."

    def _generate_by_type(self, response_type: str, prompt: str, max_tokens: int) -> str:
        """Generate response based on query type"""

        if response_type == "definition":
            return f"""Based on your question about '{prompt}', here's what I can explain:

This is a concept that requires understanding its core components and how they work together. While I'm operating in offline mode with limited knowledge, I can provide a general framework:

1. **Core Concept**: The fundamental idea or principle
2. **Key Components**: The main parts or elements involved
3. **How It Works**: The process or mechanism
4. **Applications**: Where and how it's used
5. **Related Concepts**: Connected ideas worth exploring

For detailed, up-to-date information, I recommend consulting online resources or documentation when internet connectivity is available."""

        elif response_type == "explanation":
            return f"""To explain '{prompt}', let me break it down:

**Overview**: This involves understanding the underlying principles and mechanisms.

**Step-by-Step Process**:
1. Start with the basic foundation
2. Build upon core concepts
3. Apply the principles in practice
4. Refine through iteration

**Key Points to Remember**:
- Focus on understanding fundamentals first
- Practice with examples
- Learn from both successes and failures
- Stay updated with best practices

Note: I'm currently in offline mode. For comprehensive, current information, please check online resources when available."""

        elif response_type == "creation":
            return f"""To create/build '{prompt}', here's a structured approach:

**Planning Phase**:
1. Define clear objectives and requirements
2. Research existing solutions and best practices
3. Design the architecture or structure
4. Identify necessary tools and resources

**Implementation Phase**:
1. Set up the development environment
2. Build core functionality first
3. Iterate and add features incrementally
4. Test thoroughly at each stage

**Best Practices**:
- Start simple, then expand
- Document as you go
- Use version control
- Get feedback early and often

I'm operating in offline mode, so for specific technical details and current best practices, please consult online documentation when available."""

        elif response_type == "recommendation":
            return f"""Regarding '{prompt}', here are some general recommendations:

**Considerations**:
1. **Your Specific Needs**: What are you trying to achieve?
2. **Context**: What's your current situation and constraints?
3. **Resources**: What tools and time do you have available?
4. **Experience Level**: What's your background with this topic?

**General Approach**:
- Research multiple options when possible
- Consider trade-offs (speed vs. quality, cost vs. features)
- Start with proven, stable solutions
- Be prepared to adapt based on results

**Next Steps**:
- Clarify your specific requirements
- Compare available options
- Test with a small pilot or prototype
- Iterate based on feedback

Note: I'm in offline mode. For current recommendations and comparisons, please check online resources and community forums when internet is available."""

        else:
            return self._generate_default_response(prompt, max_tokens)

    def _generate_default_response(self, prompt: str, max_tokens: int) -> str:
        """Generate a default intelligent response"""
        return f"""I understand you're asking about: "{prompt}"

**Current Status**: Using built-in knowledge base — no real LLM available.

**What I Can Help With**:
- General concepts and principles
- Murphy System commands and setup help
- Structured approaches to problems
- Best practice frameworks

**For Your Question**:
To provide the most accurate and helpful response, I would need:
1. More specific context about your situation
2. What you're trying to achieve
3. Any constraints or requirements you have

**💡 Tip**: Try `set key groq <your-key>` to add an API key for full AI capabilities.
Get a free key at: https://console.groq.com/keys

Would you like to:
- Rephrase your question with more context?
- Ask about a related topic I might have in my offline knowledge base?
- Type `help` to see available Murphy commands?"""


# Singleton instance
_fallback_instance = None

def get_fallback_llm() -> LocalLLMFallback:
    """Get or create the fallback LLM instance"""
    global _fallback_instance
    if _fallback_instance is None:
        _fallback_instance = LocalLLMFallback()
    return _fallback_instance
