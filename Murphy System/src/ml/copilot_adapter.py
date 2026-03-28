"""
GitHub Copilot Adapter — code-aware routing for LLM tasks.

Routes code-related requests through the GitHub Copilot API (openai-compatible endpoint)
with graceful fallback to Ollama or the deterministic engine.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Keywords that indicate a code-related request.
_CODE_KEYWORDS = frozenset({
    "workflow", "pipeline", "automation", "function", "class", "def",
    "async", "await", "docker", "kubernetes", "k8s", "helm",
    "terraform", "ansible", "bash", "script", "python", "javascript",
    "typescript", "yaml", "json", "api", "endpoint", "module",
    "import", "return", "variable", "loop", "algorithm", "refactor",
    "test", "unittest", "pytest", "mock", "stub", "lambda", "closure",
    "interface", "type", "struct", "enum", "decorator", "middleware",
    "ci", "cd", "lint", "build", "deploy", "container", "microservice",
    "regex", "parse", "serialize", "deserialize", "schema", "migration",
    "sql", "query", "index", "orm", "repository", "service", "handler",
    "controller", "router", "config", "env", "secret", "token", "auth",
    "jwt", "oauth", "webhook", "cron", "schedule", "queue", "worker",
    "thread", "process", "multiprocess", "async def", "await asyncio",
})

_COPILOT_API_BASE = "https://api.github.com/copilot_internal/v2"
_COPILOT_CHAT_PATH = "/engines/copilot-chat/completions"


# ---------------------------------------------------------------------------
# Enums / dataclasses
# ---------------------------------------------------------------------------

class CopilotTaskType(str, Enum):
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    TEST_GENERATION = "test_generation"
    WORKFLOW_CODE = "workflow_code"
    AUTOMATION_SCRIPT = "automation_script"


@dataclass
class CopilotRequest:
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    task_type: CopilotTaskType = CopilotTaskType.CODE_GENERATION
    prompt: str = ""
    context_code: str = ""
    language: str = "python"
    target_framework: str = ""
    constraints: List[str] = field(default_factory=list)


@dataclass
class CopilotResult:
    request_id: str = ""
    generated_code: str = ""
    explanation: str = ""
    alternatives: List[str] = field(default_factory=list)
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "generated_code": self.generated_code,
            "explanation": self.explanation,
            "alternatives": self.alternatives,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class CopilotAdapter:
    """
    Routes code-related LLM tasks through GitHub Copilot when available,
    with automatic fallback to Ollama or the deterministic template engine.
    """

    def __init__(self) -> None:
        self._github_token: str = os.environ.get("GITHUB_TOKEN", "")
        self._copilot_token: str = os.environ.get("GITHUB_COPILOT_TOKEN", "")
        self._ollama_llm: Optional[Any] = None
        self._mfm_service: Optional[Any] = None

        try:
            from src.llm_integration import OllamaLLM  # type: ignore
            self._ollama_llm = OllamaLLM()
        except Exception:
            try:
                from llm_integration import OllamaLLM  # type: ignore
                self._ollama_llm = OllamaLLM()
            except Exception:
                logger.debug("OllamaLLM unavailable in CopilotAdapter")

        try:
            from src.murphy_foundation_model.mfm_inference import MFMInferenceService  # type: ignore
            self._mfm_service = MFMInferenceService()
        except Exception:
            try:
                from murphy_foundation_model.mfm_inference import MFMInferenceService  # type: ignore
                self._mfm_service = MFMInferenceService()
            except Exception:
                logger.debug("MFMInferenceService unavailable in CopilotAdapter")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def is_code_task(
        self, prompt: str, context: Optional[str] = None
    ) -> Tuple[bool, float]:
        """
        Determine whether *prompt* represents a code-related task.

        Returns ``(is_code, confidence)`` where *confidence* is in [0, 1].
        """
        text = prompt.lower()
        if context:
            text += " " + context.lower()

        words = set(text.split())
        matches = words & _CODE_KEYWORDS

        # Also match multi-word phrases.
        phrase_matches = sum(1 for kw in _CODE_KEYWORDS if " " in kw and kw in text)
        total_matches = len(matches) + phrase_matches

        confidence = min(1.0, total_matches / 3.0)  # 3+ keyword hits → full confidence
        is_code = confidence >= 0.3

        # Heuristic: presence of code fences is a strong signal.
        if "```" in prompt or "def " in prompt or "class " in prompt:
            confidence = max(confidence, 0.8)
            is_code = True

        return is_code, round(confidence, 2)

    def generate(self, request: CopilotRequest) -> CopilotResult:
        """
        Generate code/documentation using the best available backend.

        Tries Copilot API → Ollama → MFM → deterministic template.
        """
        prompt = self._build_copilot_prompt(request)

        # 1. GitHub Copilot API.
        if self._github_token or self._copilot_token:
            try:
                return self._call_copilot_api(prompt, request)
            except Exception as exc:
                logger.info("Copilot API failed (%s); falling back", exc)

        # 2. Local fallback chain.
        return self._call_fallback(request, prompt)

    # ------------------------------------------------------------------
    # Prompt engineering
    # ------------------------------------------------------------------

    def _build_copilot_prompt(self, request: CopilotRequest) -> str:
        """Build a Murphy-specific, context-rich prompt for the code model."""
        lines: List[str] = []

        task_instructions = {
            CopilotTaskType.CODE_GENERATION: "Generate clean, well-documented code for the following task.",
            CopilotTaskType.CODE_REVIEW: "Review the following code and provide actionable feedback.",
            CopilotTaskType.REFACTORING: "Refactor the following code to improve readability and performance.",
            CopilotTaskType.DOCUMENTATION: "Write clear documentation (docstrings, comments) for the following.",
            CopilotTaskType.TEST_GENERATION: "Generate comprehensive unit tests for the following code.",
            CopilotTaskType.WORKFLOW_CODE: (
                "Generate a Murphy System workflow automation script for the following task."
            ),
            CopilotTaskType.AUTOMATION_SCRIPT: (
                "Write a production-ready automation script adhering to Murphy System conventions."
            ),
        }

        lines.append(f"# Murphy System — {request.task_type.value.replace('_', ' ').title()}")
        lines.append(task_instructions.get(request.task_type, "Complete the following task."))
        lines.append("")

        if request.language:
            lines.append(f"Language: {request.language}")
        if request.target_framework:
            lines.append(f"Framework: {request.target_framework}")
        if request.constraints:
            lines.append("Constraints:")
            for c in request.constraints:
                lines.append(f"  - {c}")
        lines.append("")

        lines.append("## Task")
        lines.append(request.prompt)

        if request.context_code:
            lines.append("")
            lines.append("## Existing Code")
            lines.append("```" + request.language)
            lines.append(request.context_code)
            lines.append("```")

        lines.append("")
        lines.append(
            "Output ONLY the requested code/documentation. "
            "If code is requested, wrap it in a fenced code block."
        )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    def _call_copilot_api(self, prompt: str, request: CopilotRequest) -> CopilotResult:
        """
        Call the GitHub Copilot API (openai-compatible chat completion).

        Falls back gracefully if the token is invalid or the request fails.
        """
        try:
            import urllib.request as _urllib_req
            import json as _json
        except ImportError:
            raise RuntimeError("urllib unavailable — cannot call Copilot API")

        token = self._copilot_token or self._github_token
        if not token:
            raise RuntimeError("No GITHUB_TOKEN or GITHUB_COPILOT_TOKEN set")

        payload = _json.dumps({
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert software engineer embedded in the Murphy System. "
                        "Follow Murphy System coding conventions: pure Python preferred, "
                        "thread-safe with threading.Lock(), lazy imports with try/except, "
                        "dataclass-based, logging via logger = logging.getLogger(__name__)."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2048,
            "temperature": 0.2,
            "top_p": 0.95,
        }).encode("utf-8")

        req = _urllib_req.Request(
            f"{_COPILOT_API_BASE}{_COPILOT_CHAT_PATH}",
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Editor-Version": "Murphy/1.0",
                "Copilot-Integration-Id": "murphy-system",
            },
            method="POST",
        )

        with _urllib_req.urlopen(req, timeout=60) as resp:  # nosec B310
            body = _json.loads(resp.read().decode("utf-8"))

        content: str = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        code, explanation = _extract_code_and_explanation(content)

        return CopilotResult(
            request_id=request.request_id,
            generated_code=code,
            explanation=explanation,
            confidence=0.9,
            metadata={"source": "copilot_api", "model": "gpt-4o"},
        )

    def _call_fallback(self, request: CopilotRequest, prompt: str) -> CopilotResult:
        """Try Ollama → MFM → deterministic template."""
        response: Optional[str] = None

        # Ollama.
        if self._ollama_llm is not None:
            try:
                response = self._ollama_llm.generate(prompt, max_tokens=1024, temperature=0.2)  # type: ignore
                source = "ollama"
            except Exception as exc:
                logger.debug("Ollama fallback failed: %s", exc)

        # MFM.
        if response is None and self._mfm_service is not None:
            try:
                response = self._mfm_service.infer(prompt)  # type: ignore
                source = "mfm"
            except Exception as exc:
                logger.debug("MFM fallback failed: %s", exc)

        # Deterministic template.
        if response is None:
            response = _deterministic_code_template(request)
            source = "deterministic"
            confidence = 0.2
        else:
            confidence = 0.7

        code, explanation = _extract_code_and_explanation(response)
        return CopilotResult(
            request_id=request.request_id,
            generated_code=code,
            explanation=explanation,
            confidence=confidence,
            warnings=["Generated via fallback engine"] if source == "deterministic" else [],
            metadata={"source": source},
        )


# ---------------------------------------------------------------------------
# Helpers (module-level, no state)
# ---------------------------------------------------------------------------

def _extract_code_and_explanation(content: str) -> Tuple[str, str]:
    """Split LLM output into (code_block, explanation_text)."""
    code_parts: List[str] = []
    explanation_parts: List[str] = []
    in_block = False
    current_block: List[str] = []

    for line in content.splitlines():
        if line.startswith("```") and not in_block:
            in_block = True
            current_block = []
        elif line.startswith("```") and in_block:
            in_block = False
            code_parts.append("\n".join(current_block))
        elif in_block:
            current_block.append(line)
        else:
            explanation_parts.append(line)

    code = "\n\n".join(code_parts).strip()
    explanation = "\n".join(explanation_parts).strip()
    # If no fenced blocks found, treat entire content as code.
    if not code:
        code = content.strip()
    return code, explanation


def _deterministic_code_template(request: CopilotRequest) -> str:
    """Minimal deterministic template when all LLM backends are unavailable."""
    lang = request.language or "python"
    task_desc = request.prompt[:120].replace('"', "'")

    templates = {
        CopilotTaskType.CODE_GENERATION: (
            f'```{lang}\n# TODO: implement — {task_desc}\ndef main():\n    pass\n```'
        ),
        CopilotTaskType.TEST_GENERATION: (
            f'```{lang}\nimport unittest\n\nclass TestGenerated(unittest.TestCase):\n'
            f'    def test_placeholder(self):\n        # TODO: {task_desc}\n        self.assertTrue(True)\n```'
        ),
        CopilotTaskType.DOCUMENTATION: (
            f'```{lang}\n"""\n{task_desc}\n\nTODO: expand documentation.\n"""\n```'
        ),
        CopilotTaskType.WORKFLOW_CODE: (
            f'```{lang}\n# Murphy Workflow — {task_desc}\n'
            f'from src.orchestration import workflow\n\n'
            f'@workflow\ndef generated_workflow():\n    pass\n```'
        ),
    }
    return templates.get(
        request.task_type,
        f'```{lang}\n# TODO: {task_desc}\npass\n```',
    )
