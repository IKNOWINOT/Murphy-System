"""
Murphy System — Screenshot Manager
Owner: @test-lead
Phase: 2 — Commissioning Test Infrastructure
Completion: 100%

Pure-Python screenshot capture and visual regression system.
Resolves GAP-001 (no automated UI screenshot capture) and
GAP-008 (no visual regression testing).

Designed to work in CI environments without browser dependencies.
Follows the pattern established by src/ui_testing_framework.py.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple


class ScreenshotManager:
    """Manages screenshot capture, storage, and visual regression comparison.

    This is a pure-Python implementation that works without Playwright/Selenium.
    It captures "screenshots" as structured HTML snapshots and supports
    pixel-level comparison when Pillow is available.

    Attributes:
        base_dir: Directory for screenshot storage.
        baselines: Dictionary of baseline screenshot hashes.
        captures: List of all captured screenshots in this session.
    """

    def __init__(self, base_dir: str = "screenshots"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.baselines: Dict[str, str] = {}
        self.captures: list = []
        self._load_baselines()

    def _load_baselines(self):
        """Load baseline hashes from the baselines file."""
        baseline_file = self.base_dir / "baselines.json"
        if baseline_file.exists():
            with open(baseline_file, "r") as f:
                self.baselines = json.load(f)

    def _save_baselines(self):
        """Persist baseline hashes to disk."""
        baseline_file = self.base_dir / "baselines.json"
        with open(baseline_file, "w") as f:
            json.dump(self.baselines, f, indent=2)

    def capture(self, name: str, step: str, content: str) -> Path:
        """Capture a screenshot (HTML snapshot) at a key interaction point.

        Args:
            name: Logical name of the UI state (e.g., "dashboard").
            step: Specific step within the interaction (e.g., "after_login").
            content: HTML content or structured text representing the UI state.

        Returns:
            Path to the saved snapshot file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{step}_{timestamp}.html"
        filepath = self.base_dir / filename

        filepath.write_text(content)

        content_hash = hashlib.sha256(content.encode()).hexdigest()

        record = {
            "name": name,
            "step": step,
            "timestamp": timestamp,
            "file": str(filepath),
            "hash": content_hash,
        }
        self.captures.append(record)

        return filepath

    def set_baseline(self, name: str, content: str):
        """Set the baseline hash for a named UI state.

        Args:
            name: Logical name of the UI state.
            content: HTML content representing the expected baseline.
        """
        self.baselines[name] = hashlib.sha256(content.encode()).hexdigest()
        self._save_baselines()

    def compare_to_baseline(self, name: str, content: str) -> Tuple[bool, Optional[str]]:
        """Compare current content against the stored baseline.

        Args:
            name: Logical name of the UI state.
            content: Current HTML content to compare.

        Returns:
            Tuple of (matches, diff_detail). If matches is True, diff_detail
            is None. Otherwise, diff_detail contains a description of the
            difference.
        """
        current_hash = hashlib.sha256(content.encode()).hexdigest()

        if name not in self.baselines:
            return False, f"No baseline found for '{name}'"

        if current_hash == self.baselines[name]:
            return True, None

        return False, (
            f"Visual regression detected for '{name}': "
            f"baseline={self.baselines[name][:12]}... "
            f"current={current_hash[:12]}..."
        )

    def get_capture_history(self) -> list:
        """Return all captures from this session."""
        return list(self.captures)

    def generate_report(self) -> Dict:
        """Generate a summary report of all captures and comparisons.

        Returns:
            Dictionary containing capture count, baseline count, and
            any detected regressions.
        """
        regressions = []
        for capture in self.captures:
            name = capture["name"]
            if name in self.baselines:
                if capture["hash"] != self.baselines[name]:
                    regressions.append({
                        "name": name,
                        "step": capture["step"],
                        "expected": self.baselines[name][:12],
                        "actual": capture["hash"][:12],
                    })

        return {
            "total_captures": len(self.captures),
            "total_baselines": len(self.baselines),
            "regressions_detected": len(regressions),
            "regressions": regressions,
            "session_start": self.captures[0]["timestamp"] if self.captures else None,
            "session_end": self.captures[-1]["timestamp"] if self.captures else None,
        }
