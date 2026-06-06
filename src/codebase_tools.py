"""
codebase_tools.py — Read-only Murphy self-inspection helpers
============================================================

WHAT THIS IS:
  Three safe, read-only tools the executor agent can call to inspect
  Murphy's own source tree before answering briefs:
    - grep_codebase(pattern, file_glob)    → list of (path, lineno, line)
    - read_source(relative_path, max_bytes)→ file content (truncated)
    - list_dir(relative_path)              → file/dir listing

WHY IT EXISTS:
  Without these, the executor agent answers from generic LLM knowledge.
  With these, the LLM can ground its answers in Murphy's actual source.
  Reduces hallucinations (e.g. Murphy named non-existent access_control.py).

CONSTRAINTS (security):
  - All paths MUST resolve under MURPHY_SRC (/opt/Murphy-System).
  - Symlink escapes are blocked via resolve() + relative_to() check.
  - No write operations. Ever.
  - Max bytes returned per call is bounded so a runaway tool call cannot
    overflow the LLM context window or memory.

LAST UPDATED: 2026-05-26 founder + Murphy (gap #1 unlock)
"""
from __future__ import annotations
import re
import os
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger("murphy.codebase_tools")

# ── Path-recognition helpers (added 2026-05-26) ───────────────────────────
import difflib as _difflib

def _suggest_paths(wanted: str, limit: int = 5):
    """Fuzzy-match a wrong path against the real codebase tree.
    Returns up to `limit` plausible real paths, ordered by similarity."""
    try:
        wanted_base = wanted.split("/")[-1].lower()
        wanted_stem = wanted_base.rsplit(".",1)[0]
        wanted_full = wanted.lower()
        all_files = []
        for root, _dirs, files in __import__("os").walk(str(MURPHY_SRC)):
            # skip __pycache__, archives, backups
            if any(skip in root for skip in ("__pycache__", "/_archive", "/backups", "/venv", "/node_modules", "/.git", "/static/vendor", "incoming_files")):
                continue
            for f in files:
                if not f.endswith((".py", ".html", ".json", ".md", ".sh", ".sql", ".txt")):
                    continue
                if f.endswith(".bak") or ".bak" in f or ".pre-" in f or ".pre_" in f:
                    continue
                full = __import__("os").path.join(root, f)
                try:
                    rel = full[len(str(MURPHY_SRC))+1:]
                except Exception:
                    rel = full
                all_files.append(rel)

        # Score 1: exact basename match (strongest)
        exact = [p for p in all_files if p.split("/")[-1].lower() == wanted_base]
        # Score 2: stem match (file.py → file_anything.py)
        stem = [p for p in all_files if wanted_stem and wanted_stem in p.split("/")[-1].lower() and p not in exact]
        # Score 3: full-path fuzzy
        all_lower = [p.lower() for p in all_files]
        fuzzy_idx = _difflib.get_close_matches(wanted_full, all_lower, n=limit*2, cutoff=0.55)
        fuzzy = [all_files[all_lower.index(m)] for m in fuzzy_idx if all_files[all_lower.index(m)] not in exact and all_files[all_lower.index(m)] not in stem]

        suggestions = (exact + stem + fuzzy)[:limit]
        return suggestions
    except Exception as _e:
        logger.debug("suggest_paths failed: %s", _e)
        return []


def find_file(name_pattern: str, max_results: int = 20):
    """Locate files by basename glob or substring.
    Use when you don't know the exact path.

    Args:
        name_pattern: glob like '*scheduler*.py' or 'voice_bridge.py' or substring 'scheduler'
        max_results: cap

    Returns: {"matches": [str, ...], "total": int, "truncated": bool}
    """
    import fnmatch
    pat = name_pattern.lower()
    has_glob = any(c in pat for c in "*?[")
    matches = []
    for root, _dirs, files in __import__("os").walk(str(MURPHY_SRC)):
        if any(skip in root for skip in ("__pycache__", "/_archive", "/backups", "/venv", "/node_modules", "/.git", "/static/vendor", "incoming_files")):
            continue
        for f in files:
            if f.endswith(".bak") or ".bak" in f or ".pre-" in f or ".pre_" in f:
                continue
            f_lower = f.lower()
            if has_glob:
                if not fnmatch.fnmatch(f_lower, pat):
                    continue
            else:
                if pat not in f_lower:
                    continue
            full = __import__("os").path.join(root, f)
            try:
                rel = full[len(str(MURPHY_SRC))+1:]
            except Exception:
                rel = full
            matches.append(rel)
    matches.sort(key=lambda x: (x.count("/"), len(x), x))  # shorter, shallower first
    truncated = len(matches) > max_results
    return {"matches": matches[:max_results], "total": len(matches), "truncated": truncated}


def path_exists(relative_path: str) -> dict:
    """Cheap check — does this path exist? Returns {'exists': bool, 'is_file': bool, 'is_dir': bool, 'suggestions': [...]}"""
    try:
        full = _safe_resolve(relative_path)
    except PermissionError as exc:
        return {"exists": False, "error": str(exc), "suggestions": []}
    if full.exists():
        return {"exists": True, "is_file": full.is_file(), "is_dir": full.is_dir(), "suggestions": []}
    return {"exists": False, "is_file": False, "is_dir": False, "suggestions": _suggest_paths(relative_path)}



MURPHY_SRC = Path("/opt/Murphy-System")
MAX_GREP_MATCHES   = 50      # cap matches per call
MAX_FILE_BYTES     = 50_000  # cap file read size
MAX_DIR_ENTRIES    = 200     # cap dir listing


def _safe_resolve(relative_path: str) -> Path:
    """Resolve a path under MURPHY_SRC, refusing escapes."""
    try:
        candidate = (MURPHY_SRC / relative_path).resolve()
        candidate.relative_to(MURPHY_SRC.resolve())  # raises if outside
        return candidate
    except (ValueError, RuntimeError) as exc:
        raise PermissionError(f"path escapes MURPHY_SRC: {relative_path}") from exc


def grep_codebase(pattern: str,
                   file_glob: str = "*.py",
                   subdir: str = "src",
                   max_matches: int = 50) -> Dict[str, Any]:
    """
    Search Murphy's source tree for a regex pattern.

    Args:
        pattern: regex pattern (case-insensitive by default)
        file_glob: file extension/glob to limit (default *.py)
        subdir: relative subdir to search (default 'src')
        max_matches: cap on results returned

    Returns: {"matches": [{"path": str, "line": int, "text": str}], "total": int, "truncated": bool}
    """
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return {"matches": [], "total": 0, "truncated": False, "error": f"bad_regex: {exc}"}

    base = _safe_resolve(subdir)
    if not base.is_dir():
        return {"matches": [], "total": 0, "truncated": False, "error": "subdir_not_found"}

    cap = min(max_matches, MAX_GREP_MATCHES)
    matches: List[Dict[str, Any]] = []
    total = 0
    truncated = False

    try:
        for path in base.rglob(file_glob):
            if "__pycache__" in path.parts or "_archive" in path.parts:
                continue
            if ".bak" in path.name or path.name.endswith(".pyc"):
                continue
            try:
                with path.open(encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, 1):
                        if rx.search(line):
                            total += 1
                            if len(matches) < cap:
                                matches.append({
                                    "path": str(path.relative_to(MURPHY_SRC)),
                                    "line": lineno,
                                    "text": line.rstrip()[:200],
                                })
                            else:
                                truncated = True
            except (OSError, UnicodeDecodeError):
                continue
    except Exception as exc:
        logger.warning("grep_codebase error: %s", exc)
        return {"matches": matches, "total": total, "truncated": truncated, "error": str(exc)}

    return {"matches": matches, "total": total, "truncated": truncated}


def read_source(relative_path: str,
                 max_bytes: int = MAX_FILE_BYTES,
                 line_range: tuple = None) -> Dict[str, Any]:
    """
    Read a Murphy source file (with optional line range).

    Args:
        relative_path: path under /opt/Murphy-System (e.g. 'src/executor_agent.py')
        max_bytes: cap on bytes returned
        line_range: optional (start, end) tuple to return only those lines (1-indexed)

    Returns: {"path": str, "content": str, "lines": int, "bytes": int, "truncated": bool}
    """
    try:
        full = _safe_resolve(relative_path)
    except PermissionError as exc:
        return {"error": str(exc), "content": ""}

    if not full.exists():
        return {"error": "file_not_found", "path": relative_path,
                "content": "", "suggestions": _suggest_paths(relative_path)}
    if not full.is_file():
        return {"error": "not_a_file", "path": relative_path, "content": ""}

    try:
        content = full.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return {"error": f"read_error: {exc}", "content": ""}

    total_lines = content.count("\n") + 1
    if line_range and len(line_range) == 2:
        start, end = line_range
        lines = content.splitlines()
        content = "\n".join(lines[max(0, start-1):end])

    truncated = False
    cap = min(max_bytes, MAX_FILE_BYTES)
    if len(content) > cap:
        content = content[:cap] + f"\n\n... [TRUNCATED — {len(content)-cap} more bytes]"
        truncated = True

    return {
        "path":      str(full.relative_to(MURPHY_SRC)),
        "content":   content,
        "lines":     total_lines,
        "bytes":     len(content),
        "truncated": truncated,
    }


def list_dir(relative_path: str = "src") -> Dict[str, Any]:
    """
    List files and subdirectories of a Murphy source directory.

    Returns: {"path": str, "files": [str], "dirs": [str], "total": int}
    """
    try:
        full = _safe_resolve(relative_path)
    except PermissionError as exc:
        return {"error": str(exc)}

    if not full.is_dir():
        return {"error": "not_a_directory", "path": relative_path}

    files = []
    dirs = []
    try:
        for entry in sorted(full.iterdir()):
            if entry.name.startswith(".") or "__pycache__" in entry.name:
                continue
            if entry.is_dir():
                dirs.append(entry.name + "/")
            else:
                files.append(entry.name)
            if len(files) + len(dirs) >= MAX_DIR_ENTRIES:
                break
    except OSError as exc:
        return {"error": f"list_error: {exc}"}

    return {
        "path":  str(full.relative_to(MURPHY_SRC)),
        "files": files,
        "dirs":  dirs,
        "total": len(files) + len(dirs),
    }


# ── Persistent path index (Phase 2 — 2026-05-26) ───────────────────────────
import sqlite3 as _sqlite3
INDEX_DB = "/var/lib/murphy-production/file_index.db"

def _ensure_index_schema():
    with _sqlite3.connect(INDEX_DB, timeout=4) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS file_index (
            path TEXT PRIMARY KEY,
            basename TEXT NOT NULL,
            dirname TEXT NOT NULL,
            size INTEGER,
            lines INTEGER,
            modified REAL,
            indexed_at REAL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_basename ON file_index(basename)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_dirname  ON file_index(dirname)")

def refresh_path_index() -> dict:
    """Walk the codebase, rebuild file_index. Called every 5 min by APScheduler."""
    import os as _os, time as _time
    _ensure_index_schema()
    SKIP_DIRS = ("__pycache__", "/_archive", "/backups", "/venv", "/node_modules",
                 "/.git", "/static/vendor", "incoming_files")
    rows = []
    now = _time.time()
    for root, _dirs, files in _os.walk(str(MURPHY_SRC)):
        if any(s in root for s in SKIP_DIRS): continue
        for f in files:
            if f.endswith(".bak") or ".bak" in f or ".pre-" in f or ".pre_" in f: continue
            if not f.endswith((".py",".html",".json",".md",".sh",".sql",".txt",".css",".js",".ts",".tsx",".yml",".yaml",".toml",".ini")): continue
            full = _os.path.join(root, f)
            try:
                rel = full[len(str(MURPHY_SRC))+1:]
                st = _os.stat(full)
                # cheap line count for .py only
                lines = 0
                if f.endswith(".py") and st.st_size < 500_000:
                    try:
                        with open(full, "rb") as fh:
                            lines = sum(1 for _ in fh)
                    except: pass
                rows.append((rel, f, _os.path.dirname(rel), st.st_size, lines, st.st_mtime, now))
            except OSError: continue
    with _sqlite3.connect(INDEX_DB, timeout=8) as db:
        db.execute("DELETE FROM file_index")
        db.executemany("INSERT INTO file_index VALUES (?,?,?,?,?,?,?)", rows)
        db.commit()
    return {"indexed": len(rows), "elapsed_ms": int((_time.time()-now)*1000)}


def path_exists_fast(relative_path: str) -> dict:
    """Like path_exists, but uses the SQLite index (microseconds vs ms)."""
    try:
        _ensure_index_schema()
        with _sqlite3.connect(INDEX_DB, timeout=2) as db:
            row = db.execute("SELECT path,size,lines FROM file_index WHERE path=?",
                             (relative_path,)).fetchone()
        if row:
            return {"exists": True, "path": row[0], "size": row[1], "lines": row[2]}
        return {"exists": False, "suggestions": _suggest_paths_fast(relative_path)}
    except _sqlite3.OperationalError:
        # fallback to filesystem
        return path_exists(relative_path)


def _suggest_paths_fast(wanted: str, limit: int = 5) -> list:
    """Index-backed fuzzy match — 100x faster than walking the tree."""
    try:
        import difflib as _dl
        _ensure_index_schema()
        wanted_base = wanted.split("/")[-1].lower()
        wanted_stem = wanted_base.rsplit(".",1)[0]
        with _sqlite3.connect(INDEX_DB, timeout=2) as db:
            # Score 1: exact basename
            exact = [r[0] for r in db.execute(
                "SELECT path FROM file_index WHERE LOWER(basename)=? LIMIT 10",
                (wanted_base,)).fetchall()]
            # Score 2: stem contains
            stem = [r[0] for r in db.execute(
                "SELECT path FROM file_index WHERE LOWER(basename) LIKE ? AND path NOT IN ({}) LIMIT 20".format(
                    ",".join("?"*len(exact)) if exact else "''"),
                [f"%{wanted_stem}%"] + exact).fetchall()] if wanted_stem else []
            # Score 3: fuzzy against all basenames if still nothing
            if len(exact) + len(stem) < limit:
                all_paths = [r[0] for r in db.execute("SELECT path FROM file_index").fetchall()]
                fuzzy = _dl.get_close_matches(wanted.lower(),
                                              [p.lower() for p in all_paths],
                                              n=limit, cutoff=0.55)
                path_map = {p.lower(): p for p in all_paths}
                fuzzy_paths = [path_map[f] for f in fuzzy if path_map[f] not in exact and path_map[f] not in stem]
            else:
                fuzzy_paths = []
        return (exact + stem + fuzzy_paths)[:limit]
    except Exception as _e:
        logger.debug("suggest_paths_fast failed: %s", _e)
        return _suggest_paths(wanted, limit)


def find_file_fast(name_pattern: str, max_results: int = 20) -> dict:
    """Index-backed file finder."""
    try:
        _ensure_index_schema()
        pat = name_pattern.lower()
        sql_pat = pat.replace("*","%").replace("?","_") if any(c in pat for c in "*?") else f"%{pat}%"
        with _sqlite3.connect(INDEX_DB, timeout=2) as db:
            rows = db.execute(
                "SELECT path FROM file_index WHERE LOWER(basename) LIKE ? "
                "ORDER BY LENGTH(path), path LIMIT ?",
                (sql_pat, max_results+5)).fetchall()
        matches = [r[0] for r in rows]
        return {"matches": matches[:max_results], "total": len(matches),
                "truncated": len(matches) > max_results}
    except _sqlite3.OperationalError:
        return find_file(name_pattern, max_results)
