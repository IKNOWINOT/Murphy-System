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

src/runtime/tiered_orchestrator.py
Primary system orchestrator that manages tiered runtime loading.

The tiered orchestrator loads only the capability packs that a given team
actually needs, rather than booting the full monolith on every startup.
When any critical (KERNEL / PLATFORM) pack fails, it falls back to the
original ``MurphySystem`` monolith so the system is never left dark.

Tier overview
-------------
- KERNEL   (0) -- always loaded; system dies without these
- PLATFORM (1) -- loaded at startup; needed for basic operation
- DOMAIN   (2) -- loaded on-demand based on team / onboarding profile
- EPHEMERAL(3) -- spun up per-task, torn down when done

Thread-safety
-------------
All mutations to pack status are protected by ``threading.Lock``.

Fallback
--------
When ``fallback_mode == "monolith"`` and a KERNEL / PLATFORM pack fails,
``fallback_to_monolith()`` is called automatically.  The monolith file
(``src/runtime/murphy_system_core.py``) is **never imported** unless the
fallback is actually triggered.

Python 3.9+ compatible.

Copyright (c) 2020 Inoni Limited Liability Company / Creator: Corey Post / License: BSL 1.1
"""

from __future__ import annotations

import importlib
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger("murphy.tiered_orchestrator")


# ---------------------------------------------------------------------------
# Pack status & data structures
# ---------------------------------------------------------------------------


class PackStatus(Enum):
    """Lifecycle state of a RuntimePack (merged from both simple and tiered defs)."""
    REGISTERED = "registered"  # Pack is known to the orchestrator but not yet loaded.
    LOADING = "loading"        # Pack is currently being loaded.
    LOADED = "loaded"          # Pack is fully loaded and its router (if any) is active.
    ACTIVE = "active"          # Pack is active (alias used by tiered orchestrator).
    IDLE = "idle"              # Pack is loaded but idle (candidate for eviction).
    UNLOADING = "unloading"    # Pack is being unloaded.
    FAILED = "failed"          # Pack failed to load; error details in pack.error.
    UNLOADED = "unloaded"      # Pack was deliberately unloaded or skipped at boot.


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class RuntimeTier(str, Enum):
    """Execution tier for a runtime pack."""

    KERNEL = "kernel"      # Tier 0 -- always loaded, system dies without these
    PLATFORM = "platform"  # Tier 1 -- loaded at startup, needed for basic operation
    DOMAIN = "domain"      # Tier 2 -- loaded on-demand based on team/onboarding profile
    EPHEMERAL = "ephemeral"  # Tier 3 -- spun up per-task, torn down when done


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class RuntimePack:
    """Definition and runtime state of a loadable capability pack.

    A pack bundles:
      - A set of *capabilities* it provides (e.g. ``{"hvac", "energy_management"}``).
      - Tier, module list, and dependency declarations for tiered loading.
      - An optional *router_factory* callable that returns a FastAPI ``APIRouter``
        when the pack is active.
      - Optional *on_load* / *on_unload* hooks for setup/teardown.
    """
    name: str
    capabilities: Union[Set[str], List[str]] = field(default_factory=set)  # Set[str] or List[str]
    description: str = ""
    version: str = "1.0.0"
    tier: Optional[Any] = None                # RuntimeTier, optional for simple packs
    modules: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    api_routers: List[str] = field(default_factory=list)
    idle_timeout_minutes: int = 30
    max_memory_mb: int = 512
    router_factory: Optional[Any] = None      # () -> APIRouter | None
    on_load: Optional[Any] = None             # async () -> None
    on_unload: Optional[Any] = None           # async () -> None
    status: PackStatus = PackStatus.REGISTERED
    router: Optional[Any] = None              # populated after load
    last_activity: Optional[float] = None
    load_time_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class BootResult:
    """Result returned by :meth:`TieredOrchestrator.boot`."""
    success: bool
    fallback_used: bool = False
    loaded_packs: List[str] = field(default_factory=list)
    skipped_packs: List[str] = field(default_factory=list)
    failed_packs: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    error: Optional[str] = None
    boot_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# TieredOrchestrator
# Orchestrator
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
        return dict(self._registry)

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
    """Primary system orchestrator that manages tiered runtime loading.

    Parameters
    ----------
    fallback_mode:
        How to react when a KERNEL / PLATFORM pack fails to load.
        - ``"monolith"``  — import and boot the original MurphySystem
          monolith as a safety net (default, safest option).
        - ``"degraded"``  — log the error and continue without the failed
          pack.  Some functionality will be missing.
        - ``"strict"``    — abort startup immediately on any failure.
    """

    def __init__(self, fallback_mode: str = "monolith") -> None:
        if fallback_mode not in ("monolith", "degraded", "strict"):
            raise ValueError(
                f"Invalid fallback_mode '{fallback_mode}'. "
                "Choose 'monolith', 'degraded', or 'strict'."
            )
        self.fallback_mode: str = fallback_mode

        # Registry of all packs keyed by name
        self._registry: Dict[str, RuntimePack] = {}
        # Alias for backward compat with methods that use self._packs
        self._packs = self._registry

        # Active packs dict (name → pack)
        self._active_packs: Dict[str, RuntimePack] = {}

        # Monolith fallback reference (lazy — only set if fallback is used)
        self._monolith: Optional[Any] = None

        # Whether we are currently running in monolith-fallback mode
        self._in_fallback: bool = False

        # Thread-safety lock for all status mutations
        self._lock: threading.Lock = threading.Lock()

        logger.info(
            "TieredOrchestrator initialised (fallback_mode=%s)", fallback_mode
        )

    # ------------------------------------------------------------------
    # Pack registration
    # ------------------------------------------------------------------

    def register_pack(self, pack: RuntimePack) -> None:
        """Register a ``RuntimePack`` with the orchestrator.

        Silently ignores duplicate registrations (same pack name).
        """
        with self._lock:
            if pack.name in self._registry:
                logger.warning("Pack '%s' already registered -- skipping duplicate.", pack.name)
                return
            self._registry[pack.name] = pack
            logger.debug("Registered pack '%s' (tier=%s)", pack.name, pack.tier)

    # ------------------------------------------------------------------
    # Boot sequence
    # ------------------------------------------------------------------

    async def boot(self, team_profile: Optional[Dict] = None) -> BootResult:
        """Boot the tiered runtime.

        Boot sequence
        ~~~~~~~~~~~~~
        1. Load all KERNEL packs  — failure → system abort / monolith fallback
        2. Load all PLATFORM packs — failure → system abort / monolith fallback
        3. If *team_profile* is provided, load matching DOMAIN packs
        4. EPHEMERAL packs are **never** pre-loaded

        Parameters
        ----------
        team_profile:
            Optional dict from the onboarding flow.  Expected to contain a
            ``"capabilities"`` key with a list of capability tag strings,
            e.g. ``["crm_automation", "data_processing"]``.

        Returns
        -------
        BootResult
        """
        start = time.monotonic()
        loaded: List[str] = []
        failed: List[str] = []

        logger.info("TieredOrchestrator.boot() starting …")

        # ---- Step 1: KERNEL packs ----------------------------------------
        kernel_packs = self._packs_by_tier(RuntimeTier.KERNEL)
        for pack in kernel_packs:
            ok = await self.load_pack(pack.name)
            if ok:
                loaded.append(pack.name)
            else:
                failed.append(pack.name)
                logger.critical(
                    "KERNEL pack '%s' failed to load — system cannot continue",
                    pack.name,
                )
                return await self._handle_critical_failure(
                    f"KERNEL pack '{pack.name}' failed",
                    loaded,
                    failed,
                    start,
                )

        # ---- Step 2: PLATFORM packs --------------------------------------
        platform_packs = self._packs_by_tier(RuntimeTier.PLATFORM)
        for pack in platform_packs:
            ok = await self.load_pack(pack.name)
            if ok:
                loaded.append(pack.name)
            else:
                failed.append(pack.name)
                logger.critical(
                    "PLATFORM pack '%s' failed to load — system cannot continue",
                    pack.name,
                )
                return await self._handle_critical_failure(
                    f"PLATFORM pack '{pack.name}' failed",
                    loaded,
                    failed,
                    start,
                )

        # ---- Step 3: DOMAIN packs from team profile ----------------------
        if team_profile:
            capabilities: List[str] = team_profile.get("capabilities", [])
            logger.info(
                "Loading DOMAIN packs for team capabilities: %s", capabilities
            )
            for capability in capabilities:
                pack_name = await self.request_capability(capability)
                if pack_name and pack_name not in loaded:
                    loaded.append(pack_name)
                elif pack_name is None:
                    logger.warning(
                        "No pack found for capability '%s'", capability
                    )

        # ---- Step 4: Untiered packs (tier=None) — for backward compat ----
        # Packs with no tier are treated like simple packs: load all of them
        # when no team_profile is given, or filter by capability intersection
        # when a team_profile is provided.
        skipped: List[str] = []
        required_caps: set = set(team_profile.get("capabilities", [])) if team_profile else set()
        with self._lock:
            untiered_packs = [p for p in self._registry.values() if p.tier is None]
        for pack in untiered_packs:
            pack_caps = set(pack.capabilities) if pack.capabilities else set()
            if not required_caps or pack_caps & required_caps:
                ok = await self._load_pack(pack)
                if ok:
                    loaded.append(pack.name)
                else:
                    failed.append(pack.name)
            else:
                pack.status = PackStatus.UNLOADED
                skipped.append(pack.name)

        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info(
            "TieredOrchestrator.boot() completed in %.1f ms -- "
            "loaded=%s, failed=%s, skipped=%s",
            elapsed_ms,
            loaded,
            failed,
            skipped,
        )
        return BootResult(
            success=len(failed) == 0,
            fallback_used=False,
            loaded_packs=loaded,
            skipped_packs=skipped,
            failed_packs=failed,
            boot_time_ms=elapsed_ms,
        )

    # ------------------------------------------------------------------
    # Pack loading / unloading
    # ------------------------------------------------------------------

    async def load_pack(self, pack_name: str) -> bool:
        """Load a runtime pack by name.

        Steps
        ~~~~~
        1. Verify all declared dependencies are already ``ACTIVE``.
        2. ``importlib.import_module()`` every module listed in the pack.
        3. Set pack status to ``ACTIVE``.
        4. On failure: log, set status to ``FAILED``.

        Returns
        -------
        bool
            ``True`` on success, ``False`` on any failure.
        """
        with self._lock:
            pack = self._registry.get(pack_name)
            if pack is None:
                logger.error("load_pack: unknown pack '%s'", pack_name)
                return False
            if pack.status in (PackStatus.LOADED, PackStatus.ACTIVE):
                logger.debug("Pack '%s' is already active", pack_name)
                return True
            if pack.status == PackStatus.LOADING:
                logger.warning(
                    "Pack '%s' is already being loaded (concurrent call?)",
                    pack_name,
                )
                return False
            pack.status = PackStatus.LOADING

        load_start = time.monotonic()

        # Check dependencies -----------------------------------------------
        for dep_name in pack.dependencies:
            dep = self._registry.get(dep_name)
            if dep is None or dep.status != PackStatus.ACTIVE:
                # Try to load the dependency first
                logger.info(
                    "Pack '%s' depends on '%s' — loading dependency first",
                    pack_name,
                    dep_name,
                )
                dep_ok = await self.load_pack(dep_name)
                if not dep_ok:
                    error_msg = (
                        f"Dependency '{dep_name}' failed to load for pack "
                        f"'{pack_name}'"
                    )
                    logger.error(error_msg)
                    with self._lock:
                        pack.status = PackStatus.FAILED
                        pack.error = error_msg
                    return False

        # Import modules ---------------------------------------------------
        imported_modules: Dict[str, Any] = {}
        for module_path in pack.modules:
            try:
                mod = importlib.import_module(module_path)
                imported_modules[module_path] = mod
                logger.debug(
                    "Pack '%s': imported module '%s'", pack_name, module_path
                )
            except ImportError as exc:
                error_msg = (
                    f"ImportError loading module '{module_path}' "
                    f"for pack '{pack_name}': {exc}"
                )
                logger.error(error_msg)
                with self._lock:
                    pack.status = PackStatus.FAILED
                    pack.error = error_msg
                return False
            except Exception as exc:  # noqa: BLE001
                error_msg = (
                    f"Unexpected error loading module '{module_path}' "
                    f"for pack '{pack_name}': {exc}"
                )
                logger.exception(error_msg)
                with self._lock:
                    pack.status = PackStatus.FAILED
                    pack.error = error_msg
                return False

        elapsed_ms = (time.monotonic() - load_start) * 1000

        with self._lock:
            pack.status = PackStatus.LOADED
            pack.last_activity = time.time()
            pack.load_time_ms = elapsed_ms
            pack.error = None
            self._active_packs[pack_name] = pack

        logger.info(
            "Pack '%s' loaded successfully in %.1f ms", pack_name, elapsed_ms
        )
        return True

    async def unload_pack(self, pack_name: str) -> bool:
        """Unload an idle domain pack to free resources.

        KERNEL and PLATFORM packs cannot be unloaded.

        Returns
        -------
        bool
            ``True`` on success, ``False`` if the pack cannot be unloaded.
        """
        with self._lock:
            pack = self._registry.get(pack_name)
            if pack is None:
                logger.error("unload_pack: unknown pack '%s'", pack_name)
                return False

            if pack.tier in (RuntimeTier.KERNEL, RuntimeTier.PLATFORM):
                logger.warning(
                    "Cannot unload '%s': KERNEL and PLATFORM packs are permanent",
                    pack_name,
                )
                return False

            if pack.status not in (PackStatus.LOADED, PackStatus.ACTIVE, PackStatus.IDLE):
                logger.debug(
                    "unload_pack: pack '%s' is not active/idle (status=%s)",
                    pack_name,
                    pack.status,
                )
                return False

            pack.status = PackStatus.UNLOADING

        logger.info("Unloading pack '%s' …", pack_name)

        # Remove from active packs and clear references --------------------
        with self._lock:
            self._active_packs.pop(pack_name, None)
            pack.status = PackStatus.UNLOADED
            pack.last_activity = None

        logger.info("Pack '%s' unloaded successfully", pack_name)
        return True

    # ------------------------------------------------------------------
    # Capability-based on-demand loading
    # ------------------------------------------------------------------

    async def request_capability(self, capability: str) -> Optional[str]:
        """Find and (if necessary) load the pack that provides *capability*.

        Uses the ``CAPABILITY_TO_PACK`` mapping from the runtime packs
        registry.  If the pack is already active, returns its name
        immediately without reloading.

        Parameters
        ----------
        capability:
            A capability tag string, e.g. ``"crm_automation"``.

        Returns
        -------
        Optional[str]
            The pack name that was loaded, or ``None`` if no pack provides
            the requested capability or loading failed.
        """
        try:
            from src.runtime.runtime_packs.registry import CAPABILITY_TO_PACK  # noqa: PLC0415
        except ImportError:
            logger.error(
                "request_capability: could not import CAPABILITY_TO_PACK mapping"
            )
            return None

        pack_name = CAPABILITY_TO_PACK.get(capability)
        if pack_name is None:
            logger.debug(
                "request_capability: no pack found for capability '%s'",
                capability,
            )
            return None

        with self._lock:
            pack = self._registry.get(pack_name)
            if pack is None:
                logger.warning(
                    "request_capability: capability '%s' maps to pack '%s' "
                    "but that pack is not registered",
                    capability,
                    pack_name,
                )
                return None
            if pack.status == PackStatus.ACTIVE:
                pack.last_activity = time.time()
                return pack_name

        # Pack is registered but not active — load it now
        logger.info(
            "Lazy-loading pack '%s' for capability '%s'",
            pack_name,
            capability,
        )
        ok = await self.load_pack(pack_name)
        if ok:
            return pack_name
        logger.error(
            "Failed to lazy-load pack '%s' for capability '%s'",
            pack_name,
            capability,
        )
        return None

    # ------------------------------------------------------------------
    # Status / health
    # ------------------------------------------------------------------

    def get_status(self) -> Dict:
        """Return the full orchestrator status dict.

        Suitable for use in ``/api/health`` and ``/api/modules`` responses.
        """
        with self._lock:
            packs_info = {
                name: {
                    "tier": pack.tier.value,
                    "status": pack.status.value,
                    "modules": pack.modules,
                    "capabilities": pack.capabilities,
                    "load_time_ms": pack.load_time_ms,
                    "last_activity": pack.last_activity,
                    "error": pack.error,
                }
                for name, pack in self._registry.items()
            }
            return {
                "fallback_mode": self.fallback_mode,
                "in_fallback": self._in_fallback,
                "registered_packs": len(self._registry),
                "active_packs": len(self._active_packs),
                "packs": packs_info,
            }

    # ------------------------------------------------------------------
    # Idle sweep
    # ------------------------------------------------------------------

    async def idle_sweep(self) -> List[str]:
        """Check for idle DOMAIN packs past their timeout and unload them.

        Only ``DOMAIN`` packs are subject to idle eviction.  ``KERNEL`` and
        ``PLATFORM`` packs are permanent.

        Returns
        -------
        List[str]
            Names of packs that were unloaded during this sweep.
        """
        now = time.time()
        to_unload: List[str] = []

        with self._lock:
            for name, pack in self._registry.items():
                if pack.tier != RuntimeTier.DOMAIN:
                    continue
                if pack.status not in (PackStatus.ACTIVE, PackStatus.IDLE):
                    continue
                if pack.idle_timeout_minutes <= 0:
                    continue  # auto-unload disabled for this pack
                if pack.last_activity is None:
                    continue
                idle_seconds = now - pack.last_activity
                timeout_seconds = pack.idle_timeout_minutes * 60
                if idle_seconds >= timeout_seconds:
                    logger.info(
                        "Pack '%s' idle for %.0f s (timeout=%s min) — "
                        "scheduling unload",
                        name,
                        idle_seconds,
                        pack.idle_timeout_minutes,
                    )
                    to_unload.append(name)
                    pack.status = PackStatus.IDLE  # mark before releasing lock

        unloaded: List[str] = []
        for pack_name in to_unload:
            ok = await self.unload_pack(pack_name)
            if ok:
                unloaded.append(pack_name)

        if unloaded:
            logger.info("idle_sweep: unloaded %s", unloaded)

        return unloaded

    # ------------------------------------------------------------------
    # Monolith fallback
    # ------------------------------------------------------------------

    async def fallback_to_monolith(self) -> bool:
        """Emergency: load the original monolith runtime as safety net.

        Imports and boots ``src.runtime.murphy_system_core.MurphySystem``
        exactly as it was before the tiered orchestrator existed.  This
        function is the *only* place in the tiered system that touches the
        monolith files.

        Returns
        -------
        bool
            ``True`` if the monolith started successfully, ``False``
            otherwise.
        """
        logger.critical(
            "═══════════════════════════════════════════════════════\n"
            "  TIERED ORCHESTRATOR ENTERING MONOLITH FALLBACK MODE  \n"
            "  All KERNEL/PLATFORM failures triggered this path.    \n"
            "  System is running on the legacy MurphySystem runtime. \n"
            "═══════════════════════════════════════════════════════"
        )
        try:
            # Imported here — never at module level — so the monolith is
            # not loaded unless the fallback path is actually triggered.
            from src.runtime.murphy_system_core import MurphySystem  # noqa: PLC0415

            murphy = MurphySystem()
            await murphy.startup()  # type: ignore[attr-defined]
            self._monolith = murphy
            self._in_fallback = True
            logger.critical(
                "Monolith fallback ACTIVE — MurphySystem started successfully"
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.critical(
                "Monolith fallback FAILED — system is in an unknown state: %s",
                exc,
                exc_info=True,
            )
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _packs_by_tier(self, tier: RuntimeTier) -> List[RuntimePack]:
        """Return all registered packs of *tier*, in registration order."""
        with self._lock:
            return [p for p in self._registry.values() if p.tier == tier]

    async def _handle_critical_failure(
        self,
        reason: str,
        loaded: List[str],
        failed: List[str],
        start: float,
    ) -> BootResult:
        """Handle a KERNEL / PLATFORM failure according to *fallback_mode*."""
        elapsed_ms = (time.monotonic() - start) * 1000

        if self.fallback_mode == "monolith":
            fallback_ok = await self.fallback_to_monolith()
            return BootResult(
                success=fallback_ok,
                fallback_used=True,
                loaded_packs=loaded,
                failed_packs=failed,
                error=reason,
                boot_time_ms=elapsed_ms,
            )

        if self.fallback_mode == "degraded":
            logger.error(
                "DEGRADED mode: continuing without failed pack. reason=%s",
                reason,
            )
            return BootResult(
                success=True,
                fallback_used=False,
                loaded_packs=loaded,
                failed_packs=failed,
                error=reason,
                boot_time_ms=elapsed_ms,
            )

        # "strict"
        logger.critical(
            "STRICT mode: aborting startup. reason=%s", reason
        )
        return BootResult(
            success=False,
            fallback_used=False,
            loaded_packs=loaded,
            failed_packs=failed,
            error=reason,
            boot_time_ms=elapsed_ms,
        )
