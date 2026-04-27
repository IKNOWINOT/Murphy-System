"""
LLM Integration Layer
Integrates local LLMs with MFGC system for enhanced reasoning
"""

import json
import logging
import os
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Available LLM providers"""
    OLLAMA = "ollama"  # Local Ollama models
    TRANSFORMERS = "transformers"  # Hugging Face transformers
    LLAMACPP = "llamacpp"  # llama.cpp Python bindings
    NONE = "none"  # Rule-based only


class LLMConfig:
    """LLM configuration"""

    # Recommended models by RAM tier.  Names match Ollama pull names exactly.
    MODELS = {
        'tiny': {
            'name': 'tinyllama',
            'size': '1.1B',
            'ram': '1 GB',
            'provider': LLMProvider.OLLAMA,
            'description': 'TinyLlama 1.1B — fast, < 2 GB RAM required'
        },
        'small': {
            'name': 'phi3',
            'size': '3.8B',
            'ram': '2.3 GB',
            'provider': LLMProvider.OLLAMA,
            'description': 'Microsoft Phi-3 — best quality under 4 GB RAM'
        },
        'medium': {
            'name': 'llama3',
            'size': '8B',
            'ram': '4.7 GB',
            'provider': LLMProvider.OLLAMA,
            'description': 'Meta Llama 3 8B — default, requires 6 GB+ RAM'
        }
    }

    @classmethod
    def get_recommended_model(cls, available_ram_gb: float) -> str:
        """Return the recommended model tier for the given available RAM."""
        if available_ram_gb >= 6:
            return 'medium'    # llama3 — needs ~4.7 GB, safe at 6 GB+
        elif available_ram_gb >= 2.5:
            return 'small'     # phi3 — needs ~2.3 GB, safe at 2.5 GB+
        else:
            return 'tiny'      # tinyllama — needs ~1 GB


class OllamaLLM:
    """
    Ollama LLM integration

    Ollama is the easiest way to run local LLMs:
    - Simple installation
    - Automatic model management
    - Good performance
    - Multiple model support
    """

    def __init__(self, model_name: str = "phi3"):
        """
        Initialize Ollama LLM

        Args:
            model_name: Ollama model name — must match a pulled model.
                        Defaults to "phi3" (requires ~2.3 GB RAM).
                        Use "llama3" on 6 GB+ systems, "tinyllama" under 2.5 GB.
        """
        self.model_name = model_name
        self.base_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")

        # Check if Ollama is available
        self.available = self._check_ollama()

        if self.available:
            logger.info(f"✓ Ollama available with model: {model_name}")
        else:
            logger.info("⚠ Ollama not available - install with: curl -fsSL https://ollama.com/install.sh | sh")

    def _check_ollama(self) -> bool:
        """Check if Ollama is running"""
        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception as exc:
            logger.debug("Ollama connectivity check failed: %s", exc)
            return False

    def generate(self, prompt: str, system_prompt: Optional[str] = None,
                max_tokens: int = 500, temperature: float = 0.7) -> str:
        """
        Generate text using Ollama

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            Generated text
        """
        if not self.available:
            return "[Ollama not available - using fallback]"

        try:
            import requests

            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }

            if system_prompt:
                payload["system"] = system_prompt

            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            else:
                return f"[Error: {response.status_code}]"

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return f"[Error: {str(exc)}]"

    def chat(self, messages: List[Dict[str, str]],
            max_tokens: int = 500, temperature: float = 0.7) -> str:
        """
        Chat completion using Ollama

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Assistant response
        """
        if not self.available:
            return "[Ollama not available - using fallback]"

        try:
            import requests

            payload = {
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }

            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("message", {}).get("content", "")
            else:
                return f"[Error: {response.status_code}]"

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return f"[Error: {str(exc)}]"


class LLMEnhancedMFGC:
    """
    MFGC system enhanced with LLM reasoning

    Uses LLM for:
    1. Candidate generation (more creative solutions)
    2. Risk analysis (better risk identification)
    3. Gate synthesis (more comprehensive gates)
    4. Natural language understanding
    """

    def __init__(self, llm_provider: LLMProvider = LLMProvider.OLLAMA,
                 model_name: str = "phi"):
        """
        Initialize LLM-enhanced MFGC

        PATCH-125: Redirected to MurphyLLMProvider (FM-001 fix).
        OllamaLLM is a legacy backend; MurphyLLMProvider handles
        DeepInfra→Together.ai fallback transparently.
        """
        self.llm_provider = llm_provider
        # Use unified LLM provider regardless of legacy enum value
        try:
            from src.llm_provider import MurphyLLMProvider
            self._unified_llm = MurphyLLMProvider.from_env()
        except Exception:
            self._unified_llm = None
        # Keep self.llm = None to signal legacy path is disabled
        self.llm = None

    def generate_candidates(self, task: str, phase: str,
                          existing_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate solution candidates using LLM

        Args:
            task: Task description
            phase: Current MFGC phase
            existing_candidates: Candidates from rule-based system

        Returns:
            Enhanced list of candidates
        """
        if not self.llm or not self.llm.available:
            return existing_candidates

        prompt = f"""Task: {task}
Phase: {phase}

Generate 3-5 creative solution approaches for this task in the {phase} phase.
Focus on practical, implementable solutions.

Format your response as JSON:
[
  {{"approach": "...", "pros": ["..."], "cons": ["..."], "score": 0.0-1.0}},
  ...
]"""

        if self._unified_llm:
            result = self._unified_llm.complete(prompt=prompt, max_tokens=500)
            response = result.content if result else ""
        else:
            response = ""

        # Try to parse JSON response
        try:
            llm_candidates = json.loads(response)
            if isinstance(llm_candidates, list):
                # Merge with existing candidates
                return existing_candidates + llm_candidates
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.debug("LLM candidate response not valid JSON, returning existing candidates: %s", exc)

        return existing_candidates

    def analyze_risks(self, task: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze risks using LLM

        Args:
            task: Task description
            candidates: Solution candidates

        Returns:
            List of identified risks
        """
        if not self.llm or not self.llm.available:
            return []

        prompt = f"""Task: {task}

Candidates:
{json.dumps(candidates, indent=2)}

Identify potential risks and failure modes for these solutions.
Consider: technical risks, business risks, security risks, operational risks.

Format as JSON:
[
  {{"risk": "...", "probability": 0.0-1.0, "impact": 0.0-1.0, "mitigation": "..."}},
  ...
]"""

        if self._unified_llm:
            result = self._unified_llm.complete(prompt=prompt, max_tokens=500)
            response = result.content if result else ""
        else:
            response = ""

        try:
            risks = json.loads(response)
            if isinstance(risks, list):
                return risks
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.debug("LLM risk analysis response not valid JSON, returning empty list: %s", exc)

        return []

    def synthesize_gates(self, task: str, risks: List[Dict[str, Any]]) -> List[str]:
        """
        Synthesize control gates using LLM

        Args:
            task: Task description
            risks: Identified risks

        Returns:
            List of control gates
        """
        if not self.llm or not self.llm.available:
            return []

        prompt = f"""Task: {task}

Risks:
{json.dumps(risks, indent=2)}

Generate specific, actionable control gates to prevent these risks.
Each gate should be a clear checkpoint or validation step.

Format as JSON array of strings:
["Gate 1", "Gate 2", ...]"""

        if self._unified_llm:
            result = self._unified_llm.complete(prompt=prompt, max_tokens=300)
            response = result.content if result else ""
        else:
            response = ""

        try:
            gates = json.loads(response)
            if isinstance(gates, list):
                return [str(g) for g in gates]
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.debug("LLM gate synthesis response not valid JSON, returning empty list: %s", exc)

        return []

    def enhance_conversation(self, message: str, context: Dict[str, Any]) -> str:
        """
        Enhance conversation responses using LLM

        Args:
            message: User message
            context: Conversation context

        Returns:
            Enhanced response
        """
        if not self.llm or not self.llm.available:
            return None

        messages = [
            {
                "role": "system",
                "content": "You are a helpful AI assistant integrated with a Murphy-Free Generative Control system. Provide clear, accurate, and helpful responses."
            },
            {
                "role": "user",
                "content": message
            }
        ]

        if self._unified_llm:
            msgs_text = "\n".join(m.get("content", "") for m in messages)
            result = self._unified_llm.complete(prompt=msgs_text, max_tokens=500)
            return result.content if result else None
        return None


def get_system_info() -> Dict[str, Any]:
    """Get system information for LLM selection"""
    import psutil

    # Get available RAM
    mem = psutil.virtual_memory()
    available_ram_gb = mem.available / (1024**3)

    return {
        'available_ram_gb': available_ram_gb,
        'total_ram_gb': mem.total / (1024**3),
        'cpu_count': os.cpu_count(),
        'recommended_model': LLMConfig.get_recommended_model(available_ram_gb)
    }


def print_installation_guide():
    """Print installation guide for Ollama"""
    logger.info("""
╔══════════════════════════════════════════════════════════════╗
║              LLM Enhancement Installation Guide              ║
╚══════════════════════════════════════════════════════════════╝

To enable LLM-enhanced MFGC, install Ollama:

1. Install Ollama:
   curl -fsSL https://ollama.com/install.sh | sh

2. Enable and start Ollama as a system service:
   systemctl enable ollama
   systemctl start ollama

3. Pull a model (choose based on available RAM):

   For 6 GB+ RAM (default, best quality):
   ollama pull llama3

   For 2.5–6 GB RAM:
   ollama pull phi3

   For < 2.5 GB RAM (minimal):
   ollama pull tinyllama

4. Set OLLAMA_MODEL in your environment file if not using llama3:
   OLLAMA_MODEL=phi3

5. Restart the Murphy service

Current system specs:
""")

    info = get_system_info()
    logger.info(f"  • Available RAM: {info['available_ram_gb']:.1f} GB")
    logger.info(f"  • Total RAM: {info['total_ram_gb']:.1f} GB")
    logger.info(f"  • CPU cores: {info['cpu_count']}")
    logger.info(f"  • Recommended model: {info['recommended_model']}")


if __name__ == "__main__":
    print_installation_guide()
