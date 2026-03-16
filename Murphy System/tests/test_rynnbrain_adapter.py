# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tests for the RynnBrain adapter — RYNNBRAIN-001.

Covers:
  - Conversation format conversion (Murphy → RynnBrain)
  - Bounding box output parsing (RynnBrain → Murphy)
  - Planning streaming format handling
  - Navigation trajectory parsing
  - Model variant selection
"""
from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

from integration_engine.adapters.rynnbrain_adapter import (
    BoundingBox,
    MurphyPrompt,
    NavWaypoint,
    PlanStep,
    RynnBrainAdapter,
    RYNNBRAIN_COMMIT,
    RYNNBRAIN_VARIANTS,
    TaskType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _adapter(variant: str = "8b") -> RynnBrainAdapter:
    return RynnBrainAdapter(variant=variant)


# ---------------------------------------------------------------------------
# Conversation format conversion (Murphy → RynnBrain)
# ---------------------------------------------------------------------------

class TestConversationFormat:
    def test_plain_string_prompt_creates_user_message(self):
        adapter = _adapter()
        messages = adapter.to_rynnbrain_messages("describe the scene")
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_text_content_block_present(self):
        adapter = _adapter()
        messages = adapter.to_rynnbrain_messages("hello")
        content = messages[0]["content"]
        text_blocks = [b for b in content if b.get("type") == "text"]
        assert len(text_blocks) == 1
        assert text_blocks[0]["text"] == "hello"

    def test_image_content_blocks_prepended(self):
        adapter = _adapter()
        messages = adapter.to_rynnbrain_messages("caption this", images=["img1.jpg", "img2.png"])
        content = messages[0]["content"]
        img_blocks = [b for b in content if b.get("type") == "image"]
        assert len(img_blocks) == 2
        assert img_blocks[0]["image"] == "img1.jpg"
        # Images come before text
        types = [b["type"] for b in content]
        assert types.index("image") < types.index("text")

    def test_system_message_added(self):
        adapter = _adapter()
        messages = adapter.to_rynnbrain_messages("go forward", system="You are a robot.")
        assert messages[0]["role"] == "system"
        assert messages[0]["content"][0]["text"] == "You are a robot."
        assert messages[1]["role"] == "user"

    def test_murphy_prompt_object_conversion(self):
        adapter = _adapter()
        prompt = MurphyPrompt(
            text="what objects are here?",
            images=["scene.jpg"],
            system="Embodied AI",
            task_type=TaskType.GENERAL,
        )
        messages = adapter.to_rynnbrain_messages(prompt)
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        user_content = messages[1]["content"]
        assert any(b.get("image") == "scene.jpg" for b in user_content)
        assert any(b.get("text") == "what objects are here?" for b in user_content)

    def test_no_images_no_image_blocks(self):
        adapter = _adapter()
        messages = adapter.to_rynnbrain_messages("just text")
        content = messages[0]["content"]
        assert not any(b.get("type") == "image" for b in content)

    def test_to_rynnbrain_payload_includes_model_id(self):
        adapter = _adapter("8b")
        payload = adapter.to_rynnbrain_payload("test")
        assert "model_id" in payload
        assert "RynnBrain-8B" in payload["model_id"]
        assert payload["revision"] == RYNNBRAIN_COMMIT


# ---------------------------------------------------------------------------
# Bounding box parsing (RynnBrain → Murphy)
# ---------------------------------------------------------------------------

class TestBoundingBoxParsing:
    def test_single_box_parsed(self):
        adapter = _adapter()
        output = "<cup> (10,20), (50,80) </cup>"
        boxes = adapter.parse_bounding_boxes(output)
        assert len(boxes) == 1
        b = boxes[0]
        assert b.label == "cup"
        assert b.x1 == 10
        assert b.y1 == 20
        assert b.x2 == 50
        assert b.y2 == 80

    def test_multiple_boxes_parsed(self):
        adapter = _adapter()
        output = (
            "<cup> (10,20), (50,80) </cup> "
            "<table> (0,0), (200,300) </table>"
        )
        boxes = adapter.parse_bounding_boxes(output)
        assert len(boxes) == 2
        labels = {b.label for b in boxes}
        assert labels == {"cup", "table"}

    def test_no_boxes_returns_empty(self):
        adapter = _adapter()
        boxes = adapter.parse_bounding_boxes("The scene shows a kitchen.")
        assert boxes == []

    def test_box_to_dict(self):
        box = BoundingBox(label="mug", x1=5, y1=10, x2=55, y2=90)
        d = box.to_dict()
        assert d["label"] == "mug"
        assert d["x1"] == 5
        assert d["x2"] == 55

    def test_whitespace_variants_parsed(self):
        adapter = _adapter()
        output = "<door>(0, 10),(100,200)</door>"
        boxes = adapter.parse_bounding_boxes(output)
        assert len(boxes) == 1
        assert boxes[0].label == "door"


# ---------------------------------------------------------------------------
# Planning streaming format
# ---------------------------------------------------------------------------

class TestPlanningStreamFormat:
    def test_json_steps_parsed(self):
        adapter = _adapter("plan")
        stream_text = (
            '{"step_index": 0, "action": "move forward", "reasoning": "clear path"}\n'
            '{"step_index": 1, "action": "turn left", "reasoning": "obstacle ahead"}\n'
        )
        steps = adapter.parse_planning_stream(stream_text)
        assert len(steps) == 2
        assert steps[0].action == "move forward"
        assert steps[0].reasoning == "clear path"
        assert steps[1].action == "turn left"

    def test_numbered_text_steps_parsed(self):
        adapter = _adapter()
        stream_text = (
            "1. Move to the door\n"
            "2. Open the door\n"
            "3. Walk through\n"
        )
        steps = adapter.parse_planning_stream(stream_text)
        assert len(steps) == 3
        assert "Move to the door" in steps[0].action

    def test_empty_stream_returns_empty(self):
        adapter = _adapter()
        steps = adapter.parse_planning_stream("")
        assert steps == []

    def test_plan_step_to_dict(self):
        step = PlanStep(step_index=0, action="go left", reasoning="obstacle")
        d = step.to_dict()
        assert d["action"] == "go left"
        assert d["reasoning"] == "obstacle"
        assert d["step_index"] == 0


# ---------------------------------------------------------------------------
# Navigation trajectory parsing
# ---------------------------------------------------------------------------

class TestNavigationTrajectory:
    def test_json_trajectory_parsed(self):
        adapter = _adapter("nav")
        output = (
            '{"trajectory": ['
            '{"step": 0, "position": [0.0, 0.0, 0.0], "heading": 0.0, "action": "forward"},'
            '{"step": 1, "position": [1.0, 0.0, 0.0], "heading": 0.0, "action": "forward"}'
            ']}'
        )
        waypoints = adapter.parse_navigation_trajectory(output)
        assert len(waypoints) == 2
        assert waypoints[0].action == "forward"
        assert waypoints[1].position == [1.0, 0.0, 0.0]

    def test_array_trajectory_parsed(self):
        adapter = _adapter()
        output = (
            '[{"step": 0, "position": [0, 0, 0], "heading": 90.0, "action": "turn"}]'
        )
        waypoints = adapter.parse_navigation_trajectory(output)
        assert len(waypoints) == 1
        assert waypoints[0].heading == 90.0

    def test_no_trajectory_returns_empty(self):
        adapter = _adapter()
        waypoints = adapter.parse_navigation_trajectory("No waypoints here.")
        assert waypoints == []

    def test_waypoint_to_dict(self):
        wp = NavWaypoint(step=0, position=[1.0, 2.0, 0.5], heading=45.0, action="turn_right")
        d = wp.to_dict()
        assert d["action"] == "turn_right"
        assert d["heading"] == 45.0


# ---------------------------------------------------------------------------
# Model variant selection
# ---------------------------------------------------------------------------

class TestModelVariantSelection:
    def test_default_variant_is_8b(self):
        adapter = RynnBrainAdapter()
        assert adapter.variant == "8b"
        assert "RynnBrain-8B" in adapter.model_id

    def test_2b_variant(self):
        adapter = RynnBrainAdapter(variant="2b")
        assert "RynnBrain-2B" in adapter.model_id

    def test_30b_variant(self):
        adapter = RynnBrainAdapter(variant="30b")
        assert "30B" in adapter.model_id

    def test_plan_variant(self):
        adapter = RynnBrainAdapter(variant="plan")
        assert "Plan" in adapter.model_id

    def test_nav_variant(self):
        adapter = RynnBrainAdapter(variant="nav")
        assert "Nav" in adapter.model_id

    def test_cop_variant(self):
        adapter = RynnBrainAdapter(variant="cop")
        assert "CoP" in adapter.model_id

    def test_unknown_variant_raises(self):
        with pytest.raises(ValueError, match="Unknown RynnBrain variant"):
            RynnBrainAdapter(variant="nonexistent-model-xyz")

    def test_model_load_kwargs_no_trust_remote_code(self):
        adapter = RynnBrainAdapter()
        kwargs = adapter.get_model_load_kwargs()
        assert kwargs.get("trust_remote_code") is False

    def test_model_load_kwargs_pinned_revision(self):
        adapter = RynnBrainAdapter()
        kwargs = adapter.get_model_load_kwargs()
        assert kwargs["revision"] == RYNNBRAIN_COMMIT

    def test_list_variants_returns_all(self):
        variants = RynnBrainAdapter.list_variants()
        assert "2b" in variants
        assert "8b" in variants
        assert "30b" in variants
        assert "plan" in variants
        assert "nav" in variants
        assert "cop" in variants

    def test_commit_pinned_constant(self):
        assert len(RYNNBRAIN_COMMIT) == 40  # Full SHA-1 hex hash
        assert RYNNBRAIN_COMMIT == "4e694f27d5a23b3c3b487be1a97e708c15cb9fd4"
