"""Centralized security monitoring and RBAC enforcement."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import time
from typing import Dict, List

PERMS_FILE = os.path.join("security", "permissions.json")
API_USAGE_FILE = os.path.join("logs", "api_usage.json")
SEC_EVENTS_FILE = os.path.join("logs", "security_events.json")

@dataclass
class Role:
    permissions: List[str]

class SecurityBot:
    def __init__(self) -> None:
        self.roles: Dict[str, Role] = {}
        self.config_hash: str | None = None
        self.throttled: Dict[str, float] = {}
        self.suspicious: list[str] = []

    def set_role(self, user_id: str, permissions: List[str]) -> None:
        self.roles[user_id] = Role(permissions)

    def has_permission(self, user_id: str, action: str) -> bool:
        role = self.roles.get(user_id)
        return role is not None and action in role.permissions

    def require(self, user_id: str, action: str) -> None:
        if not self.has_permission(user_id, action):
            raise PermissionError(f"Unauthorized for: {action}")

    def store_config_hash(self, hash_value: str) -> None:
        self.config_hash = hash_value

    def validate_config_hash(self, hash_value: str) -> bool:
        return self.config_hash == hash_value

    def flag_suspicious_schedule(self, task_id: str) -> None:
        self.suspicious.append(task_id)

    def throttle_bot(self, bot: str, duration: int) -> None:
        self.throttled[bot] = time.time() + duration

    def unthrottle_bot(self, bot: str) -> None:
        self.throttled.pop(bot, None)

    def is_throttled(self, bot: str) -> bool:
        expire = self.throttled.get(bot)
        if expire is None:
            return False
        if expire < time.time():
            self.throttled.pop(bot, None)
            return False
        return True


def load_permissions() -> Dict[str, dict]:
    if not os.path.exists(PERMS_FILE):
        return {}
    with open(PERMS_FILE, "r") as f:
        return json.load(f)


def check_permission(role: str, command: str) -> bool:
    perms = load_permissions()
    return command in perms.get(role, {}).get("can_execute", [])


def log_activity(key_id: str, command: str, task_id: str, status: str, latency: int) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "key_id": key_id,
        "command": command,
        "task_id": task_id,
        "latency_ms": latency,
        "status": status,
    }
    os.makedirs(os.path.dirname(API_USAGE_FILE), exist_ok=True)
    with open(API_USAGE_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def log_security_event(event_type: str, detail: str, action: str | None = None) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "detail": detail,
        "action": action or "none",
    }
    os.makedirs(os.path.dirname(SEC_EVENTS_FILE), exist_ok=True)
    with open(SEC_EVENTS_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def scan_for_anomalies(threshold: int = 1000) -> list[dict]:
    if not os.path.exists(API_USAGE_FILE):
        return []
    with open(API_USAGE_FILE, "r") as f:
        usage = [json.loads(line) for line in f if line.strip()]
    from collections import Counter

    key_counts = Counter(entry["key_id"] for entry in usage)
    flagged = []
    for key, count in key_counts.items():
        if count > threshold:
            flagged.append({"key_id": key, "issue": "suspicious usage volume"})
    return flagged


def revoke_key(key_id: str) -> bool:
    from .key_manager_bot import _load_keys, _save_keys

    keys = _load_keys()
    for entry in keys:
        if entry["key_id"] == key_id:
            entry["status"] = "revoked"
            _save_keys(keys)
            log_security_event("key_revoked", f"revoked {key_id}")
            return True
    return False
