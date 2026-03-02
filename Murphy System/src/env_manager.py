"""
Environment Manager for Murphy System

Provides utilities for reading, writing, and reloading .env files,
as well as validating API keys for supported providers.
"""

import os
import re
from typing import Dict, List, Optional, Tuple


# Supported providers and their key format patterns
API_KEY_FORMATS: Dict[str, Dict[str, str]] = {
    "groq": {
        "env_var": "GROQ_API_KEY",
        "prefix": "gsk_",
        "pattern": r"^gsk_[A-Za-z0-9]{20,}$",
        "hint": "Groq keys start with 'gsk_'",
    },
    "openai": {
        "env_var": "OPENAI_API_KEY",
        "prefix": "sk-",
        "pattern": r"^sk-[A-Za-z0-9_-]{20,}$",
        "hint": "OpenAI keys start with 'sk-'",
    },
    "anthropic": {
        "env_var": "ANTHROPIC_API_KEY",
        "prefix": "sk-ant-",
        "pattern": r"^sk-ant-[A-Za-z0-9_-]{20,}$",
        "hint": "Anthropic keys start with 'sk-ant-'",
    },
}


def get_env_path() -> str:
    """Return the path to the .env file in the Murphy System directory."""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")


def read_env(path: Optional[str] = None) -> Dict[str, str]:
    """Parse a .env file into a dict.

    Skips blank lines and comments (lines starting with ``#``).
    Strips optional surrounding quotes from values.
    """
    if path is None:
        path = get_env_path()
    result: Dict[str, str] = {}
    if not os.path.isfile(path):
        return result
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            result[key] = value
    return result


def write_env_key(path: Optional[str], key: str, value: str) -> None:
    """Add or update a single key in a .env file without clobbering others.

    If the file does not exist it will be created.  If the key already
    exists, only that line is replaced.
    """
    if path is None:
        path = get_env_path()

    lines: List[str] = []
    found = False

    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()

    new_line = f"{key}={value}\n"
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        existing_key = stripped.split("=", 1)[0].strip()
        if existing_key == key:
            lines[i] = new_line
            found = True
            break

    if not found:
        # Ensure file ends with newline before appending
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(new_line)

    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)


def reload_env(path: Optional[str] = None) -> Dict[str, str]:
    """Re-read the .env file and update ``os.environ``.

    Returns the dict of values that were loaded.
    """
    if path is None:
        path = get_env_path()
    env_vars = read_env(path)
    for k, v in env_vars.items():
        os.environ[k] = v
    return env_vars


def validate_api_key(provider: str, key: str) -> Tuple[bool, str]:
    """Validate an API key's format for a given provider.

    Returns ``(True, message)`` on success or ``(False, message)`` on failure.
    """
    provider = provider.lower()
    if provider not in API_KEY_FORMATS:
        supported = ", ".join(sorted(API_KEY_FORMATS.keys()))
        return False, f"Unknown provider '{provider}'. Supported: {supported}"

    fmt = API_KEY_FORMATS[provider]
    if not re.match(fmt["pattern"], key):
        return False, f"Invalid key format. {fmt['hint']}"

    return True, f"Key format valid for {provider}"
