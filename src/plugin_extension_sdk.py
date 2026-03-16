"""
Plugin/Extension SDK — enables third-party module development, registration,
sandboxed execution, manifest validation, and lifecycle management.

Implements RECOMMENDATIONS.md Section 6.2.6.
"""

import hashlib
import importlib
import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class PluginState(Enum):
    """Plugin state (Enum subclass)."""
    REGISTERED = "registered"
    VALIDATED = "validated"
    INSTALLED = "installed"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    UNINSTALLED = "uninstalled"
    FAILED = "failed"


class PluginCapability(Enum):
    """Plugin capability (Enum subclass)."""
    READ_DATA = "read_data"
    WRITE_DATA = "write_data"
    EXECUTE_TASKS = "execute_tasks"
    MANAGE_WORKFLOWS = "manage_workflows"
    ACCESS_TELEMETRY = "access_telemetry"
    SEND_NOTIFICATIONS = "send_notifications"
    MODIFY_CONFIG = "modify_config"
    ADMIN = "admin"


MANIFEST_SCHEMA = {
    "required": ["name", "version", "author", "description", "entry_point", "capabilities"],
    "optional": ["dependencies", "min_murphy_version", "max_murphy_version",
                  "config_schema", "hooks", "tags", "license", "homepage"],
    "version_pattern": r"^\d+\.\d+\.\d+$",
    "name_pattern": r"^[a-z][a-z0-9_-]{2,63}$",
}


class PluginManifest:
    """Validated plugin manifest."""

    def __init__(self, data: Dict[str, Any]):
        self.name: str = data["name"]
        self.version: str = data["version"]
        self.author: str = data["author"]
        self.description: str = data["description"]
        self.entry_point: str = data["entry_point"]
        self.capabilities: List[str] = data["capabilities"]
        self.dependencies: List[str] = data.get("dependencies", [])
        self.min_murphy_version: Optional[str] = data.get("min_murphy_version")
        self.max_murphy_version: Optional[str] = data.get("max_murphy_version")
        self.config_schema: Dict = data.get("config_schema", {})
        self.hooks: Dict[str, str] = data.get("hooks", {})
        self.tags: List[str] = data.get("tags", [])
        self.license: str = data.get("license", "MIT")
        self.homepage: str = data.get("homepage", "")
        self.checksum: str = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "entry_point": self.entry_point,
            "capabilities": self.capabilities,
            "dependencies": self.dependencies,
            "config_schema": self.config_schema,
            "hooks": self.hooks,
            "tags": self.tags,
            "license": self.license,
            "checksum": self.checksum,
        }


class PluginSandbox:
    """Sandboxed execution environment for plugins."""

    def __init__(self, manifest: PluginManifest, allowed_capabilities: List[str]):
        self.manifest = manifest
        self.allowed_capabilities = set(allowed_capabilities)
        self._call_count = 0
        self._error_count = 0
        self._total_time_ms = 0.0
        self._max_calls_per_minute = 1000
        self._call_timestamps: List[float] = []
        self._lock = threading.Lock()

    def check_capability(self, capability: str) -> bool:
        return capability in self.allowed_capabilities

    def execute(self, handler: Callable, *args, **kwargs) -> Dict[str, Any]:
        with self._lock:
            now = time.time()
            self._call_timestamps = [t for t in self._call_timestamps if now - t < 60]
            if len(self._call_timestamps) >= self._max_calls_per_minute:
                return {
                    "success": False,
                    "error": "rate_limit_exceeded",
                    "plugin": self.manifest.name,
                }
            capped_append(self._call_timestamps, now)

        start = time.monotonic()
        try:
            result = handler(*args, **kwargs)
            elapsed = (time.monotonic() - start) * 1000
            with self._lock:
                self._call_count += 1
                self._total_time_ms += elapsed
            return {
                "success": True,
                "result": result,
                "plugin": self.manifest.name,
                "elapsed_ms": round(elapsed, 2),
            }
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            elapsed = (time.monotonic() - start) * 1000
            with self._lock:
                self._call_count += 1
                self._error_count += 1
                self._total_time_ms += elapsed
            return {
                "success": False,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "plugin": self.manifest.name,
                "elapsed_ms": round(elapsed, 2),
            }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "plugin": self.manifest.name,
                "call_count": self._call_count,
                "error_count": self._error_count,
                "error_rate": (self._error_count / self._call_count * 100) if self._call_count > 0 else 0,
                "avg_time_ms": round(self._total_time_ms / self._call_count, 2) if self._call_count > 0 else 0,
                "total_time_ms": round(self._total_time_ms, 2),
            }


class PluginExtensionSDK:
    """
    Plugin/Extension SDK for Murphy System.
    Enables third-party developers to create, validate, install, and manage plugins
    within the Murphy ecosystem with sandboxed execution and lifecycle management.
    """

    def __init__(self, murphy_version: str = "1.0.0"):
        self.murphy_version = murphy_version
        self._plugins: Dict[str, Dict[str, Any]] = {}
        self._sandboxes: Dict[str, PluginSandbox] = {}
        self._hooks: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()
        self._event_log: List[Dict[str, Any]] = []
        self._allowed_capabilities: List[str] = [c.value for c in PluginCapability]

    def validate_manifest(self, manifest_data: Dict[str, Any]) -> Dict[str, Any]:
        errors = []
        warnings = []

        for field in MANIFEST_SCHEMA["required"]:
            if field not in manifest_data:
                errors.append(f"Missing required field: {field}")

        if errors:
            return {"valid": False, "errors": errors, "warnings": warnings}

        name = manifest_data.get("name", "")
        if not re.match(MANIFEST_SCHEMA["name_pattern"], name):
            errors.append(f"Invalid plugin name '{name}': must match {MANIFEST_SCHEMA['name_pattern']}")

        version = manifest_data.get("version", "")
        if not re.match(MANIFEST_SCHEMA["version_pattern"], version):
            errors.append(f"Invalid version '{version}': must be semver (e.g. 1.0.0)")

        capabilities = manifest_data.get("capabilities", [])
        valid_caps = {c.value for c in PluginCapability}
        for cap in capabilities:
            if cap not in valid_caps:
                warnings.append(f"Unknown capability '{cap}' — will be ignored")

        entry_point = manifest_data.get("entry_point", "")
        if not entry_point:
            errors.append("entry_point must not be empty")

        if not manifest_data.get("author"):
            errors.append("author must not be empty")

        if not manifest_data.get("description"):
            errors.append("description must not be empty")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def register_plugin(self, manifest_data: Dict[str, Any]) -> Dict[str, Any]:
        validation = self.validate_manifest(manifest_data)
        if not validation["valid"]:
            return {
                "registered": False,
                "errors": validation["errors"],
            }

        manifest = PluginManifest(manifest_data)
        with self._lock:
            if manifest.name in self._plugins:
                existing = self._plugins[manifest.name]
                if existing["state"] not in (PluginState.UNINSTALLED, PluginState.FAILED):
                    return {
                        "registered": False,
                        "errors": [f"Plugin '{manifest.name}' already registered with state {existing['state'].value}"],
                    }

            self._plugins[manifest.name] = {
                "manifest": manifest,
                "state": PluginState.VALIDATED,
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "config": {},
                "handler": None,
            }
            self._log_event("registered", manifest.name)

        return {
            "registered": True,
            "plugin": manifest.name,
            "version": manifest.version,
            "checksum": manifest.checksum,
        }

    def install_plugin(self, plugin_name: str, handler: Optional[Callable] = None,
                       config: Optional[Dict] = None) -> Dict[str, Any]:
        with self._lock:
            if plugin_name not in self._plugins:
                return {"installed": False, "error": f"Plugin '{plugin_name}' not found"}

            plugin = self._plugins[plugin_name]
            if plugin["state"] not in (PluginState.VALIDATED, PluginState.UNINSTALLED, PluginState.FAILED):
                return {"installed": False, "error": f"Plugin in wrong state: {plugin['state'].value}"}

            manifest = plugin["manifest"]
            allowed = [c for c in manifest.capabilities if c in self._allowed_capabilities]
            sandbox = PluginSandbox(manifest, allowed)
            self._sandboxes[plugin_name] = sandbox

            plugin["handler"] = handler
            plugin["config"] = config or {}
            plugin["state"] = PluginState.INSTALLED
            plugin["installed_at"] = datetime.now(timezone.utc).isoformat()
            self._log_event("installed", plugin_name)

        return {
            "installed": True,
            "plugin": plugin_name,
            "capabilities_granted": allowed,
        }

    def activate_plugin(self, plugin_name: str) -> Dict[str, Any]:
        with self._lock:
            if plugin_name not in self._plugins:
                return {"activated": False, "error": f"Plugin '{plugin_name}' not found"}

            plugin = self._plugins[plugin_name]
            if plugin["state"] != PluginState.INSTALLED:
                return {"activated": False, "error": f"Plugin must be installed first, current: {plugin['state'].value}"}

            manifest = plugin["manifest"]
            if manifest.hooks.get("on_activate"):
                hook_name = manifest.hooks["on_activate"]
                if hook_name in self._hooks:
                    for fn in self._hooks[hook_name]:
                        try:
                            fn(plugin_name)
                        except Exception as exc:
                            logger.debug("Suppressed exception: %s", exc)
                            pass

            plugin["state"] = PluginState.ACTIVE
            plugin["activated_at"] = datetime.now(timezone.utc).isoformat()
            self._log_event("activated", plugin_name)

        return {"activated": True, "plugin": plugin_name}

    def suspend_plugin(self, plugin_name: str, reason: str = "") -> Dict[str, Any]:
        with self._lock:
            if plugin_name not in self._plugins:
                return {"suspended": False, "error": f"Plugin '{plugin_name}' not found"}

            plugin = self._plugins[plugin_name]
            if plugin["state"] != PluginState.ACTIVE:
                return {"suspended": False, "error": f"Plugin not active: {plugin['state'].value}"}

            plugin["state"] = PluginState.SUSPENDED
            plugin["suspended_at"] = datetime.now(timezone.utc).isoformat()
            plugin["suspend_reason"] = reason
            self._log_event("suspended", plugin_name, {"reason": reason})

        return {"suspended": True, "plugin": plugin_name, "reason": reason}

    def uninstall_plugin(self, plugin_name: str) -> Dict[str, Any]:
        with self._lock:
            if plugin_name not in self._plugins:
                return {"uninstalled": False, "error": f"Plugin '{plugin_name}' not found"}

            plugin = self._plugins[plugin_name]
            plugin["state"] = PluginState.UNINSTALLED
            plugin["handler"] = None
            plugin["uninstalled_at"] = datetime.now(timezone.utc).isoformat()
            self._sandboxes.pop(plugin_name, None)
            self._log_event("uninstalled", plugin_name)

        return {"uninstalled": True, "plugin": plugin_name}

    def execute_plugin(self, plugin_name: str, *args, **kwargs) -> Dict[str, Any]:
        with self._lock:
            if plugin_name not in self._plugins:
                return {"success": False, "error": f"Plugin '{plugin_name}' not found"}

            plugin = self._plugins[plugin_name]
            if plugin["state"] != PluginState.ACTIVE:
                return {"success": False, "error": f"Plugin not active: {plugin['state'].value}"}

            handler = plugin["handler"]
            if handler is None:
                return {"success": False, "error": "No handler registered"}

            sandbox = self._sandboxes.get(plugin_name)

        if sandbox is None:
            return {"success": False, "error": "No sandbox available"}

        result = sandbox.execute(handler, *args, **kwargs)
        self._log_event("executed", plugin_name, {"success": result["success"]})
        return result

    def get_plugin_info(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if plugin_name not in self._plugins:
                return None
            plugin = self._plugins[plugin_name]
            info = {
                "name": plugin_name,
                "state": plugin["state"].value,
                "manifest": plugin["manifest"].to_dict(),
                "config": plugin["config"],
                "registered_at": plugin.get("registered_at"),
            }
            if plugin_name in self._sandboxes:
                info["stats"] = self._sandboxes[plugin_name].get_stats()
            return info

    def list_plugins(self, state: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            plugins = []
            for name, plugin in self._plugins.items():
                if state and plugin["state"].value != state:
                    continue
                plugins.append({
                    "name": name,
                    "version": plugin["manifest"].version,
                    "state": plugin["state"].value,
                    "author": plugin["manifest"].author,
                    "description": plugin["manifest"].description,
                })
            return plugins

    def register_hook(self, hook_name: str, callback: Callable):
        with self._lock:
            if hook_name not in self._hooks:
                self._hooks[hook_name] = []
            self._hooks[hook_name].append(callback)

    def get_event_log(self, plugin_name: Optional[str] = None,
                      limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            events = self._event_log
            if plugin_name:
                events = [e for e in events if e["plugin"] == plugin_name]
            return events[-limit:]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            state_counts = {}
            for plugin in self._plugins.values():
                s = plugin["state"].value
                state_counts[s] = state_counts.get(s, 0) + 1
            return {
                "module": "plugin_extension_sdk",
                "murphy_version": self.murphy_version,
                "total_plugins": len(self._plugins),
                "state_counts": state_counts,
                "total_events": len(self._event_log),
                "available_capabilities": self._allowed_capabilities,
            }

    def _log_event(self, action: str, plugin_name: str, extra: Optional[Dict] = None):
        event = {
            "action": action,
            "plugin": plugin_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            event.update(extra)
        capped_append(self._event_log, event)
