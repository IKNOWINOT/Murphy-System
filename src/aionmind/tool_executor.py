"""
AionMind Tool Executor - PATCH-062
Copyright 2020 Inoni LLC | License: BSL 1.1

Provides 10 real, executable tools that AionMind can call via cognitive_execute.
Tools are registered into UniversalToolRegistry on import.

Label: TOOL-EXEC-001
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BLOCKED_SHELL_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"dd\s+if=",
    r":(\s*\{.*\}\s*;\s*)+",
    r"chmod\s+777\s+/",
    r">/dev/sd",
    r"shutdown",
    r"reboot",
    r"halt",
]

_ALLOWED_WRITE_ROOTS = [
    "/opt/Murphy-System/src/",
    "/opt/Murphy-System/static/",
    "/opt/Murphy-System/",
    "/tmp/murphy_",
]

_SHELL_TIMEOUT = 30
_HTTP_TIMEOUT  = 20


def _shell_is_safe(cmd):
    for pat in _BLOCKED_SHELL_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            return False, f"Blocked pattern: {pat}"
    return True, ""


def _write_path_is_safe(path):
    p = str(Path(path).resolve())
    for root in _ALLOWED_WRITE_ROOTS:
        if p.startswith(root):
            return True, ""
    return False, f"Write outside approved roots: {p}"


def http_get(url, headers=None, timeout=_HTTP_TIMEOUT):
    try:
        req = urllib.request.Request(url, headers=headers or {}, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"status": resp.status, "body": body, "headers": dict(resp.headers)}
    except Exception as exc:
        return {"status": 0, "body": "", "error": str(exc)}


def http_post(url, payload, headers=None, timeout=_HTTP_TIMEOUT):
    try:
        data = json.dumps(payload).encode()
        hdrs = {"Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"status": resp.status, "body": body, "headers": dict(resp.headers)}
    except Exception as exc:
        return {"status": 0, "body": "", "error": str(exc)}


def file_read(path, max_bytes=500000):
    try:
        p = Path(path)
        if not p.exists():
            return {"ok": False, "error": f"File not found: {path}"}
        content = p.read_bytes()[:max_bytes].decode("utf-8", errors="replace")
        return {"ok": True, "content": content, "bytes": len(content), "truncated": len(content) >= max_bytes}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def file_write(path, content, overwrite=False):
    ok, reason = _write_path_is_safe(path)
    if not ok:
        return {"ok": False, "error": reason}
    try:
        p = Path(path)
        if p.exists() and not overwrite:
            return {"ok": False, "error": "File exists and overwrite=False"}
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(p)
        return {"ok": True, "bytes_written": len(content.encode())}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def file_append(path, content):
    ok, reason = _write_path_is_safe(path)
    if not ok:
        return {"ok": False, "error": reason}
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        return {"ok": True, "bytes_appended": len(content.encode())}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def shell_exec(cmd, cwd="/opt/Murphy-System", timeout=_SHELL_TIMEOUT):
    ok, reason = _shell_is_safe(cmd)
    if not ok:
        return {"ok": False, "error": f"BLOCKED: {reason}", "stdout": "", "stderr": "", "returncode": -1}
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=cwd,
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout[-10000:],
            "stderr": result.stderr[-5000:],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timeout after {timeout}s", "stdout": "", "stderr": "", "returncode": -1}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "stdout": "", "stderr": "", "returncode": -1}


def env_read(keys=None):
    SECRET_PATTERNS = re.compile(r"(key|secret|token|password|pass|api|auth|private)", re.IGNORECASE)
    if keys:
        return {k: os.getenv(k, "") for k in keys if not SECRET_PATTERNS.search(k)}
    return {k: v for k, v in os.environ.items() if not SECRET_PATTERNS.search(k)}


def web_fetch(url, timeout=_HTTP_TIMEOUT):
    result = http_get(url, timeout=timeout)
    if result.get("error"):
        return result
    body = result["body"]
    text = re.sub(r"<[^>]+>", " ", body)
    text = re.sub(r"\s+", " ", text).strip()
    return {"ok": True, "url": url, "text": text[:50000], "chars": len(text)}


def json_parse(text):
    try:
        return {"ok": True, "data": json.loads(text)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def json_format(data, indent=2):
    try:
        return {"ok": True, "json": json.dumps(data, indent=indent, default=str)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def murphy_patch(patch_id, file_path, new_content, backup=True, description=""):
    """
    Safe self-modification: write a new version of a Murphy source file.
    Safety chain:
      1. Path must be inside approved roots
      2. Backs up original before writing
      3. Validates Python syntax before replacing .py files
      4. Returns {ok, backup_path, bytes_written}
    Label: PATCH-062e
    """
    ok, reason = _write_path_is_safe(file_path)
    if not ok:
        return {"ok": False, "error": f"murphy_patch safety: {reason}"}

    p = Path(file_path)
    backup_path = None

    if backup and p.exists():
        ts = int(time.time())
        backup_path = str(p) + f".bak.{ts}"
        try:
            import shutil
            shutil.copy2(str(p), backup_path)
        except Exception as exc:
            return {"ok": False, "error": f"Backup failed: {exc}"}

    if file_path.endswith(".py"):
        try:
            compile(new_content, file_path, "exec")
        except SyntaxError as exc:
            return {
                "ok": False,
                "error": f"SyntaxError — file NOT written: {exc}",
                "backup_path": backup_path,
            }

    result = file_write(file_path, new_content, overwrite=True)
    if not result["ok"]:
        return result

    logger.info("murphy_patch [%s] applied to %s (%s)", patch_id, file_path, description)
    return {
        "ok": True,
        "patch_id": patch_id,
        "file": file_path,
        "backup_path": backup_path,
        "bytes_written": result["bytes_written"],
        "description": description,
    }


# ---------------------------------------------------------------------------
# Registry wiring
# ---------------------------------------------------------------------------

_TOOLS_REGISTERED = False
_REGISTRY_SINGLETON = None


def _get_registry():
    global _REGISTRY_SINGLETON
    if _REGISTRY_SINGLETON is None:
        from src.tool_registry.registry import UniversalToolRegistry
        _REGISTRY_SINGLETON = UniversalToolRegistry()
    return _REGISTRY_SINGLETON


def register_all_tools():
    """Register all 11 tools. Idempotent."""
    global _TOOLS_REGISTERED
    if _TOOLS_REGISTERED:
        return
    try:
        from src.tool_registry.models import (
            ToolDefinition, ToolInputSchema, ToolOutputSchema,
            CostEstimate, CostTier, PermissionLevel,
        )
        registry = _get_registry()

        _tool_defs = [
            ("net.http_get",      "HTTP GET",         "Perform an HTTP GET request.", http_get,      PermissionLevel.LOW,          CostTier.FREE,  ["network","http","api"],          "network", False),
            ("net.http_post",     "HTTP POST",        "HTTP POST with JSON payload.", http_post,     PermissionLevel.MEDIUM,       CostTier.FREE,  ["network","http","api"],          "network", False),
            ("fs.file_read",      "File Read",        "Read a file.",                 file_read,     PermissionLevel.LOW,          CostTier.FREE,  ["file","read"],                   "files",   False),
            ("fs.file_write",     "File Write",       "Write a file (safe roots).",   file_write,    PermissionLevel.HIGH,         CostTier.FREE,  ["file","write"],                  "files",   True),
            ("fs.file_append",    "File Append",      "Append to a file.",            file_append,   PermissionLevel.MEDIUM,       CostTier.FREE,  ["file","append"],                 "files",   False),
            ("sys.shell_exec",    "Shell Execute",    "Run a sandboxed shell cmd.",   shell_exec,    PermissionLevel.CRITICAL,     CostTier.FREE,  ["system","shell"],                "system",  True),
            ("sys.env_read",      "Env Read",         "Read env vars (no secrets).",  env_read,      PermissionLevel.LOW,          CostTier.FREE,  ["system","env"],                  "system",  False),
            ("web.fetch",         "Web Fetch",        "Fetch URL as plain text.",     web_fetch,     PermissionLevel.LOW,          CostTier.FREE,  ["web","scrape","fetch"],          "web",     False),
            ("data.json_parse",   "JSON Parse",       "Parse JSON string.",           json_parse,    PermissionLevel.UNRESTRICTED, CostTier.FREE,  ["data","json"],                   "data",    False),
            ("data.json_format",  "JSON Format",      "Format object as JSON.",       json_format,   PermissionLevel.UNRESTRICTED, CostTier.FREE,  ["data","json"],                   "data",    False),
            ("self.murphy_patch", "Murphy Self-Patch","Safe source file patch+backup.",murphy_patch, PermissionLevel.CRITICAL,     CostTier.FREE,  ["self","patch","code","modify"], "self",    True),
        ]

        for tool_id, name, desc, fn, perm, cost_tier, tags, category, req_approval in _tool_defs:
            defn = ToolDefinition(
                tool_id=tool_id, name=name, description=desc,
                permission_level=perm,
                cost_estimate=CostEstimate(tier=cost_tier),
                input_schema=ToolInputSchema(),
                output_schema=ToolOutputSchema(),
                provider="aionmind.tool_executor",
                tags=tags, category=category,
                requires_approval=req_approval,
                metadata={"_callable": fn},
            )
            registry.register(defn)

        _TOOLS_REGISTERED = True
        logger.info("PATCH-062: Registered %d tools into UniversalToolRegistry", len(_tool_defs))
    except Exception as exc:
        logger.warning("PATCH-062: Tool registration failed: %s", exc)


def dispatch_tool(tool_id, **kwargs):
    """
    Dispatch a registered tool by ID.
    Label: TOOL-EXEC-002
    """
    try:
        registry = _get_registry()
        defn = registry.get(tool_id)
        fn = defn.metadata.get("_callable")
        if fn is None:
            return {"ok": False, "error": f"No callable for {tool_id}"}
        start = time.monotonic()
        result = fn(**kwargs)
        elapsed_ms = (time.monotonic() - start) * 1000
        if isinstance(result, dict):
            result["_tool_id"] = tool_id
            result["_elapsed_ms"] = round(elapsed_ms, 2)
        return result
    except KeyError:
        return {"ok": False, "error": f"Tool not found: {tool_id}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


register_all_tools()
