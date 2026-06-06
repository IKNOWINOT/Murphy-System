"""Cap A.4 — bash (safe command execution).

Security model:
  - Reuses Murphy CommandInjectionPreventer (security_plane.hardening)
    for allowlist + dangerous-pattern blocklist consistency
  - Extends allowlist with read-only/aggregate utilities
  - No shell=True, ever. shlex-parsed argv only
  - Timeout (default 30s, hard cap 120s)
  - stdout/stderr capped at 256 KB each
  - cwd must pass _path_guard.is_allowed()
  - Exit code returned (non-zero NOT treated as error)
  - Pipes, redirects, substitutions REJECTED at validation time
"""
from __future__ import annotations
import os, re, shlex, subprocess, sys
from typing import Any, Dict, Optional
from ._path_guard import is_allowed, canonicalize, allowed_roots

sys.path.insert(0, "/opt/Murphy-System/src")
from security_plane.hardening import CommandInjectionPreventer

TRANSITION_EXTRA_ALLOWED = {
    "wc", "head", "tail", "awk", "sort", "uniq", "tr",
    "md5sum", "sha256sum", "stat", "file",
    "tee", "which", "id", "uname", "du", "df",
}
EFFECTIVE_ALLOWED = CommandInjectionPreventer.ALLOWED_COMMANDS | TRANSITION_EXTRA_ALLOWED
DANGEROUS_PATTERNS = CommandInjectionPreventer.DANGEROUS_PATTERNS
DEFAULT_TIMEOUT = 30
MAX_TIMEOUT = 120
MAX_STDOUT_BYTES = 256 * 1024


def _is_safe(command: str):
    if not command or not command.strip():
        return False, "empty command"
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command):
            return False, f"dangerous pattern matched: {pattern}"
    try:
        parts = shlex.split(command)
    except ValueError as e:
        return False, f"shlex parse failed: {e}"
    if not parts:
        return False, "no command after parse"
    base = parts[0]
    if base not in EFFECTIVE_ALLOWED:
        return False, f"base command not allowlisted: {base!r}"
    return True, parts


def bash(command, *, cwd=None, timeout_s=DEFAULT_TIMEOUT,
         env_extra=None, dry_run=False):
    out = {
        "ok": False, "command": command, "argv": None, "cwd": cwd,
        "exit_code": None, "stdout": "", "stderr": "",
        "stdout_truncated": False, "stderr_truncated": False,
        "timed_out": False, "dry_run": dry_run, "error": None,
    }
    try:
        ok, result = _is_safe(command)
        if not ok:
            out["error"] = result; return out
        argv = result
        out["argv"] = argv

        if cwd:
            if not is_allowed(cwd):
                out["error"] = f"cwd not under allowed roots: {allowed_roots()}"
                return out
            cwd = canonicalize(cwd)
            out["cwd"] = cwd
            if not os.path.isdir(cwd):
                out["error"] = f"cwd is not a directory: {cwd}"
                return out

        timeout_s = min(max(1, int(timeout_s)), MAX_TIMEOUT)

        if dry_run:
            out["ok"] = True
            return out

        env = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
               "LANG": "C", "LC_ALL": "C"}
        if env_extra:
            for k, v in env_extra.items():
                if isinstance(k, str) and isinstance(v, str):
                    if k not in {"LD_PRELOAD", "LD_LIBRARY_PATH"}:
                        env[k] = v

        try:
            proc = subprocess.run(
                argv, cwd=cwd, env=env,
                capture_output=True, timeout=timeout_s, shell=False,
            )
        except subprocess.TimeoutExpired:
            out["timed_out"] = True
            out["error"] = f"timed out after {timeout_s}s"
            return out

        out["exit_code"] = proc.returncode
        sb = proc.stdout or b""
        eb = proc.stderr or b""
        if len(sb) > MAX_STDOUT_BYTES:
            out["stdout"] = sb[:MAX_STDOUT_BYTES].decode("utf-8", errors="replace")
            out["stdout_truncated"] = True
        else:
            out["stdout"] = sb.decode("utf-8", errors="replace")
        if len(eb) > MAX_STDOUT_BYTES:
            out["stderr"] = eb[:MAX_STDOUT_BYTES].decode("utf-8", errors="replace")
            out["stderr_truncated"] = True
        else:
            out["stderr"] = eb.decode("utf-8", errors="replace")

        out["ok"] = True
        return out
    except FileNotFoundError as e:
        out["error"] = f"command not found: {e}"; return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def execute_bash(**kwargs):
    return bash(
        command=kwargs.get("command", ""),
        cwd=kwargs.get("cwd"),
        timeout_s=kwargs.get("timeout_s", DEFAULT_TIMEOUT),
        env_extra=kwargs.get("env_extra"),
        dry_run=kwargs.get("dry_run", False),
    )
