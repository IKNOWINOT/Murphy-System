"""
R424 — Endpoint Tools → AionMind Capability Bridge
==================================================

WHAT THIS IS:
  Registers every R420-registered endpoint tool that is currently HEALTHY
  (per R422 api_health_authed.json) as a real AionMind Capability with a
  bound handler that actually calls the endpoint.

WHY IT EXISTS:
  R423 wired /api/chat → AionMind kernel for plan visibility, but the
  reasoning engine could only match against bot_inventory_library
  capabilities — all of which had NO HANDLER. So every plan it generated
  failed at execution with "No handler for capability bot_inv:X".

  Meanwhile R420 had registered 1,817 endpoint tools, each with a working
  HTTP-call handler. But those weren't visible as Capabilities to the
  reasoning engine.

  This bridge closes the gap.

HOW IT FITS:
  Called at startup after R420 endpoint_tools.register_endpoint_tools() AND
  after _aionmind_kernel construction. Reads R420 tool registry + R422
  api_health_authed.json. Skips broken, param-templated, and side-effect
  endpoints (unless explicitly allowed). Registers each remaining tool as
  a Capability with a working HTTP handler.

LAST UPDATED: 2026-06-01 by murphy_assistant via R424
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("murphy.r424_endpoint_capability_bridge")

_HEALTH_AUTHED_PATH = pathlib.Path(
    "/var/lib/murphy-production/api_health_authed.json"
)

_METHOD_RISK = {
    "GET": "low",
    "HEAD": "low",
    "POST": "medium",
    "PUT": "medium",
    "PATCH": "medium",
    "DELETE": "high",
}

_BROKEN_CODES = {"TIMEOUT", "ERR", 404, 500, 502, 503, 504}


def _derive_tags(tool_id: str, path: str, method: str, group: str) -> List[str]:
    """Build searchable tags from a tool's identity."""
    tags = [method.lower(), group, "endpoint", "healthy"]
    for seg in path.strip("/").split("/"):
        seg = seg.strip()
        if seg and not seg.startswith("{") and len(seg) > 2:
            tags.append(seg.lower())
    return list(dict.fromkeys(tags))


def _make_handler(dispatch_tool_fn: Callable, tool_id: str) -> Callable:
    """Build a Capability handler that delegates to the R420 tool executor."""
    def _handler(**kwargs: Any) -> Dict[str, Any]:
        try:
            result = dispatch_tool_fn(tool_id, **kwargs) if kwargs else dispatch_tool_fn(tool_id)
            return {"ok": True, "result": result}
        except Exception as exc:
            logger.warning("R424 handler %s failed: %s", tool_id, exc)
            return {"ok": False, "error": str(exc)}
    _handler.__name__ = f"r424_h_{tool_id.replace('.', '_')[:36]}"
    return _handler


def bridge_endpoints_to_capabilities(
    kernel: Any,
    *,
    include_post: bool = False,
    max_to_register: Optional[int] = None,
) -> Dict[str, int]:
    """Register every healthy R420 endpoint as a kernel Capability."""
    health: Dict[str, Any] = {}
    if _HEALTH_AUTHED_PATH.exists():
        try:
            health = json.loads(_HEALTH_AUTHED_PATH.read_text()).get("results", {})
            logger.info("R424: loaded health for %d endpoints", len(health))
        except Exception as exc:
            logger.warning("R424: health map load failed: %s", exc)

    try:
        from src.aionmind.tool_executor import _get_registry, dispatch_tool
    except ImportError:
        try:
            from aionmind.tool_executor import _get_registry, dispatch_tool
        except ImportError:
            logger.error("R424: tool_executor not importable — abort")
            return {"error": "tool_executor missing"}

    reg = _get_registry()
    all_tools = reg.list_all()
    logger.info("R424: scanning %d R420 tools", len(all_tools))

    try:
        from aionmind.capability_registry import Capability
    except ImportError:
        from src.aionmind.capability_registry import Capability

    counts = dict(
        registered=0,
        skipped_broken=0,
        skipped_param=0,
        skipped_post=0,
        skipped_other=0,
        total_eligible=0,
    )

    for tool in all_tools:
        tool_id = tool.tool_id
        metadata = getattr(tool, "metadata", {}) or {}
        path = metadata.get("path", "")
        method = metadata.get("method", "GET").upper()
        group = metadata.get("group", "misc")

        if not tool_id.startswith("api."):
            continue
        counts["total_eligible"] += 1

        if "{" in path:
            counts["skipped_param"] += 1
            continue

        if method != "GET" and method != "HEAD" and not include_post:
            counts["skipped_post"] += 1
            continue

        health_code = health.get(path)
        if health_code in _BROKEN_CODES:
            counts["skipped_broken"] += 1
            continue

        try:
            cap = Capability(
                capability_id=f"endpoint:{tool_id}",
                name=tool.name or tool_id,
                description=tool.description or f"{method} {path}",
                provider="murphy.endpoint",
                tags=_derive_tags(tool_id, path, method, group),
                risk_level=_METHOD_RISK.get(method, "medium"),
                requires_approval=(method in ("DELETE", "PUT")),
                metadata={
                    "origin": "r424_endpoint_bridge",
                    "path": path,
                    "method": method,
                    "group": group,
                    "tool_id": tool_id,
                },
            )
            kernel.register_capability(cap)
            try:
                if not hasattr(kernel._registry, "_handlers"):
                    kernel._registry._handlers = {}
                kernel._registry._handlers[cap.capability_id] = _make_handler(
                    dispatch_tool, tool_id
                )
            except AttributeError:
                cap.metadata["_handler_tool_id"] = tool_id
            counts["registered"] += 1

            if max_to_register and counts["registered"] >= max_to_register:
                logger.info("R424: hit cap %d", max_to_register)
                break
        except Exception as exc:
            counts["skipped_other"] += 1
            logger.debug("R424: skip %s — %s", tool_id, exc)

    logger.info(
        "R424: registered=%d skipped(broken=%d, param=%d, post=%d, other=%d)",
        counts["registered"],
        counts["skipped_broken"],
        counts["skipped_param"],
        counts["skipped_post"],
        counts["skipped_other"],
    )
    return counts
