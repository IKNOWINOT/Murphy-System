"""
Murphy System — State Validator
Owner: @sec-eng
Phase: 2 — Commissioning Test Infrastructure
Completion: 100%

Validates system state integrity, component states, and automation
persistence. Resolves GAP-007 (no persistent self-improvement state).
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class StateValidator:
    """Validates Murphy System state persistence and integrity.

    Checks that component states, automation configurations, and
    self-improvement data are correctly persisted and retrievable.

    Attributes:
        state_file: Path to the system state file.
        state: Currently loaded state dictionary.
    """

    def __init__(self, state_file: str = ".murphy_persistence/state.json"):
        self.state_file = Path(state_file)
        self.state: Dict[str, Any] = {}

    def load_state(self) -> Dict:
        """Load the current system state from disk.

        Returns:
            The loaded state dictionary.
        """
        if self.state_file.exists():
            with open(self.state_file, "r") as f:
                self.state = json.load(f)
        else:
            self.state = {}
        return self.state

    def save_state(self, state: Optional[Dict] = None):
        """Persist the current state to disk.

        Args:
            state: Optional state to save. If None, saves self.state.
        """
        if state is not None:
            self.state = state

        self.state["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def set_component_state(self, component: str, component_state: Dict):
        """Set the state for a specific component.

        Args:
            component: Component identifier.
            component_state: State dictionary for the component.
        """
        if "components" not in self.state:
            self.state["components"] = {}
        self.state["components"][component] = {
            **component_state,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def validate_component_state(
        self, component: str, expected_state: Dict
    ) -> bool:
        """Verify that a component's state matches expectations.

        Args:
            component: Component identifier.
            expected_state: Dictionary of expected key-value pairs.

        Returns:
            True if all expected values match.

        Raises:
            AssertionError: If state doesn't match expectations.
        """
        components = self.state.get("components", {})
        actual = components.get(component, {})

        for key, value in expected_state.items():
            assert actual.get(key) == value, (
                f"Component '{component}' state mismatch: "
                f"expected {key}={value}, got {key}={actual.get(key)}"
            )
        return True

    def set_automation_state(self, automation_id: str, automation_config: Dict):
        """Set the state for an automation.

        Args:
            automation_id: Automation identifier.
            automation_config: Configuration dictionary.
        """
        if "automations" not in self.state:
            self.state["automations"] = {}
        self.state["automations"][automation_id] = {
            **automation_config,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def validate_automation_enabled(self, automation_id: str) -> bool:
        """Verify that a specific automation is enabled.

        Args:
            automation_id: Automation identifier to check.

        Returns:
            True if the automation exists and is enabled.

        Raises:
            AssertionError: If automation is not found or not enabled.
        """
        automations = self.state.get("automations", {})
        automation = automations.get(automation_id, {})

        assert automation.get("enabled") is True, (
            f"Automation '{automation_id}' is not enabled. "
            f"Current state: {automation}"
        )
        return True

    def validate_state_integrity(self) -> Dict:
        """Run a comprehensive integrity check on the system state.

        Returns:
            Dictionary with check results: passed, failed, warnings.
        """
        results = {"passed": [], "failed": [], "warnings": []}

        # Check required top-level keys
        for key in ["system_version", "components", "automations", "last_updated"]:
            if key in self.state:
                results["passed"].append(f"Required key '{key}' present")
            else:
                results["failed"].append(f"Required key '{key}' missing")

        # Check component states have timestamps
        for comp_name, comp_state in self.state.get("components", {}).items():
            if "updated_at" in comp_state:
                results["passed"].append(f"Component '{comp_name}' has timestamp")
            else:
                results["warnings"].append(
                    f"Component '{comp_name}' missing timestamp"
                )

        # Check automation states have enabled flag
        for auto_id, auto_state in self.state.get("automations", {}).items():
            if "enabled" in auto_state:
                results["passed"].append(f"Automation '{auto_id}' has enabled flag")
            else:
                results["warnings"].append(
                    f"Automation '{auto_id}' missing enabled flag"
                )

        return results

    def get_improvement_history(self) -> List[Dict]:
        """Retrieve self-improvement history from state.

        Returns:
            List of improvement records.
        """
        return self.state.get("improvement_history", [])

    def record_improvement(self, improvement: Dict):
        """Record a self-improvement action.

        Args:
            improvement: Dictionary describing the improvement.
        """
        if "improvement_history" not in self.state:
            self.state["improvement_history"] = []
        self.state["improvement_history"].append({
            **improvement,
            "recorded_at": datetime.now().isoformat(),
        })
