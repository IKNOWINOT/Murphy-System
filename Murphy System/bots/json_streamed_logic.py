"""JSON Streamed Logic Subsystem (JSL)
This file defines the full pipeline for streamed JSON-based logic ingestion,
transformation, and plugin registration using RubixCubeBot, JSONBot, and
LibrarianBot.
Target: Codex-compatible, production-level clarity.
"""

import os
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .plugin_loader import load_plugin
from .librarian_bot import LibrarianBot, Document
from .json_bot import JSONBot
from .rubixcube_bot import log_usage

STREAMED_DIR = Path("plugins/streamed")
STREAMED_DIR.mkdir(parents=True, exist_ok=True)

STREAMED_LOG = STREAMED_DIR / "ingestion_log.jsonl"

REQUIRED_FIELDS = ["function_name", "description", "parameters", "code_body"]


class JSONStreamedLogicIngestor:
    def __init__(self, jsonbot: JSONBot, librarian: LibrarianBot) -> None:
        self.jsonbot = jsonbot
        self.librarian = librarian

    def ingest_json(self, payload: Dict[str, Any]) -> Optional[str]:
        for field in REQUIRED_FIELDS:
            if field not in payload:
                print(f"Missing field: {field}")
                return None

        function_name = payload["function_name"].strip()
        description = payload["description"].strip()
        parameters = payload["parameters"]
        code_body = payload["code_body"].strip()

        param_str = ", ".join(parameters)
        indented_body = code_body if code_body.startswith("    ") else "    " + code_body.replace("\n", "\n    ")
        function_code = (
            f"def {function_name}({param_str}):\n"
            f"    \"\"\"{description}\"\"\"\n"
            f"{indented_body}\n"
        )

        plugin_id = uuid.uuid4().hex[:8]
        plugin_path = STREAMED_DIR / f"{function_name}_{plugin_id}.py"
        with open(plugin_path, "w", encoding="utf-8") as f:
            f.write(function_code)

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "function_name": function_name,
            "plugin_id": plugin_id,
            "plugin_path": str(plugin_path),
            "summary": description,
        }
        with open(STREAMED_LOG, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(log_entry) + "\n")

        try:
            load_plugin(str(plugin_path))
        except Exception as e:
            print(f"Failed to load plugin: {e}")

        self.librarian.add_document(
            Document(
                id=hash(plugin_id),
                text=f"{function_name}: {description}",
                tags=["streamed", "function", function_name],
            )
        )

        log_usage("JSONStreamedLogic", 1, cpu=0.01, memory=0.01)

        return plugin_id


if __name__ == "__main__":
    jsonbot = JSONBot(strict=False)
    librarian = LibrarianBot()
    ingestor = JSONStreamedLogicIngestor(jsonbot, librarian)

    sample_input = {
        "function_name": "add_numbers",
        "description": "Add two numbers and return the result.",
        "parameters": ["a", "b"],
        "code_body": "return a + b",
    }

    plugin_id = ingestor.ingest_json(sample_input)
    if plugin_id:
        print(f"Plugin {plugin_id} created and loaded successfully.")
