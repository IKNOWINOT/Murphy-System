"""
Murphy CLI — Command-line interface for murphy.systems
======================================================

A production-grade CLI for interacting with the Murphy System API, modeled
after the MiniMax-AI/cli pattern.  Supports authentication, chat, forge
generation, agent management, automation control, HITL workflows, and
system administration.

Usage::

    murphy auth login --api-key <key>
    murphy chat --message "Describe a compliance automation"
    murphy forge generate --query "Build an onboarding app"
    murphy status

Module label: CLI-CORE-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

__version__ = "1.0.0"
__cli_name__ = "murphy"
__api_default__ = "https://murphy.systems"
