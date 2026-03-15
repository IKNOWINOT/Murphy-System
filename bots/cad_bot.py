"""CADBot - Fully unified visual production AI for CAD creation, reverse engineering, 3D printing, open-source sourcing, file modification, and deployment packaging."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict
from datetime import datetime, timezone
from pathlib import Path
from .gpt_oss_runner import GPTOSSRunner

from .analysis_bot import AnalysisBot
from .engineering_bot import EngineeringBot
from .simulation_bot import SimulationBot
try:
    from .ghost_controller_bot import GhostControllerBot
except Exception:  # pynput / pygetwindow may be absent on headless systems
    GhostControllerBot = None  # type: ignore[assignment,misc]

OUTPUT_DIR = Path("generated_cad")
PRINT_LOG = OUTPUT_DIR / "print_log.json"
OUTPUT_DIR.mkdir(exist_ok=True)

SUPPORTED_FORMATS = ["scad", "stl", "step", "svg", "dxf", "gcode"]

class CADBot:
    def __init__(self, model_path: str = "./models/gpt-oss-20b") -> None:
        self.runner = GPTOSSRunner(model_path)
        self.analysis = AnalysisBot(model_path)
        self.engineer = EngineeringBot(model_path)
        self.simulator = SimulationBot(model_path)
        self.ghost = GhostControllerBot(model_path) if GhostControllerBot is not None else None
        self.memory_file = OUTPUT_DIR / "cadbot_memory.json"
        self.history: list[dict] = []

    def route_request(self, request: str) -> dict:
        analysis = self.analysis.analyze_scope(request)
        if "error" in analysis:
            return {"status": "fail", "reason": analysis.get("error")}
        return analysis

    def generate_model_prompt(self, task_scope: dict, filetype: str = "scad") -> str:
        return f"""
You are CADBot.
Design a component with real-world ratios, engineering constraints, and open-source awareness.
Output: {filetype.upper()}

Domain: {task_scope.get('domain')}
Inputs: {json.dumps(task_scope, indent=2)}
Output a valid {filetype} format file content only.
"""

    def extract_ratios(self, cad_code: str) -> list[str]:
        matches = re.findall(r'([0-9]+\.?[0-9]*)\s*[:/]\s*([0-9]+\.?[0-9]*)', cad_code)
        return [f"{a}:{b}" for a, b in matches]

    def generate_cad_file(self, request: str, filetype: str = "scad") -> dict:
        scope = self.route_request(request)
        if scope.get("status") == "fail":
            return scope

        if filetype not in SUPPORTED_FORMATS:
            return {"status": "fail", "reason": f"Unsupported format: {filetype}"}

        prompt = self.generate_model_prompt(scope, filetype)
        cad_code = self.runner.chat(prompt)
        filename = f"cad_model_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.{filetype}"
        path = OUTPUT_DIR / filename

        with open(path, "w", encoding="utf-8") as f:
            f.write(cad_code)

        task_record = {
            "request": request,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cad_file": str(path),
            "format": filetype,
            "task_scope": scope,
            "ratios": self.extract_ratios(cad_code),
            "parts_list": self.generate_parts_list(scope),
            "power_profile": self.generate_power_profile(scope),
            "github_modules": self.suggest_github_modules(scope),
            "wiring_schematic": self.draw_wiring_schematic(scope)
        }
        self.history.append(task_record)
        self.save_robot_package(task_record)
        self.save_memory()
        return {"status": "success", "file": str(path), "ratios": task_record["ratios"]}

    def generate_parts_list(self, scope: dict) -> list[str]:
        prompt = f"""
You are CADBot.
Extract or generate a parts list from the following scope:
{json.dumps(scope, indent=2)}
Return a JSON array of physical components needed.
"""
        try:
            return json.loads(self.runner.chat(prompt))
        except Exception:
            return []

    def generate_power_profile(self, scope: dict) -> dict:
        prompt = f"""
You are CADBot.
Estimate power requirements based on the following project scope:
{json.dumps(scope, indent=2)}
Return voltage, amperage, runtime_estimate, and battery_type.
"""
        try:
            return json.loads(self.runner.chat(prompt))
        except Exception:
            return {}

    def suggest_github_modules(self, scope: dict) -> list[str]:
        prompt = f"""
You are CADBot. Suggest open-source GitHub repos related to:
{json.dumps(scope, indent=2)}
Return an array of GitHub URLs or keywords.
"""
        try:
            return json.loads(self.runner.chat(prompt))
        except Exception:
            return []

    def draw_wiring_schematic(self, scope: dict) -> str:
        prompt = f"""
You are CADBot. Create a simplified SVG wiring diagram for this hardware:
{json.dumps(scope, indent=2)}
Return SVG markup only.
"""
        try:
            return self.runner.chat(prompt)
        except Exception:
            return ""

    def reverse_engineer_gcode(self, gcode: str) -> dict:
        lines = gcode.strip().split("\n")
        layer_count = sum(1 for line in lines if line.startswith(";LAYER"))
        extrusion_volume = sum(float(part[1:]) for line in lines for part in line.split() if part.startswith("E"))
        return {
            "layers": layer_count,
            "extrusion_total": round(extrusion_volume, 3),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def print_gcode(self, gcode: str, printer_name: str = "SimPrinter") -> dict:
        summary = self.reverse_engineer_gcode(gcode)
        log = {
            "printer": printer_name,
            "start_time": summary["timestamp"],
            "layers": summary["layers"],
            "extrusion_volume": summary["extrusion_total"],
            "status": "completed"
        }
        with open(PRINT_LOG, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2)
        return log

    def modify_existing_file(self, filepath: str, instruction: str) -> dict:
        if not Path(filepath).exists():
            return {"status": "fail", "reason": "File does not exist."}
        content = Path(filepath).read_text()
        prompt = f"""
You are CADBot. The user provided this CAD/G-code content and asked:
Instruction: {instruction}
File content:
{content[:1500]}
---
Return the modified version only.
"""
        modified = self.runner.chat(prompt)
        Path(filepath).write_text(modified)
        return {"status": "modified", "file": filepath, "instruction": instruction}

    def save_robot_package(self, data: dict) -> None:
        pkg_file = OUTPUT_DIR / f"robot_package_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        with open(pkg_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def save_memory(self) -> None:
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=2)

    def respond_to_roll_call(self, task_description: str) -> dict:
        prompt = f"""
You are CADBot. The task is: {task_description}
Can you assist in generating or modifying CAD, STL, GCODE, schematics, BOMs, and open-source logic?
Respond as: {{"can_help": true, "confidence": float, "suggested_subtask": str}}
"""
        try:
            response = self.runner.chat(prompt, stop_token="}")
            return json.loads(response + "}")
        except Exception as e:
            return {"can_help": False, "error": str(e)}