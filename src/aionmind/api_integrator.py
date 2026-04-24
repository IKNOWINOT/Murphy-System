"""
API Auto-Integrator — PATCH-064
Copyright 2020 Inoni LLC | License: BSL 1.1

Gives AionMind the ability to:
  1. Fetch docs/OpenAPI spec for any external API
  2. Generate a Python connector module for it
  3. Register the new connector's tools into UniversalToolRegistry
  4. Persist the connector to /opt/Murphy-System/src/connectors/

This is the loop: intent -> fetch docs -> write code -> register tools -> available immediately.

Label: API-AUTO-001
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CONNECTOR_DIR = Path("/opt/Murphy-System/src/connectors")
_CONNECTOR_DIR.mkdir(parents=True, exist_ok=True)

# Write __init__.py if missing
_init = _CONNECTOR_DIR / "__init__.py"
if not _init.exists():
    _init.write_text("# Auto-generated connectors package\n")


# ---------------------------------------------------------------------------
# Step 1: Fetch API documentation or OpenAPI spec
# ---------------------------------------------------------------------------

def fetch_api_docs(api_name: str, docs_url: str, spec_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch documentation for an external API.
    Returns {ok, api_name, docs_text, spec} where spec is parsed OpenAPI if available.
    Label: API-AUTO-002
    """
    from src.aionmind.tool_executor import web_fetch, http_get, json_parse

    result = {"ok": False, "api_name": api_name, "docs_text": "", "spec": None}

    # Try OpenAPI spec first (structured)
    if spec_url:
        spec_resp = http_get(spec_url, timeout=15)
        if spec_resp.get("status") == 200:
            parsed = json_parse(spec_resp["body"])
            if parsed["ok"]:
                result["spec"] = parsed["data"]
                logger.info("API-AUTO-002: Got OpenAPI spec for %s (%d bytes)", api_name, len(spec_resp["body"]))

    # Also fetch docs as plain text
    docs_resp = web_fetch(docs_url, timeout=15)
    if docs_resp.get("ok"):
        result["docs_text"] = docs_resp.get("text", "")[:30000]
        result["ok"] = True
    elif result["spec"]:
        result["ok"] = True  # spec alone is enough

    return result


# ---------------------------------------------------------------------------
# Step 2: Generate connector module via LLM
# ---------------------------------------------------------------------------

def generate_connector_code(api_name: str, docs_text: str, spec: Optional[Dict],
                             base_url: str = "", auth_type: str = "api_key") -> Dict[str, Any]:
    """
    Use LLM to generate a Python connector module for the given API.
    Returns {ok, code, module_name}.
    Label: API-AUTO-003
    """
    try:
        from src.llm_provider import MurphyLLMProvider
        llm = MurphyLLMProvider.from_env()

        spec_summary = ""
        if spec and "paths" in spec:
            paths = list(spec["paths"].keys())[:20]
            spec_summary = f"\nOpenAPI paths: {', '.join(paths)}"

        system = (
            "You are Murphy's API connector generator. "
            "Write a clean, minimal Python module that wraps an external REST API. "
            "The module must define: "
            "(1) A client class named <ApiName>Client with __init__(self, api_key=None, base_url=None) "
            "(2) Methods for the 5 most important endpoints "
            "(3) A TOOL_DEFINITIONS list of dicts: [{'fn': <method>, 'tool_id': str, 'name': str, "
            "'description': str, 'tags': list, 'requires_approval': bool}] "
            "Use only stdlib (urllib, json, os). No third-party deps. "
            "Return ONLY the Python code, no explanation."
        )

        prompt = (
            f"Generate a Murphy connector for: {api_name}\n"
            f"Base URL: {base_url or '(infer from docs)'}\n"
            f"Auth type: {auth_type}\n"
            f"Docs excerpt:\n{docs_text[:8000]}"
            f"{spec_summary}"
        )

        completion = llm.complete(prompt, system=system, max_tokens=2000, temperature=0.2)

        code = completion.content
        # Extract code block if wrapped
        code_match = re.search(r"```python\n(.*?)```", code, re.DOTALL)
        if code_match:
            code = code_match.group(1)

        # Validate syntax
        try:
            compile(code, f"{api_name}_connector.py", "exec")
        except SyntaxError as exc:
            return {"ok": False, "error": f"LLM-generated code has SyntaxError: {exc}", "code": code}

        module_name = re.sub(r"[^a-z0-9_]", "_", api_name.lower()) + "_connector"
        return {"ok": True, "code": code, "module_name": module_name}

    except Exception as exc:
        return {"ok": False, "error": str(exc), "code": ""}


# ---------------------------------------------------------------------------
# Step 3: Write connector to disk
# ---------------------------------------------------------------------------

def write_connector(module_name: str, code: str) -> Dict[str, Any]:
    """
    Write the generated connector to /opt/Murphy-System/src/connectors/<module_name>.py
    With backup if it already exists.
    Label: API-AUTO-004
    """
    from src.aionmind.tool_executor import murphy_patch
    file_path = str(_CONNECTOR_DIR / f"{module_name}.py")
    return murphy_patch(
        patch_id=f"api-auto-{module_name}",
        file_path=file_path,
        new_content=code,
        backup=True,
        description=f"Auto-generated connector: {module_name}",
    )


# ---------------------------------------------------------------------------
# Step 4: Register connector tools into UniversalToolRegistry
# ---------------------------------------------------------------------------

def register_connector_tools(module_name: str, api_key: Optional[str] = None,
                              base_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Import the connector module and register its TOOL_DEFINITIONS.
    Label: API-AUTO-005
    """
    try:
        import importlib
        import sys

        # Ensure connectors dir is on path
        connectors_parent = str(_CONNECTOR_DIR.parent)
        if connectors_parent not in sys.path:
            sys.path.insert(0, connectors_parent)

        module_path = f"connectors.{module_name}"
        if module_path in sys.modules:
            del sys.modules[module_path]  # force reload

        mod = importlib.import_module(module_path)
        tool_defs = getattr(mod, "TOOL_DEFINITIONS", [])

        if not tool_defs:
            return {"ok": False, "error": "Module has no TOOL_DEFINITIONS list"}

        from src.tool_registry.registry import UniversalToolRegistry
        from src.tool_registry.models import (
            ToolDefinition, ToolInputSchema, ToolOutputSchema,
            CostEstimate, CostTier, PermissionLevel,
        )

        registry = UniversalToolRegistry()
        registered = []

        # Instantiate client
        client_class_name = None
        for name in dir(mod):
            if name.endswith("Client") and name[0].isupper():
                client_class_name = name
                break

        client_instance = None
        if client_class_name:
            try:
                cls = getattr(mod, client_class_name)
                client_instance = cls(api_key=api_key, base_url=base_url)
            except Exception as exc:
                logger.debug("Could not instantiate %s: %s", client_class_name, exc)

        for td in tool_defs:
            fn = td.get("fn")
            if callable(fn) and client_instance:
                import functools
                fn = functools.partial(getattr(client_instance, fn.__name__))

            defn = ToolDefinition(
                tool_id=td.get("tool_id", f"connector.{module_name}.{td.get('name','unknown')}"),
                name=td.get("name", ""),
                description=td.get("description", ""),
                permission_level=PermissionLevel.MEDIUM,
                cost_estimate=CostEstimate(tier=CostTier.CHEAP),
                input_schema=ToolInputSchema(),
                output_schema=ToolOutputSchema(),
                provider=f"connector.{module_name}",
                tags=td.get("tags", []),
                requires_approval=td.get("requires_approval", False),
                metadata={"_callable": fn, "module": module_name},
            )
            registry.register(defn)
            registered.append(defn.tool_id)

        logger.info("API-AUTO-005: Registered %d tools from %s", len(registered), module_name)
        return {"ok": True, "module": module_name, "tools_registered": registered}

    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Full pipeline: intent → working connector
# ---------------------------------------------------------------------------

def integrate_api(
    api_name: str,
    docs_url: str,
    base_url: str = "",
    auth_type: str = "api_key",
    api_key: Optional[str] = None,
    spec_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    One-shot: fetch docs → generate code → write → register tools.
    Returns {ok, module_name, tools_registered, steps}.
    Label: API-AUTO-006
    """
    steps = []

    # 1. Fetch docs
    docs_result = fetch_api_docs(api_name, docs_url, spec_url=spec_url)
    steps.append({"step": "fetch_docs", "ok": docs_result["ok"]})
    if not docs_result["ok"]:
        return {"ok": False, "error": "Could not fetch API docs", "steps": steps}

    # 2. Generate code
    code_result = generate_connector_code(
        api_name, docs_result["docs_text"], docs_result.get("spec"),
        base_url=base_url, auth_type=auth_type,
    )
    steps.append({"step": "generate_code", "ok": code_result["ok"]})
    if not code_result["ok"]:
        return {"ok": False, "error": code_result["error"], "steps": steps, "code": code_result.get("code")}

    module_name = code_result["module_name"]

    # 3. Write to disk
    write_result = write_connector(module_name, code_result["code"])
    steps.append({"step": "write_connector", "ok": write_result["ok"], "file": write_result.get("file")})
    if not write_result["ok"]:
        return {"ok": False, "error": write_result["error"], "steps": steps}

    # 4. Register tools
    reg_result = register_connector_tools(module_name, api_key=api_key, base_url=base_url)
    steps.append({"step": "register_tools", "ok": reg_result["ok"], "tools": reg_result.get("tools_registered", [])})

    return {
        "ok": reg_result["ok"],
        "api_name": api_name,
        "module_name": module_name,
        "tools_registered": reg_result.get("tools_registered", []),
        "steps": steps,
    }
