# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
RynnBrain Adapter — Murphy ↔ RynnBrain data-format translation layer.

Pinned to commit: 4e694f27d5a23b3c3b487be1a97e708c15cb9fd4

This adapter translates:
  - Murphy internal prompts  →  RynnBrain conversation JSON format
  - RynnBrain bounding-box output  →  Murphy internal bbox dicts
  - RynnBrain planning streaming output  →  Murphy plan steps
  - RynnBrain navigation trajectory output  →  Murphy nav trajectory

Usage::

    adapter = RynnBrainAdapter()

    # Convert Murphy prompt to RynnBrain messages
    messages = adapter.to_rynnbrain_messages(prompt="describe the scene", images=["/path/img.jpg"])

    # Parse bounding boxes from RynnBrain text output
    bboxes = adapter.parse_bounding_boxes(model_output="<cup> (10,20), (50,80) </cup>")

    # Stream planning output
    for step in adapter.parse_planning_stream(stream_text):
        print(step)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("integration_engine.adapters.rynnbrain")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RYNNBRAIN_COMMIT = "4e694f27d5a23b3c3b487be1a97e708c15cb9fd4"
RYNNBRAIN_HF_BASE = "Alibaba-DAMO-Academy"

RYNNBRAIN_VARIANTS: Dict[str, str] = {
    "2b": f"{RYNNBRAIN_HF_BASE}/RynnBrain-2B",
    "8b": f"{RYNNBRAIN_HF_BASE}/RynnBrain-8B",
    "30b": f"{RYNNBRAIN_HF_BASE}/RynnBrain-30B-A3B",
    "30b-moe": f"{RYNNBRAIN_HF_BASE}/RynnBrain-30B-A3B",
    "plan": f"{RYNNBRAIN_HF_BASE}/RynnBrain-Plan",
    "nav": f"{RYNNBRAIN_HF_BASE}/RynnBrain-Nav",
    "cop": f"{RYNNBRAIN_HF_BASE}/RynnBrain-CoP",
}

# ---------------------------------------------------------------------------
# Murphy internal types (lightweight stand-ins for the full Murphy types)
# ---------------------------------------------------------------------------


class TaskType(str, Enum):
    """Task Type."""
    GENERAL = "general"
    PLANNING = "planning"
    NAVIGATION = "navigation"


@dataclass
class MurphyPrompt:
    """Murphy's internal prompt representation."""
    text: str
    images: List[str] = field(default_factory=list)   # file paths or URLs
    system: Optional[str] = None
    task_type: TaskType = TaskType.GENERAL


@dataclass
class BoundingBox:
    """Murphy's internal bounding-box representation."""
    label: str
    x1: int
    y1: int
    x2: int
    y2: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
        }


@dataclass
class PlanStep:
    """One step in a RynnBrain planning output."""
    step_index: int
    action: str
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "action": self.action,
            "reasoning": self.reasoning,
        }


@dataclass
class NavWaypoint:
    """One waypoint in a navigation trajectory."""
    step: int
    position: List[float]
    heading: float
    action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "position": self.position,
            "heading": self.heading,
            "action": self.action,
        }


# ---------------------------------------------------------------------------
# RynnBrainAdapter
# ---------------------------------------------------------------------------

class RynnBrainAdapter:
    """
    Translates between Murphy's internal data structures and RynnBrain's
    conversation / output formats.

    All model references are pinned to ``RYNNBRAIN_COMMIT`` to prevent
    supply-chain drift.
    """

    # Pattern: <label> (x1,y1), (x2,y2) </label>
    _BBOX_RE = re.compile(
        r"<(\S+?)>\s*\((\d+)\s*,\s*(\d+)\)\s*,\s*\((\d+)\s*,\s*(\d+)\)\s*</\S+?>",
        re.DOTALL,
    )

    # Planning step pattern: optional JSON lines like {"step": N, "action": "...", ...}
    _PLAN_JSON_RE = re.compile(r"\{[^{}]*\"action\"\s*:[^{}]*\}", re.DOTALL)

    # Numbered step pattern: "1. Do something" or "Step 1: Do something"
    _PLAN_TEXT_RE = re.compile(
        r"(?:^|\n)\s*(?:Step\s+)?(\d+)[.:]\s*(.+?)(?=\n\s*(?:Step\s+)?\d+[.:]|\Z)",
        re.DOTALL,
    )

    def __init__(self, variant: str = "8b") -> None:
        """
        Args:
            variant: One of the keys in RYNNBRAIN_VARIANTS (default '8b').
        """
        variant_lower = variant.lower()
        if variant_lower not in RYNNBRAIN_VARIANTS:
            raise ValueError(
                f"Unknown RynnBrain variant '{variant}'. "
                f"Choose from: {', '.join(RYNNBRAIN_VARIANTS)}"
            )
        self.variant = variant_lower
        self.model_id = RYNNBRAIN_VARIANTS[variant_lower]
        self.pinned_commit = RYNNBRAIN_COMMIT

    # ------------------------------------------------------------------
    # Murphy → RynnBrain
    # ------------------------------------------------------------------

    def to_rynnbrain_messages(
        self,
        prompt: Union[str, MurphyPrompt],
        images: Optional[List[str]] = None,
        system: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Convert a Murphy prompt to RynnBrain's conversation message list.

        Args:
            prompt:  Either a plain string or a ``MurphyPrompt`` instance.
            images:  Optional list of image paths/URLs (overrides MurphyPrompt.images).
            system:  Optional system message text (overrides MurphyPrompt.system).

        Returns:
            List of ``{"role": ..., "content": [...]}`` dicts ready for the
            RynnBrain processor.
        """
        if isinstance(prompt, MurphyPrompt):
            text = prompt.text
            img_list = images if images is not None else prompt.images
            sys_text = system if system is not None else prompt.system
        else:
            text = prompt
            img_list = images or []
            sys_text = system

        messages: List[Dict[str, Any]] = []

        # Optional system turn
        if sys_text:
            messages.append({
                "role": "system",
                "content": [{"type": "text", "text": sys_text}],
            })

        # User turn: images first, then text
        content: List[Dict[str, Any]] = []
        for img in img_list:
            content.append({"type": "image", "image": img})
        content.append({"type": "text", "text": text})

        messages.append({"role": "user", "content": content})

        return messages

    def to_rynnbrain_payload(
        self,
        prompt: Union[str, MurphyPrompt],
        images: Optional[List[str]] = None,
        system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build the full payload dict that would be passed to the HuggingFace
        processor (before tokenisation).
        """
        return {
            "messages": self.to_rynnbrain_messages(prompt, images, system),
            "model_id": self.model_id,
            "revision": self.pinned_commit,
        }

    # ------------------------------------------------------------------
    # RynnBrain → Murphy: bounding boxes
    # ------------------------------------------------------------------

    def parse_bounding_boxes(self, model_output: str) -> List[BoundingBox]:
        """
        Parse bounding-box tags from RynnBrain model output.

        Expected format::

            <cup> (10,20), (50,80) </cup>
            <table> (0,100), (200,300) </table>

        Returns:
            List of :class:`BoundingBox` instances.
        """
        boxes: List[BoundingBox] = []
        for m in self._BBOX_RE.finditer(model_output):
            label = m.group(1)
            x1, y1, x2, y2 = int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
            boxes.append(BoundingBox(label=label, x1=x1, y1=y1, x2=x2, y2=y2))
        return boxes

    # ------------------------------------------------------------------
    # RynnBrain → Murphy: planning output
    # ------------------------------------------------------------------

    def parse_planning_stream(
        self, stream_text: str
    ) -> List[PlanStep]:
        """
        Parse planning output from RynnBrain into Murphy ``PlanStep`` objects.

        Handles two formats:
        1. JSON lines: ``{"action": "...", "reasoning": "..."}``
        2. Plain numbered text: ``1. Do X``, ``Step 2: Do Y``

        Args:
            stream_text: The full text output from the model (streaming complete).

        Returns:
            List of :class:`PlanStep` instances in order.
        """
        steps: List[PlanStep] = []

        # Try JSON format first
        for i, m in enumerate(self._PLAN_JSON_RE.finditer(stream_text)):
            try:
                obj = json.loads(m.group(0))
                steps.append(PlanStep(
                    step_index=obj.get("step_index", obj.get("step", i)),
                    action=obj.get("action", ""),
                    reasoning=obj.get("reasoning", obj.get("thought", "")),
                ))
            except json.JSONDecodeError:
                pass

        if steps:
            return steps

        # Fallback: numbered text steps
        for m in self._PLAN_TEXT_RE.finditer(stream_text):
            idx = int(m.group(1)) - 1
            action = m.group(2).strip()
            steps.append(PlanStep(step_index=idx, action=action))

        return steps

    # ------------------------------------------------------------------
    # RynnBrain → Murphy: navigation trajectory
    # ------------------------------------------------------------------

    def parse_navigation_trajectory(
        self, model_output: str
    ) -> List[NavWaypoint]:
        """
        Parse a navigation trajectory from RynnBrain output.

        Expects either a JSON array of waypoints or embedded JSON object with
        a ``trajectory`` key.

        Args:
            model_output: Raw text output from the model.

        Returns:
            List of :class:`NavWaypoint` objects.
        """
        waypoints: List[NavWaypoint] = []
        decoder = json.JSONDecoder()

        # Scan the string for the first valid JSON value (array or object)
        idx = 0
        while idx < len(model_output):
            # Find the next '{' or '[' to try JSON decoding from
            next_brace = model_output.find('{', idx)
            next_bracket = model_output.find('[', idx)

            if next_brace == -1 and next_bracket == -1:
                break

            # Pick the earlier one
            if next_brace == -1:
                start = next_bracket
            elif next_bracket == -1:
                start = next_brace
            else:
                start = min(next_brace, next_bracket)

            try:
                obj, end_pos = decoder.raw_decode(model_output, start)
                items: List[Dict] = []
                if isinstance(obj, list):
                    items = obj
                elif isinstance(obj, dict):
                    items = obj.get("trajectory", [])

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    pos_raw = item.get("position", [0.0, 0.0, 0.0])
                    if not isinstance(pos_raw, list):
                        pos_raw = [0.0, 0.0, 0.0]
                    waypoints.append(NavWaypoint(
                        step=int(item.get("step", len(waypoints))),
                        position=[float(x) for x in pos_raw],
                        heading=float(item.get("heading", 0.0)),
                        action=str(item.get("action", "")),
                    ))
                if waypoints:
                    return waypoints
                idx = start + end_pos
            except (json.JSONDecodeError, ValueError, TypeError):
                idx = start + 1

        return waypoints

    # ------------------------------------------------------------------
    # Model reference helpers
    # ------------------------------------------------------------------

    def get_model_load_kwargs(self) -> Dict[str, Any]:
        """
        Return the kwargs to pass to ``from_pretrained`` when loading the model.

        Intentionally does NOT set ``trust_remote_code=True`` — RynnBrain uses
        standard AutoModel classes and does not require it.
        """
        return {
            "revision": self.pinned_commit,
            "trust_remote_code": False,  # Not required by RynnBrain
        }

    @staticmethod
    def list_variants() -> Dict[str, str]:
        """Return mapping of variant key → HuggingFace model ID."""
        return dict(RYNNBRAIN_VARIANTS)
