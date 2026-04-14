# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""MurphyOS journald structured logging integration.

Bridges Murphy Event Backbone events to systemd-journald structured fields so
that every confidence change, gate decision, swarm lifecycle event, security
alert, and LLM request is queryable via ``journalctl``.

When ``python-systemd`` is installed the module writes structured entries
directly through the C journal API.  Otherwise it falls back to the
``/usr/bin/logger`` command so that the integration works inside minimal
containers and CI runners.

Typical usage::

    from murphy_journal import MurphyJournal

    journal = MurphyJournal()
    journal.log_confidence_change(old_score=0.72, new_score=0.85)
    journal.log_gate_decision("deploy", "allow", confidence=0.85)

    # Query recent events
    for entry in journal.query_events(event_type="confidence", limit=10):
        print(entry)
"""
from __future__ import annotations

import datetime
import json
import logging
import shutil
import subprocess
import uuid
from typing import Any, Dict, Iterator, List, Optional, Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOG = logging.getLogger("murphy.journal")

SYSLOG_IDENTIFIER = "murphy-system"

VALID_EVENT_TYPES = frozenset({
    "confidence",
    "gate",
    "swarm",
    "forge",
    "security",
    "llm",
    "automation",
})

VALID_SEVERITIES = frozenset({
    "emergency",
    "alert",
    "critical",
    "error",
    "warning",
    "notice",
    "info",
    "debug",
})

# Map Murphy severity names to syslog numeric priority (RFC 5424).
_SEVERITY_PRIORITY: Dict[str, int] = {
    "emergency": 0,
    "alert":     1,
    "critical":  2,
    "error":     3,
    "warning":   4,
    "notice":    5,
    "info":      6,
    "debug":     7,
}

# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

_ERR_001 = "MURPHY-JOURNAL-ERR-001"  # python-systemd unavailable; using logger fallback
_ERR_002 = "MURPHY-JOURNAL-ERR-002"  # logger binary not found on PATH
_ERR_003 = "MURPHY-JOURNAL-ERR-003"  # journal send failed
_ERR_004 = "MURPHY-JOURNAL-ERR-004"  # invalid event type
_ERR_005 = "MURPHY-JOURNAL-ERR-005"  # invalid severity level
_ERR_006 = "MURPHY-JOURNAL-ERR-006"  # journal query failed
_ERR_007 = "MURPHY-JOURNAL-ERR-007"  # subprocess logger invocation failed
_ERR_008 = "MURPHY-JOURNAL-ERR-008"  # timestamp parse error

# ---------------------------------------------------------------------------
# Optional python-systemd import
# ---------------------------------------------------------------------------

_HAS_SYSTEMD = False
_journal_mod: Any = None

try:
    from systemd import journal as _journal_mod  # type: ignore[import-untyped]
    _HAS_SYSTEMD = True
except ImportError:  # MURPHY-JOURNAL-ERR-001
    _LOG.info(
        "%s: python-systemd not installed; falling back to logger(1)",
        _ERR_001,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _validate_event_type(event_type: str) -> None:
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"{_ERR_004}: unknown event type {event_type!r}; "
            f"expected one of {sorted(VALID_EVENT_TYPES)}"
        )


def _validate_severity(severity: str) -> None:
    if severity not in VALID_SEVERITIES:
        raise ValueError(
            f"{_ERR_005}: unknown severity {severity!r}; "
            f"expected one of {sorted(VALID_SEVERITIES)}"
        )


# ---------------------------------------------------------------------------
# MurphyJournal
# ---------------------------------------------------------------------------

class MurphyJournal:
    """Bridge between Murphy Event Backbone and systemd-journald.

    Parameters
    ----------
    syslog_identifier:
        Value written to the ``SYSLOG_IDENTIFIER`` journal field.
        Defaults to ``"murphy-system"``.
    """

    def __init__(self, syslog_identifier: str = SYSLOG_IDENTIFIER) -> None:
        self._syslog_id = syslog_identifier
        self._use_native = _HAS_SYSTEMD
        self._logger_bin: Optional[str] = None

        if not self._use_native:
            self._logger_bin = shutil.which("logger")
            if self._logger_bin is None:  # MURPHY-JOURNAL-ERR-002
                _LOG.warning(
                    "%s: logger(1) not found on PATH; journal writes disabled",
                    _ERR_002,
                )

    # -- public helpers -----------------------------------------------------

    @property
    def backend(self) -> str:
        """Return ``"systemd"``, ``"logger"``, or ``"none"``."""
        if self._use_native:
            return "systemd"
        if self._logger_bin is not None:
            return "logger"
        return "none"

    # -- core write ---------------------------------------------------------

    def log_event(
        self,
        event_type: str,
        message: str,
        severity: str = "info",
        **fields: Any,
    ) -> None:
        """Write a structured journal entry.

        Parameters
        ----------
        event_type:
            One of the ``VALID_EVENT_TYPES`` categories.
        message:
            Human-readable log message (``MESSAGE`` field).
        severity:
            One of ``VALID_SEVERITIES``.
        **fields:
            Additional structured fields (keys are upper-cased automatically).
        """
        _validate_event_type(event_type)
        _validate_severity(severity)

        structured: Dict[str, str] = {
            "MURPHY_EVENT_TYPE": event_type,
            "MURPHY_SEVERITY": severity,
            "SYSLOG_IDENTIFIER": self._syslog_id,
            "PRIORITY": str(_SEVERITY_PRIORITY[severity]),
        }
        for key, value in fields.items():
            structured[key.upper()] = str(value)

        if self._use_native:
            self._send_native(message, structured)
        elif self._logger_bin is not None:
            self._send_logger(message, severity, structured)
        else:
            _LOG.debug("journal write skipped (no backend): %s", message)

    # -- convenience methods ------------------------------------------------

    def log_confidence_change(
        self,
        old_score: float,
        new_score: float,
    ) -> None:
        """Log a Murphy Fractal Governance Confidence transition."""
        direction = "increased" if new_score > old_score else "decreased"
        self.log_event(
            event_type="confidence",
            message=(
                f"MFGC confidence {direction}: {old_score:.4f} → {new_score:.4f}"
            ),
            severity="notice" if abs(new_score - old_score) > 0.1 else "info",
            MURPHY_CONFIDENCE=f"{new_score:.4f}",
            MURPHY_CONFIDENCE_OLD=f"{old_score:.4f}",
        )

    def log_gate_decision(
        self,
        gate_name: str,
        action: str,
        confidence: float,
    ) -> None:
        """Log a governance gate allow / deny / escalate decision."""
        self.log_event(
            event_type="gate",
            message=f"Gate {gate_name!r} → {action} (confidence={confidence:.4f})",
            severity="warning" if action == "deny" else "info",
            MURPHY_CONFIDENCE=f"{confidence:.4f}",
            MURPHY_GATE_NAME=gate_name,
            MURPHY_GATE_ACTION=action,
        )

    def log_swarm_lifecycle(
        self,
        agent_id: str,
        action: str,
        role: str = "",
    ) -> None:
        """Log an agent spawn / kill / error lifecycle event."""
        self.log_event(
            event_type="swarm",
            message=f"Swarm agent {agent_id} {action}" + (f" role={role}" if role else ""),
            severity="error" if action == "error" else "info",
            MURPHY_AGENT_ID=agent_id,
            MURPHY_SWARM_ACTION=action,
            MURPHY_SWARM_ROLE=role,
        )

    def log_security_event(
        self,
        engine: str,
        event: str,
        severity: str = "warning",
    ) -> None:
        """Log a Murphy security-engine event."""
        _validate_severity(severity)
        self.log_event(
            event_type="security",
            message=f"Security [{engine}]: {event}",
            severity=severity,
            MURPHY_SECURITY_ENGINE=engine,
        )

    def log_llm_request(
        self,
        provider: str,
        model: str,
        tokens: int,
        latency_ms: float,
    ) -> None:
        """Log an LLM inference request for cost / performance tracking."""
        self.log_event(
            event_type="llm",
            message=(
                f"LLM {provider}/{model}: {tokens} tokens in {latency_ms:.0f}ms"
            ),
            severity="info",
            MURPHY_LLM_PROVIDER=provider,
            MURPHY_LLM_MODEL=model,
            MURPHY_LLM_TOKENS=str(tokens),
            MURPHY_LLM_LATENCY_MS=f"{latency_ms:.1f}",
        )

    # -- query --------------------------------------------------------------

    def query_events(
        self,
        since: Optional[str] = None,
        until: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, str]]:
        """Query the journal for Murphy events.

        Parameters
        ----------
        since:
            ISO-8601 timestamp or systemd time-span (e.g. ``"-1h"``).
        until:
            ISO-8601 timestamp or systemd time-span.
        event_type:
            Optional filter on ``MURPHY_EVENT_TYPE``.
        limit:
            Maximum entries to return (default 100).

        Returns
        -------
        list[dict[str, str]]
            Journal entries as flat dictionaries.
        """
        if event_type is not None:
            _validate_event_type(event_type)

        if self._use_native:
            return self._query_native(since, until, event_type, limit)
        return self._query_journalctl(since, until, event_type, limit)

    # -- private: native systemd backend ------------------------------------

    def _send_native(
        self,
        message: str,
        fields: Dict[str, str],
    ) -> None:
        """Send a structured entry via python-systemd."""
        try:
            _journal_mod.send(MESSAGE=message, **fields)  # type: ignore[union-attr]
        except Exception as exc:  # MURPHY-JOURNAL-ERR-003
            _LOG.error(
                "%s: journal send failed: %s", _ERR_003, exc,
            )

    def _query_native(
        self,
        since: Optional[str],
        until: Optional[str],
        event_type: Optional[str],
        limit: int,
    ) -> List[Dict[str, str]]:
        """Query journal using python-systemd reader."""
        results: List[Dict[str, str]] = []
        try:
            reader = _journal_mod.Reader()  # type: ignore[union-attr]
            reader.add_match(SYSLOG_IDENTIFIER=self._syslog_id)
            if event_type:
                reader.add_match(MURPHY_EVENT_TYPE=event_type)
            if since:
                reader.seek_realtime(self._parse_timestamp(since))
            for entry in reader:
                results.append(
                    {k: str(v) for k, v in entry.items() if isinstance(k, str)}
                )
                if len(results) >= limit:
                    break
        except Exception as exc:  # MURPHY-JOURNAL-ERR-006
            _LOG.error("%s: native query failed: %s", _ERR_006, exc)
        return results

    # -- private: logger(1) fallback ----------------------------------------

    def _send_logger(
        self,
        message: str,
        severity: str,
        fields: Dict[str, str],
    ) -> None:
        """Send an entry via the ``logger`` command."""
        priority = _SEVERITY_PRIORITY.get(severity, 6)
        tag = fields.get("SYSLOG_IDENTIFIER", self._syslog_id)

        # Encode structured data as SD-ELEMENT per RFC 5424.
        sd_pairs = " ".join(
            f'{k}="{v}"' for k, v in sorted(fields.items())
            if k not in ("SYSLOG_IDENTIFIER", "PRIORITY")
        )
        full_message = f"[murphy {sd_pairs}] {message}" if sd_pairs else message

        cmd: List[str] = [
            self._logger_bin,  # type: ignore[list-item]
            "--journald" if self._has_logger_journald() else "--id",
            "-t", tag,
            "-p", f"user.{severity}" if priority <= 4 else f"local0.{severity}",
            full_message,
        ]
        try:
            subprocess.run(  # noqa: S603
                cmd,
                check=True,
                capture_output=True,
                timeout=5,
            )
        except subprocess.SubprocessError as exc:  # MURPHY-JOURNAL-ERR-007
            _LOG.error("%s: logger(1) invocation failed: %s", _ERR_007, exc)

    def _query_journalctl(
        self,
        since: Optional[str],
        until: Optional[str],
        event_type: Optional[str],
        limit: int,
    ) -> List[Dict[str, str]]:
        """Query journal via ``journalctl`` subprocess."""
        cmd: List[str] = [
            "journalctl",
            "--output=json",
            "--no-pager",
            f"--lines={limit}",
            f"SYSLOG_IDENTIFIER={self._syslog_id}",
        ]
        if event_type:
            cmd.append(f"MURPHY_EVENT_TYPE={event_type}")
        if since:
            cmd.extend(["--since", since])
        if until:
            cmd.extend(["--until", until])

        results: List[Dict[str, str]] = []
        try:
            proc = subprocess.run(  # noqa: S603, S607
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            for line in proc.stdout.strip().splitlines():
                if line:
                    results.append(json.loads(line))
        except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
            # MURPHY-JOURNAL-ERR-006
            _LOG.error("%s: journalctl query failed: %s", _ERR_006, exc)
        return results

    # -- private: helpers ---------------------------------------------------

    @staticmethod
    def _has_logger_journald() -> bool:
        """Return *True* if ``logger --journald`` is supported."""
        try:
            proc = subprocess.run(  # noqa: S603, S607
                ["logger", "--journald", "--help"],
                capture_output=True,
                timeout=3,
            )
            return proc.returncode == 0
        except (FileNotFoundError, subprocess.SubprocessError):
            return False

    @staticmethod
    def _parse_timestamp(value: str) -> datetime.datetime:
        """Parse an ISO-8601 timestamp into a *datetime* object."""
        try:
            return datetime.datetime.fromisoformat(value)
        except ValueError as exc:  # MURPHY-JOURNAL-ERR-008
            _LOG.warning(
                "%s: could not parse timestamp %r: %s", _ERR_008, value, exc,
            )
            return datetime.datetime.now(datetime.timezone.utc)
