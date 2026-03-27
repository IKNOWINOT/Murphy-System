#!/usr/bin/env python3
"""
Murphy System — Interactive Natural Language Terminal UI

This file is a thin shim that imports from the murphy_terminal package.
The monolithic implementation has been decomposed into:

    murphy_terminal/
    ├── __init__.py      # Package exports
    ├── __main__.py      # Entry point for python -m murphy_terminal
    ├── config.py        # Configuration and constants
    ├── api_client.py    # MurphyAPIClient class
    ├── dialog.py        # DialogContext class
    ├── widgets.py       # StatusBar, MurphyInput widgets
    └── app.py           # MurphyTerminalApp class

For the legacy monolithic implementation, see murphy_terminal_legacy.py.

Usage:
    python murphy_terminal.py
    python -m murphy_terminal

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post | License: BSL 1.1
"""

from murphy_terminal.app import main

if __name__ == "__main__":
    main()
