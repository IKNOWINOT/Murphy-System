# Copyright © 2020 Inoni LLC | License: BSL 1.1
"""Murphy Self-Manifest — PATCH-066 | Label: SELF-MANIFEST-001

Provides Murphy with a live structured self-model:
- Module registry (every .py, classes, functions, imports, LLM call sites)
- Patch lineage (git log → PATCH history)
- Test coverage map
- Health snapshot
- Dependency graph

Exposed at:
  GET  /api/self/manifest   (founder/admin only, cached 120s)
  GET  /api/self/health     (fast summary, public)
  GET  /api/self/patch-log  (PATCH history)
"""
from __future__ import annotations
import ast, json, logging, os, re, subprocess, threading, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SRC_ROOT = Path("/opt/Murphy-System/src")
_PROJECT_ROOT = Path("/opt/Murphy-System")
_MANIFEST_LOCK = threading.Lock()
_MANIFEST_CACHE: Optional[Dict] = None
_MANIFEST_TTL = 120
_MANIFEST_BUILT_AT: float = 0.0


def _scan_module(path: Path) -> Dict:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return {"file": str(path.relative_to(_PROJECT_ROOT)), "parse_error": str(e),
                    "classes": [], "functions": [], "imports": [], "loc": 0, "llm_calls": []}
        classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        imports = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imports += [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module:
                imports.append(n.module)
        llm_patterns = ["MurphyLLMProvider", "llm.complete", "openai", "together",
                        "deepinfra", "ollama", "Ollama", "ChatCompletion", "llm_provider"]
        llm_calls = [p for p in llm_patterns if p in source]
        loc = sum(1 for l in source.splitlines() if l.strip() and not l.strip().startswith("#"))
        docstring = ""
        if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
            docstring = str(tree.body[0].value.value)[:200]
        return {"file": str(path.relative_to(_PROJECT_ROOT)), "classes": classes[:30],
                "functions": functions[:50], "imports": list(set(imports))[:40],
                "loc": loc, "llm_calls": list(set(llm_calls)),
                "docstring_preview": docstring, "size_bytes": path.stat().st_size,
                "last_modified": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()}
    except Exception as exc:
        return {"file": str(path), "error": str(exc)}


def _build_module_registry() -> List[Dict]:
    modules = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        modules.append(_scan_module(path))
    return modules


def _get_patch_lineage(limit: int = 30) -> List[Dict]:
    try:
        result = subprocess.run(
            ["git", "-C", str(_PROJECT_ROOT), "log",
             f"-{limit}", "--pretty=format:%H|%ai|%s"],
            capture_output=True, text=True, timeout=15)
        entries = []
        for line in result.stdout.splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3:
                sha, date, msg = parts
                pm = re.search(r"PATCH[-\s](\d+)", msg, re.IGNORECASE)
                entries.append({"sha": sha[:10], "date": date, "message": msg,
                                "patch_id": pm.group(0) if pm else None})
        return entries
    except Exception as exc:
        logger.warning("SELF-MANIFEST: patch lineage failed: %s", exc)
        return []


def _scan_test_coverage() -> Dict:
    test_dir = _PROJECT_ROOT / "tests"
    coverage = {}
    if not test_dir.exists():
        return coverage
    for tf in sorted(test_dir.rglob("test_*.py")):
        try:
            src = tf.read_text(errors="replace")
            imports = re.findall(r"from src\.(\S+) import|import src\.(\S+)", src)
            flat = [x for pair in imports for x in pair if x]
            coverage[str(tf.relative_to(_PROJECT_ROOT))] = {
                "covers": flat[:20], "test_count": src.count("def test_"),
                "last_modified": datetime.fromtimestamp(tf.stat().st_mtime, tz=timezone.utc).isoformat()}
        except Exception:
            pass
    return coverage


def _build_health_snapshot() -> Dict:
    health = {}
    try:
        import urllib.request as _ur2
        with _ur2.urlopen("http://127.0.0.1:8000/api/health", timeout=5) as _hr:
            health["api_http_status"] = _hr.status
    except Exception:
        health["api_http_status"] = 0
    try:
        r = subprocess.run(["systemctl", "is-active", "murphy-production"],
                           capture_output=True, text=True, timeout=5)
        health["service_active"] = r.stdout.strip() == "active"
    except Exception:
        health["service_active"] = False
    try:
        r = subprocess.run(["git", "-C", str(_PROJECT_ROOT), "log", "-1", "--oneline"],
                           capture_output=True, text=True, timeout=5)
        health["git_head"] = r.stdout.strip()
    except Exception:
        health["git_head"] = "unknown"
    health["src_file_count"] = sum(1 for _ in _SRC_ROOT.rglob("*.py")
                                   if "__pycache__" not in str(_))
    health["snapshot_ts"] = datetime.now(timezone.utc).isoformat()
    return health


def build_manifest(force: bool = False) -> Dict:
    global _MANIFEST_CACHE, _MANIFEST_BUILT_AT
    with _MANIFEST_LOCK:
        now = time.time()
        if not force and _MANIFEST_CACHE and (now - _MANIFEST_BUILT_AT) < _MANIFEST_TTL:
            return _MANIFEST_CACHE
        logger.info("SELF-MANIFEST-001: Building manifest...")
        t0 = time.time()
        modules = _build_module_registry()
        manifest = {
            "label": "SELF-MANIFEST-001", "patch": "PATCH-066",
            "built_at": datetime.now(timezone.utc).isoformat(),
            "health": _build_health_snapshot(),
            "patch_lineage": _get_patch_lineage(30),
            "module_count": len(modules),
            "module_registry": modules,
            "llm_call_map": [{"file": m["file"], "llm_patterns": m.get("llm_calls", [])}
                             for m in modules if m.get("llm_calls")],
            "test_coverage": _scan_test_coverage(),
            "build_time_s": None,
        }
        manifest["build_time_s"] = round(time.time() - t0, 2)
        logger.info("SELF-MANIFEST-001: Built in %.1fs — %d modules", manifest["build_time_s"], len(modules))
        _MANIFEST_CACHE = manifest
        _MANIFEST_BUILT_AT = now
        return manifest


def get_health_summary() -> Dict:
    health = _build_health_snapshot()
    return {"label": "SELF-MANIFEST-001/health", "health": health,
            "recent_patches": _get_patch_lineage(5),
            "manifest_cached": _MANIFEST_CACHE is not None,
            "cache_age_s": round(time.time() - _MANIFEST_BUILT_AT, 0) if _MANIFEST_CACHE else None}


def get_patch_log(limit: int = 50) -> List[Dict]:
    return _get_patch_lineage(limit)
