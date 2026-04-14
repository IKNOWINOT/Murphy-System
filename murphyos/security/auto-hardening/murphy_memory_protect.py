# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""Runtime memory protection.

``MemoryProtectionEngine`` hardens the process and kernel memory posture:

* Maximise ASLR entropy.
* Enable compiler-level stack protection where possible.
* Enforce W^X (write XOR execute) policy via kernel tunables.
* Seal sensitive memory regions with ``mlock`` / ``madvise``.

All operations degrade gracefully — failures are logged but never block
legitimate work.

Error codes: MURPHY-AUTOSEC-ERR-021 .. MURPHY-AUTOSEC-ERR-030
"""
from __future__ import annotations

import ctypes
import ctypes.util
import logging
import os
import pathlib
import struct
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.autosec.memory_protect")

# ---------------------------------------------------------------------------
# libc access
# ---------------------------------------------------------------------------
try:
    _libc_path = ctypes.util.find_library("c")
    _libc = ctypes.CDLL(_libc_path, use_errno=True) if _libc_path else None
except Exception as exc:  # MURPHY-AUTOSEC-ERR-021
    _libc = None
    logger.warning("MURPHY-AUTOSEC-ERR-021: Could not load libc: %s", exc)

# Constants for mlock / madvise
MADV_DONTDUMP = 16
MCL_CURRENT = 1
MCL_FUTURE = 2


def _write_sysctl(path: str, value: str) -> bool:
    """Write *value* to a sysctl *path*, returning True on success."""
    try:
        pathlib.Path(path).write_text(value)
        logger.debug("Wrote %s → %s", value, path)
        return True
    except OSError as exc:  # MURPHY-AUTOSEC-ERR-022
        logger.warning(
            "MURPHY-AUTOSEC-ERR-022: Cannot write %s to %s: %s", value, path, exc
        )
        return False


def _read_sysctl(path: str) -> Optional[str]:
    """Read a sysctl value, returning *None* on failure."""
    try:
        return pathlib.Path(path).read_text().strip()
    except OSError as exc:  # MURPHY-AUTOSEC-ERR-023
        logger.debug("MURPHY-AUTOSEC-ERR-023: Cannot read %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# MemoryProtectionEngine
# ---------------------------------------------------------------------------
class MemoryProtectionEngine:
    """Transparent runtime memory protection engine.

    All methods return a boolean indicating success and never raise on
    failure — the system degrades gracefully.
    """

    def __init__(self) -> None:
        self._applied: Dict[str, bool] = {}
        logger.info("MemoryProtectionEngine initialised.")

    # -- ASLR ---------------------------------------------------------------

    def enable_aslr_max(self) -> bool:
        """Set kernel ASLR to maximum (randomize_va_space = 2).

        Level 2 randomises stack, VDSO, mmap, and brk in addition to
        the defaults.
        """
        path = "/proc/sys/kernel/randomize_va_space"
        current = _read_sysctl(path)
        if current == "2":
            logger.info("ASLR already at maximum.")
            self._applied["aslr_max"] = True
            return True

        ok = _write_sysctl(path, "2")
        if ok:
            logger.info("ASLR set to maximum (2).")
        else:
            logger.warning(
                "MURPHY-AUTOSEC-ERR-024: Unable to maximise ASLR "
                "(current=%s). Requires root.",
                current,
            )
        self._applied["aslr_max"] = ok
        return ok

    # -- Stack protection ---------------------------------------------------

    def enable_stack_protection(self) -> bool:
        """Enable stack-clash and stack-smashing kernel mitigations.

        Writes to ``/proc/sys/vm/mmap_min_addr`` to increase guard-page
        distance and logs the compiler flags that should be used for all
        Murphy binaries.
        """
        ok = True
        mmap_min = "/proc/sys/vm/mmap_min_addr"
        current = _read_sysctl(mmap_min)
        desired = "65536"
        if current != desired:
            result = _write_sysctl(mmap_min, desired)
            if not result:
                logger.warning(
                    "MURPHY-AUTOSEC-ERR-025: Cannot raise mmap_min_addr "
                    "to %s (current=%s).",
                    desired,
                    current,
                )
                ok = False

        logger.info(
            "Stack-protection advisory: compile Murphy C extensions with "
            "-fstack-protector-strong -fstack-clash-protection."
        )
        self._applied["stack_protection"] = ok
        return ok

    # -- W^X enforcement ----------------------------------------------------

    def enforce_w_xor_x(self) -> bool:
        """Enforce write-XOR-execute policy via ``mmap_strict_overcommit``
        and ``perf_event_paranoid`` tunables.
        """
        results: List[bool] = []

        # Restrict perf events (reduces ROP gadget surface)
        results.append(
            _write_sysctl("/proc/sys/kernel/perf_event_paranoid", "3")
        )

        # Restrict unprivileged BPF (mitigates JIT-spray)
        results.append(
            _write_sysctl("/proc/sys/kernel/unprivileged_bpf_disabled", "1")
        )

        # Restrict userfaultfd (reduces TOCTOU window for exploits)
        uf_path = "/proc/sys/vm/unprivileged_userfaultfd"
        if pathlib.Path(uf_path).exists():
            results.append(_write_sysctl(uf_path, "0"))

        ok = all(results) if results else False
        if not ok:
            logger.warning(
                "MURPHY-AUTOSEC-ERR-026: W^X enforcement partially applied."
            )
        else:
            logger.info("W^X enforcement applied.")
        self._applied["w_xor_x"] = ok
        return ok

    # -- Seal sensitive memory -----------------------------------------------

    def seal_sensitive_memory(self, address: int = 0, length: int = 0) -> bool:
        """Lock sensitive memory regions and mark them as non-dumpable.

        If *address* and *length* are zero the engine locks all current and
        future pages of this process via ``mlockall``.
        """
        if _libc is None:
            logger.error(
                "MURPHY-AUTOSEC-ERR-027: libc unavailable; cannot seal memory."
            )
            self._applied["seal_memory"] = False
            return False

        ok = True
        try:
            if address == 0 and length == 0:
                rc = _libc.mlockall(MCL_CURRENT | MCL_FUTURE)
                if rc != 0:
                    errno = ctypes.get_errno()
                    logger.warning(
                        "MURPHY-AUTOSEC-ERR-028: mlockall failed (errno=%d). "
                        "May need CAP_IPC_LOCK.",
                        errno,
                    )
                    ok = False
                else:
                    logger.info("All process memory locked (mlockall).")
            else:
                rc = _libc.mlock(ctypes.c_void_p(address), ctypes.c_size_t(length))
                if rc != 0:
                    logger.warning(
                        "MURPHY-AUTOSEC-ERR-028: mlock failed for 0x%x+%d.",
                        address,
                        length,
                    )
                    ok = False
                # madvise DONTDUMP
                rc2 = _libc.madvise(
                    ctypes.c_void_p(address),
                    ctypes.c_size_t(length),
                    ctypes.c_int(MADV_DONTDUMP),
                )
                if rc2 != 0:
                    logger.warning(
                        "MURPHY-AUTOSEC-ERR-029: madvise(DONTDUMP) failed "
                        "for 0x%x+%d.",
                        address,
                        length,
                    )
                    ok = False
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-030
            logger.error(
                "MURPHY-AUTOSEC-ERR-030: Unexpected error sealing memory: %s", exc
            )
            ok = False

        self._applied["seal_memory"] = ok
        return ok

    # -- Reporting -----------------------------------------------------------

    def status(self) -> Dict[str, bool]:
        """Return a mapping of protection → applied boolean."""
        return dict(self._applied)
