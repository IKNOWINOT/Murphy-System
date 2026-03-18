"""
Murphy System Tiered Orchestrator
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1

Central orchestrator for tiered (on-demand) runtime mode. Manages
RuntimePack registration, capability-based loading, and graceful
fallback to monolith mode.

Designed to be the PRIMARY orchestrator when MURPHY_RUNTIME_MODE=tiered.
Each pack handles a domain (e.g. "hvac", "compliance", "analytics") and is
only loaded if a team profile actually requires those capabilities.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("murphy.tiered_orchestrator")


# ---------------------------------------------------------------------------
# Pack status & data structures
# ---------------------------------------------------------------------------


class PackStatus(Enum):
    """Lifecycle state of a RuntimePack."""
    REGISTERED = "registered"
    LOADING = "loading"
    LOADED = "loaded"
    FAILED = "failed"
    UNLOADED = "unloaded"


@dataclass
class RuntimePack:
    """
    Describes a loadable domain pack.

    A pack bundles:
      - A set of *capabilities* it provides (e.g. ``{"hvac", "energy_management"}``).
      - An optional *router_factory* callable that returns a FastAPI ``APIRouter``
        when the pack is active.
      - Optional *on_load* / *on_unload* hooks for setup/teardown.
    """
    name: str
    capabilities: Set[str] = field(default_factory=set)
    description: str = ""
    version: str = "1.0.0"
    router_factory: Optional[Any] = None  # () -> APIRouter | None
    on_load: Optional[Any] = None        # async () -> None
    on_unload: Optional[Any] = None      # async () -> None
    status: PackStatus = PackStatus.REGISTERED
    router: Optional[Any] = None         # populated after load
    error: Optional[str] = None


@dataclass
class BootResult:
    """Result returned by :meth:`TieredOrchestrator.boot`."""
    success: bool
    loaded_packs: List[str] = field(default_factory=list)
    skipped_packs: List[str] = field(default_factory=list)
    failed_packs: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    boot_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# TieredOrchestrator
# ---------------------------------------------------------------------------


class TieredOrchestrator:
    """
    Manages on-demand loading of :class:`RuntimePack` instances.

    Usage::

        orchestrator = TieredOrchestrator()
        for pack in get_all_packs():
            orchestrator.register_pack(pack)
        result = await orchestrator.boot(team_profile={"capabilities": ["billing"]})

    Args:
        fallback_mode: What to do when a pack fails.  ``"monolith"`` triggers a
            full fallback; ``"skip"`` just marks the pack as failed and continues.
    """

    def __init__(self, fallback_mode: str = "monolith") -> None:
        self._packs: Dict[str, RuntimePack] = {}
        self._fallback_mode = fallback_mode
        self._booted = False

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_pack(self, pack: RuntimePack) -> None:
        """Register a pack with the orchestrator."""
        if pack.name in self._packs:
            logger.warning("Pack '%s' already registered — skipping duplicate.", pack.name)
            return
        self._packs[pack.name] = pack
        logger.debug("Registered pack '%s' (capabilities=%s)", pack.name, pack.capabilities)

    # ------------------------------------------------------------------
    # Boot
    # ------------------------------------------------------------------

    async def boot(self, team_profile: Optional[Dict[str, Any]] = None) -> BootResult:
        """
        Boot the orchestrator.

        Determines which packs are needed based on *team_profile* and loads them.
        If *team_profile* is empty/None, **all** registered packs are loaded.

        Returns:
            :class:`BootResult` describing what was loaded, skipped, and failed.
        """
        start = time.monotonic()
        result = BootResult(success=False)

        required_caps: Set[str] = set()
        if team_profile:
            caps = team_profile.get("capabilities", [])
            if isinstance(caps, list):
                required_caps = set(caps)

        for name, pack in self._packs.items():
            # If no capabilities were requested, load everything
            if not required_caps or pack.capabilities & required_caps:
                loaded = await self._load_pack(pack)
                if loaded:
                    result.loaded_packs.append(name)
                else:
                    result.failed_packs.append(name)
                    if pack.error:
                        result.errors.append(f"{name}: {pack.error}")
            else:
                pack.status = PackStatus.UNLOADED
                result.skipped_packs.append(name)
                logger.debug("Skipping pack '%s' — capabilities not requested.", name)

        result.boot_time_ms = (time.monotonic() - start) * 1000
        result.success = len(result.failed_packs) == 0
        self._booted = True

        logger.info(
            "Tiered boot complete in %.1fms — loaded=%d skipped=%d failed=%d",
            result.boot_time_ms,
            len(result.loaded_packs),
            len(result.skipped_packs),
            len(result.failed_packs),
        )
        return result

    # ------------------------------------------------------------------
    # Dynamic load / unload
    # ------------------------------------------------------------------

    async def load_pack(self, name: str) -> bool:
        """Load (or reload) a pack by name. Returns True on success."""
        pack = self._packs.get(name)
        if pack is None:
            logger.error("Cannot load unknown pack '%s'.", name)
            return False
        return await self._load_pack(pack)

    async def unload_pack(self, name: str) -> bool:
        """Unload a pack by name. Calls its *on_unload* hook if present."""
        pack = self._packs.get(name)
        if pack is None:
            logger.error("Cannot unload unknown pack '%s'.", name)
            return False
        try:
            if pack.on_unload:
                await pack.on_unload()
            pack.status = PackStatus.UNLOADED
            pack.router = None
            logger.info("Unloaded pack '%s'.", name)
            return True
        except Exception as exc:
            logger.error("Error unloading pack '%s': %s", name, exc)
            return False

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return a JSON-serialisable status dict."""
        return {
            "booted": self._booted,
            "fallback_mode": self._fallback_mode,
            "packs": {
                name: {
                    "status": pack.status.value,
                    "capabilities": list(pack.capabilities),
                    "version": pack.version,
                    "description": pack.description,
                    "error": pack.error,
                }
                for name, pack in self._packs.items()
            },
        }

    def get_active_routers(self) -> List[Any]:
        """Return a list of FastAPI ``APIRouter`` instances from loaded packs."""
        routers = []
        for pack in self._packs.values():
            if pack.status == PackStatus.LOADED and pack.router is not None:
                routers.append(pack.router)
        return routers

    @property
    def packs(self) -> Dict[str, RuntimePack]:
        """Read-only view of all registered packs."""
        return dict(self._packs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _load_pack(self, pack: RuntimePack) -> bool:
        pack.status = PackStatus.LOADING
        try:
            if pack.on_load:
                await pack.on_load()
            if pack.router_factory:
                pack.router = pack.router_factory()
            pack.status = PackStatus.LOADED
            pack.error = None
            logger.info("Loaded pack '%s'.", pack.name)
            return True
        except Exception as exc:
            pack.status = PackStatus.FAILED
            pack.error = str(exc)
            logger.error("Failed to load pack '%s': %s", pack.name, exc)
            return False
