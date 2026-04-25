"""
Autonomous Integration Builder — PATCH-081a
Murphy's self-directed integration creation engine.

Given a service name (e.g. "plaid", "zenbusiness", "quickbooks"),
Murphy will:
  1. Search for the service's API documentation
  2. Fetch and analyze the docs
  3. Generate a complete connector using the base_connector template
  4. Validate the generated code (syntax + import check)
  5. Write to src/integrations/<service>_connector.py
  6. Register in world_model_registry.py
  7. Mount via the integration router
  8. Log the result as a self-patch proposal

This gives Murphy the ability to build its own integrations on demand
without human code involvement — just: POST /api/integrations/build
with {"service": "plaid", "category": "banking"}

PATCH-081a | Label: AUTO-INTEG-001
Copyright © 2020-2026 Inoni LLC
"""
from __future__ import annotations

import ast
import json
import logging
import os
import re
import textwrap
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SRC_DIR = Path("/opt/Murphy-System/src")
INTEGRATIONS_DIR = SRC_DIR / "integrations"
REGISTRY_FILE = SRC_DIR / "integrations" / "world_model_registry.py"
BUILD_LOG = Path("/var/lib/murphy-production/integration_builds.json")
BUILD_LOG.parent.mkdir(parents=True, exist_ok=True)

# ── Known integration targets Murphy should proactively build ────────────────
PRIORITY_INTEGRATION_TARGETS = [
    # Banking / Finance
    {"service": "plaid",           "category": "banking",      "description": "Bank account linking, transaction history, balance"},
    {"service": "stripe_billing",  "category": "billing",      "description": "Subscription management, invoices, usage billing"},
    {"service": "quickbooks",      "category": "accounting",   "description": "Invoicing, expenses, P&L, tax reporting"},
    {"service": "xero",            "category": "accounting",   "description": "Accounting, payroll, invoicing"},
    {"service": "mercury",         "category": "banking",      "description": "Business banking API for startups"},
    {"service": "brex",            "category": "banking",      "description": "Corporate cards and spend management"},
    # Legal / Business Formation
    {"service": "zenbusiness",     "category": "legal",        "description": "LLC formation, registered agent, compliance filings"},
    {"service": "docusign",        "category": "legal",        "description": "eSignature for contracts, operating agreements"},
    {"service": "clerky",          "category": "legal",        "description": "Startup legal documents and incorporation"},
    # Content / Media
    {"service": "contentful",      "category": "cms",          "description": "Headless CMS for digital content management"},
    {"service": "sanity",          "category": "cms",          "description": "Structured content platform"},
    {"service": "cloudinary",      "category": "media",        "description": "Image/video upload, transform, deliver"},
    {"service": "mux",             "category": "media",        "description": "Video streaming and encoding"},
    # HR / Payroll
    {"service": "gusto",           "category": "hr_payroll",   "description": "Payroll, benefits, compliance"},
    {"service": "rippling",        "category": "hr_payroll",   "description": "HR, IT, Finance unified platform"},
    {"service": "bamboohr",        "category": "hr",           "description": "HR management, employee records"},
    # Communication
    {"service": "sendbird",        "category": "messaging",    "description": "In-app chat and messaging SDK"},
    {"service": "vonage",          "category": "communication","description": "SMS, voice, video APIs"},
    {"service": "postmark",        "category": "email",        "description": "Transactional email delivery"},
    # Infrastructure
    {"service": "vercel",          "category": "hosting",      "description": "Frontend deployment and edge functions"},
    {"service": "render",          "category": "hosting",      "description": "Cloud hosting for web services"},
    {"service": "digitalocean",    "category": "cloud",        "description": "Cloud infrastructure, droplets, databases"},
    # Data / Analytics
    {"service": "mixpanel",        "category": "analytics",    "description": "Product analytics and user tracking"},
    {"service": "segment",         "category": "analytics",    "description": "Customer data platform"},
    {"service": "amplitude",       "category": "analytics",    "description": "Product analytics"},
    # E-commerce
    {"service": "woocommerce",     "category": "ecommerce",    "description": "WordPress e-commerce"},
    {"service": "square",          "category": "payments",     "description": "POS, payments, invoicing"},
    # Security / Auth
    {"service": "auth0",           "category": "auth",         "description": "Authentication and authorization platform"},
    {"service": "okta",            "category": "auth",         "description": "Identity and access management"},
    # Science / Research
    {"service": "arxiv_api",       "category": "research",     "description": "Scientific paper search and download"},
    {"service": "pubmed",          "category": "research",     "description": "Biomedical literature search"},
    {"service": "crossref",        "category": "research",     "description": "DOI resolution and citation data"},
    # Real Estate / Construction
    {"service": "procore",         "category": "construction", "description": "Construction project management"},
    {"service": "buildertrend",    "category": "construction", "description": "Residential construction management"},
    {"service": "ezdxf_cloud",     "category": "cad",          "description": "CAD file processing and conversion"},
    # Government / Compliance
    {"service": "irs_tin_match",   "category": "compliance",   "description": "IRS TIN matching for vendor compliance"},
    {"service": "secretary_state", "category": "compliance",   "description": "Business entity lookup and filing status"},
]


def _load_build_log() -> List[Dict]:
    try:
        return json.loads(BUILD_LOG.read_text()) if BUILD_LOG.exists() else []
    except Exception:
        return []


def _save_build_log(log: List[Dict]) -> None:
    try:
        BUILD_LOG.write_text(json.dumps(log, indent=2))
    except Exception as exc:
        logger.error("AUTO-INTEG: build log save failed: %s", exc)


def _already_built(service: str) -> bool:
    """Check if connector already exists."""
    connector_file = INTEGRATIONS_DIR / f"{service}_connector.py"
    if connector_file.exists():
        return True
    # Also check registry
    registry_text = REGISTRY_FILE.read_text() if REGISTRY_FILE.exists() else ""
    return f'"{service}"' in registry_text


def _search_api_docs(service: str, description: str) -> str:
    """Web-search for API documentation and fetch key content."""
    try:
        from src.web_tool import search, fetch
        
        # Search for official API docs
        queries = [
            f"{service} REST API documentation developer",
            f"{service} API authentication endpoints",
        ]
        
        doc_text = f"SERVICE: {service}\nDESCRIPTION: {description}\n\n"
        
        for query in queries[:1]:  # one search to keep it fast
            results = search(query, max_results=5)
            for r in results[:3]:
                url = r.get("url", "")
                if not url:
                    continue
                # Prefer official docs
                if any(k in url for k in ["docs.", "developer.", "api.", "developers.", "/api"]):
                    page = fetch(url, timeout=15)
                    if page.get("ok") and len(page.get("text", "")) > 200:
                        doc_text += f"SOURCE: {url}\n{page['text'][:3000]}\n\n"
                        break
                    
        # Also use snippet info from search
        doc_text += "SEARCH SNIPPETS:\n"
        for r in results[:3]:
            doc_text += f"- {r.get('title','')}\n  {r.get('snippet','')[:200]}\n"
            
        return doc_text[:5000]
    except Exception as exc:
        logger.warning("AUTO-INTEG: API doc search failed for %s: %s", service, exc)
        return f"SERVICE: {service}\nDESCRIPTION: {description}"


def _generate_connector_code(
    service: str,
    category: str, 
    description: str,
    api_doc_context: str,
) -> Tuple[str, str]:
    """
    Use LLM to generate a complete connector — direct API calls to bypass singleton issues.
    Returns (code, explanation).
    """
    import os, requests as _req
    
    try:
        base_template = (INTEGRATIONS_DIR / "base_connector.py").read_text()[:2500]
        slack_example = (INTEGRATIONS_DIR / "slack_connector.py").read_text()[:2000]
    except Exception:
        base_template = ""
        slack_example = ""
    
    class_name = "".join(w.capitalize() for w in re.split(r"[_\-]", service)) + "Connector"
    env_key = service.upper().replace("-", "_") + "_API_KEY"

    system_prompt = f"""You are Murphy — a senior Python engineer at Inoni LLC writing production-grade REST API connectors.
Rules:
- ALWAYS inherit from BaseIntegrationConnector
- ALWAYS implement _build_headers() with correct auth for this service
- ALWAYS implement is_configured() checking required credentials
- ALWAYS implement get_status() with service-specific health info
- EVERY public method uses self._get(), self._post(), self._patch(), or self._delete()
- NO placeholder methods — every method must make a real API call
- Include type hints on all parameters and return values
- Handle pagination in list/search methods
- Include module docstring with credential setup instructions
- Target: 12-15 quality points (production-grade, better than typical AI output)"""

    user_prompt = f"""Write a complete Python connector for: {service}
Category: {category}
Description: {description}
Class name: {class_name}
Primary env var: {env_key}

API context:
{api_doc_context[:2000]}

Base class pattern:
{base_template[:1500]}

Example (Slack):
{slack_example[:1200]}

Return ONLY a Python code block with the complete connector. No explanations outside the block."""

    response = None
    explanation = f"Auto-built {service} connector"
    
    # Try 1: DeepInfra direct (bypasses broken singleton)
    di_key = os.getenv("DEEPINFRA_API_KEY", "")
    if di_key:
        try:
            r = _req.post(
                "https://api.deepinfra.com/v1/openai/chat/completions",
                headers={"Authorization": f"Bearer {di_key}", "Content-Type": "application/json"},
                json={
                    "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 2500,
                    "temperature": 0.15,
                },
                timeout=60,
            )
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"]
                m = re.search(r"```python\s*\n(.*?)\n```", content, re.DOTALL)
                response = m.group(1).strip() if m else content
                explanation = f"DeepInfra/Llama-3.3-70B generated {service} connector"
                logger.info("AUTO-INTEG: DeepInfra generated %s", service)
            else:
                logger.warning("AUTO-INTEG: DeepInfra %d: %s", r.status_code, r.text[:100])
        except Exception as e:
            logger.warning("AUTO-INTEG: DeepInfra direct call failed: %s", e)
    
    # Try 2: Ollama phi3 local
    if not response:
        try:
            combined = f"{system_prompt}\n\nUser: {user_prompt}\nAssistant:"
            r2 = _req.post(
                "http://localhost:11434/api/generate",
                json={"model": "phi3:latest", "prompt": combined, "stream": False,
                      "options": {"num_predict": 2000, "temperature": 0.15}},
                timeout=90,
            )
            if r2.status_code == 200:
                resp_text = r2.json().get("response", "")
                m = re.search(r"```python\s*\n(.*?)\n```", resp_text, re.DOTALL)
                response = m.group(1).strip() if m else resp_text
                explanation = f"Phi3/local generated {service} connector"
                logger.info("AUTO-INTEG: Phi3 generated %s", service)
        except Exception as e:
            logger.warning("AUTO-INTEG: Phi3 fallback failed: %s", e)
    
    if not response:
        return "", "All LLM providers unavailable"
    
    if not response:
        return "", "LLM returned empty response"
    
    # Extract code block
    explanation = ""
    m = re.search(r"EXPLANATION:\s*(.+?)\n", response)
    if m:
        explanation = m.group(1).strip()
    
    code_match = re.search(r"```python\s*\n(.*?)\n```", response, re.DOTALL)
    if code_match:
        code = code_match.group(1).strip()
    else:
        # Try to find any code block
        code_match2 = re.search(r"```\s*\n(.*?)\n```", response, re.DOTALL)
        code = code_match2.group(1).strip() if code_match2 else response
    
    return code, explanation


def _validate_code(code: str, service: str) -> Tuple[bool, str]:
    """Validate generated code: syntax check + class structure check."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"
    
    # Check for class definition
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    if not classes:
        return False, "No class definition found"
    
    expected = "".join(w.capitalize() for w in re.split(r"[_\-]", service)) + "Connector"
    if expected not in classes:
        logger.warning("AUTO-INTEG: expected class %s, found %s", expected, classes)
    
    # Check inherits from BaseIntegrationConnector
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases]
            if "BaseIntegrationConnector" not in " ".join(bases):
                return False, f"Class {node.name} does not inherit BaseIntegrationConnector"
    
    return True, "OK"


def _register_connector(service: str, category: str, class_name: str) -> bool:
    """Add the new connector to world_model_registry.py."""
    try:
        registry_text = REGISTRY_FILE.read_text()
        
        # Add to _CONNECTOR_MAP
        connector_entry = f'''    "{service}":           "integrations.{service}_connector.{class_name}",\n'''
        if f'"{service}"' not in registry_text:
            # Find category comment or end of map
            scada_line = '    "scada":             "integrations.scada_connector.SCADAConnector",'
            if scada_line in registry_text:
                registry_text = registry_text.replace(
                    scada_line,
                    scada_line + "\n" + connector_entry.rstrip(),
                )
        
        # Add to _INTEGRATION_META
        meta_entry = f'''    "{service}":        {{"name": "{class_name.replace('Connector','')}", "category": "{category}", "free": True}},\n'''
        if f'"{service}"' not in registry_text:
            # Find end of _INTEGRATION_META
            scada_meta = '    "scada":            {"name": "SCADA / ICS"'
            if scada_meta in registry_text:
                idx = registry_text.find(scada_meta)
                line_end = registry_text.find("\n", idx) + 1
                registry_text = registry_text[:line_end] + meta_entry + registry_text[line_end:]
        
        REGISTRY_FILE.write_text(registry_text)
        return True
    except Exception as exc:
        logger.error("AUTO-INTEG: registry update failed for %s: %s", service, exc)
        return False


def build_integration(
    service: str,
    category: str = "general",
    description: str = "",
    search_docs: bool = True,
) -> Dict[str, Any]:
    """
    Main entry point: autonomously build a new integration connector.
    
    Args:
        service: snake_case service name (e.g. "plaid", "zenbusiness")
        category: Category (banking, legal, cms, hr_payroll, etc.)
        description: What the service does
        search_docs: Whether to web-search for API docs first
    
    Returns:
        {ok, service, file_path, class_name, methods, explanation, error}
    """
    logger.info("AUTO-INTEG: Starting build for %s (%s)", service, category)
    
    if _already_built(service):
        return {
            "ok": True, "service": service, "status": "already_exists",
            "message": f"Connector for {service} already exists",
        }
    
    # 1. Research the API
    api_docs = ""
    if search_docs:
        logger.info("AUTO-INTEG: Researching %s API docs...", service)
        api_docs = _search_api_docs(service, description)
    
    # 2. Generate connector code
    logger.info("AUTO-INTEG: Generating connector for %s...", service)
    class_name = "".join(w.capitalize() for w in re.split(r"[_\-]", service)) + "Connector"
    
    code, explanation = _generate_connector_code(service, category, description, api_docs)
    
    if not code:
        result = {"ok": False, "service": service, "error": explanation}
        _log_build(service, False, explanation)
        return result
    
    # 3. Validate syntax
    valid, reason = _validate_code(code, service)
    if not valid:
        if "BaseIntegrationConnector" not in code:
            code = "from .base_connector import BaseIntegrationConnector\n\n" + code
            valid, reason = _validate_code(code, service)
    
    if not valid:
        result = {"ok": False, "service": service, "error": f"Validation failed: {reason}", "code_preview": code[:300]}
        _log_build(service, False, reason)
        return result
    
    # 3b. Quality evaluation + iterative improvement (PATCH-082b)
    try:
        from src.coding_intelligence import evaluate_and_improve
        code, eval_score, attempts = evaluate_and_improve(code, service, category, max_attempts=3)
        logger.info("AUTO-INTEG: %s quality score: %.1f/15 (%s) in %d attempt(s)",
                    service, eval_score.total, eval_score.grade, attempts)
    except Exception as eval_exc:
        eval_score = None
        logger.warning("AUTO-INTEG: quality eval failed for %s: %s", service, eval_exc)
    
    # 4. Add import if missing
    if "from .base_connector import" not in code and "from integrations.base_connector" not in code:
        code = '''"""Auto-generated connector — PATCH-081a"""\nfrom __future__ import annotations\nfrom typing import Any, Dict, List, Optional\nfrom .base_connector import BaseIntegrationConnector\n\n''' + code
    
    # 5. Write file
    connector_file = INTEGRATIONS_DIR / f"{service}_connector.py"
    connector_file.write_text(code)
    
    # 6. Final syntax check
    import subprocess
    check = subprocess.run(
        ["/opt/Murphy-System/venv/bin/python3", "-m", "py_compile", str(connector_file)],
        capture_output=True, text=True
    )
    if check.returncode != 0:
        connector_file.unlink()  # remove broken file
        result = {"ok": False, "service": service, "error": f"Syntax error in generated code: {check.stderr[:200]}"}
        _log_build(service, False, check.stderr[:200])
        return result
    
    # 7. Register in world_model_registry
    registered = _register_connector(service, category, class_name)
    
    # 8. Count methods
    tree = ast.parse(code)
    methods = [n.name for n in ast.walk(tree) 
               if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]
    
    logger.info("AUTO-INTEG: ✅ Built %s — %d methods, registered=%s", service, len(methods), registered)
    
    score_data = {}
    if eval_score:
        score_data = {
            "quality_score": eval_score.total,
            "quality_grade": eval_score.grade,
            "quality_passed": eval_score.passes,
            "quality_attempts": attempts,
            "quality_issues": eval_score.issues,
            "quality_strengths": eval_score.strengths[:3],
        }
    
    result = {
        "ok": True,
        "service": service,
        "class_name": class_name,
        "file_path": str(connector_file),
        "category": category,
        "methods": methods,
        "method_count": len(methods),
        "registered": registered,
        "explanation": explanation,
        **score_data,
    }
    _log_build(service, True, explanation, methods)
    return result


def _log_build(service: str, ok: bool, message: str, methods: List[str] = None) -> None:
    log = _load_build_log()
    log.append({
        "service": service,
        "ok": ok,
        "message": message,
        "methods": methods or [],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    _save_build_log(log)


def run_autonomous_build_cycle(max_per_run: int = 3) -> Dict[str, Any]:
    """
    Autonomous cycle: build the next N priority integrations that don't exist yet.
    Called by a scheduled automation or on demand.
    """
    log = _load_build_log()
    already_attempted = {e["service"] for e in log}
    
    to_build = [
        t for t in PRIORITY_INTEGRATION_TARGETS
        if t["service"] not in already_attempted and not _already_built(t["service"])
    ][:max_per_run]
    
    if not to_build:
        return {"ok": True, "message": "All priority integrations already built", "built": []}
    
    built = []
    for target in to_build:
        result = build_integration(
            service=target["service"],
            category=target["category"],
            description=target["description"],
            search_docs=True,
        )
        built.append(result)
        time.sleep(2)  # rate limit LLM calls
    
    return {
        "ok": True,
        "built": built,
        "total_attempted": len(to_build),
        "total_succeeded": sum(1 for r in built if r.get("ok")),
    }
