# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""MurphyOS Auto-Hardening Security Layer.

Philosophy: "Humans don't want to perform security — the system keeps our
stuff secure for us."  Every mechanism is automatic, invisible to users,
and never blocks legitimate work.

Exports
-------
AutoSecOrchestrator : class
    Master orchestrator that initialises and coordinates all security engines.
"""
from __future__ import annotations

from .murphy_autosec_orchestrator import AutoSecOrchestrator

__all__ = ["AutoSecOrchestrator"]
