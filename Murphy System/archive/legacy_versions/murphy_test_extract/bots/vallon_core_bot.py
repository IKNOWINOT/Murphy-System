"""Core security orchestrator combining role management, key handling,
config validation, and crypto helpers."""

from __future__ import annotations

from typing import Dict, List, Optional

from .security_bot import Role
from .key_manager_bot import KeyManagerBot
from .config_manager import ConfigManagerBot
from .crypto_utils import (
    encrypt_payload,
    decrypt_payload,
    sign_message,
    verify_signature,
)


class VallonCoreBot:
    """Govern security, API keys, and config integrity under Vallon's oversight."""

    def __init__(self, config_path: str = "config.yml") -> None:
        self.roles: Dict[str, Role] = {}
        self.key_manager = KeyManagerBot()
        self.config_watcher = ConfigManagerBot(path=config_path)

    # ------------------------------------------------------------------
    # Role / permission logic
    def set_role(self, user_id: str, permissions: List[str]) -> None:
        """Assign a role with permissions to a user."""
        self.roles[user_id] = Role(permissions)

    def has_permission(self, user_id: str, action: str) -> bool:
        role = self.roles.get(user_id)
        return role is not None and action in role.permissions

    def require(self, user_id: str, action: str) -> None:
        """Raise if ``user_id`` lacks permission for ``action``."""
        if not self.has_permission(user_id, action):
            raise PermissionError(f"Unauthorized for: {action}")

    # ------------------------------------------------------------------
    # Key management helpers
    def generate_api_key(self, bot_name: str, key_id: str, key_value: str) -> None:
        self.key_manager.register_key(bot_name, key_id, key_value)

    def use_api_key(
        self, bot_name: str, key_id: str, max_calls: int = 100, window: int = 60
    ) -> bool:
        return self.key_manager.use_key(bot_name, key_id, max_calls, window)

    def get_api_key(self, bot_name: str, key_id: str) -> Optional[str]:
        return self.key_manager.get_key(bot_name, key_id)

    # ------------------------------------------------------------------
    # Config monitoring
    def start_config_monitoring(self) -> None:
        self.config_watcher.start_watcher()

    def stop_config_monitoring(self) -> None:
        self.config_watcher.stop_watcher()

    def validate_config_hash(self, hash_value: str) -> bool:
        return self.config_watcher.secbot.validate_config_hash(hash_value)

    # ------------------------------------------------------------------
    def get_cognitive_signature(self) -> dict:
        return {
            "kiren": 0.10,
            "veritas": 0.25,
            "vallon": 0.65,
        }
