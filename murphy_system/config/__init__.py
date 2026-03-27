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

__all__ = ["load_config", "get", "get_all"]
