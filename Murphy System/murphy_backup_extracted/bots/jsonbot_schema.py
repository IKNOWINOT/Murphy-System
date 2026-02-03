"""JSON schema validator for task dispatch."""

from __future__ import annotations

from typing import Any, Tuple
import json
import hashlib
from .cache_manager import get_cache, set_cache

import jsonschema

TASK_SCHEMA = {
    "type": "object",
    "required": ["task_id", "task_type", "parameters", "assigned_to"],
    "properties": {
        "task_id": {"type": "string"},
        "task_type": {"type": "string"},
        "assigned_to": {"type": "string"},
        "parameters": {"type": "object"},
        "priority": {"type": "integer"},
    },
}


def validate_json(data: Any, schema_id: str = "task") -> Tuple[bool, str | None]:
    key_source = json.dumps(data, sort_keys=True).encode()
    key = f"validate_{schema_id}_" + hashlib.sha1(key_source).hexdigest()
    cached = get_cache(key)
    if cached:
        return True, None if cached.get("error") is None else (False, cached["error"])  # type: ignore
    try:
        jsonschema.validate(instance=data, schema=TASK_SCHEMA)
        set_cache(key, {"error": None})
        return True, None
    except jsonschema.exceptions.ValidationError as exc:
        set_cache(key, {"error": str(exc)})
        return False, str(exc)
