"""
playwright_task_definitions — backward-compatibility shim.

All implementation has moved to murphy_native_automation.py.
Murphy's own UITestingFramework, GhostController desktop runner,
direct API calls, and webbrowser.open() are used natively.
Playwright is never a dependency.

Import this module as before — everything is re-exported unchanged.

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from murphy_native_automation import (  # noqa: F401
    # Core types
    NativeTask,
    NativeStep,
    NativeTaskFactory,
    MurphyNativeRunner,
    MurphyAPIClient,
    GhostDesktopRunner,
    GhostControllerExporter,
    PlaywrightExporter,
    TaskType,
    ActionType,
    TaskStatus,
    # Backward-compatible aliases
    BrowserTask,
    TaskStep,
    BrowserTaskFactory,
    MurphyTaskRunner,
    PlaywrightTask,
    PlaywrightTaskFactory,
)

__all__ = [
    "NativeTask", "NativeStep", "NativeTaskFactory", "MurphyNativeRunner",
    "MurphyAPIClient", "GhostDesktopRunner", "GhostControllerExporter",
    "PlaywrightExporter", "TaskType", "ActionType", "TaskStatus",
    "BrowserTask", "TaskStep", "BrowserTaskFactory", "MurphyTaskRunner",
    "PlaywrightTask", "PlaywrightTaskFactory",
]
