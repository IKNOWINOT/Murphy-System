"""
subsystem_registry.py — Centralized optional-subsystem availability map.

Class S Roadmap, Item 1 (scaffolding).

Background
----------
`murphy_production_server.py` historically wired ~30 optional subsystems via
inline ``try/except ImportError`` blocks. That pattern (a) duplicated import
bookkeeping, (b) made the server file the single point of failure for
diagnosing missing modules, and (c) prevented other code paths (workers,
CLI entrypoints, tests) from sharing the same view of "what is available".

This module replaces that pattern with a single, typed registry. Callers ask
the registry whether a subsystem is available and receive either the imported
module/symbol or a sentinel. Server, workers, and tests share one source of
truth; the registry can be inspected, exported as a dict, or rendered as a
status table.

Usage
-----
    from src.runtime import subsystem_registry as reg

    if reg.is_available("graphql_api_layer"):
        gql = reg.get("graphql_api_layer")
        gql.attach(app)

    # Or, declarative attach pattern (preferred):
    reg.register("hitl", import_path="src.hitl_persistence")
    hitl = reg.require("hitl")           # raises if unavailable

The registry is intentionally lazy: a subsystem is only imported the first
time it is requested via :func:`get`, :func:`require`, or
:func:`is_available`. Import failures are captured and remembered; subsequent
calls return the cached failure without re-attempting the import.

Design notes
------------
* No I/O at import time. Importing this module is free.
* Thread-safe registration and resolution via a module-level lock.
* All exceptions during subsystem import are coerced to ``ImportError`` for
  the caller's benefit while the original traceback is preserved on the
  ``SubsystemEntry``.
* The registry deliberately does NOT swallow non-ImportError exceptions
  silently — they are logged via the standard ``logging`` module so that
  unexpected failures (e.g. ``RuntimeError`` raised by a subsystem's
  ``__init__``) remain visible.
"""

from __future__ import annotations

import importlib
import logging
import threading
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Optional

__all__ = [
    "SubsystemEntry",
    "SubsystemRegistry",
    "default_registry",
    "register",
    "is_available",
    "get",
    "require",
    "snapshot",
]

logger = logging.getLogger(__name__)


@dataclass
class SubsystemEntry:
    """Descriptor for one optional subsystem."""

    name: str
    """Stable identifier used by callers (e.g. ``"graphql_api_layer"``)."""

    import_path: str
    """Dotted module path to import (e.g. ``"src.graphql_api_layer"``)."""

    attribute: Optional[str] = None
    """Optional attribute on the imported module to expose (e.g. ``"router"``).
    When ``None``, the module itself is returned by :meth:`get`."""

    description: str = ""
    """Human-readable description for status reporting."""

    # Resolved state (populated on first access).
    _resolved: bool = field(default=False, init=False, repr=False)
    _value: Any = field(default=None, init=False, repr=False)
    _error: Optional[BaseException] = field(default=None, init=False, repr=False)

    @property
    def available(self) -> bool:
        """``True`` once the subsystem has been resolved without error."""
        return self._resolved and self._error is None

    @property
    def error(self) -> Optional[BaseException]:
        """The exception raised on the most recent resolution attempt, if any."""
        return self._error

    def status(self) -> str:
        """Render a single-word status: ``available`` / ``unavailable`` / ``unresolved``."""
        if not self._resolved:
            return "unresolved"
        return "available" if self._error is None else "unavailable"


class SubsystemRegistry:
    """Thread-safe registry of optional subsystems."""

    def __init__(self) -> None:
        self._entries: dict[str, SubsystemEntry] = {}
        self._lock = threading.RLock()

    # ---- registration --------------------------------------------------

    def register(
        self,
        name: str,
        *,
        import_path: str,
        attribute: Optional[str] = None,
        description: str = "",
    ) -> SubsystemEntry:
        """Register a subsystem. Idempotent: re-registering the same ``name``
        with identical ``import_path`` and ``attribute`` is a no-op; conflicting
        re-registration raises :class:`ValueError`."""
        with self._lock:
            existing = self._entries.get(name)
            if existing is not None:
                if (
                    existing.import_path == import_path
                    and existing.attribute == attribute
                ):
                    return existing
                raise ValueError(
                    f"Subsystem {name!r} is already registered with a different "
                    f"target ({existing.import_path}!{existing.attribute})"
                )
            entry = SubsystemEntry(
                name=name,
                import_path=import_path,
                attribute=attribute,
                description=description,
            )
            self._entries[name] = entry
            return entry

    # ---- resolution ----------------------------------------------------

    def _resolve(self, entry: SubsystemEntry) -> None:
        """Attempt to import the subsystem; cache success or failure on the entry."""
        if entry._resolved:
            return
        try:
            module: ModuleType = importlib.import_module(entry.import_path)
            value: Any = module
            if entry.attribute is not None:
                value = getattr(module, entry.attribute)
        except ImportError as exc:
            entry._error = exc
            entry._value = None
            logger.debug(
                "Subsystem %r unavailable (ImportError on %s): %s",
                entry.name,
                entry.import_path,
                exc,
            )
        except Exception as exc:  # noqa: BLE001 — coerce to ImportError but log
            entry._error = ImportError(
                f"Subsystem {entry.name!r} failed to initialize: {exc}"
            )
            entry._value = None
            logger.warning(
                "Subsystem %r raised %s during import of %s: %s",
                entry.name,
                type(exc).__name__,
                entry.import_path,
                exc,
                exc_info=True,
            )
        else:
            entry._value = value
            entry._error = None
        finally:
            entry._resolved = True

    def is_available(self, name: str) -> bool:
        """Return ``True`` iff the subsystem can be imported successfully.
        Unknown names return ``False`` rather than raising."""
        entry = self._entries.get(name)
        if entry is None:
            return False
        with self._lock:
            self._resolve(entry)
            return entry.available

    def get(self, name: str, default: Any = None) -> Any:
        """Return the resolved subsystem value or ``default`` if unavailable."""
        entry = self._entries.get(name)
        if entry is None:
            return default
        with self._lock:
            self._resolve(entry)
            return entry._value if entry.available else default

    def require(self, name: str) -> Any:
        """Return the resolved subsystem value or raise :class:`ImportError`."""
        entry = self._entries.get(name)
        if entry is None:
            raise ImportError(f"Subsystem {name!r} is not registered")
        with self._lock:
            self._resolve(entry)
            if not entry.available:
                # Preserve the original error if we have one.
                raise entry._error or ImportError(
                    f"Subsystem {name!r} is unavailable"
                )
            return entry._value

    # ---- introspection -------------------------------------------------

    def snapshot(self, *, resolve: bool = True) -> dict[str, dict[str, Any]]:
        """Return a serializable view of every registered subsystem.

        When ``resolve`` is ``True`` (the default) any unresolved entries are
        resolved first so the snapshot reflects current availability. When
        ``False``, unresolved entries are reported with status ``"unresolved"``
        and no import is attempted.
        """
        with self._lock:
            entries = list(self._entries.values())
        if resolve:
            for entry in entries:
                with self._lock:
                    self._resolve(entry)
        return {
            entry.name: {
                "import_path": entry.import_path,
                "attribute": entry.attribute,
                "description": entry.description,
                "status": entry.status(),
                "error": (
                    f"{type(entry._error).__name__}: {entry._error}"
                    if entry._error is not None
                    else None
                ),
            }
            for entry in entries
        }

    def names(self) -> list[str]:
        """Return the registered subsystem names in registration order."""
        with self._lock:
            return list(self._entries)

    def clear(self) -> None:
        """Remove all entries. Intended for tests."""
        with self._lock:
            self._entries.clear()


# ---------------------------------------------------------------------------
# Module-level convenience API backed by a process-wide default registry.
# ---------------------------------------------------------------------------
default_registry: SubsystemRegistry = SubsystemRegistry()


def register(
    name: str,
    *,
    import_path: str,
    attribute: Optional[str] = None,
    description: str = "",
) -> SubsystemEntry:
    """Register a subsystem on the process-wide :data:`default_registry`."""
    return default_registry.register(
        name,
        import_path=import_path,
        attribute=attribute,
        description=description,
    )


def is_available(name: str) -> bool:
    """Convenience wrapper around :meth:`SubsystemRegistry.is_available`."""
    return default_registry.is_available(name)


def get(name: str, default: Any = None) -> Any:
    """Convenience wrapper around :meth:`SubsystemRegistry.get`."""
    return default_registry.get(name, default)


def require(name: str) -> Any:
    """Convenience wrapper around :meth:`SubsystemRegistry.require`."""
    return default_registry.require(name)


def snapshot(*, resolve: bool = True) -> dict[str, dict[str, Any]]:
    """Convenience wrapper around :meth:`SubsystemRegistry.snapshot`."""
    return default_registry.snapshot(resolve=resolve)
