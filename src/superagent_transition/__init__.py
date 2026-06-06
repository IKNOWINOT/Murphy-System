"""R12 transition — dual-registration of superagent caps into Murphy."""
from .migration import (
    get_skill_manager,
    migrate_capability,
    list_migrated,
    rollback_capability,
    MigrationResult,
)
__all__ = [
    "get_skill_manager", "migrate_capability",
    "list_migrated", "rollback_capability", "MigrationResult",
]
