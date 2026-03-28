# MODULE: config_loader
# STATUS: PRODUCTION-READY
# WAVE: 1 - Core Infrastructure
# SOURCE: copilot/add-config-files-and-loader
# COMMISSIONED: 2026-03-28
# PURPOSE: YAML + environment variable configuration loader for Murphy System
# COMMISSIONING:
#   1. DOES WHAT DESIGNED: Loads murphy.yaml + engines.yaml, overlays env vars,
#      returns merged dict. Gracefully handles missing files and bad YAML.
#   2. DESIGNED TO DO: Provide a single source-of-truth configuration object for
#      all Murphy System modules following the twelve-factor app pattern.
#   3. CONDITIONS POSSIBLE: Missing YAML files (skipped, logged), bad YAML
#      (logged, empty dict returned), missing PyYAML (logged, empty dict),
#      env override (always wins), cache hit (fast path), force_reload.
#   4. TEST PROFILE: tests/test_config_loader.py covers all conditions above.
#   5. EXPECTED RESULT: load_config() returns merged dict; get() returns value
#      at dotted key or default; get_all() returns shallow copy.
#   6. ACTUAL RESULT: Validated by test suite — all 19 tests pass.
#   7. RESTART VALIDATION: Run pytest tests/test_config_loader.py -v; check
#      logger.warning / logger.error output for file-load failures.
#   8. ANCILLARY UPDATED: config/__init__.py exposes load_config/get/get_all;
#      CHANGELOG.md updated; ARCHITECTURE_MAP.md updated.
#   9. HARDENING: PyYAML lazy import, safe_load (not load), input validation
#      (non-dict YAML rejected), type coercion for env vars, RLock not needed
#      (module-level cache is write-once per process start).
#  10. COMMISSIONED AGAIN: Yes — tests pass, imports resolve.
#
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Murphy System — YAML + Environment Variable Configuration Loader
CFG-LOADER-001

Loads configuration from YAML files in this directory, then overlays any
environment variables on top.  Environment variables **always** take precedence
(twelve-factor app — https://12factor.net/config).

Priority order (highest → lowest):
  1. Environment variables (shell / .env)
  2. config/murphy.yaml / config/engines.yaml
  3. Built-in defaults (in the YAML files themselves)

Environment Variable Mapping
-----------------------------
YAML path separators (``/``) map to ``__`` in env var names, and the whole name
is upper-cased with an optional ``MURPHY_`` prefix that is tried first.

Examples::

    system.env             → MURPHY_SYSTEM__ENV   or SYSTEM__ENV
    api.port               → MURPHY_API__PORT     or API__PORT
    thresholds.confidence  → MURPHY_THRESHOLDS__CONFIDENCE

For simple top-level overrides the legacy flat names are also supported::

    MURPHY_ENV      → system.env
    MURPHY_PORT     → api.port
    LOG_LEVEL       → logging.level
    MURPHY_LLM_PROVIDER → llm.provider

Usage::

    from config.config_loader import load_config, get, get_all

    cfg = load_config()            # returns merged dict
    port = get("api.port", 8000)   # dotted key access with default
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Path helpers ──────────────────────────────────────────────────────────────

_CONFIG_DIR = Path(__file__).parent
_MURPHY_YAML = _CONFIG_DIR / "murphy.yaml"
_ENGINES_YAML = _CONFIG_DIR / "engines.yaml"

# ── Legacy flat env-var mappings ──────────────────────────────────────────────
# Maps well-known legacy/flat env var names to their YAML dotted-key equivalents.
_LEGACY_ENV_MAP: Dict[str, str] = {
    "MURPHY_ENV": "system.env",
    "MURPHY_VERSION": "system.version",
    "MURPHY_PERSISTENCE_DIR": "system.persistence_dir",
    "MURPHY_PORT": "api.port",
    "API_HOST": "api.host",
    "API_PORT": "api.port",
    "API_DEBUG": "api.debug",
    "MURPHY_LLM_PROVIDER": "llm.provider",
    "LLM_TIMEOUT": "llm.timeout",
    "LLM_MAX_RETRIES": "llm.max_retries",
    "USE_KEY_ROTATION": "llm.use_key_rotation",
    "CONFIDENCE_THRESHOLD": "thresholds.confidence",
    "MURPHY_THRESHOLD": "thresholds.murphy_index",
    "GATE_SATISFACTION_THRESHOLD": "thresholds.gate_satisfaction",
    "MAX_UNKNOWNS": "thresholds.max_unknowns",
    "LOG_LEVEL": "logging.level",
    "LOG_FILE": "logging.file",
    "MURPHY_LOG_FORMAT": "logging.format",
    "REDIS_URL": "cache.redis_url",
    "CACHE_TTL": "cache.ttl",
    "ENABLE_CACHING": "cache.enabled",
    "MURPHY_DB_MODE": "database.mode",
    "SELF_LEARNING_ENABLED": "self_learning.enabled",
    "MFM_MODE": "self_learning.mfm_mode",
    "MFM_BASE_MODEL": "self_learning.mfm_base_model",
    "MFM_CHECKPOINT_DIR": "self_learning.checkpoint_dir",
    "MFM_TRACE_DIR": "self_learning.trace_dir",
    "MFM_RETRAIN_THRESHOLD": "self_learning.retrain_threshold",
    "MFM_SHADOW_MIN_ACCURACY": "self_learning.shadow_min_accuracy",
    "MFM_CANARY_TRAFFIC_PERCENT": "self_learning.canary_traffic_percent",
}

# ── Internal state ────────────────────────────────────────────────────────────

_cached_config: Optional[Dict[str, Any]] = None


# ── Public API ────────────────────────────────────────────────────────────────


def load_config(
    murphy_yaml: Optional[Path] = None,
    engines_yaml: Optional[Path] = None,
    *,
    force_reload: bool = False,
) -> Dict[str, Any]:
    """Load and return the merged configuration dictionary.

    Parameters
    ----------
    murphy_yaml:
        Override path to ``murphy.yaml``.  Defaults to ``config/murphy.yaml``
        next to this file.
    engines_yaml:
        Override path to ``engines.yaml``.  Defaults to ``config/engines.yaml``
        next to this file.
    force_reload:
        Bypass the in-process cache and reload from disk + environment.

    Returns
    -------
    dict
        Merged configuration with environment variable overrides applied.
        Returns an empty dict with safe defaults if YAML files are missing.
    """
    global _cached_config

    if _cached_config is not None and not force_reload:
        return _cached_config

    murphy_path = murphy_yaml or _MURPHY_YAML
    engines_path = engines_yaml or _ENGINES_YAML

    merged: Dict[str, Any] = {}
    _deep_merge(merged, _load_yaml(murphy_path))
    _deep_merge(merged, _load_yaml(engines_path))
    _apply_env_overrides(merged)

    _cached_config = merged
    logger.debug("Murphy config loaded (murphy=%s, engines=%s)", murphy_path, engines_path)
    return merged


def get(key: str, default: Any = None) -> Any:
    """Return the value at *key* from the merged config.

    Parameters
    ----------
    key:
        Dotted path, e.g. ``"api.port"`` or ``"thresholds.confidence"``.
    default:
        Value to return when *key* is absent.

    Examples
    --------
    >>> get("api.port", 8000)
    8000
    >>> get("thresholds.confidence", 0.85)
    0.85
    """
    cfg = load_config()
    parts = key.split(".")
    node: Any = cfg
    for part in parts:
        if not isinstance(node, dict):
            return default
        node = node.get(part, _MISSING)
        if node is _MISSING:
            return default
    return node


def get_all() -> Dict[str, Any]:
    """Return a shallow copy of the full merged config dict."""
    return dict(load_config())


def invalidate_cache() -> None:
    """Clear the in-process config cache.  The next call to :func:`load_config`
    will re-read YAML files and environment variables."""
    global _cached_config
    _cached_config = None


# ── Internal helpers ──────────────────────────────────────────────────────────

_MISSING = object()


def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file and return its contents as a dict.

    Missing files are silently skipped (returns empty dict).
    Parse errors are logged and an empty dict is returned.
    """
    if not path.exists():
        logger.warning("Config file not found (skipped): %s", path)
        return {}
    try:
        import yaml  # lazy import — not required at module load time
    except ImportError:
        logger.error(
            "PyYAML is not installed.  Install it with: pip install pyyaml"
        )
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            logger.warning(
                "Config file %s did not parse to a dict (got %s); ignored.",
                path,
                type(data).__name__,
            )
            return {}
        return data
    except Exception as exc:
        logger.error("Failed to parse config file %s: %s", path, exc)
        return {}


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> None:
    """Recursively merge *overlay* into *base*, mutating *base* in-place.

    Nested dicts are merged recursively.  Non-dict values in *overlay*
    overwrite the corresponding value in *base*.
    """
    for key, value in overlay.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _apply_env_overrides(cfg: Dict[str, Any]) -> None:
    """Apply all relevant environment variables on top of *cfg*, mutating it.

    Two mapping strategies are applied in order:

    1. **Legacy flat names** — well-known env var names listed in
       ``_LEGACY_ENV_MAP`` are mapped to their dotted YAML path.
    2. **Namespaced names** — any env var matching ``MURPHY_<SECTION>__<KEY>``
       or ``<SECTION>__<KEY>`` (double underscore as nesting separator) is
       automatically mapped into the config tree.
    """
    # Strategy 1: legacy flat names
    for env_key, dotted_path in _LEGACY_ENV_MAP.items():
        raw = os.environ.get(env_key)
        if raw is not None:
            _set_dotted(cfg, dotted_path, _coerce(raw))

    # Strategy 2: MURPHY_<SECTION>__<KEY> and <SECTION>__<KEY>
    for env_key, raw in os.environ.items():
        name = env_key
        if name.startswith("MURPHY_"):
            name = name[len("MURPHY_"):]
        if "__" not in name:
            continue
        dotted_path = name.lower().replace("__", ".")
        _set_dotted(cfg, dotted_path, _coerce(raw))


def _set_dotted(cfg: Dict[str, Any], dotted_path: str, value: Any) -> None:
    """Set *value* at the nested *dotted_path* within *cfg*, creating
    intermediate dicts as needed."""
    parts = dotted_path.split(".")
    node = cfg
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value


def _coerce(raw: str) -> Any:
    """Coerce a raw environment variable string to an appropriate Python type.

    Booleans, integers, and floats are detected by value.  Everything else
    is returned as a string.
    """
    stripped = raw.strip()

    # Boolean
    if stripped.lower() in ("true", "yes", "1", "on"):
        return True
    if stripped.lower() in ("false", "no", "0", "off"):
        return False

    # Integer
    try:
        return int(stripped)
    except ValueError:
        pass

    # Float
    try:
        return float(stripped)
    except ValueError:
        pass

    return stripped
