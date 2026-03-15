"""
UI Test Completeness Framework

Provides comprehensive UI testing coverage without browser dependencies.
Validates component contracts, data shapes, accessibility, responsive layouts,
and user interaction flows programmatically.

All methods return dictionaries suitable for JSON serialization.
Thread-safe via threading.Lock on shared state.
"""

import copy
import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ============================================================================
# Component Contract Validator
# ============================================================================

class ComponentContractValidator:
    """Validates UI component contracts: props, state, events, render output."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._registered: Dict[str, Dict[str, Any]] = {}

    def register_component(
        self,
        name: str,
        required_props: List[str],
        optional_props: Optional[List[str]] = None,
        state_fields: Optional[List[str]] = None,
        events: Optional[List[str]] = None,
        render_output_keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Register a component contract specification."""
        contract: Dict[str, Any] = {
            "name": name,
            "required_props": list(required_props),
            "optional_props": list(optional_props or []),
            "state_fields": list(state_fields or []),
            "events": list(events or []),
            "render_output_keys": list(render_output_keys or []),
        }
        with self._lock:
            self._registered[name] = contract
        return {"registered": True, "component": name}

    def validate_props(self, name: str, props: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that supplied props satisfy the component contract."""
        with self._lock:
            contract = self._registered.get(name)
        if contract is None:
            return {"valid": False, "errors": [f"Component '{name}' not registered"]}

        errors: List[str] = []
        for rp in contract["required_props"]:
            if rp not in props:
                errors.append(f"Missing required prop: {rp}")

        allowed = set(contract["required_props"]) | set(contract["optional_props"])
        for key in props:
            if key not in allowed:
                errors.append(f"Unknown prop: {key}")

        return {"valid": len(errors) == 0, "errors": errors}

    def validate_state(self, name: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Validate component state against its contract."""
        with self._lock:
            contract = self._registered.get(name)
        if contract is None:
            return {"valid": False, "errors": [f"Component '{name}' not registered"]}

        errors: List[str] = []
        expected = set(contract["state_fields"])
        for key in state:
            if key not in expected:
                errors.append(f"Unexpected state field: {key}")
        for key in expected:
            if key not in state:
                errors.append(f"Missing state field: {key}")

        return {"valid": len(errors) == 0, "errors": errors}

    def validate_events(self, name: str, event_names: List[str]) -> Dict[str, Any]:
        """Validate that emitted events are declared in the contract."""
        with self._lock:
            contract = self._registered.get(name)
        if contract is None:
            return {"valid": False, "errors": [f"Component '{name}' not registered"]}

        errors: List[str] = []
        allowed = set(contract["events"])
        for ev in event_names:
            if ev not in allowed:
                errors.append(f"Undeclared event: {ev}")

        return {"valid": len(errors) == 0, "errors": errors}

    def validate_render_output(self, name: str, output: Dict[str, Any]) -> Dict[str, Any]:
        """Validate render output contains all expected keys."""
        with self._lock:
            contract = self._registered.get(name)
        if contract is None:
            return {"valid": False, "errors": [f"Component '{name}' not registered"]}

        errors: List[str] = []
        for key in contract["render_output_keys"]:
            if key not in output:
                errors.append(f"Missing render output key: {key}")

        return {"valid": len(errors) == 0, "errors": errors}

    def get_contract(self, name: str) -> Dict[str, Any]:
        """Return the registered contract for a component."""
        with self._lock:
            contract = self._registered.get(name)
        if contract is None:
            return {"found": False, "contract": None}
        return {"found": True, "contract": copy.deepcopy(contract)}

    def list_components(self) -> Dict[str, Any]:
        """List all registered component names."""
        with self._lock:
            names = list(self._registered.keys())
        return {"components": names, "count": len(names)}


# ============================================================================
# Data Shape Validator
# ============================================================================

class DataShapeValidator:
    """Validates API response data shapes against expected schemas."""

    # Built-in schemas for common Murphy endpoints
    BUILTIN_SCHEMAS: Dict[str, Dict[str, Any]] = {
        "status_endpoint": {
            "required_fields": ["status", "uptime", "version"],
            "field_types": {"status": str, "uptime": (int, float), "version": str},
        },
        "execution_summary": {
            "required_fields": ["task_id", "status", "started_at", "duration"],
            "field_types": {
                "task_id": str,
                "status": str,
                "started_at": str,
                "duration": (int, float),
            },
        },
        "module_catalog": {
            "required_fields": ["modules", "total_count"],
            "field_types": {"modules": list, "total_count": int},
        },
    }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._custom_schemas: Dict[str, Dict[str, Any]] = {}

    def register_schema(
        self,
        name: str,
        required_fields: List[str],
        field_types: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a custom data shape schema."""
        schema: Dict[str, Any] = {
            "required_fields": list(required_fields),
            "field_types": dict(field_types or {}),
        }
        with self._lock:
            self._custom_schemas[name] = schema
        return {"registered": True, "schema": name}

    def _resolve_schema(self, schema_name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            custom = self._custom_schemas.get(schema_name)
        if custom is not None:
            return custom
        return self.BUILTIN_SCHEMAS.get(schema_name)

    def validate(self, schema_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate *data* against the named schema."""
        schema = self._resolve_schema(schema_name)
        if schema is None:
            return {"valid": False, "errors": [f"Schema '{schema_name}' not found"]}

        errors: List[str] = []
        for field in schema["required_fields"]:
            if field not in data:
                errors.append(f"Missing required field: {field}")

        for field, expected_type in schema.get("field_types", {}).items():
            if field in data:
                if not isinstance(data[field], expected_type):
                    errors.append(
                        f"Field '{field}' expected type {expected_type}, "
                        f"got {type(data[field]).__name__}"
                    )

        return {"valid": len(errors) == 0, "errors": errors}

    def validate_list_items(
        self, schema_name: str, items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate every item in a list against a schema."""
        results: List[Dict[str, Any]] = []
        all_valid = True
        for idx, item in enumerate(items):
            r = self.validate(schema_name, item)
            r["index"] = idx
            results.append(r)
            if not r["valid"]:
                all_valid = False
        return {"all_valid": all_valid, "results": results, "total": len(items)}

    def list_schemas(self) -> Dict[str, Any]:
        """Return names of all available schemas."""
        with self._lock:
            custom = list(self._custom_schemas.keys())
        builtin = list(self.BUILTIN_SCHEMAS.keys())
        return {"builtin": builtin, "custom": custom}


# ============================================================================
# Accessibility Checker
# ============================================================================

_WCAG_AA_CONTRAST = 4.5
_WCAG_AA_LARGE_CONTRAST = 3.0


def _relative_luminance(r: int, g: int, b: int) -> float:
    """Compute WCAG relative luminance from sRGB 0-255 values."""
    channels = []
    for c in (r, g, b):
        s = c / 255.0
        channels.append(s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_ratio(fg: Tuple[int, int, int], bg: Tuple[int, int, int]) -> float:
    l1 = _relative_luminance(*fg)
    l2 = _relative_luminance(*bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class AccessibilityChecker:
    """Validates WCAG compliance for color contrast, ARIA, keyboard nav, and screen reader support."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._results: List[Dict[str, Any]] = []

    def check_color_contrast(
        self,
        fg: Tuple[int, int, int],
        bg: Tuple[int, int, int],
        large_text: bool = False,
    ) -> Dict[str, Any]:
        """Check WCAG AA color contrast ratio."""
        ratio = round(_contrast_ratio(fg, bg), 2)
        threshold = _WCAG_AA_LARGE_CONTRAST if large_text else _WCAG_AA_CONTRAST
        passed = ratio >= threshold
        result = {
            "check": "color_contrast",
            "ratio": ratio,
            "threshold": threshold,
            "large_text": large_text,
            "passed": passed,
        }
        with self._lock:
            capped_append(self._results, result)
        return result

    def check_aria_labels(self, elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate elements have required ARIA attributes."""
        issues: List[str] = []
        for elem in elements:
            tag = elem.get("tag", "unknown")
            role = elem.get("role")
            aria_label = elem.get("aria-label")
            aria_labelledby = elem.get("aria-labelledby")

            interactive = tag in ("button", "input", "select", "textarea", "a")
            if interactive and not aria_label and not aria_labelledby and not elem.get("text"):
                issues.append(f"<{tag}> missing accessible label")

            if role and role not in (
                "button", "checkbox", "dialog", "link", "menu",
                "menuitem", "navigation", "search", "tab", "tabpanel",
                "alert", "status", "progressbar", "textbox", "listbox",
                "option", "grid", "row", "cell", "banner", "main",
                "complementary", "contentinfo", "form", "region",
            ):
                issues.append(f"<{tag}> has unrecognized role '{role}'")

        passed = len(issues) == 0
        result = {"check": "aria_labels", "passed": passed, "issues": issues, "element_count": len(elements)}
        with self._lock:
            capped_append(self._results, result)
        return result

    def check_keyboard_navigation(self, tab_order: List[str]) -> Dict[str, Any]:
        """Validate keyboard tab order is logical (non-empty, no duplicates)."""
        issues: List[str] = []
        if not tab_order:
            issues.append("Empty tab order")
        seen: set = set()
        for item in tab_order:
            if item in seen:
                issues.append(f"Duplicate tab stop: {item}")
            seen.add(item)

        passed = len(issues) == 0
        result = {"check": "keyboard_navigation", "passed": passed, "issues": issues, "tab_stops": len(tab_order)}
        with self._lock:
            capped_append(self._results, result)
        return result

    def check_screen_reader(self, page_structure: Dict[str, Any]) -> Dict[str, Any]:
        """Validate page structure for screen reader support."""
        issues: List[str] = []
        if not page_structure.get("title"):
            issues.append("Page missing title")
        if not page_structure.get("h1"):
            issues.append("Page missing h1 heading")
        if not page_structure.get("landmarks"):
            issues.append("Page has no landmark regions")
        if page_structure.get("images"):
            for img in page_structure["images"]:
                if not img.get("alt"):
                    issues.append(f"Image missing alt text: {img.get('src', 'unknown')}")

        passed = len(issues) == 0
        result = {"check": "screen_reader", "passed": passed, "issues": issues}
        with self._lock:
            capped_append(self._results, result)
        return result

    def get_report(self) -> Dict[str, Any]:
        """Return aggregate accessibility report."""
        with self._lock:
            results = list(self._results)
        total = len(results)
        passed = sum(1 for r in results if r.get("passed"))
        return {
            "total_checks": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total, 4) if total else 0.0,
            "results": results,
        }


# ============================================================================
# Responsive Layout Tester
# ============================================================================

VIEWPORT_PRESETS: Dict[str, Dict[str, int]] = {
    "mobile": {"width": 375, "height": 667},
    "tablet": {"width": 768, "height": 1024},
    "desktop": {"width": 1280, "height": 800},
    "wide": {"width": 1920, "height": 1080},
}


class ResponsiveLayoutTester:
    """Tests UI layout rules at various viewport sizes."""

    def __init__(self, breakpoints: Optional[Dict[str, int]] = None) -> None:
        self._lock = threading.Lock()
        self._breakpoints = breakpoints or {"mobile": 480, "tablet": 768, "desktop": 1024}
        self._results: List[Dict[str, Any]] = []

    def classify_viewport(self, width: int) -> str:
        """Return the layout class for a given viewport width."""
        sorted_bp = sorted(self._breakpoints.items(), key=lambda x: x[1])
        for name, threshold in sorted_bp:
            if width < threshold:
                return name
        return sorted_bp[-1][0] if sorted_bp else "unknown"

    def test_layout_rules(
        self,
        viewport_name: str,
        layout: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate layout rules for a specific viewport."""
        vp = VIEWPORT_PRESETS.get(viewport_name)
        if vp is None:
            return {"valid": False, "errors": [f"Unknown viewport: {viewport_name}"]}

        errors: List[str] = []
        width = vp["width"]

        sidebar_visible = layout.get("sidebar_visible")
        if width < self._breakpoints.get("tablet", 768) and sidebar_visible:
            errors.append("Sidebar should be hidden on mobile")

        nav_type = layout.get("nav_type")
        if width < self._breakpoints.get("tablet", 768) and nav_type != "hamburger":
            errors.append("Mobile should use hamburger navigation")

        columns = layout.get("columns", 1)
        if width < self._breakpoints.get("mobile", 480) and columns > 1:
            errors.append("Mobile should use single column layout")

        font_size = layout.get("font_size")
        if font_size is not None and font_size < 12:
            errors.append("Font size below minimum readable size (12px)")

        touch_target = layout.get("touch_target_size")
        if width < self._breakpoints.get("tablet", 768) and touch_target is not None:
            if touch_target < 44:
                errors.append("Touch targets must be at least 44px on mobile")

        result = {
            "viewport": viewport_name,
            "dimensions": vp,
            "valid": len(errors) == 0,
            "errors": errors,
        }
        with self._lock:
            capped_append(self._results, result)
        return result

    def test_all_viewports(self, layout_fn: Any) -> Dict[str, Any]:
        """Run layout tests across all preset viewports.

        *layout_fn* is called with (viewport_name, width, height) and must
        return a layout dict.
        """
        results: Dict[str, Any] = {}
        all_valid = True
        for vp_name, dims in VIEWPORT_PRESETS.items():
            layout = layout_fn(vp_name, dims["width"], dims["height"])
            r = self.test_layout_rules(vp_name, layout)
            results[vp_name] = r
            if not r["valid"]:
                all_valid = False
        return {"all_valid": all_valid, "viewports": results}

    def get_report(self) -> Dict[str, Any]:
        """Return aggregate responsive layout report."""
        with self._lock:
            results = list(self._results)
        total = len(results)
        passed = sum(1 for r in results if r.get("valid"))
        return {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "results": results,
        }


# ============================================================================
# User Interaction Simulator
# ============================================================================

class UserInteractionSimulator:
    """Simulates user flows and validates expected state transitions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._flows: Dict[str, Dict[str, Any]] = {}
        self._history: List[Dict[str, Any]] = []

    def register_flow(
        self,
        name: str,
        steps: List[str],
        initial_state: Dict[str, Any],
        transitions: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Register a user flow with named steps and expected state transitions.

        *transitions* maps step name -> dict of state changes applied after
        that step completes.
        """
        flow: Dict[str, Any] = {
            "name": name,
            "steps": list(steps),
            "initial_state": copy.deepcopy(initial_state),
            "transitions": copy.deepcopy(transitions),
        }
        with self._lock:
            self._flows[name] = flow
        return {"registered": True, "flow": name, "step_count": len(steps)}

    def execute_flow(
        self,
        name: str,
        step_results: Optional[Dict[str, bool]] = None,
    ) -> Dict[str, Any]:
        """Execute a registered flow, applying transitions for each step.

        *step_results* optionally maps step name -> success bool.  If a step
        fails, execution halts at that step.
        """
        with self._lock:
            flow = self._flows.get(name)
        if flow is None:
            return {"success": False, "error": f"Flow '{name}' not registered"}

        step_results = step_results or {}
        state = copy.deepcopy(flow["initial_state"])
        executed: List[Dict[str, Any]] = []

        for step in flow["steps"]:
            succeeded = step_results.get(step, True)
            transition = flow["transitions"].get(step, {})
            if succeeded:
                state.update(transition)
            record = {
                "step": step,
                "succeeded": succeeded,
                "state_after": copy.deepcopy(state),
            }
            executed.append(record)
            if not succeeded:
                break

        completed = len(executed) == len(flow["steps"]) and all(
            s["succeeded"] for s in executed
        )
        result = {
            "flow": name,
            "completed": completed,
            "steps_executed": len(executed),
            "total_steps": len(flow["steps"]),
            "final_state": state,
            "step_details": executed,
        }
        with self._lock:
            capped_append(self._history, result)
        return result

    def simulate_login(
        self, username: str, password: str, valid_users: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Simulate a login interaction."""
        valid_users = valid_users or {"admin": "admin123", "user": "pass"}
        success = valid_users.get(username) == password
        state = {
            "authenticated": success,
            "username": username if success else None,
            "error": None if success else "Invalid credentials",
        }
        result = {"action": "login", "success": success, "state": state}
        with self._lock:
            capped_append(self._history, result)
        return result

    def simulate_task_submission(
        self, task_name: str, params: Dict[str, Any], authenticated: bool = True
    ) -> Dict[str, Any]:
        """Simulate submitting a task."""
        if not authenticated:
            return {"action": "submit_task", "success": False, "error": "Not authenticated"}
        if not task_name:
            return {"action": "submit_task", "success": False, "error": "Task name required"}

        task_id = f"task-{abs(hash(task_name)) % 100000:05d}"
        result = {
            "action": "submit_task",
            "success": True,
            "task_id": task_id,
            "task_name": task_name,
            "params": params,
            "state": {"status": "submitted", "progress": 0},
        }
        with self._lock:
            capped_append(self._history, result)
        return result

    def simulate_settings_change(
        self,
        setting_key: str,
        new_value: Any,
        current_settings: Dict[str, Any],
        allowed_keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Simulate changing a configuration setting."""
        if allowed_keys and setting_key not in allowed_keys:
            return {
                "action": "settings_change",
                "success": False,
                "error": f"Unknown setting: {setting_key}",
            }
        old_value = current_settings.get(setting_key)
        updated = dict(current_settings)
        updated[setting_key] = new_value
        result = {
            "action": "settings_change",
            "success": True,
            "setting": setting_key,
            "old_value": old_value,
            "new_value": new_value,
            "settings": updated,
        }
        with self._lock:
            capped_append(self._history, result)
        return result

    def get_history(self) -> Dict[str, Any]:
        """Return interaction history."""
        with self._lock:
            history = list(self._history)
        return {"interactions": history, "count": len(history)}


# ============================================================================
# Facade
# ============================================================================

class UITestSuite:
    """Convenience facade that groups all UI testing subsystems."""

    def __init__(self) -> None:
        self.contracts = ComponentContractValidator()
        self.shapes = DataShapeValidator()
        self.accessibility = AccessibilityChecker()
        self.responsive = ResponsiveLayoutTester()
        self.interactions = UserInteractionSimulator()

    def full_report(self) -> Dict[str, Any]:
        """Aggregate reports from all subsystems."""
        return {
            "components": self.contracts.list_components(),
            "schemas": self.shapes.list_schemas(),
            "accessibility": self.accessibility.get_report(),
            "responsive": self.responsive.get_report(),
            "interactions": self.interactions.get_history(),
        }
