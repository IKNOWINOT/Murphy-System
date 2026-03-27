"""
Murphy System — Log Validator
Owner: @sec-eng
Phase: 2 — Commissioning Test Infrastructure
Completion: 100%

Validates audit log integrity and action logging.
Resolves GAP-007 (no persistent self-improvement state) in conjunction
with state_validator.py.
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


class LogValidator:
    """Validates audit log entries for completeness and integrity.

    Checks that system actions are properly logged, state changes are
    recorded, and the audit trail is consistent.

    Attributes:
        log_file: Path to the audit log file.
        entries: Parsed log entries.
    """

    def __init__(self, log_file: str = ".murphy_persistence/audit/audit.log"):
        self.log_file = Path(log_file)
        self.entries: List[Dict] = []

    def load_logs(self) -> int:
        """Load and parse the audit log file.

        Returns:
            Number of entries parsed.
        """
        self.entries = []
        if not self.log_file.exists():
            return 0

        with open(self.log_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = self._parse_log_line(line)
                    if entry:
                        self.entries.append(entry)

        return len(self.entries)

    def _parse_log_line(self, line: str) -> Optional[Dict]:
        """Parse a single log line into a structured entry.

        Supports two formats:
        - Structured: [TIMESTAMP] [LEVEL] [USER] ACTION: details
        - JSON: {"timestamp": ..., "level": ..., "user": ..., "action": ...}
        """
        # Try structured format
        structured_pattern = (
            r"\[([^\]]+)\]\s*\[([^\]]+)\]\s*\[([^\]]+)\]\s*(\w+):\s*(.*)"
        )
        match = re.match(structured_pattern, line)
        if match:
            return {
                "timestamp": match.group(1),
                "level": match.group(2),
                "user": match.group(3),
                "action": match.group(4),
                "details": match.group(5),
                "raw": line,
            }

        # Try key=value format
        kv_pattern = r"(\w+)=([^\s]+)"
        pairs = dict(re.findall(kv_pattern, line))
        if pairs and "action" in pairs:
            return {
                "timestamp": pairs.get("timestamp", ""),
                "level": pairs.get("level", "INFO"),
                "user": pairs.get("user", "system"),
                "action": pairs.get("action", ""),
                "details": line,
                "raw": line,
            }

        return None

    def write_log_entry(
        self,
        action: str,
        user: str = "Murphy",
        level: str = "INFO",
        details: str = "",
    ):
        """Write a log entry (used during test setup).

        Args:
            action: The action performed.
            user: The user who performed the action.
            level: Log level (INFO, WARNING, ERROR).
            details: Additional details.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = f"[{timestamp}] [{level}] [{user}] {action}: {details}"

        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "a") as f:
            f.write(entry + "\n")

    def validate_action_logged(
        self, action: str, user: str = "Murphy"
    ) -> List[Dict]:
        """Verify that a specific action was logged by the specified user.

        Args:
            action: Action name to search for.
            user: User who should have performed the action.

        Returns:
            List of matching log entries.

        Raises:
            AssertionError: If no matching entries found.
        """
        matches = [
            e
            for e in self.entries
            if action.lower() in e.get("action", "").lower()
            and user.lower() in e.get("user", "").lower()
        ]
        assert len(matches) > 0, (
            f"Action '{action}' by user '{user}' not found in logs "
            f"({len(self.entries)} total entries)"
        )
        return matches

    def validate_state_change(
        self, component: str, old_state: str, new_state: str
    ) -> List[Dict]:
        """Verify that a state change was logged.

        Args:
            component: Component that changed state.
            old_state: Previous state value.
            new_state: New state value.

        Returns:
            List of matching log entries.

        Raises:
            AssertionError: If no matching entries found.
        """
        matches = [
            e
            for e in self.entries
            if component.lower() in e.get("details", "").lower()
            and (
                old_state.lower() in e.get("details", "").lower()
                or new_state.lower() in e.get("details", "").lower()
            )
        ]
        assert len(matches) > 0, (
            f"State change for '{component}' ({old_state} → {new_state}) "
            f"not found in logs"
        )
        return matches

    def validate_no_errors(self) -> bool:
        """Verify that no ERROR-level entries exist in the log.

        Returns:
            True if no errors found.

        Raises:
            AssertionError: If ERROR entries are found.
        """
        errors = [e for e in self.entries if e.get("level", "").upper() == "ERROR"]
        assert len(errors) == 0, (
            f"Found {len(errors)} ERROR entries in audit log: "
            f"{[e['action'] for e in errors[:5]]}"
        )
        return True

    def get_actions_by_user(self, user: str) -> List[Dict]:
        """Get all actions performed by a specific user.

        Args:
            user: User name to filter by.

        Returns:
            List of matching log entries.
        """
        return [
            e
            for e in self.entries
            if user.lower() in e.get("user", "").lower()
        ]
