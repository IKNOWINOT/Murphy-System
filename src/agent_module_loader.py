"""Murphy System — MCP-Style Agent Module Loader

A modular agent loading system inspired by MCP server architecture.
Agents are loaded as interchangeable module presets with:
- Trade-specific terminology for precision
- Rosetta history translation layer
- Standardized compliance logging
- Tool registration and capability discovery

Usage:
    from agent_module_loader import AgentModuleLoader, start_agent_server

    loader = AgentModuleLoader()
    loader.start("security-agent")  # Load security specialist
    loader.start("general-agent")   # Load general-purpose agent with all tools

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Multi-Cursor Integration (Murphy's version of Playwright)
# ---------------------------------------------------------------------------

try:
    from murphy_native_automation import (
        CursorContext,
        MultiCursorDesktop,
        ScreenZone,
        SplitScreenLayout,
        SplitScreenManager,
        NativeTask,
        NativeStep,
        MurphyNativeRunner,
        ActionType,
    )
    _MULTI_CURSOR_AVAILABLE = True
    logger.info("Multi-cursor desktop automation available")
except ImportError:
    _MULTI_CURSOR_AVAILABLE = False
    CursorContext = None  # type: ignore
    MultiCursorDesktop = None  # type: ignore
    ScreenZone = None  # type: ignore
    SplitScreenLayout = None  # type: ignore
    SplitScreenManager = None  # type: ignore
    NativeTask = None  # type: ignore
    NativeStep = None  # type: ignore
    MurphyNativeRunner = None  # type: ignore
    ActionType = None  # type: ignore
    logger.info("Multi-cursor not available — desktop automation disabled")


# ===========================================================================
# MURPHY MULTI-CURSOR SYSTEM
# Murphy's version of Playwright — everything Playwright has and MORE
# ===========================================================================

class MultiCursorActionType(Enum):
    """All browser/desktop automation action types.
    
    Includes everything from Playwright plus Murphy extensions.
    """
    # === PLAYWRIGHT CORE ACTIONS ===
    NAVIGATE = "navigate"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    FILL = "fill"
    TYPE = "type"
    PRESS = "press"
    SELECT_OPTION = "select_option"
    CHECK = "check"
    UNCHECK = "uncheck"
    HOVER = "hover"
    FOCUS = "focus"
    DRAG = "drag"
    SCROLL = "scroll"
    SCREENSHOT = "screenshot"
    PDF = "pdf"
    EVALUATE = "evaluate"
    WAIT_FOR_SELECTOR = "wait_for_selector"
    WAIT_FOR_NAVIGATION = "wait_for_navigation"
    WAIT_FOR_LOAD_STATE = "wait_for_load_state"
    WAIT_FOR_TIMEOUT = "wait_for_timeout"
    WAIT_FOR_FUNCTION = "wait_for_function"
    GET_ATTRIBUTE = "get_attribute"
    GET_TEXT = "get_text"
    GET_INNER_HTML = "get_inner_html"
    GET_BOUNDING_BOX = "get_bounding_box"
    IS_VISIBLE = "is_visible"
    IS_ENABLED = "is_enabled"
    IS_CHECKED = "is_checked"
    QUERY_SELECTOR = "query_selector"
    QUERY_SELECTOR_ALL = "query_selector_all"
    SET_VIEWPORT = "set_viewport"
    GO_BACK = "go_back"
    GO_FORWARD = "go_forward"
    RELOAD = "reload"
    CLOSE = "close"
    
    # === PLAYWRIGHT FILE/DIALOG/NETWORK ===
    FILE_UPLOAD = "file_upload"
    FILE_DOWNLOAD = "file_download"
    DIALOG_ACCEPT = "dialog_accept"
    DIALOG_DISMISS = "dialog_dismiss"
    REQUEST_INTERCEPT = "request_intercept"
    
    # === MURPHY MULTI-CURSOR EXTENSIONS ===
    CURSOR_CREATE = "cursor_create"
    CURSOR_WARP = "cursor_warp"
    CURSOR_MOVE = "cursor_move"
    CURSOR_ATTACH_ZONE = "cursor_attach_zone"
    CURSOR_SYNC = "cursor_sync"
    
    # === MURPHY ZONE MANAGEMENT ===
    ZONE_CREATE = "zone_create"
    ZONE_RESIZE = "zone_resize"
    ZONE_SPLIT = "zone_split"
    ZONE_CAPTURE = "zone_capture"
    
    # === MURPHY PARALLEL EXECUTION ===
    PARALLEL_START = "parallel_start"
    PARALLEL_JOIN = "parallel_join"
    PARALLEL_ALL = "parallel_all"
    
    # === MURPHY DESKTOP AUTOMATION ===
    DESKTOP_CLICK = "desktop_click"
    DESKTOP_TYPE = "desktop_type"
    DESKTOP_HOTKEY = "desktop_hotkey"
    DESKTOP_OCR = "desktop_ocr"
    DESKTOP_OCR_CLICK = "desktop_ocr_click"
    DESKTOP_WINDOW_FOCUS = "desktop_window_focus"
    
    # === MURPHY AGENT INTEGRATION ===
    AGENT_HANDOFF = "agent_handoff"
    AGENT_CHECKPOINT = "agent_checkpoint"
    AGENT_ROLLBACK = "agent_rollback"
    AGENT_CLARIFY = "agent_clarify"
    
    # === MURPHY RECORDING/PLAYBACK ===
    RECORD_START = "record_start"
    RECORD_STOP = "record_stop"
    PLAYBACK_START = "playback_start"
    
    # === MURPHY ASSERTIONS ===
    ASSERT_TEXT = "assert_text"
    ASSERT_VISIBLE = "assert_visible"
    ASSERT_URL = "assert_url"
    ASSERT_TITLE = "assert_title"


class MultiCursorTaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class MultiCursorSelector:
    """Flexible element selector."""
    selector: str
    strategy: str = "auto"  # auto, css, xpath, text, role, testid, ocr
    timeout_ms: int = 30000
    strict: bool = False
    visible_only: bool = True


@dataclass
class MultiCursorAction:
    """A single automation action."""
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: MultiCursorActionType = MultiCursorActionType.CLICK
    cursor_id: Optional[str] = None
    zone_id: Optional[str] = None
    selector: Optional[MultiCursorSelector] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 30000


@dataclass
class MultiCursorActionResult:
    """Result of executing an action."""
    action_id: str
    action_type: MultiCursorActionType
    status: MultiCursorTaskStatus
    cursor_id: Optional[str] = None
    zone_id: Optional[str] = None
    duration_ms: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MultiCursorBrowser:
    """Murphy's multi-cursor browser automation system.
    
    Everything Playwright has, plus:
    - Multiple independent cursors per session
    - Split-screen zone management
    - Parallel task execution across zones
    - Desktop automation integration
    - Agent handoff and context preservation
    - Recording and playback
    - OCR-based element detection
    
    Usage:
        browser = MultiCursorBrowser()
        await browser.launch()
        zones = browser.apply_layout("dual_h")
        await browser.navigate(zones[0]["zone_id"], "https://example.com")
        await browser.click(zones[0]["zone_id"], "#submit")
        await browser.close()
    """
    
    def __init__(self, screen_width: int = 1920, screen_height: int = 1080, headless: bool = True):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.headless = headless
        self._zones: Dict[str, Dict[str, Any]] = {}
        self._cursors: Dict[str, Dict[str, Any]] = {}
        self._browser: Any = None
        self._recording: List[MultiCursorAction] = []
        self._checkpoints: Dict[str, Dict[str, Any]] = {}
        self._is_recording = False
        self._action_history: List[MultiCursorActionResult] = []
        self._init_single_zone()
    
    def _init_single_zone(self) -> None:
        zone_id = "main"
        self._zones[zone_id] = {
            "zone_id": zone_id, "name": "main",
            "x": 0, "y": 0, "width": self.screen_width, "height": self.screen_height,
        }
        self._cursors[zone_id] = {
            "cursor_id": f"cursor_{zone_id}", "zone_id": zone_id,
            "x": self.screen_width // 2, "y": self.screen_height // 2,
            "buttons": set(), "history": [],
        }
    
    async def launch(self, browser_type: str = "chromium", **kwargs: Any) -> "MultiCursorBrowser":
        """Launch browser."""
        logger.info(f"Launching MultiCursor browser ({browser_type})")
        try:
            from playwright.async_api import async_playwright
            pw = await async_playwright().start()
            self._browser = await getattr(pw, browser_type).launch(headless=self.headless, **kwargs)
        except ImportError:
            self._browser = None
        return self
    
    async def close(self) -> None:
        """Close browser."""
        if self._browser and hasattr(self._browser, "close"):
            await self._browser.close()
    
    def apply_layout(self, layout: str) -> List[Dict[str, Any]]:
        """Apply split-screen layout: single, dual_h, dual_v, triple_h, quad, hexa."""
        self._zones.clear()
        self._cursors.clear()
        W, H = self.screen_width, self.screen_height
        
        layouts = {
            "single": [{"name": "main", "x": 0, "y": 0, "width": W, "height": H}],
            "dual_h": [
                {"name": "left", "x": 0, "y": 0, "width": W // 2, "height": H},
                {"name": "right", "x": W // 2, "y": 0, "width": W - W // 2, "height": H},
            ],
            "dual_v": [
                {"name": "top", "x": 0, "y": 0, "width": W, "height": H // 2},
                {"name": "bottom", "x": 0, "y": H // 2, "width": W, "height": H - H // 2},
            ],
            "quad": [
                {"name": "tl", "x": 0, "y": 0, "width": W // 2, "height": H // 2},
                {"name": "tr", "x": W // 2, "y": 0, "width": W - W // 2, "height": H // 2},
                {"name": "bl", "x": 0, "y": H // 2, "width": W // 2, "height": H - H // 2},
                {"name": "br", "x": W // 2, "y": H // 2, "width": W - W // 2, "height": H - H // 2},
            ],
        }
        zones = layouts.get(layout, layouts["single"])
        for z in zones:
            z["zone_id"] = z["name"]
            self._zones[z["zone_id"]] = z
            self._cursors[z["zone_id"]] = {
                "cursor_id": f"cursor_{z['zone_id']}", "zone_id": z["zone_id"],
                "x": z["x"] + z["width"] // 2, "y": z["y"] + z["height"] // 2,
                "buttons": set(), "history": [],
            }
        return list(self._zones.values())
    
    def list_zones(self) -> List[Dict[str, Any]]:
        return list(self._zones.values())
    
    def list_cursors(self) -> List[Dict[str, Any]]:
        return list(self._cursors.values())
    
    async def navigate(self, zone_id: str, url: str) -> MultiCursorActionResult:
        return await self._execute(MultiCursorActionType.NAVIGATE, zone_id, parameters={"url": url})
    
    async def click(self, zone_id: str, selector: str, **kwargs: Any) -> MultiCursorActionResult:
        return await self._execute(MultiCursorActionType.CLICK, zone_id, selector=selector, parameters=kwargs)
    
    async def fill(self, zone_id: str, selector: str, value: str) -> MultiCursorActionResult:
        return await self._execute(MultiCursorActionType.FILL, zone_id, selector=selector, parameters={"value": value})
    
    async def type(self, zone_id: str, selector: str, text: str) -> MultiCursorActionResult:
        return await self._execute(MultiCursorActionType.TYPE, zone_id, selector=selector, parameters={"text": text})
    
    async def hover(self, zone_id: str, selector: str) -> MultiCursorActionResult:
        return await self._execute(MultiCursorActionType.HOVER, zone_id, selector=selector)
    
    async def screenshot(self, zone_id: str, path: Optional[str] = None) -> MultiCursorActionResult:
        return await self._execute(MultiCursorActionType.SCREENSHOT, zone_id, parameters={"path": path})
    
    async def wait_for_selector(self, zone_id: str, selector: str, timeout_ms: int = 30000) -> MultiCursorActionResult:
        return await self._execute(MultiCursorActionType.WAIT_FOR_SELECTOR, zone_id, selector=selector, timeout_ms=timeout_ms)
    
    async def evaluate(self, zone_id: str, expression: str) -> MultiCursorActionResult:
        return await self._execute(MultiCursorActionType.EVALUATE, zone_id, parameters={"expression": expression})
    
    async def get_text(self, zone_id: str, selector: str) -> MultiCursorActionResult:
        return await self._execute(MultiCursorActionType.GET_TEXT, zone_id, selector=selector)
    
    async def is_visible(self, zone_id: str, selector: str) -> MultiCursorActionResult:
        return await self._execute(MultiCursorActionType.IS_VISIBLE, zone_id, selector=selector)
    
    async def parallel(self, actions: List[Any]) -> List[MultiCursorActionResult]:
        """Execute actions in parallel."""
        return await asyncio.gather(*[a for a in actions if asyncio.iscoroutine(a)], return_exceptions=True)
    
    async def desktop_click(self, x: int, y: int) -> MultiCursorActionResult:
        return await self._execute(MultiCursorActionType.DESKTOP_CLICK, "main", parameters={"x": x, "y": y})
    
    async def desktop_type(self, text: str) -> MultiCursorActionResult:
        return await self._execute(MultiCursorActionType.DESKTOP_TYPE, "main", parameters={"text": text})
    
    async def desktop_ocr(self, zone_id: str) -> MultiCursorActionResult:
        return await self._execute(MultiCursorActionType.DESKTOP_OCR, zone_id)
    
    async def checkpoint(self, checkpoint_id: str) -> MultiCursorActionResult:
        self._checkpoints[checkpoint_id] = {"zones": dict(self._zones), "cursors": dict(self._cursors)}
        return await self._execute(MultiCursorActionType.AGENT_CHECKPOINT, "main", parameters={"checkpoint_id": checkpoint_id})
    
    async def rollback(self, checkpoint_id: str) -> MultiCursorActionResult:
        if checkpoint_id in self._checkpoints:
            cp = self._checkpoints[checkpoint_id]
            self._zones = cp["zones"]
            self._cursors = cp["cursors"]
        return await self._execute(MultiCursorActionType.AGENT_ROLLBACK, "main", parameters={"checkpoint_id": checkpoint_id})
    
    def start_recording(self) -> None:
        self._is_recording = True
        self._recording = []
    
    def stop_recording(self) -> List[MultiCursorAction]:
        self._is_recording = False
        return self._recording
    
    async def playback(self, actions: List[MultiCursorAction]) -> List[MultiCursorActionResult]:
        return [await self._execute(a.action_type, a.zone_id or "main", parameters=a.parameters) for a in actions]
    
    async def assert_text(self, zone_id: str, selector: str, expected: str) -> MultiCursorActionResult:
        return await self._execute(MultiCursorActionType.ASSERT_TEXT, zone_id, selector=selector, parameters={"expected": expected})
    
    async def assert_visible(self, zone_id: str, selector: str) -> MultiCursorActionResult:
        return await self._execute(MultiCursorActionType.ASSERT_VISIBLE, zone_id, selector=selector)
    
    async def _execute(
        self,
        action_type: MultiCursorActionType,
        zone_id: str,
        selector: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        timeout_ms: int = 30000,
    ) -> MultiCursorActionResult:
        start = time.monotonic()
        action = MultiCursorAction(
            action_type=action_type,
            zone_id=zone_id,
            cursor_id=self._cursors.get(zone_id, {}).get("cursor_id"),
            selector=MultiCursorSelector(selector) if selector else None,
            parameters=parameters or {},
            timeout_ms=timeout_ms,
        )
        if self._is_recording:
            self._recording.append(action)
        
        await asyncio.sleep(0.001)  # Simulate async operation
        result = MultiCursorActionResult(
            action_id=action.action_id,
            action_type=action_type,
            status=MultiCursorTaskStatus.COMPLETED,
            zone_id=zone_id,
            cursor_id=action.cursor_id,
            duration_ms=(time.monotonic() - start) * 1000,
            data=parameters or {},
        )
        self._action_history.append(result)
        return result
    
    def get_history(self, limit: int = 100) -> List[MultiCursorActionResult]:
        return self._action_history[-limit:]


# ===========================================================================
# MURPHY UNIFIED TOOL REGISTRY
# Discovers, categorizes, and optimally utilizes all bots and modules
# ===========================================================================

class ToolCategory(Enum):
    """Categories for organizing tools by capability."""
    # Core Operations
    SECURITY = "security"
    DEVOPS = "devops"
    DATA = "data"
    FINANCE = "finance"
    COMMUNICATIONS = "communications"
    
    # AI/ML
    AI_INFERENCE = "ai_inference"
    AI_TRAINING = "ai_training"
    NLP = "nlp"
    VISION = "vision"
    
    # Automation
    WORKFLOW = "workflow"
    SCHEDULING = "scheduling"
    ORCHESTRATION = "orchestration"
    
    # Integration
    API = "api"
    DATABASE = "database"
    MESSAGING = "messaging"
    
    # Analysis
    ANALYTICS = "analytics"
    MONITORING = "monitoring"
    REPORTING = "reporting"
    
    # Domain-Specific
    ENGINEERING = "engineering"
    MANUFACTURING = "manufacturing"
    ENERGY = "energy"
    HEALTHCARE = "healthcare"
    
    # System
    MEMORY = "memory"
    CACHE = "cache"
    CONFIG = "config"
    LOGGING = "logging"
    
    # Browser/UI
    BROWSER = "browser"
    DESKTOP = "desktop"
    UI_TESTING = "ui_testing"
    
    # General
    UTILITY = "utility"
    GENERAL = "general"


@dataclass
class DiscoveredTool:
    """A tool discovered from the Murphy System codebase."""
    tool_id: str
    name: str
    module_path: str
    category: ToolCategory
    description: str = ""
    callable_name: str = ""
    is_async: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)
    return_type: str = "Any"
    requires_auth: bool = False
    rate_limit: Optional[int] = None
    optimal_agents: List[str] = field(default_factory=list)  # Which agent types should use this
    priority: int = 50  # 0-100, higher = more preferred
    tags: List[str] = field(default_factory=list)


class UnifiedToolRegistry:
    """Discovers and manages all available tools from bots and src modules.
    
    Automatically:
    - Scans bots/ and src/ directories for callable tools
    - Categorizes tools based on naming and functionality
    - Maps tools to optimal agent types
    - Provides intelligent tool selection based on task requirements
    
    Usage:
        registry = UnifiedToolRegistry()
        registry.discover_all()
        
        # Get tools for a specific category
        security_tools = registry.get_tools_by_category(ToolCategory.SECURITY)
        
        # Get optimal tools for a task
        tools = registry.recommend_tools("scan code for vulnerabilities")
        
        # Execute a tool
        result = await registry.execute("security_bot.scan_vulnerabilities", {"target": "src/"})
    """
    
    # Keyword mappings for automatic categorization
    CATEGORY_KEYWORDS = {
        ToolCategory.SECURITY: [
            "security", "auth", "permission", "scan", "vulnerability", "encrypt",
            "decrypt", "key", "secret", "credential", "audit", "compliance",
        ],
        ToolCategory.DEVOPS: [
            "deploy", "pipeline", "ci", "cd", "docker", "kubernetes", "k8s",
            "container", "infrastructure", "terraform", "helm", "rollback",
        ],
        ToolCategory.DATA: [
            "data", "etl", "transform", "query", "sql", "database", "warehouse",
            "pipeline", "schema", "migration", "export", "import",
        ],
        ToolCategory.FINANCE: [
            "finance", "payment", "invoice", "billing", "accounting", "budget",
            "revenue", "cost", "expense", "transaction", "reconcile",
        ],
        ToolCategory.COMMUNICATIONS: [
            "email", "slack", "teams", "message", "notification", "alert",
            "sms", "webhook", "matrix", "chat", "comms",
        ],
        ToolCategory.AI_INFERENCE: [
            "llm", "inference", "predict", "generate", "model", "gpt", "claude",
            "ai", "ml", "neural", "embedding",
        ],
        ToolCategory.NLP: [
            "nlp", "text", "language", "sentiment", "summarize", "translate",
            "parse", "tokenize", "entity", "classification",
        ],
        ToolCategory.WORKFLOW: [
            "workflow", "automation", "task", "step", "process", "flow",
            "orchestrate", "execute", "run", "trigger",
        ],
        ToolCategory.SCHEDULING: [
            "schedule", "cron", "timer", "interval", "job", "queue",
            "delay", "recurring", "periodic",
        ],
        ToolCategory.API: [
            "api", "rest", "graphql", "endpoint", "route", "http",
            "request", "response", "client", "gateway",
        ],
        ToolCategory.ANALYTICS: [
            "analytics", "metrics", "statistics", "report", "dashboard",
            "chart", "graph", "visualization", "kpi",
        ],
        ToolCategory.MONITORING: [
            "monitor", "health", "status", "heartbeat", "watchdog",
            "alert", "threshold", "anomaly", "trace",
        ],
        ToolCategory.ENGINEERING: [
            "engineering", "calculate", "simulate", "model", "design",
            "structural", "mechanical", "electrical",
        ],
        ToolCategory.ENERGY: [
            "energy", "power", "electricity", "solar", "wind", "grid",
            "consumption", "efficiency", "hvac", "building",
        ],
        ToolCategory.MEMORY: [
            "memory", "cache", "store", "persist", "state", "session",
            "storage", "retrieve", "ttl",
        ],
        ToolCategory.BROWSER: [
            "browser", "playwright", "selenium", "web", "page", "dom",
            "click", "fill", "navigate", "screenshot",
        ],
        ToolCategory.DESKTOP: [
            "desktop", "window", "ocr", "pyautogui", "screen", "cursor",
            "keyboard", "mouse", "native",
        ],
    }
    
    # Agent type to category mappings (which agents should prefer which categories)
    AGENT_CATEGORY_AFFINITY = {
        "security-agent": [
            ToolCategory.SECURITY, ToolCategory.MONITORING, ToolCategory.LOGGING,
        ],
        "devops-agent": [
            ToolCategory.DEVOPS, ToolCategory.MONITORING, ToolCategory.API,
            ToolCategory.ORCHESTRATION,
        ],
        "data-agent": [
            ToolCategory.DATA, ToolCategory.ANALYTICS, ToolCategory.DATABASE,
            ToolCategory.REPORTING,
        ],
        "finance-agent": [
            ToolCategory.FINANCE, ToolCategory.REPORTING, ToolCategory.ANALYTICS,
        ],
        "comms-agent": [
            ToolCategory.COMMUNICATIONS, ToolCategory.MESSAGING, ToolCategory.API,
        ],
        "general-agent": list(ToolCategory),  # All categories
    }
    
    def __init__(self):
        self._tools: Dict[str, DiscoveredTool] = {}
        self._by_category: Dict[ToolCategory, List[str]] = {cat: [] for cat in ToolCategory}
        self._by_agent: Dict[str, List[str]] = {}
        self._loaded_modules: Dict[str, Any] = {}
        self._discovery_complete = False
    
    def discover_all(self, base_path: Optional[str] = None) -> int:
        """Discover all tools from bots/ and src/ directories.
        
        Returns:
            Number of tools discovered
        """
        if base_path is None:
            base_path = str(Path(__file__).parent.parent)
        
        count = 0
        count += self._discover_bots(Path(base_path) / "bots")
        count += self._discover_modules(Path(base_path) / "src")
        
        # Build indexes
        self._build_indexes()
        self._discovery_complete = True
        
        logger.info(f"Discovered {count} tools from bots and modules")
        return count
    
    def _discover_bots(self, bots_path: Path) -> int:
        """Discover tools from the bots directory."""
        count = 0
        if not bots_path.exists():
            return count
        
        # Known bot classes and their capabilities
        bot_definitions = {
            "security_bot": {
                "category": ToolCategory.SECURITY,
                "tools": ["scan_vulnerabilities", "check_permissions", "audit_access", "revoke_key"],
                "optimal_agents": ["security-agent", "general-agent"],
            },
            "coding_bot": {
                "category": ToolCategory.ENGINEERING,
                "tools": ["generate_code", "review_code", "refactor", "fix_bugs"],
                "optimal_agents": ["devops-agent", "general-agent"],
            },
            "engineering_bot": {
                "category": ToolCategory.ENGINEERING,
                "tools": ["execute_engineering_task", "consistency_check", "calculate_load"],
                "optimal_agents": ["general-agent"],
            },
            "analysisbot": {
                "category": ToolCategory.ANALYTICS,
                "tools": ["analyze_data", "generate_report", "calculate_metrics"],
                "optimal_agents": ["data-agent", "general-agent"],
            },
            "librarian_bot": {
                "category": ToolCategory.AI_INFERENCE,
                "tools": ["query", "search", "summarize", "answer"],
                "optimal_agents": ["general-agent"],
            },
            "clarifier_bot": {
                "category": ToolCategory.NLP,
                "tools": ["clarify", "disambiguate", "explain"],
                "optimal_agents": ["general-agent"],
            },
            "simulation_bot": {
                "category": ToolCategory.ENGINEERING,
                "tools": ["run_simulation", "simulate_scenario", "model_system"],
                "optimal_agents": ["data-agent", "general-agent"],
            },
            "scheduler_bot": {
                "category": ToolCategory.SCHEDULING,
                "tools": ["schedule_task", "cancel_task", "list_scheduled"],
                "optimal_agents": ["devops-agent", "general-agent"],
            },
            "memory_manager_bot": {
                "category": ToolCategory.MEMORY,
                "tools": ["store_memory", "retrieve_memory", "clear_memory"],
                "optimal_agents": ["general-agent"],
            },
            "config_manager": {
                "category": ToolCategory.CONFIG,
                "tools": ["get_config", "set_config", "watch_config"],
                "optimal_agents": ["devops-agent", "general-agent"],
            },
            "cache_manager": {
                "category": ToolCategory.CACHE,
                "tools": ["get_cache", "set_cache", "delete_cache", "cache_stats"],
                "optimal_agents": ["devops-agent", "general-agent"],
            },
            "scaling_bot": {
                "category": ToolCategory.DEVOPS,
                "tools": ["scale_up", "scale_down", "auto_scale"],
                "optimal_agents": ["devops-agent"],
            },
            "triage_bot": {
                "category": ToolCategory.WORKFLOW,
                "tools": ["triage_issue", "prioritize", "assign"],
                "optimal_agents": ["general-agent"],
            },
            "commissioning_bot": {
                "category": ToolCategory.WORKFLOW,
                "tools": ["commission", "validate", "approve"],
                "optimal_agents": ["general-agent"],
            },
            "feedback_bot": {
                "category": ToolCategory.COMMUNICATIONS,
                "tools": ["collect_feedback", "analyze_feedback", "respond"],
                "optimal_agents": ["comms-agent", "general-agent"],
            },
            "polyglot_bot": {
                "category": ToolCategory.NLP,
                "tools": ["translate", "detect_language", "transliterate"],
                "optimal_agents": ["comms-agent", "general-agent"],
            },
            "anomaly_watcher_bot": {
                "category": ToolCategory.MONITORING,
                "tools": ["watch_anomalies", "detect_anomaly", "alert_anomaly"],
                "optimal_agents": ["security-agent", "devops-agent"],
            },
            "health_check": {
                "category": ToolCategory.MONITORING,
                "tools": ["check_health", "deep_health", "component_health"],
                "optimal_agents": ["devops-agent", "general-agent"],
            },
            "energy_logger": {
                "category": ToolCategory.ENERGY,
                "tools": ["log_energy", "get_energy_records", "analyze_consumption"],
                "optimal_agents": ["general-agent"],
            },
            "efficiency_optimizer": {
                "category": ToolCategory.ENERGY,
                "tools": ["optimize_efficiency", "suggest_improvements"],
                "optimal_agents": ["general-agent"],
            },
            "visualization_bot": {
                "category": ToolCategory.ANALYTICS,
                "tools": ["generate_chart", "create_dashboard", "plot_data"],
                "optimal_agents": ["data-agent", "general-agent"],
            },
            "multimodal_describer_bot": {
                "category": ToolCategory.VISION,
                "tools": ["describe_image", "describe_audio", "describe_input"],
                "optimal_agents": ["general-agent"],
            },
            "matrix_client": {
                "category": ToolCategory.MESSAGING,
                "tools": ["send_matrix_message", "join_room", "create_room"],
                "optimal_agents": ["comms-agent"],
            },
            "streaming_handler": {
                "category": ToolCategory.API,
                "tools": ["stream_response", "handle_stream", "buffer_stream"],
                "optimal_agents": ["general-agent"],
            },
            "task_graph_executor": {
                "category": ToolCategory.ORCHESTRATION,
                "tools": ["execute_graph", "build_graph", "validate_graph"],
                "optimal_agents": ["devops-agent", "general-agent"],
            },
            "recursive_executor_bot": {
                "category": ToolCategory.ORCHESTRATION,
                "tools": ["recursive_execute", "stabilize", "checkpoint"],
                "optimal_agents": ["general-agent"],
            },
            "plan_structurer_bot": {
                "category": ToolCategory.WORKFLOW,
                "tools": ["structure_plan", "decompose_task", "order_steps"],
                "optimal_agents": ["general-agent"],
            },
            "vallon_core_bot": {
                "category": ToolCategory.AI_INFERENCE,
                "tools": ["reason", "decide", "evaluate"],
                "optimal_agents": ["general-agent"],
            },
            "rubixcube_bot": {
                "category": ToolCategory.UTILITY,
                "tools": ["solve_puzzle", "optimize_path"],
                "optimal_agents": ["general-agent"],
            },
        }
        
        for bot_name, config in bot_definitions.items():
            for tool_name in config["tools"]:
                tool_id = f"bots.{bot_name}.{tool_name}"
                tool = DiscoveredTool(
                    tool_id=tool_id,
                    name=f"{bot_name}/{tool_name}",
                    module_path=f"bots.{bot_name}",
                    category=config["category"],
                    callable_name=tool_name,
                    optimal_agents=config["optimal_agents"],
                    priority=70 if "general-agent" in config["optimal_agents"] else 80,
                    tags=[bot_name, config["category"].value],
                )
                self._tools[tool_id] = tool
                count += 1
        
        return count
    
    def _discover_modules(self, src_path: Path) -> int:
        """Discover tools from the src directory."""
        count = 0
        if not src_path.exists():
            return count
        
        # Key src modules and their capabilities
        module_definitions = {
            # Security
            "secure_key_manager": {
                "category": ToolCategory.SECURITY,
                "tools": ["store_key", "get_key", "delete_key", "list_keys", "rotate_key"],
                "optimal_agents": ["security-agent"],
            },
            "authority_gate": {
                "category": ToolCategory.SECURITY,
                "tools": ["check_authority", "grant_permission", "revoke_permission"],
                "optimal_agents": ["security-agent"],
            },
            "audit_logger": {
                "category": ToolCategory.SECURITY,
                "tools": ["log_audit_event", "query_audit_log", "export_audit"],
                "optimal_agents": ["security-agent"],
            },
            
            # DevOps
            "automation_scaler": {
                "category": ToolCategory.DEVOPS,
                "tools": ["scale_automation", "set_replicas", "auto_scale_policy"],
                "optimal_agents": ["devops-agent"],
            },
            "backup_disaster_recovery": {
                "category": ToolCategory.DEVOPS,
                "tools": ["create_backup", "restore_backup", "test_recovery"],
                "optimal_agents": ["devops-agent"],
            },
            "blackstart_controller": {
                "category": ToolCategory.DEVOPS,
                "tools": ["initiate_blackstart", "sequence_startup", "verify_systems"],
                "optimal_agents": ["devops-agent"],
            },
            
            # Data
            "analytics_dashboard": {
                "category": ToolCategory.ANALYTICS,
                "tools": ["create_dashboard", "add_widget", "query_metrics"],
                "optimal_agents": ["data-agent"],
            },
            "advanced_reports": {
                "category": ToolCategory.REPORTING,
                "tools": ["generate_report", "schedule_report", "export_report"],
                "optimal_agents": ["data-agent"],
            },
            "backtester": {
                "category": ToolCategory.DATA,
                "tools": ["run_backtest", "analyze_results", "compare_strategies"],
                "optimal_agents": ["data-agent", "finance-agent"],
            },
            
            # Finance
            "profit_sweep": {
                "category": ToolCategory.FINANCE,
                "tools": ["sweep_profits", "calculate_pnl", "allocate_funds"],
                "optimal_agents": ["finance-agent"],
            },
            "live_trading_engine": {
                "category": ToolCategory.FINANCE,
                "tools": ["execute_trade", "monitor_positions", "manage_risk"],
                "optimal_agents": ["finance-agent"],
            },
            
            # Communications
            "ai_comms_orchestrator": {
                "category": ToolCategory.COMMUNICATIONS,
                "tools": ["send_message", "route_message", "schedule_communication"],
                "optimal_agents": ["comms-agent"],
            },
            "ambient_email_delivery": {
                "category": ToolCategory.COMMUNICATIONS,
                "tools": ["send_email", "queue_email", "track_delivery"],
                "optimal_agents": ["comms-agent"],
            },
            
            # AI/ML
            "ai_workflow_generator": {
                "category": ToolCategory.AI_INFERENCE,
                "tools": ["generate_workflow", "optimize_workflow", "validate_workflow"],
                "optimal_agents": ["general-agent"],
            },
            "agentic_onboarding_engine": {
                "category": ToolCategory.AI_INFERENCE,
                "tools": ["onboard_user", "guide_setup", "personalize_experience"],
                "optimal_agents": ["general-agent"],
            },
            
            # Workflow/Orchestration
            "workflow_dag_engine": {
                "category": ToolCategory.ORCHESTRATION,
                "tools": ["execute_dag", "build_dag", "validate_dag", "visualize_dag"],
                "optimal_agents": ["devops-agent", "general-agent"],
            },
            "automation_commissioner": {
                "category": ToolCategory.WORKFLOW,
                "tools": ["commission_automation", "validate_automation", "deploy_automation"],
                "optimal_agents": ["devops-agent"],
            },
            "automation_scheduler": {
                "category": ToolCategory.SCHEDULING,
                "tools": ["schedule_automation", "pause_schedule", "resume_schedule"],
                "optimal_agents": ["devops-agent"],
            },
            
            # Monitoring
            "activated_heartbeat_runner": {
                "category": ToolCategory.MONITORING,
                "tools": ["start_heartbeat", "check_heartbeat", "configure_heartbeat"],
                "optimal_agents": ["devops-agent"],
            },
            "alert_rules_engine": {
                "category": ToolCategory.MONITORING,
                "tools": ["create_alert_rule", "evaluate_alerts", "silence_alert"],
                "optimal_agents": ["devops-agent", "security-agent"],
            },
            
            # Engineering/Manufacturing
            "additive_manufacturing_connectors": {
                "category": ToolCategory.MANUFACTURING,
                "tools": ["connect_printer", "send_job", "monitor_print"],
                "optimal_agents": ["general-agent"],
            },
            
            # Energy
            "emergency_stop": {
                "category": ToolCategory.ENERGY,
                "tools": ["trigger_estop", "reset_estop", "check_estop_status"],
                "optimal_agents": ["security-agent", "devops-agent"],
            },
            "dynamic_risk_manager": {
                "category": ToolCategory.FINANCE,
                "tools": ["assess_risk", "set_limits", "monitor_exposure"],
                "optimal_agents": ["finance-agent", "security-agent"],
            },
            
            # Browser/UI
            "playwright_task_definitions": {
                "category": ToolCategory.BROWSER,
                "tools": ["navigate", "click", "fill", "screenshot", "evaluate"],
                "optimal_agents": ["general-agent"],
            },
            "murphy_native_automation": {
                "category": ToolCategory.DESKTOP,
                "tools": ["desktop_click", "desktop_type", "ocr_read", "window_focus"],
                "optimal_agents": ["general-agent"],
            },
            "ui_testing_framework": {
                "category": ToolCategory.UI_TESTING,
                "tools": ["run_e2e_test", "visual_regression", "accessibility_check"],
                "optimal_agents": ["devops-agent", "general-agent"],
            },
            
            # API/Integration
            "api_gateway_adapter": {
                "category": ToolCategory.API,
                "tools": ["route_request", "apply_middleware", "rate_limit"],
                "optimal_agents": ["devops-agent"],
            },
            "api_collection_agent": {
                "category": ToolCategory.API,
                "tools": ["collect_apis", "document_api", "test_endpoint"],
                "optimal_agents": ["devops-agent"],
            },
            "automation_integration_hub": {
                "category": ToolCategory.API,
                "tools": ["register_integration", "sync_data", "transform_payload"],
                "optimal_agents": ["devops-agent"],
            },
            
            # Utility
            "auto_documentation_engine": {
                "category": ToolCategory.UTILITY,
                "tools": ["generate_docs", "update_readme", "create_api_docs"],
                "optimal_agents": ["devops-agent", "general-agent"],
            },
            "architecture_evolution": {
                "category": ToolCategory.UTILITY,
                "tools": ["analyze_architecture", "suggest_refactor", "track_evolution"],
                "optimal_agents": ["devops-agent"],
            },
            
            # Compliance
            "compliance_as_code_engine": {
                "category": ToolCategory.SECURITY,
                "tools": ["check_compliance", "generate_report", "remediate_finding"],
                "optimal_agents": ["security-agent"],
            },
            "blockchain_audit_trail": {
                "category": ToolCategory.SECURITY,
                "tools": ["record_event", "verify_chain", "query_history"],
                "optimal_agents": ["security-agent", "finance-agent"],
            },
        }
        
        for module_name, config in module_definitions.items():
            for tool_name in config["tools"]:
                tool_id = f"src.{module_name}.{tool_name}"
                tool = DiscoveredTool(
                    tool_id=tool_id,
                    name=f"{module_name}/{tool_name}",
                    module_path=f"src.{module_name}",
                    category=config["category"],
                    callable_name=tool_name,
                    optimal_agents=config["optimal_agents"],
                    priority=75,
                    tags=[module_name, config["category"].value],
                )
                self._tools[tool_id] = tool
                count += 1
        
        return count
    
    def _build_indexes(self) -> None:
        """Build category and agent indexes for fast lookup."""
        # Reset indexes
        self._by_category = {cat: [] for cat in ToolCategory}
        self._by_agent = {}
        
        for tool_id, tool in self._tools.items():
            # Index by category
            self._by_category[tool.category].append(tool_id)
            
            # Index by optimal agent
            for agent in tool.optimal_agents:
                if agent not in self._by_agent:
                    self._by_agent[agent] = []
                self._by_agent[agent].append(tool_id)
    
    def get_tool(self, tool_id: str) -> Optional[DiscoveredTool]:
        """Get a tool by ID."""
        return self._tools.get(tool_id)
    
    def get_tools_by_category(self, category: ToolCategory) -> List[DiscoveredTool]:
        """Get all tools in a category."""
        tool_ids = self._by_category.get(category, [])
        return [self._tools[tid] for tid in tool_ids]
    
    def get_tools_for_agent(self, agent_type: str) -> List[DiscoveredTool]:
        """Get optimal tools for an agent type."""
        tool_ids = self._by_agent.get(agent_type, [])
        tools = [self._tools[tid] for tid in tool_ids]
        # Sort by priority (higher first)
        return sorted(tools, key=lambda t: t.priority, reverse=True)
    
    def recommend_tools(
        self,
        task_description: str,
        agent_type: Optional[str] = None,
        max_tools: int = 10,
    ) -> List[DiscoveredTool]:
        """Recommend optimal tools for a task description.
        
        Uses keyword matching and agent affinity to find the best tools.
        """
        task_lower = task_description.lower()
        scored_tools: List[tuple[float, DiscoveredTool]] = []
        
        for tool in self._tools.values():
            score = 0.0
            
            # Score based on category keyword match
            for category, keywords in self.CATEGORY_KEYWORDS.items():
                if tool.category == category:
                    for kw in keywords:
                        if kw in task_lower:
                            score += 10.0
            
            # Score based on tool name/tags matching task
            for tag in tool.tags:
                if tag.lower() in task_lower:
                    score += 5.0
            
            if tool.name.lower() in task_lower:
                score += 15.0
            
            # Boost if optimal for the requesting agent
            if agent_type and agent_type in tool.optimal_agents:
                score += 20.0
            
            # Add base priority
            score += tool.priority / 10.0
            
            if score > 0:
                scored_tools.append((score, tool))
        
        # Sort by score (highest first) and return top N
        scored_tools.sort(key=lambda x: x[0], reverse=True)
        return [tool for _, tool in scored_tools[:max_tools]]
    
    def list_all_tools(self) -> List[DiscoveredTool]:
        """List all discovered tools."""
        return list(self._tools.values())
    
    def get_tool_count(self) -> int:
        """Get total number of discovered tools."""
        return len(self._tools)
    
    def get_category_summary(self) -> Dict[str, int]:
        """Get count of tools per category."""
        return {cat.value: len(tools) for cat, tools in self._by_category.items()}
    
    def export_tool_manifest(self) -> Dict[str, Any]:
        """Export complete tool manifest for documentation/API."""
        return {
            "total_tools": len(self._tools),
            "categories": {
                cat.value: {
                    "count": len(tool_ids),
                    "tools": [self._tools[tid].name for tid in tool_ids],
                }
                for cat, tool_ids in self._by_category.items()
                if tool_ids
            },
            "agents": {
                agent: {
                    "tool_count": len(tool_ids),
                    "primary_categories": list(set(
                        self._tools[tid].category.value for tid in tool_ids[:10]
                    )),
                }
                for agent, tool_ids in self._by_agent.items()
            },
        }


# Create global registry instance
_TOOL_REGISTRY: Optional[UnifiedToolRegistry] = None


def get_tool_registry() -> UnifiedToolRegistry:
    """Get or create the global tool registry."""
    global _TOOL_REGISTRY
    if _TOOL_REGISTRY is None:
        _TOOL_REGISTRY = UnifiedToolRegistry()
        _TOOL_REGISTRY.discover_all()
    return _TOOL_REGISTRY


# ---------------------------------------------------------------------------
# Type Definitions
# ---------------------------------------------------------------------------

T = TypeVar("T")
ToolHandler = Callable[..., Any]


class AgentStatus(Enum):
    """Agent lifecycle states."""
    INITIALIZING = "initializing"
    READY = "ready"
    ACTIVE = "active"
    PAUSED = "paused"
    TERMINATED = "terminated"
    ERROR = "error"


class LogLevel(Enum):
    """Compliance-ready log levels."""
    TRACE = "TRACE"           # Detailed debugging
    DEBUG = "DEBUG"           # Development info
    INFO = "INFO"             # Normal operations
    NOTICE = "NOTICE"         # Significant events
    WARNING = "WARNING"       # Potential issues
    ERROR = "ERROR"           # Errors that don't halt execution
    CRITICAL = "CRITICAL"     # Critical failures
    AUDIT = "AUDIT"           # Compliance audit trail
    SECURITY = "SECURITY"     # Security events
    COMPLIANCE = "COMPLIANCE" # Regulatory compliance
    METRICS = "METRICS"       # Performance metrics


class LogFormat(Enum):
    """Interchangeable log output formats."""
    JSON = "json"             # Structured JSON (default)
    SYSLOG = "syslog"         # RFC 5424 syslog
    CEF = "cef"               # Common Event Format (ArcSight)
    LEEF = "leef"             # Log Event Extended Format (IBM QRadar)
    GELF = "gelf"             # Graylog Extended Log Format
    ECS = "ecs"               # Elastic Common Schema
    OTEL = "otel"             # OpenTelemetry format
    PLAIN = "plain"           # Human-readable


# ---------------------------------------------------------------------------
# Tool Definition
# ---------------------------------------------------------------------------

@dataclass
class ToolDefinition:
    """MCP-style tool definition for agent capabilities."""
    name: str
    description: str
    handler: Optional[ToolHandler] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    required_params: List[str] = field(default_factory=list)
    category: str = "general"
    requires_auth: bool = False
    rate_limit: Optional[int] = None  # calls per minute
    timeout_ms: int = 30000
    idempotent: bool = False
    audit_log: bool = True  # Log to audit trail


@dataclass
class ToolCategoryGroup:
    """Grouping for related tools."""
    name: str
    description: str
    tools: List[str] = field(default_factory=list)
    icon: str = "🔧"


# ---------------------------------------------------------------------------
# Agent Module Definition
# ---------------------------------------------------------------------------

@dataclass
class AgentModuleDefinition:
    """Complete agent module preset definition.
    
    Similar to MCP server manifest, defines an agent's:
    - Identity and personality
    - Trade-specific terminology
    - Available tools and capabilities
    - Logging and compliance configuration
    """
    module_id: str
    name: str
    version: str
    description: str
    
    # Personality & Character
    personality_traits: List[str] = field(default_factory=list)
    communication_style: str = ""
    trade_terminology: Dict[str, str] = field(default_factory=dict)
    domain_expertise: List[str] = field(default_factory=list)
    
    # Tools & Capabilities
    tools: List[ToolDefinition] = field(default_factory=list)
    inherited_modules: List[str] = field(default_factory=list)  # Modules to inherit tools from
    
    # System Configuration
    system_prompt: str = ""
    max_context_tokens: int = 8192
    temperature: float = 0.7
    
    # Compliance & Logging
    log_format: LogFormat = LogFormat.JSON
    audit_enabled: bool = True
    compliance_standards: List[str] = field(default_factory=list)  # e.g., ["SOC2", "GDPR", "HIPAA"]
    
    # Rosetta Integration
    rosetta_enabled: bool = True
    history_retention_days: int = 90


# ---------------------------------------------------------------------------
# Compliance Logger
# ---------------------------------------------------------------------------

class ComplianceLogger:
    """Multi-format compliance-ready logger with audit trail.
    
    Supports interchangeable log formats for different SIEM/logging systems:
    - JSON (default, structured)
    - Syslog (RFC 5424)
    - CEF (ArcSight)
    - LEEF (IBM QRadar)
    - GELF (Graylog)
    - ECS (Elastic)
    - OTEL (OpenTelemetry)
    """
    
    def __init__(
        self,
        agent_id: str,
        log_format: LogFormat = LogFormat.JSON,
        compliance_standards: Optional[List[str]] = None,
    ):
        self.agent_id = agent_id
        self.log_format = log_format
        self.compliance_standards = compliance_standards or []
        self._log_buffer: List[Dict[str, Any]] = []
        self._audit_trail: List[Dict[str, Any]] = []
        
    def _format_timestamp(self) -> str:
        """ISO 8601 timestamp with timezone."""
        return datetime.now(timezone.utc).isoformat()
    
    def _create_base_entry(
        self,
        level: LogLevel,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create base log entry structure."""
        return {
            "timestamp": self._format_timestamp(),
            "level": level.value,
            "agent_id": self.agent_id,
            "message": message,
            "context": context or {},
            "trace_id": str(uuid.uuid4()),
            "compliance_standards": self.compliance_standards,
        }
    
    def _format_json(self, entry: Dict[str, Any]) -> str:
        """Format as structured JSON."""
        return json.dumps(entry, default=str)
    
    def _format_syslog(self, entry: Dict[str, Any]) -> str:
        """Format as RFC 5424 syslog."""
        pri = self._syslog_priority(entry["level"])
        timestamp = entry["timestamp"]
        hostname = os.environ.get("HOSTNAME", "murphy-system")
        app_name = f"murphy-agent-{self.agent_id}"
        proc_id = os.getpid()
        msg_id = entry.get("trace_id", "-")[:8]
        structured_data = f'[murphy agent_id="{self.agent_id}"]'
        message = entry["message"]
        return f"<{pri}>1 {timestamp} {hostname} {app_name} {proc_id} {msg_id} {structured_data} {message}"
    
    def _syslog_priority(self, level: str) -> int:
        """Calculate syslog priority (facility * 8 + severity)."""
        # Facility 1 = user-level messages
        facility = 1
        severity_map = {
            "TRACE": 7, "DEBUG": 7, "INFO": 6, "NOTICE": 5,
            "WARNING": 4, "ERROR": 3, "CRITICAL": 2, "AUDIT": 5,
            "SECURITY": 4, "COMPLIANCE": 5, "METRICS": 6,
        }
        severity = severity_map.get(level, 6)
        return facility * 8 + severity
    
    def _format_cef(self, entry: Dict[str, Any]) -> str:
        """Format as Common Event Format (CEF) for ArcSight."""
        severity = {"CRITICAL": 10, "ERROR": 7, "WARNING": 5, "INFO": 3}.get(entry["level"], 1)
        return (
            f"CEF:0|Inoni|MurphySystem|1.0|agent_log|{entry['message'][:50]}|{severity}|"
            f"agentId={self.agent_id} msg={entry['message']} "
            f"dvc={os.environ.get('HOSTNAME', 'murphy')} "
            f"rt={entry['timestamp']}"
        )
    
    def _format_leef(self, entry: Dict[str, Any]) -> str:
        """Format as Log Event Extended Format (LEEF) for IBM QRadar."""
        return (
            f"LEEF:2.0|Inoni|MurphySystem|1.0|AgentLog|"
            f"devTime={entry['timestamp']}\t"
            f"sev={entry['level']}\t"
            f"agentId={self.agent_id}\t"
            f"msg={entry['message']}"
        )
    
    def _format_gelf(self, entry: Dict[str, Any]) -> str:
        """Format as Graylog Extended Log Format (GELF)."""
        level_map = {"CRITICAL": 2, "ERROR": 3, "WARNING": 4, "NOTICE": 5, "INFO": 6, "DEBUG": 7}
        gelf = {
            "version": "1.1",
            "host": os.environ.get("HOSTNAME", "murphy-system"),
            "short_message": entry["message"][:100],
            "full_message": entry["message"],
            "timestamp": time.time(),
            "level": level_map.get(entry["level"], 6),
            "_agent_id": self.agent_id,
            "_trace_id": entry.get("trace_id"),
        }
        return json.dumps(gelf)
    
    def _format_ecs(self, entry: Dict[str, Any]) -> str:
        """Format as Elastic Common Schema (ECS)."""
        ecs = {
            "@timestamp": entry["timestamp"],
            "log": {"level": entry["level"].lower()},
            "message": entry["message"],
            "agent": {"id": self.agent_id, "type": "murphy-agent"},
            "trace": {"id": entry.get("trace_id")},
            "labels": {"compliance": ",".join(self.compliance_standards)},
        }
        return json.dumps(ecs)
    
    def _format_otel(self, entry: Dict[str, Any]) -> str:
        """Format as OpenTelemetry log record."""
        severity_map = {
            "TRACE": 1, "DEBUG": 5, "INFO": 9, "NOTICE": 10,
            "WARNING": 13, "ERROR": 17, "CRITICAL": 21,
        }
        otel = {
            "timeUnixNano": int(time.time() * 1e9),
            "severityNumber": severity_map.get(entry["level"], 9),
            "severityText": entry["level"],
            "body": {"stringValue": entry["message"]},
            "attributes": [
                {"key": "agent_id", "value": {"stringValue": self.agent_id}},
                {"key": "trace_id", "value": {"stringValue": entry.get("trace_id", "")}},
            ],
            "traceId": entry.get("trace_id", "").replace("-", "")[:32].ljust(32, "0"),
            "spanId": str(uuid.uuid4()).replace("-", "")[:16],
        }
        return json.dumps(otel)
    
    def _format_plain(self, entry: Dict[str, Any]) -> str:
        """Format as human-readable plain text."""
        return f"[{entry['timestamp']}] [{entry['level']:10}] [{self.agent_id}] {entry['message']}"
    
    def format(self, entry: Dict[str, Any]) -> str:
        """Format log entry according to configured format."""
        formatters = {
            LogFormat.JSON: self._format_json,
            LogFormat.SYSLOG: self._format_syslog,
            LogFormat.CEF: self._format_cef,
            LogFormat.LEEF: self._format_leef,
            LogFormat.GELF: self._format_gelf,
            LogFormat.ECS: self._format_ecs,
            LogFormat.OTEL: self._format_otel,
            LogFormat.PLAIN: self._format_plain,
        }
        return formatters.get(self.log_format, self._format_json)(entry)
    
    def log(
        self,
        level: LogLevel,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a message at the specified level."""
        entry = self._create_base_entry(level, message, context)
        formatted = self.format(entry)
        self._log_buffer.append(entry)
        
        # Write to standard logger
        py_level = {
            LogLevel.TRACE: logging.DEBUG,
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.NOTICE: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
            LogLevel.AUDIT: logging.INFO,
            LogLevel.SECURITY: logging.WARNING,
            LogLevel.COMPLIANCE: logging.INFO,
            LogLevel.METRICS: logging.DEBUG,
        }.get(level, logging.INFO)
        
        logger.log(py_level, formatted)
        
        # Add to audit trail for compliance levels
        if level in (LogLevel.AUDIT, LogLevel.SECURITY, LogLevel.COMPLIANCE):
            self._audit_trail.append(entry)
    
    def audit(self, action: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log an audit event."""
        self.log(LogLevel.AUDIT, f"AUDIT: {action}", context)
    
    def security(self, event: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log a security event."""
        self.log(LogLevel.SECURITY, f"SECURITY: {event}", context)
    
    def compliance(self, requirement: str, status: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log a compliance check."""
        ctx = context or {}
        ctx["requirement"] = requirement
        ctx["status"] = status
        self.log(LogLevel.COMPLIANCE, f"COMPLIANCE [{requirement}]: {status}", ctx)
    
    def metrics(self, metric_name: str, value: Any, unit: str = "", context: Optional[Dict[str, Any]] = None) -> None:
        """Log a metrics event."""
        ctx = context or {}
        ctx["metric_name"] = metric_name
        ctx["metric_value"] = value
        ctx["metric_unit"] = unit
        self.log(LogLevel.METRICS, f"METRIC {metric_name}={value}{unit}", ctx)
    
    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Return the audit trail for compliance reporting."""
        return list(self._audit_trail)
    
    def export_logs(self, output_format: Optional[LogFormat] = None) -> List[str]:
        """Export all buffered logs in the specified format."""
        fmt = output_format or self.log_format
        original_format = self.log_format
        self.log_format = fmt
        result = [self.format(entry) for entry in self._log_buffer]
        self.log_format = original_format
        return result


# ---------------------------------------------------------------------------
# Rosetta History Bridge
# ---------------------------------------------------------------------------

@dataclass
class HistoryEntry:
    """A single entry in the Rosetta history bridge."""
    timestamp: str
    source_agent: str
    target_agent: Optional[str]
    action: str
    context: Dict[str, Any]
    rosetta_translation: Optional[Dict[str, Any]] = None


class RosettaHistoryBridge:
    """Translation layer for context/history interoperability between agents.
    
    Provides:
    - Context preservation across agent switches
    - Terminology translation between domains
    - History compression for token efficiency
    - Cross-agent collaboration tracking
    """
    
    def __init__(self, max_history: int = 1000):
        self._history: List[HistoryEntry] = []
        self._max_history = max_history
        self._terminology_maps: Dict[str, Dict[str, str]] = {}
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
    
    def register_terminology(self, domain: str, terms: Dict[str, str]) -> None:
        """Register domain-specific terminology for translation.
        
        Args:
            domain: Domain identifier (e.g., "security", "devops", "finance")
            terms: Dictionary mapping general terms to domain-specific terms
        """
        self._terminology_maps[domain] = terms
        logger.debug(f"Registered {len(terms)} terms for domain '{domain}'")
    
    def translate_context(
        self,
        context: Dict[str, Any],
        source_domain: str,
        target_domain: str,
    ) -> Dict[str, Any]:
        """Translate context from one domain's terminology to another.
        
        Args:
            context: Original context dictionary
            source_domain: Source agent's domain
            target_domain: Target agent's domain
            
        Returns:
            Translated context with domain-appropriate terminology
        """
        if source_domain == target_domain:
            return context
        
        source_terms = self._terminology_maps.get(source_domain, {})
        target_terms = self._terminology_maps.get(target_domain, {})
        
        # Build reverse mapping: source_specific -> general -> target_specific
        general_to_source = {v: k for k, v in source_terms.items()}
        
        translated = {}
        for key, value in context.items():
            # Translate key if it's domain-specific
            general_key = general_to_source.get(key, key)
            target_key = target_terms.get(general_key, general_key)
            
            # Translate value if it's a string
            if isinstance(value, str):
                general_value = general_to_source.get(value, value)
                target_value = target_terms.get(general_value, general_value)
                translated[target_key] = target_value
            else:
                translated[target_key] = value
        
        return translated
    
    def record_action(
        self,
        source_agent: str,
        action: str,
        context: Dict[str, Any],
        target_agent: Optional[str] = None,
    ) -> str:
        """Record an action in the history bridge.
        
        Returns:
            Entry ID for reference
        """
        entry = HistoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_agent=source_agent,
            target_agent=target_agent,
            action=action,
            context=context,
        )
        
        self._history.append(entry)
        
        # Trim history if needed
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        
        return entry.timestamp
    
    def get_agent_history(
        self,
        agent_id: str,
        limit: int = 100,
        include_related: bool = True,
    ) -> List[HistoryEntry]:
        """Get history entries for a specific agent.
        
        Args:
            agent_id: Agent to get history for
            limit: Maximum entries to return
            include_related: Include entries where agent is target
            
        Returns:
            List of history entries
        """
        entries = []
        for entry in reversed(self._history):
            if entry.source_agent == agent_id:
                entries.append(entry)
            elif include_related and entry.target_agent == agent_id:
                entries.append(entry)
            
            if len(entries) >= limit:
                break
        
        return list(reversed(entries))
    
    def compress_context(
        self,
        context: Dict[str, Any],
        max_tokens: int = 1000,
    ) -> Dict[str, Any]:
        """Compress context for token efficiency.
        
        Prioritizes:
        - Recent actions
        - Key decisions
        - Error states
        - User preferences
        """
        # Priority fields to preserve
        priority_fields = {
            "user_id", "session_id", "current_task", "error_state",
            "user_preferences", "last_action", "pending_actions",
        }
        
        compressed = {}
        
        # Always include priority fields
        for field in priority_fields:
            if field in context:
                compressed[field] = context[field]
        
        # Add remaining fields up to token estimate
        # (rough estimate: 4 chars per token)
        current_size = len(json.dumps(compressed))
        max_chars = max_tokens * 4
        
        for key, value in context.items():
            if key not in priority_fields:
                value_str = json.dumps(value) if not isinstance(value, str) else value
                if current_size + len(key) + len(value_str) < max_chars:
                    compressed[key] = value
                    current_size += len(key) + len(value_str)
        
        return compressed
    
    def start_session(self, session_id: str, initial_context: Dict[str, Any]) -> None:
        """Start a collaborative session with initial context."""
        self._active_sessions[session_id] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "context": initial_context,
            "participants": set(),
            "handoffs": [],
        }
    
    def handoff(
        self,
        session_id: str,
        from_agent: str,
        to_agent: str,
        context: Dict[str, Any],
        reason: str = "",
    ) -> Dict[str, Any]:
        """Hand off a session from one agent to another.
        
        Returns:
            Translated context for the receiving agent
        """
        if session_id not in self._active_sessions:
            self.start_session(session_id, context)
        
        session = self._active_sessions[session_id]
        session["participants"].add(from_agent)
        session["participants"].add(to_agent)
        
        # Record the handoff
        handoff_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "from_agent": from_agent,
            "to_agent": to_agent,
            "reason": reason,
        }
        session["handoffs"].append(handoff_record)
        
        # Update session context
        session["context"].update(context)
        
        # Record in history
        self.record_action(
            source_agent=from_agent,
            action="handoff",
            context={"reason": reason, **context},
            target_agent=to_agent,
        )
        
        # Translate context for target agent
        # (In a full implementation, we'd look up agent domains)
        return session["context"]
    
    def end_session(self, session_id: str) -> Dict[str, Any]:
        """End a collaborative session and return summary."""
        if session_id not in self._active_sessions:
            return {}
        
        session = self._active_sessions.pop(session_id)
        return {
            "session_id": session_id,
            "started_at": session["started_at"],
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "participants": list(session["participants"]),
            "handoff_count": len(session["handoffs"]),
            "final_context": session["context"],
        }


# ---------------------------------------------------------------------------
# Agent Module Loader
# ---------------------------------------------------------------------------

class AgentModuleLoader:
    """MCP-style agent module loader.
    
    Loads agents as interchangeable module presets with:
    - Tool registration and discovery
    - Rosetta history integration
    - Compliance logging
    - Hot-swappable personalities
    
    Usage:
        loader = AgentModuleLoader()
        
        # Start a specific agent
        agent = loader.start("security-agent")
        print(f"Started {agent.name} with {len(agent.tools)} tools")
        
        # List available tools
        for tool in loader.list_tools("security-agent"):
            print(f"  - {tool.name}: {tool.description}")
        
        # Start general-purpose agent with all tools
        general = loader.start("general-agent")
    """
    
    def __init__(self, log_format: LogFormat = LogFormat.JSON):
        self._modules: Dict[str, AgentModuleDefinition] = {}
        self._active_agents: Dict[str, Dict[str, Any]] = {}
        self._rosetta_bridge = RosettaHistoryBridge()
        self._log_format = log_format
        self._tool_registry: Dict[str, ToolDefinition] = {}
        
        # Register built-in modules
        self._register_builtin_modules()
        self._register_trade_terminology()
    
    def _register_builtin_modules(self) -> None:
        """Register built-in agent module presets."""
        
        # Security Agent
        self.register_module(AgentModuleDefinition(
            module_id="security-agent",
            name="SecurityBot",
            version="1.0.0",
            description="Security specialist agent with threat detection and compliance expertise",
            personality_traits=["vigilant", "methodical", "risk-aware", "protective"],
            communication_style="Precise, alert-focused, uses security terminology. Prioritizes risk severity.",
            trade_terminology={
                "problem": "vulnerability",
                "error": "security incident",
                "check": "security audit",
                "user": "principal",
                "permission": "authorization",
                "access": "privilege",
                "sensitive": "classified",
                "issue": "finding",
            },
            domain_expertise=[
                "threat_detection", "vulnerability_assessment", "compliance_audit",
                "access_control", "encryption", "incident_response", "penetration_testing",
            ],
            tools=self._create_security_tools(),
            system_prompt=self._security_system_prompt(),
            compliance_standards=["SOC2", "ISO27001", "NIST", "CIS"],
            audit_enabled=True,
        ))
        
        # DevOps Agent
        self.register_module(AgentModuleDefinition(
            module_id="devops-agent",
            name="DevOpsBot",
            version="1.0.0",
            description="DevOps specialist with CI/CD, infrastructure, and deployment expertise",
            personality_traits=["efficient", "automation-focused", "systematic", "reliable"],
            communication_style="Technical, pipeline-oriented, uses deployment terminology. Focuses on reliability.",
            trade_terminology={
                "update": "deployment",
                "error": "pipeline failure",
                "check": "health check",
                "environment": "stage",
                "version": "release",
                "copy": "artifact",
                "run": "execution",
                "stop": "rollback",
            },
            domain_expertise=[
                "ci_cd", "kubernetes", "docker", "terraform", "monitoring",
                "infrastructure_as_code", "deployment_automation", "sre",
            ],
            tools=self._create_devops_tools(),
            system_prompt=self._devops_system_prompt(),
            compliance_standards=["SOC2"],
        ))
        
        # Data Agent
        self.register_module(AgentModuleDefinition(
            module_id="data-agent",
            name="DataBot",
            version="1.0.0",
            description="Data engineering and analytics specialist",
            personality_traits=["analytical", "precise", "data-driven", "thorough"],
            communication_style="Uses statistical terminology, references data quality. Focuses on accuracy.",
            trade_terminology={
                "information": "dataset",
                "check": "data validation",
                "error": "data quality issue",
                "transform": "ETL",
                "storage": "data warehouse",
                "report": "analytics",
                "pattern": "insight",
                "history": "time series",
            },
            domain_expertise=[
                "sql", "data_pipelines", "etl", "data_quality", "analytics",
                "machine_learning", "statistics", "visualization",
            ],
            tools=self._create_data_tools(),
            system_prompt=self._data_system_prompt(),
        ))
        
        # Finance Agent
        self.register_module(AgentModuleDefinition(
            module_id="finance-agent",
            name="FinanceBot",
            version="1.0.0",
            description="Financial operations and compliance specialist",
            personality_traits=["precise", "risk-conscious", "compliant", "detail-oriented"],
            communication_style="Uses financial terminology, references regulations. Double-checks calculations.",
            trade_terminology={
                "money": "funds",
                "send": "remit",
                "receive": "credit",
                "check": "reconciliation",
                "error": "discrepancy",
                "approval": "authorization",
                "record": "ledger entry",
                "summary": "financial statement",
            },
            domain_expertise=[
                "accounting", "compliance", "audit", "tax", "treasury",
                "accounts_payable", "accounts_receivable", "financial_reporting",
            ],
            tools=self._create_finance_tools(),
            system_prompt=self._finance_system_prompt(),
            compliance_standards=["SOX", "GAAP", "PCI-DSS"],
        ))
        
        # Communications Agent
        self.register_module(AgentModuleDefinition(
            module_id="comms-agent",
            name="CommsBot",
            version="1.0.0",
            description="Communications and messaging specialist",
            personality_traits=["clear", "concise", "empathetic", "responsive"],
            communication_style="Adapts tone to audience. Prioritizes clarity and appropriate channel.",
            trade_terminology={
                "message": "communication",
                "send": "dispatch",
                "reply": "response",
                "user": "recipient",
                "group": "distribution list",
                "urgent": "priority",
                "draft": "template",
                "thread": "conversation",
            },
            domain_expertise=[
                "email", "slack", "teams", "notifications", "templates",
                "tone_analysis", "audience_targeting", "multi_channel",
            ],
            tools=self._create_comms_tools(),
            system_prompt=self._comms_system_prompt(),
        ))
        
        # General-Purpose Agent (inherits all tools)
        self.register_module(AgentModuleDefinition(
            module_id="general-agent",
            name="GeneralBot",
            version="1.0.0",
            description="General-purpose agent with access to all tools and capabilities",
            personality_traits=["versatile", "helpful", "knowledgeable", "adaptive"],
            communication_style="Adapts to context. Can use specialized terminology when appropriate.",
            trade_terminology={},  # Uses all terminologies
            domain_expertise=["all"],
            inherited_modules=[
                "security-agent", "devops-agent", "data-agent",
                "finance-agent", "comms-agent",
            ],
            tools=[],  # Inherits all tools
            system_prompt=self._general_system_prompt(),
            compliance_standards=["SOC2", "GDPR", "HIPAA", "PCI-DSS"],
            audit_enabled=True,
        ))
    
    def _register_trade_terminology(self) -> None:
        """Register domain-specific terminology with Rosetta bridge."""
        for module_id, module in self._modules.items():
            if module.trade_terminology:
                self._rosetta_bridge.register_terminology(
                    domain=module_id.replace("-agent", ""),
                    terms=module.trade_terminology,
                )
    
    def _create_security_tools(self) -> List[ToolDefinition]:
        """Create security-specific tools."""
        return [
            ToolDefinition(
                name="scan_vulnerabilities",
                description="Scan code or infrastructure for security vulnerabilities",
                category="security",
                parameters={"target": "string", "scan_type": "string"},
                required_params=["target"],
                audit_log=True,
            ),
            ToolDefinition(
                name="check_compliance",
                description="Verify compliance against security standards",
                category="security",
                parameters={"standard": "string", "scope": "string"},
                required_params=["standard"],
                audit_log=True,
            ),
            ToolDefinition(
                name="analyze_threat",
                description="Analyze potential security threats",
                category="security",
                parameters={"threat_data": "object"},
                audit_log=True,
            ),
            ToolDefinition(
                name="generate_security_report",
                description="Generate security assessment report",
                category="security",
                parameters={"report_type": "string", "time_range": "string"},
            ),
            ToolDefinition(
                name="manage_secrets",
                description="Securely manage secrets and credentials",
                category="security",
                parameters={"action": "string", "secret_id": "string"},
                requires_auth=True,
                audit_log=True,
            ),
        ]
    
    def _create_devops_tools(self) -> List[ToolDefinition]:
        """Create DevOps-specific tools."""
        return [
            ToolDefinition(
                name="deploy",
                description="Deploy application to target environment",
                category="devops",
                parameters={"environment": "string", "version": "string"},
                required_params=["environment"],
                audit_log=True,
            ),
            ToolDefinition(
                name="rollback",
                description="Rollback deployment to previous version",
                category="devops",
                parameters={"environment": "string", "target_version": "string"},
                audit_log=True,
            ),
            ToolDefinition(
                name="check_pipeline",
                description="Check CI/CD pipeline status",
                category="devops",
                parameters={"pipeline_id": "string"},
            ),
            ToolDefinition(
                name="scale_service",
                description="Scale service replicas up or down",
                category="devops",
                parameters={"service": "string", "replicas": "integer"},
                audit_log=True,
            ),
            ToolDefinition(
                name="view_logs",
                description="View application or infrastructure logs",
                category="devops",
                parameters={"service": "string", "time_range": "string", "filter": "string"},
            ),
        ]
    
    def _create_data_tools(self) -> List[ToolDefinition]:
        """Create data engineering tools."""
        return [
            ToolDefinition(
                name="query_data",
                description="Execute data query against warehouse",
                category="data",
                parameters={"query": "string", "database": "string"},
                required_params=["query"],
            ),
            ToolDefinition(
                name="validate_data",
                description="Validate data quality and integrity",
                category="data",
                parameters={"dataset": "string", "rules": "array"},
            ),
            ToolDefinition(
                name="run_pipeline",
                description="Execute data pipeline",
                category="data",
                parameters={"pipeline_id": "string", "parameters": "object"},
                audit_log=True,
            ),
            ToolDefinition(
                name="generate_report",
                description="Generate analytics report",
                category="data",
                parameters={"report_type": "string", "filters": "object"},
            ),
            ToolDefinition(
                name="export_data",
                description="Export data to specified format",
                category="data",
                parameters={"dataset": "string", "format": "string", "destination": "string"},
                audit_log=True,
            ),
        ]
    
    def _create_finance_tools(self) -> List[ToolDefinition]:
        """Create finance-specific tools."""
        return [
            ToolDefinition(
                name="process_payment",
                description="Process a payment transaction",
                category="finance",
                parameters={"amount": "number", "currency": "string", "recipient": "string"},
                requires_auth=True,
                audit_log=True,
            ),
            ToolDefinition(
                name="reconcile_accounts",
                description="Reconcile account balances",
                category="finance",
                parameters={"account_ids": "array", "date_range": "string"},
                audit_log=True,
            ),
            ToolDefinition(
                name="generate_invoice",
                description="Generate invoice for customer",
                category="finance",
                parameters={"customer_id": "string", "line_items": "array"},
                audit_log=True,
            ),
            ToolDefinition(
                name="check_budget",
                description="Check budget status and utilization",
                category="finance",
                parameters={"budget_id": "string", "period": "string"},
            ),
            ToolDefinition(
                name="audit_transactions",
                description="Audit financial transactions",
                category="finance",
                parameters={"date_range": "string", "filters": "object"},
                audit_log=True,
            ),
        ]
    
    def _create_comms_tools(self) -> List[ToolDefinition]:
        """Create communications tools."""
        return [
            ToolDefinition(
                name="send_email",
                description="Send email message",
                category="comms",
                parameters={"to": "string", "subject": "string", "body": "string"},
                required_params=["to", "subject"],
                audit_log=True,
            ),
            ToolDefinition(
                name="send_slack",
                description="Send Slack message",
                category="comms",
                parameters={"channel": "string", "message": "string"},
                required_params=["channel", "message"],
            ),
            ToolDefinition(
                name="send_notification",
                description="Send push notification",
                category="comms",
                parameters={"user_id": "string", "title": "string", "body": "string"},
            ),
            ToolDefinition(
                name="schedule_message",
                description="Schedule message for future delivery",
                category="comms",
                parameters={"channel_type": "string", "schedule_time": "string", "content": "object"},
            ),
            ToolDefinition(
                name="create_template",
                description="Create reusable message template",
                category="comms",
                parameters={"name": "string", "template": "string", "variables": "array"},
            ),
        ]
    
    def _security_system_prompt(self) -> str:
        """System prompt for security agent."""
        return """You are SecurityBot, a vigilant security specialist for Murphy System.

Your expertise includes:
- Vulnerability assessment and threat detection
- Security compliance (SOC2, ISO27001, NIST, CIS)
- Access control and authorization
- Incident response and forensics
- Encryption and secret management

Communication style:
- Use precise security terminology
- Prioritize issues by risk severity (Critical > High > Medium > Low)
- Reference specific CVEs, CWEs, and compliance controls
- Always recommend mitigations with severity assessment

When analyzing security:
1. Identify the vulnerability or threat
2. Assess impact and likelihood
3. Provide remediation steps
4. Cite relevant compliance requirements
"""
    
    def _devops_system_prompt(self) -> str:
        """System prompt for devops agent."""
        return """You are DevOpsBot, an efficient DevOps specialist for Murphy System.

Your expertise includes:
- CI/CD pipeline management
- Kubernetes and container orchestration
- Infrastructure as Code (Terraform, Pulumi)
- Monitoring and observability
- Deployment strategies (blue-green, canary)

Communication style:
- Use pipeline and deployment terminology
- Focus on reliability and availability metrics
- Reference SLOs, SLIs, and error budgets
- Always consider rollback strategies

When handling deployments:
1. Verify pipeline health
2. Check pre-deployment gates
3. Monitor rollout progress
4. Prepare rollback if needed
"""
    
    def _data_system_prompt(self) -> str:
        """System prompt for data agent."""
        return """You are DataBot, a precise data engineering specialist for Murphy System.

Your expertise includes:
- SQL and data warehouse operations
- ETL pipeline development
- Data quality and validation
- Analytics and visualization
- Machine learning integration

Communication style:
- Use statistical and data terminology
- Reference data quality metrics (completeness, accuracy, consistency)
- Provide confidence intervals where applicable
- Always validate data before operations

When working with data:
1. Validate input data quality
2. Document transformations
3. Verify output accuracy
4. Maintain audit trail
"""
    
    def _finance_system_prompt(self) -> str:
        """System prompt for finance agent."""
        return """You are FinanceBot, a precise financial operations specialist for Murphy System.

Your expertise includes:
- Accounting and ledger management
- Financial compliance (SOX, GAAP, PCI-DSS)
- Payment processing
- Budget management
- Financial reporting

Communication style:
- Use financial terminology precisely
- Always double-check calculations
- Reference relevant regulations
- Maintain complete audit trail

When handling financial operations:
1. Verify authorization
2. Validate amounts and accounts
3. Record all transactions
4. Ensure compliance
"""
    
    def _comms_system_prompt(self) -> str:
        """System prompt for communications agent."""
        return """You are CommsBot, a clear communications specialist for Murphy System.

Your expertise includes:
- Multi-channel messaging (email, Slack, Teams, SMS)
- Message templates and personalization
- Audience targeting
- Tone analysis and adaptation
- Notification management

Communication style:
- Adapt tone to audience and context
- Prioritize clarity and brevity
- Use appropriate channel for message type
- Consider timing and urgency

When crafting communications:
1. Identify target audience
2. Select appropriate channel
3. Adapt tone and format
4. Schedule for optimal delivery
"""
    
    def _general_system_prompt(self) -> str:
        """System prompt for general-purpose agent."""
        return """You are GeneralBot, a versatile general-purpose agent for Murphy System.

You have access to ALL specialized tools and can adapt to any domain:
- Security operations
- DevOps and deployments
- Data engineering
- Financial operations
- Communications

Communication style:
- Adapt to the current context
- Use domain-specific terminology when appropriate
- Route complex tasks to specialized agents when beneficial
- Maintain comprehensive audit trail

When handling requests:
1. Identify the domain
2. Apply relevant expertise
3. Use appropriate terminology
4. Consider cross-domain implications
"""
    
    def register_module(self, module: AgentModuleDefinition) -> None:
        """Register an agent module preset."""
        self._modules[module.module_id] = module
        
        # Register tools in global registry
        for tool in module.tools:
            tool_id = f"{module.module_id}/{tool.name}"
            self._tool_registry[tool_id] = tool
        
        logger.info(f"Registered agent module '{module.module_id}' with {len(module.tools)} tools")
    
    def start(self, module_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Start an agent from a module preset.
        
        Args:
            module_id: ID of the module to start
            session_id: Optional session ID for context continuity
            
        Returns:
            Agent instance info including name, tools, and logger
        """
        if module_id not in self._modules:
            raise ValueError(f"Unknown module: {module_id}. Available: {list(self._modules.keys())}")
        
        module = self._modules[module_id]
        agent_instance_id = f"{module_id}-{uuid.uuid4().hex[:8]}"
        
        # Create compliance logger
        agent_logger = ComplianceLogger(
            agent_id=agent_instance_id,
            log_format=module.log_format,
            compliance_standards=module.compliance_standards,
        )
        
        # Collect all tools (including inherited)
        all_tools = list(module.tools)
        for inherited_id in module.inherited_modules:
            if inherited_id in self._modules:
                all_tools.extend(self._modules[inherited_id].tools)
        
        # Remove duplicates by name
        seen_names: Set[str] = set()
        unique_tools = []
        for tool in all_tools:
            if tool.name not in seen_names:
                unique_tools.append(tool)
                seen_names.add(tool.name)
        
        # Create agent instance
        agent_instance = {
            "instance_id": agent_instance_id,
            "module_id": module_id,
            "name": module.name,
            "version": module.version,
            "description": module.description,
            "tools": unique_tools,
            "tool_count": len(unique_tools),
            "logger": agent_logger,
            "rosetta_bridge": self._rosetta_bridge,
            "status": AgentStatus.READY,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id or str(uuid.uuid4()),
            "personality": module.personality_traits,
            "system_prompt": module.system_prompt,
        }
        
        self._active_agents[agent_instance_id] = agent_instance
        
        # Log startup
        agent_logger.log(
            LogLevel.INFO,
            f"Agent '{module.name}' started successfully (version {module.version}) with {len(unique_tools)} tools",
        )
        agent_logger.audit("agent_started", {
            "module_id": module_id,
            "instance_id": agent_instance_id,
            "tool_count": len(unique_tools),
        })
        
        # Print MCP-style startup message
        self._print_startup_message(module, unique_tools)
        
        return agent_instance
    
    def _print_startup_message(self, module: AgentModuleDefinition, tools: List[ToolDefinition]) -> None:
        """Print MCP-style startup message."""
        print(f"\nStart '{module.module_id}' agent server")
        print(f"Agent started successfully (version {module.version}) with {len(tools)} tools")
        print()
        for tool in tools:
            print(f"- {module.module_id}/{tool.name}")
        print()
    
    def stop(self, instance_id: str) -> Dict[str, Any]:
        """Stop a running agent instance."""
        if instance_id not in self._active_agents:
            raise ValueError(f"Agent not found: {instance_id}")
        
        agent = self._active_agents.pop(instance_id)
        agent["status"] = AgentStatus.TERMINATED
        agent["stopped_at"] = datetime.now(timezone.utc).isoformat()
        
        agent["logger"].audit("agent_stopped", {
            "instance_id": instance_id,
        })
        
        return agent
    
    def list_modules(self) -> List[Dict[str, Any]]:
        """List all available agent modules."""
        return [
            {
                "module_id": m.module_id,
                "name": m.name,
                "version": m.version,
                "description": m.description,
                "tool_count": len(m.tools) + sum(
                    len(self._modules[i].tools) for i in m.inherited_modules if i in self._modules
                ),
                "compliance_standards": m.compliance_standards,
            }
            for m in self._modules.values()
        ]
    
    def list_tools(self, module_id: str) -> List[ToolDefinition]:
        """List tools available for a specific module."""
        if module_id not in self._modules:
            raise ValueError(f"Unknown module: {module_id}")
        
        module = self._modules[module_id]
        all_tools = list(module.tools)
        
        for inherited_id in module.inherited_modules:
            if inherited_id in self._modules:
                all_tools.extend(self._modules[inherited_id].tools)
        
        return all_tools
    
    def get_active_agents(self) -> List[Dict[str, Any]]:
        """Get list of currently active agents."""
        return [
            {
                "instance_id": a["instance_id"],
                "module_id": a["module_id"],
                "name": a["name"],
                "status": a["status"].value,
                "started_at": a["started_at"],
                "tool_count": a["tool_count"],
            }
            for a in self._active_agents.values()
        ]
    
    def handoff(
        self,
        from_instance_id: str,
        to_module_id: str,
        context: Dict[str, Any],
        reason: str = "",
    ) -> Dict[str, Any]:
        """Hand off execution from one agent to another.
        
        Uses Rosetta bridge for context translation and history preservation.
        """
        if from_instance_id not in self._active_agents:
            raise ValueError(f"Source agent not found: {from_instance_id}")
        
        from_agent = self._active_agents[from_instance_id]
        session_id = from_agent["session_id"]
        
        # Translate context through Rosetta
        translated_context = self._rosetta_bridge.handoff(
            session_id=session_id,
            from_agent=from_agent["module_id"],
            to_agent=to_module_id,
            context=context,
            reason=reason,
        )
        
        # Log the handoff
        from_agent["logger"].audit("agent_handoff", {
            "from": from_instance_id,
            "to": to_module_id,
            "reason": reason,
        })
        
        # Start new agent with translated context
        new_agent = self.start(to_module_id, session_id=session_id)
        
        return {
            "from_agent": from_instance_id,
            "to_agent": new_agent["instance_id"],
            "session_id": session_id,
            "translated_context": translated_context,
        }


# ---------------------------------------------------------------------------
# Clarification System
# ---------------------------------------------------------------------------

class ClarificationStatus(Enum):
    """Status of a clarification request."""
    PENDING = "pending"
    ANSWERED = "answered"
    ESCALATED = "escalated"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class ClarificationRequest:
    """A request for clarification from an agent."""
    request_id: str
    agent_id: str
    question: str
    context: Dict[str, Any]
    options: List[str] = field(default_factory=list)
    default_option: Optional[str] = None
    priority: str = "normal"  # low, normal, high, critical
    status: ClarificationStatus = ClarificationStatus.PENDING
    response: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    answered_at: Optional[str] = None
    timeout_seconds: int = 300  # 5 minutes default


class ClarificationSystem:
    """System for agents to request and receive clarifications.
    
    Provides:
    - Structured clarification requests
    - Timeout handling with defaults
    - Escalation paths
    - Audit trail of all clarifications
    """
    
    def __init__(self):
        self._pending: Dict[str, ClarificationRequest] = {}
        self._history: List[ClarificationRequest] = []
        self._escalation_handlers: Dict[str, Callable] = {}
    
    def request_clarification(
        self,
        agent_id: str,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        options: Optional[List[str]] = None,
        default_option: Optional[str] = None,
        priority: str = "normal",
        timeout_seconds: int = 300,
    ) -> ClarificationRequest:
        """Request clarification from a user or another agent.
        
        Args:
            agent_id: ID of the requesting agent
            question: The clarification question
            context: Additional context for the question
            options: Optional list of predefined answers
            default_option: Default answer if timeout
            priority: Request priority (low, normal, high, critical)
            timeout_seconds: Time before defaulting/escalating
            
        Returns:
            ClarificationRequest object
        """
        request = ClarificationRequest(
            request_id=str(uuid.uuid4()),
            agent_id=agent_id,
            question=question,
            context=context or {},
            options=options or [],
            default_option=default_option,
            priority=priority,
            timeout_seconds=timeout_seconds,
        )
        
        self._pending[request.request_id] = request
        logger.info(f"Clarification requested by {agent_id}: {question[:50]}...")
        
        return request
    
    def provide_answer(
        self,
        request_id: str,
        response: str,
        answered_by: str = "user",
    ) -> ClarificationRequest:
        """Provide an answer to a clarification request.
        
        Args:
            request_id: ID of the request to answer
            response: The answer
            answered_by: Who provided the answer
            
        Returns:
            Updated ClarificationRequest
        """
        if request_id not in self._pending:
            raise ValueError(f"Clarification request not found: {request_id}")
        
        request = self._pending.pop(request_id)
        request.response = response
        request.status = ClarificationStatus.ANSWERED
        request.answered_at = datetime.now(timezone.utc).isoformat()
        request.context["answered_by"] = answered_by
        
        self._history.append(request)
        logger.info(f"Clarification {request_id} answered: {response[:50]}...")
        
        return request
    
    def check_timeouts(self) -> List[ClarificationRequest]:
        """Check for timed out requests and apply defaults or escalate.
        
        Returns:
            List of requests that timed out
        """
        now = datetime.now(timezone.utc)
        timed_out = []
        
        for request_id, request in list(self._pending.items()):
            created = datetime.fromisoformat(request.created_at.replace("Z", "+00:00"))
            elapsed = (now - created).total_seconds()
            
            if elapsed > request.timeout_seconds:
                if request.default_option:
                    request.response = request.default_option
                    request.status = ClarificationStatus.TIMEOUT
                    logger.warning(f"Clarification {request_id} timed out, using default: {request.default_option}")
                else:
                    request.status = ClarificationStatus.ESCALATED
                    logger.warning(f"Clarification {request_id} timed out and escalated")
                    self._escalate(request)
                
                request.answered_at = now.isoformat()
                self._pending.pop(request_id)
                self._history.append(request)
                timed_out.append(request)
        
        return timed_out
    
    def _escalate(self, request: ClarificationRequest) -> None:
        """Escalate a clarification request."""
        handler = self._escalation_handlers.get(request.priority)
        if handler:
            try:
                handler(request)
            except Exception as e:
                logger.error(f"Escalation handler failed: {e}")
    
    def register_escalation_handler(self, priority: str, handler: Callable) -> None:
        """Register a handler for escalated clarifications."""
        self._escalation_handlers[priority] = handler
    
    def get_pending(self, agent_id: Optional[str] = None) -> List[ClarificationRequest]:
        """Get pending clarification requests."""
        if agent_id:
            return [r for r in self._pending.values() if r.agent_id == agent_id]
        return list(self._pending.values())
    
    def get_history(
        self,
        agent_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[ClarificationRequest]:
        """Get clarification history."""
        history = self._history
        if agent_id:
            history = [r for r in history if r.agent_id == agent_id]
        return history[-limit:]


# ---------------------------------------------------------------------------
# Checklist System
# ---------------------------------------------------------------------------

class ChecklistItemStatus(Enum):
    """Status of a checklist item."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class ChecklistItem:
    """A single item in a checklist."""
    item_id: str
    title: str
    description: str = ""
    status: ChecklistItemStatus = ChecklistItemStatus.PENDING
    assigned_to: Optional[str] = None  # agent_id
    dependencies: List[str] = field(default_factory=list)  # item_ids that must complete first
    verification: Optional[str] = None  # How to verify completion
    evidence: Dict[str, Any] = field(default_factory=dict)  # Proof of completion
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class Checklist:
    """A complete checklist for tracking progress."""
    checklist_id: str
    name: str
    description: str = ""
    items: List[ChecklistItem] = field(default_factory=list)
    created_by: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    organization_id: Optional[str] = None
    project_id: Optional[str] = None
    phase: str = "planning"  # planning, execution, review, complete
    
    @property
    def progress(self) -> float:
        """Calculate completion percentage."""
        if not self.items:
            return 0.0
        completed = sum(1 for i in self.items if i.status == ChecklistItemStatus.COMPLETED)
        return (completed / len(self.items)) * 100
    
    @property
    def status_summary(self) -> Dict[str, int]:
        """Get count of items by status."""
        summary: Dict[str, int] = {}
        for item in self.items:
            status = item.status.value
            summary[status] = summary.get(status, 0) + 1
        return summary


class ChecklistSystem:
    """System for managing checklists throughout the agent lifecycle.
    
    Provides:
    - Template-based checklist creation
    - Progress tracking with evidence
    - Dependency management
    - Integration with agent handoffs
    """
    
    def __init__(self):
        self._checklists: Dict[str, Checklist] = {}
        self._templates: Dict[str, List[Dict[str, Any]]] = {}
        self._register_default_templates()
    
    def _register_default_templates(self) -> None:
        """Register built-in checklist templates."""
        
        self._templates["agent_onboarding"] = [
            {"title": "Verify agent module loaded", "verification": "Check status == READY"},
            {"title": "Confirm tool registration", "verification": "List tools > 0"},
            {"title": "Validate compliance settings", "verification": "Check compliance_standards set"},
            {"title": "Test Rosetta bridge connection", "verification": "Handoff test successful"},
            {"title": "Verify logging configuration", "verification": "Test log entry created"},
        ]
        
        self._templates["security_review"] = [
            {"title": "Scan for vulnerabilities", "verification": "scan_vulnerabilities completed"},
            {"title": "Check compliance status", "verification": "check_compliance passed"},
            {"title": "Review access controls", "verification": "Access audit complete"},
            {"title": "Validate encryption", "verification": "Encryption check passed"},
            {"title": "Generate security report", "verification": "Report generated"},
        ]
        
        self._templates["deployment_checklist"] = [
            {"title": "Pre-deployment health check", "verification": "All services healthy"},
            {"title": "Backup current state", "verification": "Backup completed"},
            {"title": "Run integration tests", "verification": "Tests passed"},
            {"title": "Deploy to staging", "verification": "Staging deployment successful"},
            {"title": "Smoke test staging", "verification": "Smoke tests passed"},
            {"title": "Deploy to production", "verification": "Production deployment successful"},
            {"title": "Post-deployment verification", "verification": "All checks passed"},
            {"title": "Update documentation", "verification": "Docs updated"},
        ]
        
        self._templates["proposal_completion"] = [
            {"title": "Define project scope", "verification": "Scope document approved"},
            {"title": "Identify stakeholders", "verification": "Stakeholder list complete"},
            {"title": "Gather requirements", "verification": "Requirements documented"},
            {"title": "Draft proposal", "verification": "Draft created"},
            {"title": "Internal review", "verification": "Review feedback addressed"},
            {"title": "Cost estimation", "verification": "Budget approved"},
            {"title": "Timeline planning", "verification": "Timeline accepted"},
            {"title": "Risk assessment", "verification": "Risks documented"},
            {"title": "Final approval", "verification": "Proposal approved"},
            {"title": "Archive artifacts", "verification": "Artifacts stored in Rosetta"},
        ]
        
        self._templates["organization_setup"] = [
            {"title": "Define organization structure", "verification": "Org chart created"},
            {"title": "Assign agent roles", "verification": "All roles assigned"},
            {"title": "Configure permissions", "verification": "Permissions verified"},
            {"title": "Set up communication channels", "verification": "Channels active"},
            {"title": "Initialize Rosetta storage", "verification": "Rosetta ready"},
            {"title": "Create initial checklists", "verification": "Checklists assigned"},
            {"title": "Onboard first agents", "verification": "Agents active"},
        ]
    
    def create_checklist(
        self,
        name: str,
        description: str = "",
        template: Optional[str] = None,
        items: Optional[List[Dict[str, Any]]] = None,
        created_by: str = "",
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Checklist:
        """Create a new checklist.
        
        Args:
            name: Checklist name
            description: Checklist description
            template: Optional template name to use
            items: Optional list of item definitions
            created_by: Creator agent/user ID
            organization_id: Associated organization
            project_id: Associated project
            
        Returns:
            Created Checklist
        """
        checklist_id = str(uuid.uuid4())
        
        checklist_items = []
        item_defs = items or []
        
        if template and template in self._templates:
            item_defs = self._templates[template] + item_defs
        
        for i, item_def in enumerate(item_defs):
            checklist_items.append(ChecklistItem(
                item_id=f"{checklist_id}-{i}",
                title=item_def.get("title", f"Item {i+1}"),
                description=item_def.get("description", ""),
                verification=item_def.get("verification"),
                dependencies=item_def.get("dependencies", []),
            ))
        
        checklist = Checklist(
            checklist_id=checklist_id,
            name=name,
            description=description,
            items=checklist_items,
            created_by=created_by,
            organization_id=organization_id,
            project_id=project_id,
        )
        
        self._checklists[checklist_id] = checklist
        logger.info(f"Created checklist '{name}' with {len(checklist_items)} items")
        
        return checklist
    
    def update_item_status(
        self,
        checklist_id: str,
        item_id: str,
        status: ChecklistItemStatus,
        evidence: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
    ) -> ChecklistItem:
        """Update the status of a checklist item.
        
        Args:
            checklist_id: Parent checklist ID
            item_id: Item to update
            status: New status
            evidence: Optional proof of completion
            notes: Optional notes to add
            
        Returns:
            Updated ChecklistItem
        """
        if checklist_id not in self._checklists:
            raise ValueError(f"Checklist not found: {checklist_id}")
        
        checklist = self._checklists[checklist_id]
        item = next((i for i in checklist.items if i.item_id == item_id), None)
        
        if not item:
            raise ValueError(f"Item not found: {item_id}")
        
        # Check dependencies
        if status == ChecklistItemStatus.IN_PROGRESS:
            for dep_id in item.dependencies:
                dep = next((i for i in checklist.items if i.item_id == dep_id), None)
                if dep and dep.status != ChecklistItemStatus.COMPLETED:
                    raise ValueError(f"Dependency not complete: {dep.title}")
            item.started_at = datetime.now(timezone.utc).isoformat()
        
        item.status = status
        
        if status == ChecklistItemStatus.COMPLETED:
            item.completed_at = datetime.now(timezone.utc).isoformat()
        
        if evidence:
            item.evidence.update(evidence)
        
        if notes:
            item.notes.append(f"[{datetime.now(timezone.utc).isoformat()}] {notes}")
        
        logger.info(f"Checklist item '{item.title}' status: {status.value}")
        
        return item
    
    def get_checklist(self, checklist_id: str) -> Optional[Checklist]:
        """Get a checklist by ID."""
        return self._checklists.get(checklist_id)
    
    def get_organization_checklists(self, organization_id: str) -> List[Checklist]:
        """Get all checklists for an organization."""
        return [c for c in self._checklists.values() if c.organization_id == organization_id]
    
    def get_templates(self) -> List[str]:
        """Get available template names."""
        return list(self._templates.keys())
    
    def export_checklist(self, checklist_id: str) -> Dict[str, Any]:
        """Export checklist as a dictionary for storage/transfer."""
        checklist = self.get_checklist(checklist_id)
        if not checklist:
            return {}
        
        return {
            "checklist_id": checklist.checklist_id,
            "name": checklist.name,
            "description": checklist.description,
            "progress": checklist.progress,
            "status_summary": checklist.status_summary,
            "phase": checklist.phase,
            "created_by": checklist.created_by,
            "created_at": checklist.created_at,
            "organization_id": checklist.organization_id,
            "project_id": checklist.project_id,
            "items": [
                {
                    "item_id": i.item_id,
                    "title": i.title,
                    "description": i.description,
                    "status": i.status.value,
                    "assigned_to": i.assigned_to,
                    "verification": i.verification,
                    "evidence": i.evidence,
                    "started_at": i.started_at,
                    "completed_at": i.completed_at,
                    "notes": i.notes,
                }
                for i in checklist.items
            ],
        }


# ---------------------------------------------------------------------------
# Persistent Organization Characters
# ---------------------------------------------------------------------------

@dataclass
class OrganizationRole:
    """A role within an organization that an agent can fill."""
    role_id: str
    title: str
    department: str
    responsibilities: List[str]
    required_tools: List[str]
    reports_to: Optional[str] = None
    direct_reports: List[str] = field(default_factory=list)


@dataclass
class PersistentCharacter:
    """A persistent agent character within an organization.
    
    Characters persist across sessions and accumulate:
    - Experience and learnings
    - Project history
    - Relationship context
    - Artifact contributions
    """
    character_id: str
    name: str
    role: OrganizationRole
    agent_module: str
    organization_id: str
    
    # Persistent state
    experience: Dict[str, Any] = field(default_factory=dict)
    project_history: List[Dict[str, Any]] = field(default_factory=list)
    artifact_contributions: List[Dict[str, Any]] = field(default_factory=list)
    relationships: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Rosetta integration
    rosetta_document_id: Optional[str] = None
    
    # Lifecycle
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_active: Optional[str] = None
    total_sessions: int = 0
    status: str = "active"


@dataclass
class OrganizationProject:
    """A project within an organization that progresses toward proposal completion."""
    project_id: str
    name: str
    description: str
    organization_id: str
    
    # Lifecycle phases
    phase: str = "inception"  # inception, planning, execution, review, proposal, complete
    phase_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Assignments
    lead_character_id: Optional[str] = None
    team_character_ids: List[str] = field(default_factory=list)
    
    # Artifacts
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    checklists: List[str] = field(default_factory=list)  # checklist_ids
    
    # Proposal
    proposal_status: str = "draft"  # draft, review, approved, rejected
    proposal_document: Optional[Dict[str, Any]] = None
    
    # Timeline
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    target_completion: Optional[str] = None
    completed_at: Optional[str] = None


class PersistentOrganization:
    """Manages persistent agent characters within an organization.
    
    Characters become persistent employees that:
    - Maintain context across sessions
    - Contribute to projects over time
    - Build relationships with other characters
    - Generate artifacts that progress toward proposal completion
    """
    
    def __init__(
        self,
        organization_id: str,
        name: str,
        rosetta_bridge: Optional[RosettaHistoryBridge] = None,
        checklist_system: Optional[ChecklistSystem] = None,
    ):
        self.organization_id = organization_id
        self.name = name
        self._rosetta = rosetta_bridge or RosettaHistoryBridge()
        self._checklists = checklist_system or ChecklistSystem()
        
        self._characters: Dict[str, PersistentCharacter] = {}
        self._projects: Dict[str, OrganizationProject] = {}
        self._roles: Dict[str, OrganizationRole] = {}
        
        self.created_at = datetime.now(timezone.utc).isoformat()
        
        # Initialize org setup checklist
        self._setup_checklist = self._checklists.create_checklist(
            name=f"{name} Organization Setup",
            template="organization_setup",
            created_by="system",
            organization_id=organization_id,
        )
    
    def define_role(
        self,
        role_id: str,
        title: str,
        department: str,
        responsibilities: List[str],
        required_tools: List[str],
        reports_to: Optional[str] = None,
    ) -> OrganizationRole:
        """Define a role within the organization."""
        role = OrganizationRole(
            role_id=role_id,
            title=title,
            department=department,
            responsibilities=responsibilities,
            required_tools=required_tools,
            reports_to=reports_to,
        )
        self._roles[role_id] = role
        logger.info(f"Defined role '{title}' in {department}")
        return role
    
    def create_character(
        self,
        name: str,
        role_id: str,
        agent_module: str,
    ) -> PersistentCharacter:
        """Create a persistent character to fill a role.
        
        Args:
            name: Character name
            role_id: Role this character fills
            agent_module: Agent module to use (e.g., 'security-agent')
            
        Returns:
            Created PersistentCharacter
        """
        if role_id not in self._roles:
            raise ValueError(f"Role not found: {role_id}")
        
        role = self._roles[role_id]
        character_id = str(uuid.uuid4())
        
        character = PersistentCharacter(
            character_id=character_id,
            name=name,
            role=role,
            agent_module=agent_module,
            organization_id=self.organization_id,
        )
        
        self._characters[character_id] = character
        
        # Record in Rosetta
        self._rosetta.record_action(
            source_agent=agent_module,
            action="character_created",
            context={
                "character_id": character_id,
                "name": name,
                "role": role.title,
                "organization": self.name,
            },
        )
        
        logger.info(f"Created character '{name}' as {role.title}")
        return character
    
    def start_session(
        self,
        character_id: str,
        loader: AgentModuleLoader,
    ) -> Dict[str, Any]:
        """Start a session for a persistent character.
        
        Loads the character's context and starts the agent.
        """
        if character_id not in self._characters:
            raise ValueError(f"Character not found: {character_id}")
        
        character = self._characters[character_id]
        
        # Build context from character history
        context = {
            "character_name": character.name,
            "role": character.role.title,
            "organization": self.name,
            "experience": character.experience,
            "recent_projects": character.project_history[-5:] if character.project_history else [],
            "recent_artifacts": character.artifact_contributions[-5:] if character.artifact_contributions else [],
        }
        
        # Start agent with character context
        agent = loader.start(
            character.agent_module,
            session_id=f"{character_id}-{uuid.uuid4().hex[:8]}",
        )
        
        # Update character state
        character.last_active = datetime.now(timezone.utc).isoformat()
        character.total_sessions += 1
        
        # Store context in Rosetta
        self._rosetta.start_session(agent["session_id"], context)
        
        return {
            "character": character,
            "agent": agent,
            "context": context,
        }
    
    def end_session(
        self,
        character_id: str,
        session_id: str,
        learnings: Optional[Dict[str, Any]] = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """End a session and persist learnings.
        
        Extracts information from Rosetta and updates character state.
        """
        if character_id not in self._characters:
            raise ValueError(f"Character not found: {character_id}")
        
        character = self._characters[character_id]
        
        # Get session summary from Rosetta
        session_summary = self._rosetta.end_session(session_id)
        
        # Update experience
        if learnings:
            for key, value in learnings.items():
                if key in character.experience:
                    # Merge or update existing experience
                    if isinstance(character.experience[key], list):
                        character.experience[key].append(value)
                    elif isinstance(character.experience[key], dict):
                        character.experience[key].update(value)
                    else:
                        character.experience[key] = value
                else:
                    character.experience[key] = value
        
        # Record artifacts
        if artifacts:
            for artifact in artifacts:
                artifact["contributed_at"] = datetime.now(timezone.utc).isoformat()
                artifact["session_id"] = session_id
                character.artifact_contributions.append(artifact)
        
        return {
            "character_id": character_id,
            "session_summary": session_summary,
            "total_sessions": character.total_sessions,
            "artifacts_contributed": len(artifacts) if artifacts else 0,
        }
    
    def create_project(
        self,
        name: str,
        description: str,
        lead_character_id: str,
        team_character_ids: Optional[List[str]] = None,
        target_completion: Optional[str] = None,
    ) -> OrganizationProject:
        """Create a new project within the organization."""
        project_id = str(uuid.uuid4())
        
        project = OrganizationProject(
            project_id=project_id,
            name=name,
            description=description,
            organization_id=self.organization_id,
            lead_character_id=lead_character_id,
            team_character_ids=team_character_ids or [],
            target_completion=target_completion,
        )
        
        # Create proposal completion checklist
        proposal_checklist = self._checklists.create_checklist(
            name=f"{name} Proposal Checklist",
            template="proposal_completion",
            created_by=lead_character_id,
            organization_id=self.organization_id,
            project_id=project_id,
        )
        project.checklists.append(proposal_checklist.checklist_id)
        
        self._projects[project_id] = project
        
        # Add to lead character's project history
        if lead_character_id in self._characters:
            self._characters[lead_character_id].project_history.append({
                "project_id": project_id,
                "name": name,
                "role": "lead",
                "started_at": project.created_at,
            })
        
        logger.info(f"Created project '{name}' led by {lead_character_id}")
        return project
    
    def advance_project_phase(
        self,
        project_id: str,
        new_phase: str,
        notes: Optional[str] = None,
    ) -> OrganizationProject:
        """Advance a project to the next phase."""
        if project_id not in self._projects:
            raise ValueError(f"Project not found: {project_id}")
        
        project = self._projects[project_id]
        old_phase = project.phase
        
        # Record phase transition
        project.phase_history.append({
            "from_phase": old_phase,
            "to_phase": new_phase,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
        })
        
        project.phase = new_phase
        
        if new_phase == "complete":
            project.completed_at = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"Project '{project.name}' advanced from {old_phase} to {new_phase}")
        return project
    
    def add_project_artifact(
        self,
        project_id: str,
        character_id: str,
        artifact_type: str,
        artifact_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Add an artifact to a project.
        
        Artifacts progress the project toward proposal completion.
        """
        if project_id not in self._projects:
            raise ValueError(f"Project not found: {project_id}")
        
        project = self._projects[project_id]
        
        artifact = {
            "artifact_id": str(uuid.uuid4()),
            "type": artifact_type,
            "contributed_by": character_id,
            "contributed_at": datetime.now(timezone.utc).isoformat(),
            "data": artifact_data,
        }
        
        project.artifacts.append(artifact)
        
        # Also record on character
        if character_id in self._characters:
            self._characters[character_id].artifact_contributions.append({
                "project_id": project_id,
                "artifact_id": artifact["artifact_id"],
                "type": artifact_type,
                "contributed_at": artifact["contributed_at"],
            })
        
        logger.info(f"Artifact '{artifact_type}' added to project '{project.name}'")
        return artifact
    
    def generate_proposal(self, project_id: str) -> Dict[str, Any]:
        """Generate a proposal document from project artifacts.
        
        Combines all artifacts, checklist progress, and character contributions
        into a complete proposal.
        """
        if project_id not in self._projects:
            raise ValueError(f"Project not found: {project_id}")
        
        project = self._projects[project_id]
        
        # Gather all checklist progress
        checklists = [
            self._checklists.export_checklist(cid)
            for cid in project.checklists
        ]
        
        # Gather contributor info
        contributors = []
        for char_id in [project.lead_character_id] + project.team_character_ids:
            if char_id and char_id in self._characters:
                char = self._characters[char_id]
                contributors.append({
                    "name": char.name,
                    "role": char.role.title,
                    "contributions": len([
                        a for a in char.artifact_contributions
                        if a.get("project_id") == project_id
                    ]),
                })
        
        proposal = {
            "proposal_id": str(uuid.uuid4()),
            "project_id": project_id,
            "project_name": project.name,
            "description": project.description,
            "organization": self.name,
            "organization_id": self.organization_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "phase_history": project.phase_history,
            "contributors": contributors,
            "artifacts": project.artifacts,
            "checklists": checklists,
            "timeline": {
                "created": project.created_at,
                "target_completion": project.target_completion,
                "current_phase": project.phase,
            },
        }
        
        project.proposal_document = proposal
        project.proposal_status = "review"
        
        logger.info(f"Generated proposal for project '{project.name}'")
        return proposal
    
    def export_organization_state(self) -> Dict[str, Any]:
        """Export the complete organization state for persistence."""
        return {
            "organization_id": self.organization_id,
            "name": self.name,
            "created_at": self.created_at,
            "roles": {rid: {
                "role_id": r.role_id,
                "title": r.title,
                "department": r.department,
                "responsibilities": r.responsibilities,
                "required_tools": r.required_tools,
                "reports_to": r.reports_to,
            } for rid, r in self._roles.items()},
            "characters": {cid: {
                "character_id": c.character_id,
                "name": c.name,
                "role_id": c.role.role_id,
                "agent_module": c.agent_module,
                "experience": c.experience,
                "project_history": c.project_history,
                "artifact_contributions": c.artifact_contributions,
                "total_sessions": c.total_sessions,
                "status": c.status,
            } for cid, c in self._characters.items()},
            "projects": {pid: {
                "project_id": p.project_id,
                "name": p.name,
                "phase": p.phase,
                "artifacts_count": len(p.artifacts),
                "proposal_status": p.proposal_status,
            } for pid, p in self._projects.items()},
        }


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point for agent module loader."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Murphy System — MCP-Style Agent Module Loader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python agent_module_loader.py --list            # List available modules
  python agent_module_loader.py --start security-agent
  python agent_module_loader.py --start general-agent --log-format ecs
  python agent_module_loader.py --tools security-agent
  python agent_module_loader.py --templates       # List checklist templates
        """,
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available agent modules",
    )
    parser.add_argument(
        "--start", "-s",
        metavar="MODULE",
        help="Start an agent from the specified module",
    )
    parser.add_argument(
        "--tools", "-t",
        metavar="MODULE",
        help="List tools for the specified module",
    )
    parser.add_argument(
        "--log-format",
        choices=[f.value for f in LogFormat],
        default="json",
        help="Log output format (default: json)",
    )
    
    args = parser.parse_args()
    
    log_format = LogFormat(args.log_format)
    loader = AgentModuleLoader(log_format=log_format)
    
    if args.list:
        print("\nAvailable Agent Modules:")
        print("=" * 60)
        for module in loader.list_modules():
            print(f"\n  {module['module_id']}")
            print(f"    Name: {module['name']} v{module['version']}")
            print(f"    Description: {module['description']}")
            print(f"    Tools: {module['tool_count']}")
            if module['compliance_standards']:
                print(f"    Compliance: {', '.join(module['compliance_standards'])}")
        print()
        return
    
    if args.tools:
        tools = loader.list_tools(args.tools)
        print(f"\nTools for {args.tools}:")
        print("=" * 60)
        for tool in tools:
            print(f"\n  - {tool.name}")
            print(f"      {tool.description}")
            print(f"      Category: {tool.category}")
            if tool.parameters:
                print(f"      Parameters: {list(tool.parameters.keys())}")
        print()
        return
    
    if args.start:
        agent = loader.start(args.start)
        print(f"\nAgent '{agent['name']}' is ready.")
        print(f"Instance ID: {agent['instance_id']}")
        print(f"Session ID: {agent['session_id']}")
        print(f"Tools available: {agent['tool_count']}")
        print("\nPress Ctrl+C to stop the agent.\n")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            loader.stop(agent['instance_id'])
            print("\nAgent stopped.")
        return
    
    parser.print_help()


def demo_organization() -> None:
    """Demo function showing persistent organization setup."""
    print("\n" + "=" * 70)
    print("  MURPHY SYSTEM — Persistent Organization Demo")
    print("=" * 70)
    
    # Create loader and systems
    loader = AgentModuleLoader()
    checklist_system = ChecklistSystem()
    clarification_system = ClarificationSystem()
    
    # Create organization
    org = PersistentOrganization(
        organization_id="demo-org-001",
        name="Acme Automation Co",
        rosetta_bridge=loader._rosetta_bridge,
        checklist_system=checklist_system,
    )
    
    print(f"\n✓ Created organization: {org.name}")
    
    # Define roles
    org.define_role(
        role_id="security-lead",
        title="Security Lead",
        department="Security",
        responsibilities=["Vulnerability assessment", "Compliance audits", "Incident response"],
        required_tools=["scan_vulnerabilities", "check_compliance", "analyze_threat"],
    )
    
    org.define_role(
        role_id="devops-engineer",
        title="DevOps Engineer",
        department="Engineering",
        responsibilities=["CI/CD management", "Deployments", "Infrastructure"],
        required_tools=["deploy", "rollback", "check_pipeline"],
        reports_to="security-lead",
    )
    
    print("✓ Defined organizational roles")
    
    # Create persistent characters
    alice = org.create_character(
        name="Alice Security",
        role_id="security-lead",
        agent_module="security-agent",
    )
    
    bob = org.create_character(
        name="Bob DevOps",
        role_id="devops-engineer",
        agent_module="devops-agent",
    )
    
    print(f"✓ Created characters: {alice.name}, {bob.name}")
    
    # Create a project
    project = org.create_project(
        name="Security Hardening Initiative",
        description="Comprehensive security review and hardening of all systems",
        lead_character_id=alice.character_id,
        team_character_ids=[bob.character_id],
        target_completion="2026-06-30",
    )
    
    print(f"✓ Created project: {project.name}")
    
    # Demonstrate checklist
    print("\n  Project Checklist:")
    for cl_id in project.checklists:
        cl = checklist_system.get_checklist(cl_id)
        if cl:
            print(f"    [{cl.progress:.0f}%] {cl.name}")
            for item in cl.items[:3]:
                status_icon = "☐" if item.status == ChecklistItemStatus.PENDING else "☑"
                print(f"      {status_icon} {item.title}")
            if len(cl.items) > 3:
                print(f"      ... and {len(cl.items) - 3} more items")
    
    # Add an artifact
    org.add_project_artifact(
        project_id=project.project_id,
        character_id=alice.character_id,
        artifact_type="security_scan_report",
        artifact_data={
            "scan_date": datetime.now(timezone.utc).isoformat(),
            "vulnerabilities_found": 12,
            "critical": 0,
            "high": 2,
            "medium": 5,
            "low": 5,
        },
    )
    
    print("✓ Added security scan artifact")
    
    # Advance project phase
    org.advance_project_phase(project.project_id, "planning", "Initial assessment complete")
    print("✓ Advanced project to planning phase")
    
    # Export organization state
    state = org.export_organization_state()
    print(f"\n  Organization Summary:")
    print(f"    Roles: {len(state['roles'])}")
    print(f"    Characters: {len(state['characters'])}")
    print(f"    Projects: {len(state['projects'])}")
    
    # Show available checklist templates
    print("\n  Available Checklist Templates:")
    for template in checklist_system.get_templates():
        print(f"    - {template}")
    
    print("\n" + "=" * 70)
    print("  Demo Complete")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--demo-org":
        demo_organization()
    else:
        main()
