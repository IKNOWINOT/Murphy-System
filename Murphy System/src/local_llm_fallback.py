"""
Local LLM Fallback System
Provides intelligent responses without internet connection
Uses pattern matching and templates for offline operation
Integrates with Ollama for local model inference when available
"""

import logging
import os

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

_DEFAULT_OLLAMA_HOST = "http://localhost:11434"


def _ollama_base_url() -> str:
    """Return the Ollama base URL, honouring the OLLAMA_HOST env var."""
    return os.environ.get("OLLAMA_HOST", _DEFAULT_OLLAMA_HOST).rstrip("/")


def _check_ollama_available(base_url: str = None) -> bool:
    """Check if an Ollama instance is reachable."""
    if base_url is None:
        base_url = _ollama_base_url()
    if not _HAS_URLLIB:
        return False
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception as exc:
        logger.debug("Suppressed exception: %s", exc)
        return False


def _ollama_list_models(base_url: str = None) -> List[str]:
    """Return the list of model names currently pulled in Ollama."""
    if base_url is None:
        base_url = _ollama_base_url()
    if not _HAS_URLLIB:
        return []
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
            # Keep base name only (strip `:tag` suffix) so comparisons against
            # OLLAMA_MODEL (which users set without a tag) work correctly.
            return [m.get("name", "").split(":")[0] for m in data.get("models", [])]
    except Exception as exc:
        logger.debug("Suppressed exception listing Ollama models: %s", exc)
        return []


def _query_ollama(
    prompt: str,
    model: str = "phi3",
    base_url: str = None,
    max_tokens: int = 500,
) -> Optional[str]:
    """Query a local Ollama model. Returns the response text or None on failure."""
    if base_url is None:
        base_url = _ollama_base_url()
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


# Canonical model probe order — imported by llm_controller and other callers
# so there is a single source of truth for model names.
_OLLAMA_MODELS = ["phi3", "llama3", "mistral", "phi", "tinyllama"]

# Small models: fast, low RAM (phi3 ≈ 2.3 GB, phi ≈ 1.5 GB)
_OLLAMA_SMALL_MODELS = ["phi3", "phi", "tinyllama"]

# Medium models: best quality available locally (llama3/mistral ≈ 4–5 GB)
_OLLAMA_MEDIUM_MODELS = ["llama3", "mistral"]


def _preferred_ollama_models() -> List[str]:
    """Return model probe order, honouring OLLAMA_MODEL env var if set.

    Tags (`:latest`, etc.) are stripped so that OLLAMA_MODEL=llama3 and
    OLLAMA_MODEL=llama3:latest both resolve to the same probe entry.
    """
    env_model = os.environ.get("OLLAMA_MODEL", "").strip().split(":")[0]
    if env_model:
        return [env_model] + [m for m in _OLLAMA_MODELS if m != env_model]
    return _OLLAMA_MODELS


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

            "automation": """Business automation with Murphy System lets you streamline repetitive tasks and workflows. Common automation types include: order processing (route new orders → update inventory → send confirmation), customer onboarding (welcome emails → account setup → intro sequence), reporting (gather data → format → email to stakeholders), and lead nurturing (capture → score → route to CRM). Murphy integrates with Shopify, Stripe, QuickBooks, Slack, Gmail, and 80+ other platforms. Type 'start interview' to begin setting up your first automation.""",

            "e-commerce": """Murphy System supports e-commerce automation across the full order lifecycle. Key automations include: order fulfillment (new order → pick/pack notification → shipping label → tracking email), inventory management (low stock → reorder alert → supplier notification), customer service (return request → auto-approve → refund trigger), and revenue reporting (daily sales summary → email to owner). Integrates with Shopify, WooCommerce, Amazon, Stripe, PayPal, and ShipStation. To get started, describe your store and what you want to automate.""",

            "workflow": """Workflow automation connects your business tools so tasks happen automatically. A workflow consists of a trigger (what starts it), conditions (rules to check), and actions (what to do). Examples: "When a new lead fills out a form → add to CRM → send welcome email → schedule follow-up call". Murphy uses MFGC gates to ensure workflows are safe and complete before deploying. Key integrations: Zapier, Make (Integromat), HubSpot, Salesforce, Google Sheets, Airtable.""",

            "integrations": """Murphy System connects with 80+ platforms including: CRM (HubSpot, Salesforce, Pipedrive), payments (Stripe, PayPal, Square), accounting (QuickBooks, Xero), email (Gmail, Outlook, Mailchimp), messaging (Slack, Teams, Twilio), e-commerce (Shopify, WooCommerce), project management (Asana, Trello, Jira), calendar (Google Calendar, Calendly), and storage (Google Drive, Dropbox, S3). Type 'api keys' to see all available integrations and how to connect them.""",

            "crm": """CRM (Customer Relationship Management) automation with Murphy tracks leads, customers, and deals automatically. Common automations: new contact → add to CRM → assign to rep → send intro email; deal won → trigger onboarding workflow → update forecast; deal lost → add to re-engagement sequence. Murphy integrates with HubSpot, Salesforce, Pipedrive, and Zoho CRM. Murphy can also sync CRM data with your calendar, email, and billing systems.""",

            "reporting": """Automated reporting with Murphy System generates and delivers business insights on schedule. Common report automations: daily sales summary (gather Stripe data → format → email to owner at 8am), weekly KPI report (pull metrics from CRM + analytics → create PDF → send to team), monthly P&L (QuickBooks data → formatted spreadsheet → send to accountant). Murphy can send reports via email, Slack, or save to Google Drive. Describe your reporting needs to get started.""",
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
            (r"(automate|automation) (.+)", "automation"),
            (r"(integrate|connect|sync) (.+)", "integration"),
            (r"(help|assist|support) (.+)", "help"),
            (r"i (run|own|have|manage|operate) (.+)", "business"),
            (r"(my business|my company|our company|our business) (.+)", "business"),
            (r"(set up|setup|configure|deploy) (.+)", "creation"),
            (r"(fix|troubleshoot|debug|solve|resolve) (.+)", "explanation"),
        ]

    @property
    def ollama_available(self) -> bool:
        """Check (and cache) whether Ollama is reachable."""
        if self._ollama_available is None:
            base_url = _ollama_base_url()
            self._ollama_available = _check_ollama_available(base_url)
            if self._ollama_available:
                # Detect which model is available
                for model in _preferred_ollama_models():
                    result = _query_ollama("hi", model=model, base_url=base_url, max_tokens=5)
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
            result = _query_ollama(prompt, model=self._ollama_model,
                                   base_url=_ollama_base_url(), max_tokens=max_tokens)
            if result:
                return result

        return self._generate_offline(prompt, max_tokens)

    def _generate_offline(self, prompt: str, max_tokens: int = 500) -> str:
        """Generate a response using the built-in pattern matcher.

        When the prompt contains system-injected context (e.g. "Context: ...\n\n<user
        message>"), only the actual user query (after the last blank-line separator)
        is used for knowledge-base topic matching and pattern detection.  This prevents
        system-context words such as "murphy" or "groq" from hijacking the topic lookup
        and returning an irrelevant knowledge-base entry.

        Murphy-specific knowledge-base entries ("murphy", "murphy_setup",
        "murphy_troubleshooting") are only returned when the user is explicitly asking
        *about* Murphy as a subject — not when "Murphy" appears as an agent/actor in
        their query (e.g. "What can Murphy do for my store?" should NOT return the
        generic Murphy description).
        """
        # Isolate the user-facing query from any prepended system context.
        # Convention: context and query are separated by one or more blank lines.
        parts = [p.strip() for p in prompt.split("\n\n") if p.strip()]
        query = parts[-1] if parts else prompt
        query_lower = query.lower()

        # Topic set whose entries should only fire when Murphy is the *subject* of
        # the question, not merely mentioned as the agent doing the work.
        _MURPHY_TOPICS = {"murphy", "murphy setup", "murphy troubleshooting"}
        # Patterns that signal the user is asking *about* Murphy (subject-mode).
        _MURPHY_ABOUT_RE = re.compile(
            r"\b(what\s+is|about|tell\s+me\s+about|explain|describe|"
            r"how\s+does|what\s+does|murphy\s+system)\b"
        )

        # Check knowledge base against the user query only (not injected context).
        for topic, content in self.knowledge_base.items():
            topic_phrase = topic.replace("_", " ")
            if topic_phrase not in query_lower:
                continue
            # Gate murphy-specific entries so they only fire in subject-mode queries.
            if topic_phrase in _MURPHY_TOPICS and not _MURPHY_ABOUT_RE.search(query_lower):
                continue
            return self._format_response(content, max_tokens)

        # Pattern-based responses — also applied to the user query.
        for pattern, response_type in self.patterns:
            match = re.search(pattern, query_lower)
            if match:
                return self._generate_by_type(response_type, query, max_tokens)

        # Default intelligent response uses the clean user query.
        return self._generate_default_response(query, max_tokens)

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

        elif response_type == "integration":
            return f"""To connect and integrate '{prompt}', here's how Murphy can help:

**Integration Approach**:
1. Identify the source system (e.g., Shopify, Gmail, Stripe)
2. Identify the destination system (e.g., QuickBooks, Slack, Airtable)
3. Define the data that needs to flow between them
4. Set the trigger (webhook, scheduled sync, or real-time)

**Murphy Supported Integrations**:
- CRM: HubSpot, Salesforce, Pipedrive
- Payments: Stripe, PayPal, Square
- Accounting: QuickBooks, Xero
- Email: Gmail, Outlook, Mailchimp
- Messaging: Slack, Teams, Twilio
- E-commerce: Shopify, WooCommerce
- Calendar: Google Calendar, Calendly
- Storage: Google Drive, Dropbox, S3

**Next Steps**: Type `start interview` to describe your integration need, or type `api keys` to see all supported platforms.

💡 Add a Groq API key (`set key groq gsk_...`) for AI-powered integration planning."""

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

        elif response_type == "automation":
            return f"""Great — let's automate '{prompt}'!

Murphy System can help you build this automation. Here's the framework:

**Step 1 — Define the Trigger**
What event starts the automation? (e.g., new order, form submission, scheduled time)

**Step 2 — Set the Conditions**
Are there rules or checks? (e.g., order value > $50, customer is new, specific product category)

**Step 3 — Define the Actions**
What should happen automatically? (e.g., send email, update spreadsheet, notify Slack, create record)

**Step 4 — Connect Your Tools**
Which platforms need to be integrated? Murphy supports Shopify, Stripe, Gmail, Slack, QuickBooks, and 80+ others.

**To proceed**: Type `start interview` to walk through your specific automation needs, or describe exactly what triggers and actions you want.

💡 Add a Groq API key (`set key groq gsk_...`) to unlock full AI-powered planning."""

        elif response_type == "business":
            return f"""Thanks for sharing information about your business!

To help you automate effectively, Murphy needs a few details:

**1. What specific tasks take the most time?**
(e.g., processing orders, sending invoices, answering customer emails, scheduling, data entry)

**2. What tools do you currently use?**
(e.g., Shopify, QuickBooks, Gmail, Slack, Airtable, Stripe)

**3. What's your biggest pain point?**
(e.g., orders get lost, manual data entry, slow customer response, missed follow-ups)

**4. How often does this process happen?**
(e.g., daily, per order, weekly)

Once I understand your workflow, I can build an automation blueprint for you. Type `start interview` for a guided setup, or keep describing your situation here.

💡 **Pro tip**: Add a Groq API key for richer, more tailored automation planning."""

        elif response_type == "help":
            return f"""I'm Murphy — your AI automation assistant. Here's how I can help:

**Available Commands**:
• `start interview` — Begin guided onboarding to set up your first automation
• `help` — Show all available commands
• `status` — Check system health
• `api keys` — See all supported integrations and how to connect them
• `set key groq <key>` — Add a Groq API key for full AI capabilities

**What I Automate**:
- Order fulfillment & e-commerce workflows
- Customer onboarding & email sequences
- CRM updates & lead routing
- Invoicing & payment collection
- Reporting & data sync

**To get started**: Describe your business and what you want to automate, then type `start interview`.

Get a free Groq key at https://console.groq.com/keys for the best experience."""

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
