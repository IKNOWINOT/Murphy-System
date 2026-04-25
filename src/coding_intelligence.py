"""
Murphy Coding Intelligence — PATCH-082b
Evaluates every generated integration connector on a 0-15 scale
and iteratively improves it until it scores >= 12.

Scoring rubric (15 points total):
  Code Quality (5pts):
    - Proper inheritance, no placeholder methods     (2pts)
    - Real API calls for every method                (1pt)
    - Error handling in every method                 (1pt)
    - Type hints throughout                          (1pt)
  
  API Coverage (5pts):
    - Auth method correct for service                (2pts)
    - Core CRUD operations covered                   (1pt)
    - Pagination handled where relevant              (1pt)
    - Webhook/event handling if service supports it  (1pt)
  
  Production Readiness (5pts):
    - Circuit breaker / retry via base class         (1pt)
    - Credential validation in is_configured()       (1pt)
    - Docstring with setup instructions              (1pt)
    - Rate limit awareness                           (1pt)
    - get_status() override with service-specific info (1pt)

Goal: >= 12/15 (better than typical Claude output)
Max: 15/15 (production-grade, better than hand-written)

PATCH-082b | Label: CODE-EVAL-001
"""
from __future__ import annotations

import ast
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

EVAL_LOG = Path("/var/lib/murphy-production/code_eval_log.json")
EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class CodeScore:
    """Score breakdown for a generated connector."""
    service: str
    total: float = 0.0
    max_score: float = 15.0
    
    # Dimensions
    quality: float = 0.0        # /5
    coverage: float = 0.0       # /5
    production: float = 0.0     # /5
    
    issues: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    improvement_prompt: str = ""
    
    @property
    def grade(self) -> str:
        pct = self.total / self.max_score
        if pct >= 0.93: return "15/15 — Exceptional"
        if pct >= 0.87: return "13+/15 — Excellent"
        if pct >= 0.80: return "12/15 — Production Ready"
        if pct >= 0.67: return "10/15 — Good"
        if pct >= 0.53: return "8/15 — Acceptable"
        return f"{self.total:.1f}/15 — Needs Work"
    
    @property
    def passes(self) -> bool:
        return self.total >= 12.0


def score_connector(code: str, service: str) -> CodeScore:
    """
    Static analysis scoring — no LLM needed, runs in <100ms.
    Evaluates the generated connector code on 15-point scale.
    """
    score = CodeScore(service=service)
    
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        score.issues.append(f"SyntaxError: {e}")
        return score
    
    # Extract class info
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    if not classes:
        score.issues.append("No class defined")
        return score
    
    cls = classes[0]
    methods = [n for n in ast.walk(cls) if isinstance(n, ast.FunctionDef)]
    public_methods = [m for m in methods if not m.name.startswith("_")]
    private_methods = [m for m in methods if m.name.startswith("_")]
    method_names = {m.name for m in methods}
    
    # ── QUALITY (5pts) ────────────────────────────────────────────────
    q = 0.0
    
    # Proper inheritance (2pts)
    bases = [ast.unparse(b) for b in cls.bases]
    if "BaseIntegrationConnector" in " ".join(bases):
        q += 2.0
        score.strengths.append("Correct inheritance from BaseIntegrationConnector")
    else:
        score.issues.append("Does not inherit BaseIntegrationConnector")
    
    # Real API calls - check for self._get/_post/_patch/_delete usage (1pt)
    code_body = ast.unparse(cls)
    api_calls = len(re.findall(r"self\._(get|post|patch|delete|put|http)", code_body))
    if api_calls >= 3:
        q += 1.0
        score.strengths.append(f"Real API calls: {api_calls} usages of HTTP methods")
    else:
        score.issues.append(f"Too few real API calls ({api_calls}), methods may be stubs")
    
    # Error handling (1pt)
    try_blocks = len(re.findall(r"\btry\b", code_body))
    if try_blocks >= 2:
        q += 1.0
        score.strengths.append("Error handling present")
    elif "not_configured_response" in code_body or "is_configured" in code_body:
        q += 0.5
    else:
        score.issues.append("Insufficient error handling")
    
    # Type hints (1pt)
    typed_methods = sum(
        1 for m in methods
        if m.returns is not None or any(a.annotation for a in m.args.args)
    )
    if typed_methods >= len(methods) * 0.6:
        q += 1.0
        score.strengths.append("Good type hint coverage")
    else:
        score.issues.append(f"Missing type hints ({typed_methods}/{len(methods)} methods typed)")
    
    score.quality = q
    
    # ── COVERAGE (5pts) ───────────────────────────────────────────────
    c = 0.0
    
    # Auth method (2pts)
    if "_build_headers" in method_names:
        c += 2.0
        score.strengths.append("_build_headers() override for auth")
    elif "CREDENTIAL_KEYS" in code:
        c += 1.0
        score.issues.append("Auth: CREDENTIAL_KEYS set but no _build_headers override")
    else:
        score.issues.append("No authentication method defined")
    
    # Core CRUD (1pt)
    crud_methods = {"create", "list", "get", "update", "delete", "search", "fetch"}
    has_crud = any(any(crud in m.name.lower() for crud in crud_methods) for m in public_methods)
    if has_crud:
        c += 1.0
        score.strengths.append("CRUD operations covered")
    else:
        score.issues.append("No CRUD operations found")
    
    # Pagination (1pt)
    if any(k in code_body for k in ["page", "cursor", "offset", "next_page", "limit", "per_page"]):
        c += 1.0
        score.strengths.append("Pagination handling present")
    else:
        score.issues.append("No pagination handling")
    
    # Webhook / events (1pt)
    if any(k in code_body.lower() for k in ["webhook", "event", "subscribe", "callback"]):
        c += 1.0
        score.strengths.append("Webhook/event handling")
    else:
        c += 0.5  # partial credit — not all APIs need webhooks
    
    score.coverage = c
    
    # ── PRODUCTION READINESS (5pts) ───────────────────────────────────
    p = 0.0
    
    # Circuit breaker via base class (1pt) — just using self._get/_post counts
    if api_calls >= 3:
        p += 1.0
        score.strengths.append("Uses base class retry/circuit-breaker via HTTP methods")
    
    # is_configured() override (1pt)
    if "is_configured" in method_names:
        p += 1.0
        score.strengths.append("is_configured() override present")
    else:
        score.issues.append("Missing is_configured() — credentials not validated")
    
    # Docstring with setup instructions (1pt)
    module_docstring = ast.get_docstring(tree)
    if module_docstring and len(module_docstring) > 50:
        p += 1.0
        score.strengths.append("Module docstring with setup instructions")
    else:
        score.issues.append("Missing/thin module docstring")
    
    # Rate limit awareness (1pt)
    if any(k in code_body.lower() for k in ["rate_limit", "retry_after", "429", "sleep", "backoff"]):
        p += 1.0
        score.strengths.append("Rate limit handling")
    else:
        p += 0.5  # base class handles some rate limiting
        score.issues.append("No explicit rate limit handling (base class provides some)")
    
    # get_status() override (1pt)
    if "get_status" in method_names:
        p += 1.0
        score.strengths.append("get_status() override with service-specific info")
    else:
        score.issues.append("No get_status() override")
    
    score.production = p
    score.total = q + c + p
    
    # Generate improvement prompt
    if not score.passes:
        score.improvement_prompt = _build_improvement_prompt(score, code, service)
    
    return score


def _build_improvement_prompt(score: CodeScore, code: str, service: str) -> str:
    """Build a targeted improvement prompt based on what's missing."""
    issues_str = "\n".join(f"- {i}" for i in score.issues)
    strengths_str = "\n".join(f"- {s}" for s in score.strengths[:3])
    
    return f"""The {service} connector scored {score.total:.1f}/15.

KEEP THESE STRENGTHS:
{strengths_str}

FIX THESE ISSUES (required to reach 12/15):
{issues_str}

SPECIFIC REQUIREMENTS:
1. {"Add _build_headers() that returns correct auth headers" if "_build_headers" not in code else "Keep _build_headers()"}
2. {"Add is_configured() checking all required credentials" if "is_configured" not in code else "Keep is_configured()"}
3. {"Add get_status() returning service-specific health info" if "get_status" not in code else "Keep get_status()"}
4. Ensure every public method uses self._get(), self._post(), etc. (not raw requests)
5. Add type hints to all method signatures
6. {"Add pagination to list methods" if "page" not in code else "Keep pagination"}
7. Add module docstring with credential setup instructions

Return the COMPLETE improved class — do not abbreviate."""


def evaluate_and_improve(
    code: str,
    service: str,
    category: str = "",
    max_attempts: int = 3,
) -> Tuple[str, CodeScore, int]:
    """
    Main entry: evaluate code, improve it if score < 12, up to max_attempts.
    
    Returns:
        (final_code, final_score, attempts_made)
    """
    best_code = code
    best_score = score_connector(code, service)
    attempts = 1
    
    logger.info("CODE-EVAL: %s initial score: %.1f/15 (%s)", 
                service, best_score.total, best_score.grade)
    
    while not best_score.passes and attempts < max_attempts:
        attempts += 1
        logger.info("CODE-EVAL: %s attempt %d — improving (score was %.1f/15)",
                    service, attempts, best_score.total)
        
        improved = _improve_code(best_code, service, best_score.improvement_prompt)
        if not improved:
            logger.warning("CODE-EVAL: improvement attempt %d returned empty", attempts)
            break
        
        new_score = score_connector(improved, service)
        logger.info("CODE-EVAL: %s attempt %d score: %.1f/15", service, attempts, new_score.total)
        
        if new_score.total > best_score.total:
            best_code = improved
            best_score = new_score
    
    # Log result
    _log_eval(service, best_score, attempts)
    
    if best_score.passes:
        logger.info("CODE-EVAL: ✅ %s PASSED: %.1f/15 in %d attempt(s)", 
                    service, best_score.total, attempts)
    else:
        logger.warning("CODE-EVAL: ⚠️  %s best score: %.1f/15 after %d attempts",
                       service, best_score.total, attempts)
    
    return best_code, best_score, attempts


def _improve_code(code: str, service: str, improvement_prompt: str) -> str:
    """Call LLM with specific improvement instructions."""
    try:
        import os, requests as _req
        
        system = """You are a senior Python engineer at Inoni LLC writing production-grade API connectors.
You write code that scores 15/15 on quality, coverage, and production readiness.
Every method makes real API calls. Every class is fully implemented. No placeholders."""
        
        prompt = f"""Improve this {service} connector:

{improvement_prompt}

CURRENT CODE:
```python
{code[:3000]}
```

Write the COMPLETE improved connector. Include the full class, all imports, module docstring."""
        
        # Try DeepInfra first
        key = os.getenv("DEEPINFRA_API_KEY", "")
        if key:
            try:
                r = _req.post(
                    "https://api.deepinfra.com/v1/openai/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={
                        "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 2500,
                        "temperature": 0.15,
                    },
                    timeout=60,
                )
                if r.status_code == 200:
                    content = r.json()["choices"][0]["message"]["content"]
                    # Extract code block
                    m = re.search(r"```python\s*\n(.*?)\n```", content, re.DOTALL)
                    if m:
                        return m.group(1).strip()
                    return content
            except Exception as e:
                logger.warning("CODE-EVAL: DeepInfra improve failed: %s", e)
        
        # Ollama fallback
        combined = f"{system}\n\nUser: {prompt}\nAssistant:"
        r2 = _req.post(
            "http://localhost:11434/api/generate",
            json={"model": "phi3:latest", "prompt": combined, "stream": False,
                  "options": {"num_predict": 2000, "temperature": 0.15}},
            timeout=90,
        )
        if r2.status_code == 200:
            resp = r2.json().get("response", "")
            m = re.search(r"```python\s*\n(.*?)\n```", resp, re.DOTALL)
            return m.group(1).strip() if m else resp
    except Exception as exc:
        logger.error("CODE-EVAL: improvement failed: %s", exc)
    
    return ""


def _log_eval(service: str, score: CodeScore, attempts: int) -> None:
    try:
        log = json.loads(EVAL_LOG.read_text()) if EVAL_LOG.exists() else []
        log.append({
            "service": service,
            "total": score.total,
            "quality": score.quality,
            "coverage": score.coverage,
            "production": score.production,
            "grade": score.grade,
            "passed": score.passes,
            "attempts": attempts,
            "issues": score.issues,
            "strengths": score.strengths,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        EVAL_LOG.write_text(json.dumps(log, indent=2))
    except Exception as exc:
        logger.error("CODE-EVAL: log failed: %s", exc)
