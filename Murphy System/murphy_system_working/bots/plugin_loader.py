"""Dynamic plugin loading utilities.

This module allows new bot modules to be dropped into a ``plugins/``
directory and automatically loaded at runtime. Each plugin should
expose a ``register()`` function that performs any initialization
required by the plugin.
"""

from __future__ import annotations

import os
from importlib import util, reload
from pathlib import Path
from types import ModuleType
from typing import Dict, Iterable

PLUGINS: Dict[str, ModuleType] = {}
PLUGIN_PATHS: Dict[str, str] = {}


def _discover(directory: str) -> Iterable[Path]:
    """Yield all plugin file paths in ``directory``."""
    dpath = Path(directory)
    if not dpath.exists():
        return []
    for entry in dpath.iterdir():
        if entry.is_file() and entry.suffix == ".py":
            yield entry
        elif entry.is_dir() and (entry / "__init__.py").exists():
            yield entry / "__init__.py"


def load_plugin(path: str) -> ModuleType:
    """Load a single plugin given a file path or module name."""
    if os.path.isfile(path) or path.endswith(".py"):
        p = Path(path)
        name = p.stem
        spec = util.spec_from_file_location(name, str(p))
    else:
        # treat as module import path
        spec = util.find_spec(path)
        if spec is None:
            raise ImportError(path)
        name = path.split(".")[-1]
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load plugin {path}")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    PLUGINS[name] = module
    PLUGIN_PATHS[name] = str(p if os.path.isfile(path) or path.endswith('.py') else spec.origin)
    if hasattr(module, "register"):
        module.register()
    return module


def reload_plugin(name: str) -> ModuleType:
    """Reload a plugin module by name using its original path."""
    path = PLUGIN_PATHS.get(name)
    if not path:
        raise KeyError(f"Unknown plugin {name}")
    module = load_plugin(path)
    if hasattr(module, "__reload__"):
        module.__reload__()
    return module


def load_plugins(directory: str = "plugins", disabled: Iterable[str] | None = None) -> Dict[str, ModuleType]:
    """Load all plugins found in ``directory`` unless disabled."""
    disabled_set = set(disabled or [])
    for path in _discover(directory):
        name = Path(path).stem
        if name in disabled_set:
            continue
        load_plugin(str(path))
    return PLUGINS

