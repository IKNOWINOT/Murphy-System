"""VisualizationBot - Finalized visual analytics, chart rendering, spatial diagramming, and validation agent with CAD and SimulationBot collaboration."""
from __future__ import annotations

import json
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import matplotlib.pyplot as plt

# Optional imports - use if available
try:
    from .gpt_oss_runner import GPTOSSRunner
    from .simulation_bot import SimulationBot
    from .cad_bot import CADBot
    HAS_MODERN_ARCANA = True
except ImportError:
    # Provide stub classes if module not available
    class GPTOSSRunner:
        def __init__(self, *args, **kwargs):
            pass
    class SimulationBot:
        def __init__(self, *args, **kwargs):
            pass
    class CADBot:
        def __init__(self, *args, **kwargs):
            pass
    HAS_MODERN_ARCANA = False

VISUAL_DIR = Path("visuals")
VISUAL_DIR.mkdir(exist_ok=True)
INDEX_FILE = VISUAL_DIR / "visual_index.json"
if not INDEX_FILE.exists():
    INDEX_FILE.write_text("[]")

class VisualizationBot:
    def __init__(self, model_path: str = "./models/gpt-oss-20b") -> None:
        self.runner = GPTOSSRunner(model_path)
        self.simulator = SimulationBot(model_path)
        self.cad = CADBot(model_path)

    # --- Charting + 3D Chart Rendering ---

    @staticmethod
    def generate_chart(request: Dict[str, Any]) -> str:
        data = request.get("data", {})
        visual_id = request["visual_id"]
        output_file = VISUAL_DIR / f"{visual_id}.png"
        plt.figure(figsize=(8, 4))
        x = data.get("timestamps") or list(range(len(data.get("scores", []))))
        y = data.get("scores", [])
        if request.get("format") == "bar":
            plt.bar(x, y)
        else:
            plt.plot(x, y, marker="o")
        plt.xlabel(request.get("x_axis", ""))
        plt.ylabel(request.get("y_axis", ""))
        plt.title(request.get("title", "Chart"))
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(output_file)
        plt.close()
        VisualizationBot._append_index(request, str(output_file))
        return str(output_file)

    @staticmethod
    def generate_model(request: Dict[str, Any]) -> str:
        visual_id = request["visual_id"]
        output_file = VISUAL_DIR / f"{visual_id}.png"
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        data = request.get("data", {})
        X, Y, Z = data.get("X", []), data.get("Y", []), data.get("Z", [])
        ax.plot3D(X, Y, Z)
        plt.title(request.get("title", "Model"))
        plt.tight_layout()
        plt.savefig(output_file)
        plt.close(fig)
        VisualizationBot._append_index(request, str(output_file))
        return str(output_file)

    # --- CAD and Simulation Integration ---

    def generate_svg_from_cad_scope(self, scope: dict) -> str:
        prompt = f"""
You are VisualizationBot.
Generate a technical SVG diagram for the following CAD task:
{json.dumps(scope, indent=2)}
Render exploded view with socket orientation and dimensioned labeling.
Return only SVG.
"""
        return self.runner.chat(prompt)

    def validate_assembly_fit(self, part_chain: list[dict]) -> dict:
        return self.simulator.validate_no_overlap(part_chain)

    def ask_for_missing_info(self, part_chain: list[dict], pass_level: int = 30) -> list[str]:
        prompt = f"""
You are VisualizationBot. Review the following incomplete part definitions:
{json.dumps(part_chain, indent=2)}
Ask 3-5 follow-up questions to move from {pass_level}% to {min(pass_level+30,100)}% completion.
"""
        try:
            return json.loads(self.runner.chat(prompt))
        except Exception:
            return ["What is the slot clearance required for the actuator?", "Is the port angled or straight?", "What connector is used?"]

    def assemble_and_visualize_from_task(self, request: str, filetype: str = "scad") -> dict:
        # Combines CAD + Simulation + SVG validation for 1 unified render pass
        result = self.cad.generate_cad_file(request, filetype=filetype)
        if result.get("status") != "success":
            return result
        visual_svg = self.generate_svg_from_cad_scope(result.get("task_scope", {}))
        clearance = self.validate_assembly_fit(result.get("task_scope", {}).get("parts_list", []))
        return {
            "cad_file": result.get("file"),
            "svg_output": visual_svg[:150] + "...",
            "clearance_pass": clearance,
            "parts_list": result.get("parts_list"),
            "power_profile": result.get("power_profile"),
            "github_modules": result.get("github_modules")
        }

    def respond_to_roll_call(self, task_description: str) -> dict:
        prompt = f"""
You are VisualizationBot.
Task: {task_description}
Can you assist in visualizing, assembling, rendering, validating, and optimizing mechanical or electrical designs?
Use SimulationBot and CommissioningBot for validation and performance questions.
Return: {{"can_help": true, "confidence": 0.97, "suggested_subtask": "Assembly diagram, clearance validation, corrective questions."}}
"""
        try:
            return json.loads(self.runner.chat(prompt, stop_token="}"))
        except Exception as e:
            return {"can_help": False, "error": str(e)}