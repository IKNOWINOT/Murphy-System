# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Murphy System configuration package.

Usage::

    from config.config_loader import load_config, get

    cfg = load_config()
    threshold = get("thresholds.confidence", 0.85)

Environment variables always override YAML file values (twelve-factor app style).
"""

from .config_loader import load_config, get, get_all  # noqa: F401

# Re-export Settings / get_settings / reload_settings from src/config.py.
# That module is shadowed by this package on sys.path, so we load it by
# file path to avoid circular resolution.
import importlib.util as _ilu, pathlib as _pl

_src_config = _pl.Path(__file__).resolve().parent.parent / "src" / "config.py"
if _src_config.is_file():
    _spec = _ilu.spec_from_file_location("_murphy_settings", str(_src_config))
    _mod = _ilu.module_from_spec(_spec)
    try:
        _spec.loader.exec_module(_mod)
        Settings = _mod.Settings
        get_settings = _mod.get_settings
        reload_settings = _mod.reload_settings
    except Exception:
        pass  # pydantic-settings not installed — Settings unavailable

__all__ = ["load_config", "get", "get_all", "Settings", "get_settings",
           "reload_settings"]
