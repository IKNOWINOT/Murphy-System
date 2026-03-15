"""Key management with rate limiting and revocation."""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Tuple, List
from cryptography.fernet import Fernet

KEYS_FILE = os.path.join("keys", "api_keys.json")

def _load_keys() -> List[dict]:
    if not os.path.exists(KEYS_FILE):
        return []
    with open(KEYS_FILE, "r") as f:
        return json.load(f)

def _save_keys(data: List[dict]) -> None:
    os.makedirs(os.path.dirname(KEYS_FILE), exist_ok=True)
    with open(KEYS_FILE, "w") as f:
        json.dump(data, f, indent=2)


class KeyManagerBot:
    """Manage encrypted API keys and usage quotas."""

    def __init__(self, master_key: bytes | None = None) -> None:
        self.keys: Dict[Tuple[str, str], bytes] = {}
        self.usage_log: defaultdict[Tuple[str, str], List[float]] = defaultdict(list)
        self.fernet = Fernet(master_key or Fernet.generate_key())
        self._load_persistent()

    def _load_persistent(self) -> None:
        for entry in _load_keys():
            if entry["status"] == "active":
                token = self.fernet.encrypt(entry["key_value"].encode())
                self.keys[(entry["assigned_to"], entry["key_id"])] = token

    def register_key(self, bot_name: str, key_id: str, key_value: str) -> None:
        """Register a new key for a bot."""
        self.keys[(bot_name, key_id)] = self.fernet.encrypt(key_value.encode())

        data = _load_keys()
        data.append({
            "key_id": key_id,
            "assigned_to": bot_name,
            "status": "active",
            "key_value": key_value,
            "usage_count": 0,
            "last_used": datetime.now(timezone.utc).isoformat()
        })
        _save_keys(data)

    def use_key(self, bot_name: str, key_id: str, max_calls: int = 100, window: int = 60) -> bool:
        """Record usage and return ``True`` if under limit."""
        if (bot_name, key_id) not in self.keys:
            return False
        now = time.time()
        log = self.usage_log[(bot_name, key_id)]
        log[:] = [t for t in log if t > now - window]
        if len(log) >= max_calls:
            return False
        log.append(now)
        # update persistent record
        data = _load_keys()
        for entry in data:
            if entry["key_id"] == key_id and entry["assigned_to"] == bot_name:
                entry["usage_count"] += 1
                entry["last_used"] = datetime.now(timezone.utc).isoformat()
                break
        _save_keys(data)
        return True

    def get_key(self, bot_name: str, key_id: str) -> str | None:
        token = self.keys.get((bot_name, key_id))
        if not token:
            return None
        return self.fernet.decrypt(token).decode()

    def revoke_all_active_keys(self) -> List[Tuple[str, str]]:
        """Revoke all keys and return revoked identifiers."""
        revoked = list(self.keys.keys())
        self.keys.clear()
        self.usage_log.clear()
        return revoked

    # new persistence-based operations
    def allocate_key(self, bot_name: str) -> str | None:
        keys = _load_keys()
        for entry in keys:
            if entry["assigned_to"] == "unassigned" and entry["status"] == "active":
                entry["assigned_to"] = bot_name
                entry["last_used"] = datetime.now(timezone.utc).isoformat()
                _save_keys(keys)
                self.keys[(bot_name, entry["key_id"])] = self.fernet.encrypt(entry["key_value"].encode())
                return entry["key_id"]
        return None

    def revoke_key(self, key_id: str) -> bool:
        keys = _load_keys()
        for entry in keys:
            if entry["key_id"] == key_id:
                entry["status"] = "revoked"
                _save_keys(keys)
                self.keys.pop((entry["assigned_to"], key_id), None)
                return True
        return False

    def quarantine_key(self, key_id: str) -> bool:
        keys = _load_keys()
        for entry in keys:
            if entry["key_id"] == key_id:
                entry["status"] = "quarantined"
                _save_keys(keys)
                self.keys.pop((entry["assigned_to"], key_id), None)
                return True
        return False

    def key_status(self) -> List[dict]:
        return _load_keys()

    # --- hive_mind_math_patch_v2.0 additions ---
    def key_usage_entropy(self) -> float:
        """Compute Shannon entropy of key usage distribution."""
        import math
        counts = [len(v) for v in self.usage_log.values() if v]
        total = sum(counts)
        if total == 0:
            return 0.0
        probs = [c / total for c in counts]
        return -sum(p * math.log2(p) for p in probs)
