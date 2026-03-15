# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
plugin_sdk.py — Murphy System Connector Plugin SDK
Base class and utilities for building custom connectors.

Quick-start example:
    from plugin_sdk import ConnectorPlugin, ConnectorCategory, AuthType

    class MySlackBot(ConnectorPlugin):
        name = "MySlackBot"
        category = ConnectorCategory.COMMUNICATION
        version = "1.0.0"

        def authenticate(self, credentials: dict) -> bool:
            self._token = credentials.get("bot_token", "")
            return bool(self._token)

        def execute(self, action: str, params: dict) -> dict:
            if action == "send_message":
                # … real HTTP call …
                return {"ok": True, "ts": "1234567890.000001"}
            raise ValueError(f"Unknown action: {action}")

        def health_check(self) -> dict:
            return {"status": "ok", "latency_ms": 12}

        def schema(self) -> dict:
            return {
                "actions": ["send_message", "list_channels"],
                "auth_fields": ["bot_token"],
            }
"""

from __future__ import annotations

import abc
import importlib.util
import inspect
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Type


# ---------------------------------------------------------------------------
# Enums (re-exported so plugin authors only need to import from plugin_sdk)
# ---------------------------------------------------------------------------

class ConnectorCategory(Enum):
    CRM = "crm"
    COMMUNICATION = "communication"
    PROJECT_MANAGEMENT = "project_management"
    CLOUD = "cloud"
    DEVOPS = "devops"
    ERP = "erp"
    PAYMENT = "payment"
    KNOWLEDGE = "knowledge"
    ITSM = "itsm"
    ANALYTICS = "analytics"
    SECURITY = "security"
    IOT = "iot"
    SOCIAL = "social"
    MARKETING = "marketing"
    HR = "hr"
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    LEGAL = "legal"
    EDUCATION = "education"
    CUSTOM = "custom"


class AuthType(Enum):
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    JWT = "jwt"
    MTLS = "mtls"
    NONE = "none"


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class ConnectorPlugin(abc.ABC):
    """
    Abstract base class for all Murphy System connector plugins.

    Subclass this and implement the four abstract methods.
    Murphy System will automatically discover and load your plugin if you
    place the module in a ``plugins/`` directory and run PluginLoader.

    Attributes:
        name     : Unique identifier (e.g. "MySlackBot")
        category : ConnectorCategory enum value
        version  : Semantic version string (e.g. "1.2.0")
        auth_type: AuthType enum value (defaults to API_KEY)
    """

    name: str = ""
    category: ConnectorCategory = ConnectorCategory.CUSTOM
    version: str = "1.0.0"
    auth_type: AuthType = AuthType.API_KEY

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name:
            cls.name = cls.__name__

    # ── Required abstract methods ────────────────────────────────────────────

    @abc.abstractmethod
    def authenticate(self, credentials: Dict[str, str]) -> bool:
        """
        Validate and store credentials.

        Args:
            credentials: dict of credential fields (e.g. {"api_key": "sk-…"})

        Returns:
            True if authentication succeeded, False otherwise.
        """

    @abc.abstractmethod
    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a named action against the external service.

        Args:
            action: Action name defined in schema()["actions"]
            params: Action-specific parameters

        Returns:
            Result dict (must be JSON-serializable)

        Raises:
            ValueError: If action is unknown
            RuntimeError: If the remote call fails
        """

    @abc.abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Return the current health of this connector.

        Returns:
            dict with at least {"status": "ok"|"degraded"|"error"}
        """

    @abc.abstractmethod
    def schema(self) -> Dict[str, Any]:
        """
        Return the connector's self-describing schema.

        Returns:
            dict with keys:
              - actions (list[str])
              - auth_fields (list[str])
              - optional description (str)
        """

    # ── Provided helpers (override if needed) ────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "version": self.version,
            "auth_type": self.auth_type.value,
            "schema": self.schema(),
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} version={self.version!r}>"


# ---------------------------------------------------------------------------
# Plugin Loader
# ---------------------------------------------------------------------------

class PluginLoader:
    """
    Discovers and loads ConnectorPlugin subclasses from a directory.

    Usage:
        loader = PluginLoader("/path/to/plugins")
        plugins = loader.load_all()
        for plugin_cls in plugins:
            instance = plugin_cls()
            instance.authenticate({"api_key": "…"})
    """

    def __init__(self, plugins_dir: str) -> None:
        self.plugins_dir = Path(plugins_dir)
        self._loaded: Dict[str, Type[ConnectorPlugin]] = {}

    def load_all(self) -> List[Type[ConnectorPlugin]]:
        """Load all .py files in plugins_dir and return ConnectorPlugin subclasses."""
        self._loaded.clear()
        if not self.plugins_dir.is_dir():
            return []

        for py_file in sorted(self.plugins_dir.glob("*.py")):
            if py_file.stem.startswith("_"):
                continue
            try:
                self._load_file(py_file)
            except Exception:
                pass

        return list(self._loaded.values())

    def _load_file(self, path: Path) -> None:
        module_name = f"murphy_plugin_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            return
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)  # type: ignore[attr-defined]

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, ConnectorPlugin)
                and obj is not ConnectorPlugin
                and not inspect.isabstract(obj)
            ):
                self._loaded[obj.name or obj.__name__] = obj

    def list_discovered(self) -> List[str]:
        return list(self._loaded.keys())


# ---------------------------------------------------------------------------
# Plugin Validator
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    plugin_name: str
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed


class PluginValidator:
    """
    Validates that a ConnectorPlugin subclass satisfies the SDK contract.

    Usage:
        validator = PluginValidator()
        result = validator.validate(MyPlugin)
        if not result:
            print(result.errors)
    """

    _REQUIRED_ABSTRACT: List[str] = ["authenticate", "execute", "health_check", "schema"]
    _REQUIRED_ATTRS: List[str] = ["name", "category", "version"]

    def validate(self, plugin_cls: Type[ConnectorPlugin]) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
        name = getattr(plugin_cls, "name", None) or plugin_cls.__name__

        # Must be a proper subclass
        if not issubclass(plugin_cls, ConnectorPlugin):
            errors.append(f"{name} does not subclass ConnectorPlugin")
            return ValidationResult(name, False, errors, warnings)

        # Must not be abstract
        if inspect.isabstract(plugin_cls):
            missing = [
                m for m in self._REQUIRED_ABSTRACT
                if m in getattr(plugin_cls, "__abstractmethods__", set())
            ]
            errors.append(f"Abstract methods not implemented: {missing}")

        # Attribute checks
        for attr in self._REQUIRED_ATTRS:
            val = getattr(plugin_cls, attr, None)
            if not val:
                errors.append(f"Class attribute '{attr}' is missing or empty")

        if not isinstance(getattr(plugin_cls, "category", None), ConnectorCategory):
            errors.append("Attribute 'category' must be a ConnectorCategory enum value")

        # Instantiate and run health_check / schema if no abstract methods missing
        if not errors:
            try:
                instance = plugin_cls()
            except Exception as exc:
                errors.append(f"Failed to instantiate plugin: {exc}")
                return ValidationResult(name, False, errors, warnings)

            try:
                schema = instance.schema()
                if "actions" not in schema:
                    warnings.append("schema() result missing 'actions' key")
                if "auth_fields" not in schema:
                    warnings.append("schema() result missing 'auth_fields' key")
            except Exception as exc:
                errors.append(f"schema() raised an exception: {exc}")

        return ValidationResult(name, len(errors) == 0, errors, warnings)

    def validate_directory(self, plugins_dir: str) -> List[ValidationResult]:
        loader = PluginLoader(plugins_dir)
        classes = loader.load_all()
        return [self.validate(cls) for cls in classes]


# ---------------------------------------------------------------------------
# Example Plugin (for documentation / testing)
# ---------------------------------------------------------------------------

class ExampleEchoConnector(ConnectorPlugin):
    """
    Minimal example connector — echoes actions back as responses.
    Copy this as a starting point for your own plugin.
    """

    name = "ExampleEchoConnector"
    category = ConnectorCategory.CUSTOM
    version = "1.0.0"
    auth_type = AuthType.API_KEY

    def authenticate(self, credentials: Dict[str, str]) -> bool:
        self._key = credentials.get("api_key", "")
        return bool(self._key)

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"echo": action, "params": params, "status": "ok"}

    def health_check(self) -> Dict[str, Any]:
        return {"status": "ok", "plugin": self.name}

    def schema(self) -> Dict[str, Any]:
        return {
            "actions": ["echo", "ping"],
            "auth_fields": ["api_key"],
            "description": "Echo connector — returns the action name and params",
        }


if __name__ == "__main__":
    validator = PluginValidator()
    result = validator.validate(ExampleEchoConnector)
    print(f"Validation: {'PASS' if result else 'FAIL'}")
    if result.errors:
        print("Errors:", result.errors)
    if result.warnings:
        print("Warnings:", result.warnings)

    instance = ExampleEchoConnector()
    instance.authenticate({"api_key": "test-key-123"})
    print("Execute:", instance.execute("echo", {"msg": "hello"}))
    print("Health:", instance.health_check())
    print("Schema:", instance.schema())
