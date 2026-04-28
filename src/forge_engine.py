"""
ForgeEngine — PATCH-133
Live on-the-fly code creation: functions, modules, internal APIs, external API wrappers.

Flow:
  NL description → LLM codegen → MurphyCritic gate → AST safety check →
  write to src/user_modules/<tenant>/<name>.py → hot-import →
  (for APIs) build APIRouter → app.include_router() live →
  register in forge.db → return callable handle
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import json
import logging
import os
import re
import sqlite3
import sys
import textwrap
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("forge_engine")

# ── Paths ──────────────────────────────────────────────────────────────────────
_DB_PATH    = Path("/var/lib/murphy-production/forge.db")
_MOD_ROOT   = Path("/var/lib/murphy-production/user_modules")
_MOD_ROOT.mkdir(parents=True, exist_ok=True)
(_MOD_ROOT / "__init__.py").touch(exist_ok=True)

# ── Safety: blocked patterns ───────────────────────────────────────────────────
_BLOCKED_CALLS = {
    "os.system", "subprocess.run", "subprocess.Popen", "subprocess.call",
    "subprocess.check_output", "eval", "exec", "__import__",
    "compile", "globals", "locals", "vars",
}
_BLOCKED_IMPORTS = {
    "subprocess", "ctypes", "cffi", "signal",
    "multiprocessing", "socket", "pty",
}
_BLOCKED_OPEN_PATHS = {"/etc/", "/root/", "/proc/", "/sys/"}

# ── DB ─────────────────────────────────────────────────────────────────────────
_db_lock = threading.Lock()

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def _init_db() -> None:
    with _db_lock, _get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS forge_items (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                item_type   TEXT NOT NULL,
                description TEXT,
                source_code TEXT,
                file_path   TEXT,
                route       TEXT,
                status      TEXT DEFAULT 'active',
                tenant_id   TEXT DEFAULT 'default',
                critic_verdict TEXT,
                test_result TEXT,
                created_at  TEXT,
                updated_at  TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_forge_tenant ON forge_items(tenant_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_forge_name   ON forge_items(name, tenant_id)")
        conn.commit()

# ── Codegen prompts per type ───────────────────────────────────────────────────
_PROMPTS = {
    "function": """\
Write a single Python function. Requirements:
- Name: {name}
- Purpose: {description}
- Must return a JSON-serializable result (dict, list, str, int, float, bool, or None)
- Add Google-style docstring
- Include type hints
- Handle errors with try/except, return {{"error": str(e)}} on failure
- No global state mutation
- No file I/O unless explicitly asked
- Start with: def {name}(

Return ONLY the Python source code. No markdown fences. No explanation.
""",

    "module": """\
Write a complete Python module. Requirements:
- Module name: {name}
- Purpose: {description}
- Include a main class named {class_name} with relevant methods
- Add __all__ listing all public names
- Google-style docstrings on all public methods
- Type hints throughout
- Methods must return JSON-serializable results
- Handle errors gracefully

Return ONLY the Python source code. No markdown fences. No explanation.
""",

    "internal_api": """\
Write a FastAPI APIRouter for internal Murphy System use. Requirements:
- Router prefix: /api/user/{tenant}/{name}
- Purpose: {description}
- Import: from fastapi import APIRouter, Request, HTTPException
- Use: router = APIRouter()
- All route handlers are async def
- Return dicts (FastAPI auto-serialises)
- Add request: Request param to all handlers for auth context
- No auth logic (middleware handles it)
- Error responses: raise HTTPException(status_code=..., detail=...)
- Variable name must be exactly: router

Return ONLY the Python source code. No markdown fences. No explanation.
""",

    "external_api": """\
Write a Python class that wraps an external API. Requirements:
- Class name: {class_name}
- API service: {service}
- Purpose: {description}
- Use httpx for HTTP requests (sync, not async)
- __init__(self, api_key: str = None) — read from env if not provided
- All methods return dicts
- Handle HTTP errors, timeouts (timeout=15)
- Add a health_check() method that returns {{"status": "ok"}} or {{"status": "error", "detail": str}}
- No hardcoded secrets

Return ONLY the Python source code. No markdown fences. No explanation.
""",
}

# ── Safety checker ─────────────────────────────────────────────────────────────
def _safety_check(source: str) -> Tuple[bool, str]:
    """Parse AST and check for dangerous patterns. Returns (safe, reason)."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"

    for node in ast.walk(tree):
        # Blocked imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""]
            for name in names:
                base = name.split(".")[0]
                if base in _BLOCKED_IMPORTS:
                    return False, f"Blocked import: {name}"

        # Blocked function calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                call_str = f"{getattr(node.func.value, 'id', '')}. {node.func.attr}".replace(" ", "")
                if call_str in _BLOCKED_CALLS:
                    return False, f"Blocked call: {call_str}"
            elif isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec", "compile", "__import__"}:
                    return False, f"Blocked builtin: {node.func.id}"

        # Blocked open() with sensitive paths
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        for blocked in _BLOCKED_OPEN_PATHS:
                            if arg.value.startswith(blocked):
                                return False, f"Blocked file path: {arg.value}"

    return True, "ok"

# ── Module hot-loader ──────────────────────────────────────────────────────────
def _write_and_import(name: str, source: str, tenant_id: str) -> Tuple[Any, str]:
    """Write source to disk and hot-import it. Returns (module, file_path)."""
    tenant_dir = _MOD_ROOT / _safe_name(tenant_id)
    tenant_dir.mkdir(exist_ok=True)
    (tenant_dir / "__init__.py").touch(exist_ok=True)

    file_path = tenant_dir / f"{_safe_name(name)}.py"
    file_path.write_text(source, encoding="utf-8")

    mod_name = f"src.user_modules.{_safe_name(tenant_id)}.{_safe_name(name)}"
    # Remove stale cached version
    sys.modules.pop(mod_name, None)

    spec = importlib.util.spec_from_file_location(mod_name, str(file_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)

    return module, str(file_path)

def _safe_name(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", s).lower()[:64]

# ── LLM codegen ───────────────────────────────────────────────────────────────
def _llm_generate(prompt: str, max_tokens: int = 2048) -> str:
    try:
        from src.llm_provider import get_llm
        llm = get_llm()
        completion = llm.complete(prompt, max_tokens=max_tokens, temperature=0.1)
        # LLMCompletion object — extract text
        if hasattr(completion, "content"):
            code = completion.content or ""
        elif hasattr(completion, "text"):
            code = completion.text or ""
        else:
            code = str(completion)
        code = code.strip()
        # Strip markdown fences if the LLM ignored instructions
        code = re.sub(r"^```(?:python)?\n?", "", code)
        code = re.sub(r"\n?```$", "", code)
        return code.strip()
    except Exception as e:
        logger.error("LLM codegen failed: %s", e)
        raise RuntimeError(f"LLM unavailable: {e}") from e

# ── Router registry for dynamic API mounting ──────────────────────────────────
_mounted_routers: Dict[str, Any] = {}   # name → router
_app_ref: Any = None                    # set by register_with_app()

def register_with_app(app: Any) -> None:
    global _app_ref
    _app_ref = app
    logger.info("ForgeEngine: app reference registered, dynamic routing enabled")

def _mount_router(name: str, tenant_id: str, router: Any) -> str:
    """Mount a new APIRouter on the live app."""
    if _app_ref is None:
        raise RuntimeError("ForgeEngine not registered with app — call register_with_app(app)")
    route_key = f"forge_{_safe_name(tenant_id)}_{_safe_name(name)}"
    _mounted_routers[route_key] = router
    _app_ref.include_router(router)
    logger.info("ForgeEngine: dynamic router mounted — %s", route_key)
    return route_key

# ── Main ForgeEngine ──────────────────────────────────────────────────────────
class ForgeEngine:
    """
    PATCH-133: On-the-fly code creation engine.
    Creates functions, modules, internal APIs, and external API wrappers
    from natural language descriptions.
    """

    def __init__(self):
        _init_db()

    # ── Public API ────────────────────────────────────────────────────────────

    def create(
        self,
        description: str,
        item_type: str = "function",
        name: Optional[str] = None,
        tenant_id: str = "default",
        service: Optional[str] = None,   # for external_api
        extra_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new function, module, internal API, or external API wrapper.

        Args:
            description: Natural language description of what to build
            item_type:   'function' | 'module' | 'internal_api' | 'external_api'
            name:        Optional name (auto-derived from description if omitted)
            tenant_id:   Tenant scope
            service:     External service name (only for external_api, e.g. 'stripe')
            extra_context: Additional context appended to the prompt

        Returns:
            forge_item dict with id, name, status, source_code, file_path, route
        """
        if item_type not in _PROMPTS:
            return {"error": f"Unknown item_type: {item_type}. Use: function, module, internal_api, external_api"}

        # 1. Derive name
        if not name:
            name = self._derive_name(description, item_type)
        name = _safe_name(name)
        class_name = "".join(p.capitalize() for p in name.split("_"))

        # 2. Build prompt
        svc = service or (description.split()[0] if item_type == "external_api" else "external")
        prompt = _PROMPTS[item_type].format(
            name=name,
            description=description + (f"\n\nAdditional context:\n{extra_context}" if extra_context else ""),
            class_name=class_name,
            tenant=_safe_name(tenant_id),
            service=svc,
        )

        # 3. LLM codegen
        try:
            source = _llm_generate(prompt, max_tokens=3000)
        except RuntimeError as e:
            return {"error": str(e), "status": "failed", "step": "codegen"}

        # 4. Safety gate
        safe, reason = _safety_check(source)
        if not safe:
            return {"error": f"Safety gate BLOCKED: {reason}", "status": "blocked",
                    "step": "safety", "source_code": source}

        # 5. MurphyCritic gate
        critic_verdict = "unknown"
        try:
            from src.murphy_critic import MurphyCritic
            critic = MurphyCritic()
            result = critic.review(source, filename=f"{name}.py")
            critic_verdict = result.get("verdict", "unknown")
            if critic_verdict == "BLOCK":
                return {"error": f"MurphyCritic BLOCKED: {result.get('summary', 'unsafe code')}",
                        "status": "blocked", "step": "critic",
                        "critic_result": result, "source_code": source}
        except Exception as ce:
            logger.warning("MurphyCritic unavailable — skipping: %s", ce)
            critic_verdict = "skipped"

        # 6. Write to disk + hot-import
        try:
            module, file_path = _write_and_import(name, source, tenant_id)
        except Exception as e:
            return {"error": f"Import failed: {e}", "status": "failed",
                    "step": "import", "source_code": source}

        # 7. For internal APIs: mount the router live
        route = None
        if item_type == "internal_api":
            try:
                router = getattr(module, "router", None)
                if router is None:
                    return {"error": "internal_api code must define a variable named 'router' (APIRouter)",
                            "status": "failed", "step": "mount", "source_code": source}
                route = f"/api/user/{_safe_name(tenant_id)}/{name}"
                _mount_router(name, tenant_id, router)
            except Exception as e:
                return {"error": f"Router mount failed: {e}", "status": "failed",
                        "step": "mount", "source_code": source}

        # 8. Quick smoke test
        test_result = self._smoke_test(module, item_type, name, class_name)

        # 9. Persist to DB
        item_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with _db_lock, _get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO forge_items
                  (id, name, item_type, description, source_code, file_path,
                   route, status, tenant_id, critic_verdict, test_result, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (item_id, name, item_type, description, source, file_path,
                  route, "active", tenant_id, critic_verdict,
                  json.dumps(test_result), now, now))
            conn.commit()

        logger.info("ForgeEngine: created %s '%s' for tenant %s", item_type, name, tenant_id)
        return {
            "id": item_id,
            "name": name,
            "item_type": item_type,
            "description": description,
            "source_code": source,
            "file_path": file_path,
            "route": route,
            "status": "active",
            "critic_verdict": critic_verdict,
            "test_result": test_result,
            "created_at": now,
        }

    def invoke(self, name: str, args: Dict[str, Any], tenant_id: str = "default") -> Dict[str, Any]:
        """
        Invoke a forged function or module method by name.
        For modules, pass method="method_name" in args.
        """
        item = self._get_by_name(name, tenant_id)
        if not item:
            return {"error": f"No forge item named '{name}' for tenant {tenant_id}"}

        item_type = item["item_type"]
        file_path = item["file_path"]

        # Hot-reload in case file changed
        try:
            mod_name = f"src.user_modules.{_safe_name(tenant_id)}.{_safe_name(name)}"
            spec = importlib.util.spec_from_file_location(mod_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
        except Exception as e:
            return {"error": f"Hot-reload failed: {e}"}

        try:
            if item_type == "function":
                fn = getattr(module, name, None)
                if fn is None:
                    # Try any callable at module level
                    fns = [v for k, v in inspect.getmembers(module, inspect.isfunction)
                           if not k.startswith("_")]
                    if not fns:
                        return {"error": f"No callable found in module '{name}'"}
                    fn = fns[0]
                result = fn(**args)
                return {"result": result, "status": "ok"}

            elif item_type == "module":
                class_name = "".join(p.capitalize() for p in name.split("_"))
                cls = getattr(module, class_name, None)
                if cls is None:
                    # Find any class
                    classes = [v for k, v in inspect.getmembers(module, inspect.isclass)
                               if not k.startswith("_")]
                    if not classes:
                        return {"error": "No class found in module"}
                    cls = classes[0]
                method = args.pop("method", None)
                init_args = args.pop("init_args", {})
                instance = cls(**init_args)
                if method:
                    fn = getattr(instance, method, None)
                    if fn is None:
                        return {"error": f"Method '{method}' not found on {cls.__name__}"}
                    result = fn(**args)
                else:
                    # List available methods
                    methods = [m for m in dir(instance)
                               if not m.startswith("_") and callable(getattr(instance, m))]
                    return {"status": "module_loaded", "class": cls.__name__,
                            "available_methods": methods,
                            "usage": "Pass method='method_name' in args to call a specific method"}
                return {"result": result, "status": "ok"}

            elif item_type == "external_api":
                class_name = "".join(p.capitalize() for p in name.split("_"))
                cls = getattr(module, class_name, None)
                if cls is None:
                    classes = [v for k, v in inspect.getmembers(module, inspect.isclass)
                               if not k.startswith("_")]
                    if not classes:
                        return {"error": "No API class found"}
                    cls = classes[0]
                api_key = args.pop("api_key", None)
                method  = args.pop("method", "health_check")
                instance = cls(api_key=api_key) if api_key else cls()
                fn = getattr(instance, method, None)
                if fn is None:
                    methods = [m for m in dir(instance)
                               if not m.startswith("_") and callable(getattr(instance, m))]
                    return {"error": f"Method '{method}' not found",
                            "available_methods": methods}
                result = fn(**args)
                return {"result": result, "status": "ok"}

            elif item_type == "internal_api":
                return {"status": "mounted", "route": item["route"],
                        "message": f"API is live at {item['route']} — call it via HTTP"}

        except Exception as e:
            return {"error": str(e), "status": "invocation_error"}

    def edit(self, name: str, edit_description: str, tenant_id: str = "default") -> Dict[str, Any]:
        """Surgically edit an existing forge item using NL description."""
        item = self._get_by_name(name, tenant_id)
        if not item:
            return {"error": f"No forge item named '{name}' for tenant {tenant_id}"}

        source = item["source_code"]
        prompt = f"""\
You have an existing Python source file. Apply the following change to it.

EXISTING CODE:
```python
{source}
```

CHANGE REQUEST: {edit_description}

Return ONLY the complete updated Python source code. No markdown fences. No explanation.
Make minimal, surgical changes. Preserve all existing functionality not mentioned in the change request.
"""
        try:
            new_source = _llm_generate(prompt, max_tokens=3000)
        except RuntimeError as e:
            return {"error": str(e), "step": "codegen"}

        safe, reason = _safety_check(new_source)
        if not safe:
            return {"error": f"Safety BLOCKED: {reason}", "source_code": new_source}

        try:
            module, file_path = _write_and_import(name, new_source, tenant_id)
        except Exception as e:
            return {"error": f"Import failed: {e}", "source_code": new_source}

        test_result = self._smoke_test(module, item["item_type"], name,
                                       "".join(p.capitalize() for p in name.split("_")))
        now = datetime.utcnow().isoformat()
        with _db_lock, _get_db() as conn:
            conn.execute("""
                UPDATE forge_items
                SET source_code=?, test_result=?, updated_at=?
                WHERE name=? AND tenant_id=?
            """, (new_source, json.dumps(test_result), now, name, tenant_id))
            conn.commit()

        return {"name": name, "status": "updated", "source_code": new_source,
                "test_result": test_result, "updated_at": now}

    def list_items(self, tenant_id: str = "default", item_type: Optional[str] = None) -> List[Dict]:
        """List all forged items for a tenant."""
        with _db_lock, _get_db() as conn:
            if item_type:
                rows = conn.execute(
                    "SELECT id,name,item_type,description,route,status,critic_verdict,created_at "
                    "FROM forge_items WHERE tenant_id=? AND item_type=? AND status='active' ORDER BY created_at DESC",
                    (tenant_id, item_type)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id,name,item_type,description,route,status,critic_verdict,created_at "
                    "FROM forge_items WHERE tenant_id=? AND status='active' ORDER BY created_at DESC",
                    (tenant_id,)
                ).fetchall()
        return [dict(r) for r in rows]

    def get_item(self, item_id: str, tenant_id: str = "default") -> Optional[Dict]:
        """Get a forge item by ID (includes source code)."""
        with _db_lock, _get_db() as conn:
            row = conn.execute(
                "SELECT * FROM forge_items WHERE id=? AND tenant_id=?",
                (item_id, tenant_id)
            ).fetchone()
        return dict(row) if row else None

    def delete_item(self, item_id: str, tenant_id: str = "default") -> Dict:
        """Soft-delete a forge item."""
        with _db_lock, _get_db() as conn:
            conn.execute(
                "UPDATE forge_items SET status='deleted', updated_at=? WHERE id=? AND tenant_id=?",
                (datetime.utcnow().isoformat(), item_id, tenant_id)
            )
            conn.commit()
        return {"status": "deleted", "id": item_id}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _derive_name(self, description: str, item_type: str) -> str:
        """Derive a snake_case name from the description."""
        # Take first ~5 meaningful words
        words = re.sub(r"[^a-zA-Z0-9\s]", " ", description).lower().split()
        stop = {"a", "an", "the", "that", "which", "for", "to", "of", "in",
                "and", "or", "with", "build", "create", "make", "write", "generate"}
        name_words = [w for w in words if w not in stop][:4]
        prefix = {"function": "fn", "module": "mod", "internal_api": "api", "external_api": "ext"}
        return prefix.get(item_type, "forge") + "_" + "_".join(name_words) if name_words else \
               prefix.get(item_type, "forge") + "_" + str(int(time.time()))[-6:]

    def _get_by_name(self, name: str, tenant_id: str) -> Optional[Dict]:
        with _db_lock, _get_db() as conn:
            row = conn.execute(
                "SELECT * FROM forge_items WHERE name=? AND tenant_id=? AND status='active'",
                (name, tenant_id)
            ).fetchone()
        return dict(row) if row else None

    def _smoke_test(self, module: Any, item_type: str, name: str, class_name: str) -> Dict:
        """Quick smoke test: can we at least import and find the expected symbol?"""
        if item_type == "function":
            fn = getattr(module, name, None)
            if fn is None:
                fns = [k for k, v in inspect.getmembers(module, inspect.isfunction)
                       if not k.startswith("_")]
                return {"passed": len(fns) > 0,
                        "found": fns[0] if fns else None,
                        "note": f"Expected '{name}' but found {fns}"}
            sig = str(inspect.signature(fn))
            return {"passed": True, "function": name, "signature": sig}

        elif item_type in ("module", "external_api"):
            cls = getattr(module, class_name, None)
            if cls is None:
                classes = [k for k, v in inspect.getmembers(module, inspect.isclass)
                           if not k.startswith("_")]
                return {"passed": len(classes) > 0, "found_classes": classes}
            methods = [m for m in dir(cls) if not m.startswith("_") and callable(getattr(cls, m))]
            return {"passed": True, "class": class_name, "methods": methods}

        elif item_type == "internal_api":
            router = getattr(module, "router", None)
            if router is None:
                return {"passed": False, "error": "No 'router' variable found"}
            routes = [f"{m} {r.path}" for r in getattr(router, "routes", [])
                      for m in getattr(r, "methods", ["GET"])]
            return {"passed": True, "routes": routes}

        return {"passed": True, "note": "No smoke test for this type"}


# ── Module-level singleton ─────────────────────────────────────────────────────
_forge: Optional[ForgeEngine] = None
_forge_lock = threading.Lock()

def get_forge() -> ForgeEngine:
    global _forge
    if _forge is None:
        with _forge_lock:
            if _forge is None:
                _forge = ForgeEngine()
    return _forge
