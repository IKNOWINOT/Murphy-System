# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""Master orchestrator for the MurphyOS Auto-Hardening Security Layer.

``AutoSecOrchestrator`` initialises, coordinates, and monitors every
security engine.  It exposes a unified health-check, a 0–100 security
posture score, and a threat summary.  Integration with D-Bus / systemd is
attempted but never required.

Error codes: MURPHY-AUTOSEC-ERR-076 .. MURPHY-AUTOSEC-ERR-085
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.autosec.orchestrator")

# ---------------------------------------------------------------------------
# Local engine imports (deferred to allow partial installs)
# ---------------------------------------------------------------------------
try:
    from .murphy_auto_encrypt import AutoEncryptEngine
except ImportError as exc:  # MURPHY-AUTOSEC-ERR-076
    AutoEncryptEngine = None  # type: ignore[assignment,misc]
    logger.warning("MURPHY-AUTOSEC-ERR-076: AutoEncryptEngine unavailable: %s", exc)

try:
    from .murphy_auto_patch import AutoPatchEngine
except ImportError as exc:  # MURPHY-AUTOSEC-ERR-076
    AutoPatchEngine = None  # type: ignore[assignment,misc]
    logger.warning("MURPHY-AUTOSEC-ERR-076: AutoPatchEngine unavailable: %s", exc)

try:
    from .murphy_memory_protect import MemoryProtectionEngine
except ImportError as exc:  # MURPHY-AUTOSEC-ERR-076
    MemoryProtectionEngine = None  # type: ignore[assignment,misc]
    logger.warning("MURPHY-AUTOSEC-ERR-076: MemoryProtectionEngine unavailable: %s", exc)

try:
    from .murphy_network_sentinel import NetworkSentinel
except ImportError as exc:  # MURPHY-AUTOSEC-ERR-076
    NetworkSentinel = None  # type: ignore[assignment,misc]
    logger.warning("MURPHY-AUTOSEC-ERR-076: NetworkSentinel unavailable: %s", exc)

try:
    from .murphy_credential_vault import CredentialVault
except ImportError as exc:  # MURPHY-AUTOSEC-ERR-076
    CredentialVault = None  # type: ignore[assignment,misc]
    logger.warning("MURPHY-AUTOSEC-ERR-076: CredentialVault unavailable: %s", exc)

try:
    from .murphy_integrity_monitor import IntegrityMonitor
except ImportError as exc:  # MURPHY-AUTOSEC-ERR-076
    IntegrityMonitor = None  # type: ignore[assignment,misc]
    logger.warning("MURPHY-AUTOSEC-ERR-076: IntegrityMonitor unavailable: %s", exc)

# Optional D-Bus / systemd integration
try:
    import dbus  # type: ignore[import-untyped]

    _HAS_DBUS = True
except ImportError:  # MURPHY-AUTOSEC-ERR-077
    _HAS_DBUS = False
    logger.debug("MURPHY-AUTOSEC-ERR-077: D-Bus not available.")

try:
    from systemd import journal as _sd_journal  # type: ignore[import-untyped]

    _HAS_SYSTEMD = True
except ImportError:  # MURPHY-AUTOSEC-ERR-078
    _HAS_SYSTEMD = False
    logger.debug("MURPHY-AUTOSEC-ERR-078: systemd journal not available.")


# ---------------------------------------------------------------------------
# AutoSecOrchestrator
# ---------------------------------------------------------------------------
class AutoSecOrchestrator:
    """Master orchestrator for all auto-hardening security engines.

    Usage::

        orch = AutoSecOrchestrator()
        orch.initialize()          # starts all engines
        print(orch.get_security_posture())   # 0–100
        print(orch.get_threat_summary())
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._engines: Dict[str, Any] = {}
        self._started = False
        self._start_time: float = 0
        self._lock = threading.Lock()
        logger.info("AutoSecOrchestrator created.")

    # -- initialisation -----------------------------------------------------

    def initialize(self) -> Dict[str, bool]:
        """Start every available engine.  Returns a mapping of
        engine-name → success-boolean.
        """
        results: Dict[str, bool] = {}

        # 1. Encryption
        if AutoEncryptEngine is not None:
            try:
                eng = AutoEncryptEngine(
                    pqc_key_provider=self._config.get("pqc_key_provider"),
                )
                self._engines["encrypt"] = eng
                results["encrypt"] = True
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-079
                logger.error("MURPHY-AUTOSEC-ERR-079: Encrypt init failed: %s", exc)
                results["encrypt"] = False
        else:
            results["encrypt"] = False

        # 2. Patch
        if AutoPatchEngine is not None:
            try:
                eng = AutoPatchEngine(
                    patch_url=self._config.get("patch_url", ""),
                )
                self._engines["patch"] = eng
                results["patch"] = True
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-079
                logger.error("MURPHY-AUTOSEC-ERR-079: Patch init failed: %s", exc)
                results["patch"] = False
        else:
            results["patch"] = False

        # 3. Memory protection
        if MemoryProtectionEngine is not None:
            try:
                mem = MemoryProtectionEngine()
                mem.enable_aslr_max()
                mem.enable_stack_protection()
                mem.enforce_w_xor_x()
                mem.seal_sensitive_memory()
                self._engines["memory"] = mem
                results["memory"] = True
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-080
                logger.error("MURPHY-AUTOSEC-ERR-080: Memory init failed: %s", exc)
                results["memory"] = False
        else:
            results["memory"] = False

        # 4. Network sentinel
        if NetworkSentinel is not None:
            try:
                ns = NetworkSentinel(
                    allowlist=set(self._config.get("network_allowlist", [])),
                    block_duration=self._config.get("block_duration", 3600),
                )
                ns.load_state()
                self._engines["network"] = ns
                results["network"] = True
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-081
                logger.error("MURPHY-AUTOSEC-ERR-081: Network init failed: %s", exc)
                results["network"] = False
        else:
            results["network"] = False

        # 5. Credential vault
        if CredentialVault is not None:
            try:
                vault = CredentialVault(
                    pqc_key_provider=self._config.get("pqc_key_provider"),
                )
                self._engines["vault"] = vault
                results["vault"] = True
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-082
                logger.error("MURPHY-AUTOSEC-ERR-082: Vault init failed: %s", exc)
                results["vault"] = False
        else:
            results["vault"] = False

        # 6. Integrity monitor
        if IntegrityMonitor is not None:
            try:
                im = IntegrityMonitor(
                    watched_paths=self._config.get("integrity_paths", []),
                    check_interval=self._config.get("integrity_interval", 300),
                )
                if not im.load_baseline():
                    im.build_baseline()
                im.start()
                self._engines["integrity"] = im
                results["integrity"] = True
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-083
                logger.error("MURPHY-AUTOSEC-ERR-083: Integrity init failed: %s", exc)
                results["integrity"] = False
        else:
            results["integrity"] = False

        self._started = True
        self._start_time = time.time()
        self._notify_systemd("READY=1")
        logger.info("AutoSecOrchestrator initialised: %s", results)
        return results

    # -- health & posture ---------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Return engine-level health information."""
        health: Dict[str, Any] = {
            "started": self._started,
            "uptime_seconds": time.time() - self._start_time if self._started else 0,
            "engines": {},
        }
        for name, eng in self._engines.items():
            try:
                if hasattr(eng, "status"):
                    health["engines"][name] = {"ok": True, "detail": eng.status()}
                else:
                    health["engines"][name] = {"ok": True}
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-084
                logger.error(
                    "MURPHY-AUTOSEC-ERR-084: Health check failed for %s: %s",
                    name,
                    exc,
                )
                health["engines"][name] = {"ok": False, "error": str(exc)}
        return health

    def get_security_posture(self) -> int:
        """Compute a security posture score from 0 (unprotected) to 100.

        Each engine contributes equal weight; partial credit is given
        for engines that are running but report degraded status.
        """
        if not self._engines:
            return 0

        total_engines = 6  # max possible
        active = len(self._engines)
        base_score = int((active / total_engines) * 80)

        # Bonus for clean integrity + no active threats
        bonus = 0
        if "integrity" in self._engines:
            try:
                changed = self._engines["integrity"].verify_integrity()
                if not changed:
                    bonus += 10
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-084
                logger.debug("MURPHY-AUTOSEC-ERR-084: Integrity score error: %s", exc)

        if "network" in self._engines:
            try:
                summary = self._engines["network"].threat_summary()
                if summary.get("active_blocks", 0) == 0:
                    bonus += 10
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-084
                logger.debug("MURPHY-AUTOSEC-ERR-084: Network score error: %s", exc)

        return min(base_score + bonus, 100)

    def get_threat_summary(self) -> Dict[str, Any]:
        """Aggregate threat information from all engines."""
        summary: Dict[str, Any] = {"timestamp": time.time(), "engines": {}}

        if "network" in self._engines:
            try:
                summary["engines"]["network"] = self._engines["network"].threat_summary()
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-085
                logger.error("MURPHY-AUTOSEC-ERR-085: Threat summary error (network): %s", exc)

        if "vault" in self._engines:
            try:
                overdue = self._engines["vault"].check_breach_indicators()
                summary["engines"]["vault"] = {"overdue_rotations": overdue}
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-085
                logger.error("MURPHY-AUTOSEC-ERR-085: Threat summary error (vault): %s", exc)

        if "integrity" in self._engines:
            try:
                changed = self._engines["integrity"].verify_integrity()
                summary["engines"]["integrity"] = {"tampered_files": changed}
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-085
                logger.error("MURPHY-AUTOSEC-ERR-085: Threat summary error (integrity): %s", exc)

        return summary

    # -- systemd / D-Bus integration ----------------------------------------

    def _notify_systemd(self, state: str) -> None:
        """Send a systemd notification (best-effort)."""
        if _HAS_SYSTEMD:
            try:
                _sd_journal.send(f"MurphyOS AutoSec: {state}")
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-078
                logger.debug("MURPHY-AUTOSEC-ERR-078: systemd notify failed: %s", exc)

    # -- shutdown -----------------------------------------------------------

    def shutdown(self) -> None:
        """Gracefully stop all engines."""
        logger.info("AutoSecOrchestrator shutting down …")
        for name, eng in self._engines.items():
            if hasattr(eng, "stop"):
                try:
                    eng.stop()
                except Exception as exc:  # MURPHY-AUTOSEC-ERR-084
                    logger.error(
                        "MURPHY-AUTOSEC-ERR-084: Shutdown error for %s: %s", name, exc
                    )
            if hasattr(eng, "save_state"):
                try:
                    eng.save_state()
                except Exception as exc:  # MURPHY-AUTOSEC-ERR-084
                    logger.error(
                        "MURPHY-AUTOSEC-ERR-084: State save error for %s: %s", name, exc
                    )
        self._started = False
        self._notify_systemd("STOPPING=1")
        logger.info("AutoSecOrchestrator shutdown complete.")
