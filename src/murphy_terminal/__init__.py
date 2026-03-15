"""Murphy Terminal — Universal Command Registry Package.

Re-exports the command registry for convenient access::

    from murphy_terminal import CommandRegistry, build_registry, CommandCategory

Copyright 2024 Inoni LLC – BSL-1.1
"""

from .command_registry import (
    MURPHY_COMMANDS,
    CommandCategory,
    CommandDefinition,
    CommandRegistry,
    build_registry,
)

__all__ = [
    "CommandCategory",
    "CommandDefinition",
    "CommandRegistry",
    "MURPHY_COMMANDS",
    "build_registry",
]
