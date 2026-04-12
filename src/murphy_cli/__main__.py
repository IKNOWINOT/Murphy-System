"""
Murphy CLI — Package runner
============================

Allows ``python -m murphy_cli`` invocation.

Module label: CLI-PMOD-001
"""

import sys

from murphy_cli.main import main

sys.exit(main())
