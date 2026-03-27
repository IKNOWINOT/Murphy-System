"""
Murphy System — Interactive Natural Language Terminal UI Package

A conversational TUI (Terminal User Interface) for interacting with
Murphy System via natural language.

This package decomposes the monolithic murphy_terminal.py into:
- config.py: Configuration and constants
- api_client.py: MurphyAPIClient class
- dialog.py: DialogContext class
- widgets.py: StatusBar, MurphyInput widgets
- app.py: MurphyTerminalApp class
- __main__.py: Entry point

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post | License: BSL 1.1
"""

from murphy_terminal.api_client import MurphyAPIClient
from murphy_terminal.dialog import DialogContext
from murphy_terminal.app import MurphyTerminalApp
from murphy_terminal.config import (
    API_URL,
    DEFAULT_API_URL,
    MODULE_COMMAND_MAP,
    API_PROVIDER_LINKS,
)

__all__ = [
    "MurphyAPIClient",
    "DialogContext",
    "MurphyTerminalApp",
    "API_URL",
    "DEFAULT_API_URL",
    "MODULE_COMMAND_MAP",
    "API_PROVIDER_LINKS",
]

__version__ = "3.0.0"
